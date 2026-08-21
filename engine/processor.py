"""Batch processing orchestrator.

Flow per the prototype spec:
    read -> map -> clean -> validate -> deduplicate -> transform -> save
Batching is done directly in Python (no Redis/Celery), with a DB transaction
per batch so a failed insert cannot leave a partially written batch.
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import validation as V
from .detection import UnreadableFile, open_source
from .mapping import (apply_plan, build_plan, is_reference_sheet,
                      is_repeated_header, sheet_role)
from .reference import enrich, load_reference

log = logging.getLogger("engine.processor")

PROGRESS_SHEET_WEIGHT = 0.98


@dataclass
class BatchOutcome:
    rows: list[dict] = field(default_factory=list)
    valid: int = 0
    invalid: int = 0
    duplicate: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class ProcessResult:
    total_rows: int = 0
    processed_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    skipped_rows: int = 0
    errors: list[dict] = field(default_factory=list)
    mapping_report: dict = field(default_factory=dict)
    detected_format: str | None = None
    sheet_count: int = 0


class Processor:
    """Stateless engine. The caller supplies persistence + progress callbacks."""

    def __init__(self, *, batch_size: int = 1000, enable_enrichment: bool = True,
                 reference_path: Path | None = None, record_grain: str = "owner"):
        self.batch_size = max(1, batch_size)
        self.record_grain = record_grain
        self.ref = (load_reference(str(reference_path))
                    if enable_enrichment and reference_path else None)

    # ------------------------------------------------------------------
    def process(
        self,
        path: Path,
        *,
        source_name: str,
        on_batch: Callable[[list[dict]], int],
        on_progress: Callable[[ProcessResult, str], None] | None = None,
        seen_hashes: set[str] | None = None,
    ) -> ProcessResult:
        result = ProcessResult()
        seen: set[str] = seen_hashes if seen_hashes is not None else set()

        fmt, sheets = open_source(path)          # raises UnreadableFile
        result.detected_format = fmt

        # DLD-style workbooks split one record across a property sheet and an
        # owner sheet keyed on P-NUMBER. Index the property side first so owner
        # rows can be completed with their location instead of being stored
        # half-empty.
        self._property_index = self._build_property_index(path, result)

        for sheet in sheets:
            result.sheet_count += 1
            try:
                self._process_sheet(sheet, source_name, result, seen, on_batch, on_progress)
            except Exception as exc:                     # one bad sheet must not kill the job
                log.exception("sheet failed: %s", sheet.name)
                result.errors.append({
                    "sheet_name": sheet.name, "batch_number": None, "source_row": None,
                    "severity": "ERROR", "code": "SHEET_FAILED",
                    "message": f"{type(exc).__name__}: {exc}",
                    "payload": {"traceback": traceback.format_exc()[-2000:]},
                })
        return result

    # ------------------------------------------------------------------
    def _build_property_index(self, path: Path, result: ProcessResult) -> dict:
        """pi_number -> location fields, when the file has a property/owner split."""
        try:
            from .inspection import inspect_source
            info = inspect_source(path)
        except Exception:
            return {}

        roles = {}
        for sh in info.sheets:
            if sh.is_reference:
                continue
            roles[sh.name] = sheet_role(set(sh.mapped_targets))
        if "property" not in roles.values() or "owner" not in roles.values():
            return {}

        index: dict[str, dict] = {}
        try:
            _fmt, sheets = open_source(path)
            for sheet in sheets:
                if roles.get(sheet.name) != "property":
                    # still need to drain the generator to advance the reader
                    for _ in sheet.rows:
                        pass
                    continue
                buffered = []
                it = sheet.rows
                for _ in range(50):
                    try:
                        buffered.append(next(it))
                    except StopIteration:
                        break
                n_cols = max([sheet.n_cols] + [len(r) for r in buffered] or [0])
                samples = {i: [r[i] for r in buffered if i < len(r)]
                           for i in range(n_cols)}
                plan = build_plan(sheet.header, sheet.headerless, n_cols, samples)
                for raw in list(buffered) + list(it):
                    if not any(c not in (None, "") for c in raw):
                        continue
                    fields, _extras = apply_plan(plan, raw)
                    key = fields.get("PI number")
                    if key in (None, ""):
                        continue
                    index.setdefault(str(key).strip(), fields)
        except Exception as exc:
            log.warning("property index failed: %s", exc)
            return {}

        if index:
            result.errors.append({
                "sheet_name": None, "batch_number": None, "source_row": None,
                "severity": "WARNING", "code": "PROPERTY_OWNER_JOIN",
                "message": (f"Indexed {len(index):,} properties on PI number and "
                            "merged them into owner rows, so each record carries "
                            "both the person and the location."),
                "payload": {"properties": len(index)},
            })
        return index

    # ------------------------------------------------------------------
    def _process_sheet(self, sheet, source_name, result, seen, on_batch, on_progress):
        # sample the first rows so overloaded headers (AREA / TYPE) resolve on values
        sample_rows: list[list] = []
        row_iter = sheet.rows
        buffered: list[list] = []
        for _ in range(50):
            try:
                r = next(row_iter)
            except StopIteration:
                break
            buffered.append(r)
            sample_rows.append(r)

        n_cols = max([sheet.n_cols] + [len(r) for r in sample_rows] or [0])
        samples = {i: [r[i] for r in sample_rows if i < len(r)] for i in range(n_cols)}
        plan = build_plan(sheet.header, sheet.headerless, n_cols, samples)

        result.mapping_report[sheet.name] = plan.report()

        if is_reference_sheet(sheet.header, sheet.name):
            result.errors.append({
                "sheet_name": sheet.name, "batch_number": None, "source_row": None,
                "severity": "WARNING", "code": "REFERENCE_SHEET_SKIPPED",
                "message": ("This sheet is a developer/community lookup, not owner "
                            "records. It is used to enrich Developer/Community on "
                            "real records instead of being stored as records."),
                "payload": {"header": sheet.header[:20]},
            })
            for _ in buffered:
                result.skipped_rows += 1
                result.total_rows += 1
            for _ in row_iter:
                result.skipped_rows += 1
                result.total_rows += 1
            return

        role = sheet_role(set(plan.index_to_target.values()))
        if getattr(self, "_property_index", None) and role == "property":
            result.errors.append({
                "sheet_name": sheet.name, "batch_number": None, "source_row": None,
                "severity": "WARNING", "code": "PROPERTY_SHEET_MERGED",
                "message": ("Property sheet merged into owner records on PI number "
                            "rather than stored as separate location-only rows."),
                "payload": None,
            })
            for _ in buffered:
                result.total_rows += 1
                result.skipped_rows += 1
            for _ in row_iter:
                result.total_rows += 1
                result.skipped_rows += 1
            return

        if not plan.index_to_target and not plan.composite:
            result.errors.append({
                "sheet_name": sheet.name, "batch_number": None, "source_row": None,
                "severity": "WARNING", "code": "NO_MAPPABLE_COLUMNS",
                "message": ("No column on this sheet maps to any of the 23 target "
                            "fields; sheet skipped."),
                "payload": {"header": sheet.header[:40], "headerless": sheet.headerless},
            })
            for _ in buffered:
                result.skipped_rows += 1
            for _ in row_iter:
                result.skipped_rows += 1
            return

        batch: list[dict] = []
        batch_no = 0
        row_no = (sheet.header_row_index + 1) if sheet.header_row_index >= 0 else 0

        def flush():
            nonlocal batch, batch_no
            if not batch:
                return
            batch_no += 1
            try:
                on_batch(batch)
            except Exception as exc:
                log.exception("batch insert failed")
                result.errors.append({
                    "sheet_name": sheet.name, "batch_number": batch_no, "source_row": None,
                    "severity": "ERROR", "code": "BATCH_INSERT_FAILED",
                    "message": f"{type(exc).__name__}: {exc}",
                    "payload": {"batch_size": len(batch)},
                })
                result.valid_rows -= len(batch)
                result.invalid_rows += len(batch)
            batch = []

        consecutive_empty = 0

        def handle(raw_row):
            nonlocal row_no, consecutive_empty
            row_no += 1

            if not any(c not in (None, "") for c in raw_row):
                consecutive_empty += 1
                if consecutive_empty >= 100:
                    return
                result.skipped_rows += 1
                return
            else:
                consecutive_empty = 0

            result.total_rows += 1
            result.processed_rows += 1
            if not sheet.headerless and is_repeated_header(raw_row, plan):
                result.skipped_rows += 1
                return

            try:
                fields, extras = apply_plan(plan, raw_row)
            except Exception as exc:
                result.errors.append({
                    "sheet_name": sheet.name, "batch_number": batch_no + 1,
                    "source_row": row_no, "severity": "ERROR", "code": "MAP_FAILED",
                    "message": f"{type(exc).__name__}: {exc}", "payload": None,
                })
                result.invalid_rows += 1
                return

            if V.looks_like_building_row(extras, fields):
                result.skipped_rows += 1
                return

            # complete the owner row with its property's location
            pidx = getattr(self, "_property_index", None)
            if pidx:
                key = fields.get("PI number")
                if key not in (None, ""):
                    prop = pidx.get(str(key).strip())
                    if prop:
                        for k, v in prop.items():
                            if v not in (None, "") and fields.get(k) in (None, ""):
                                fields[k] = v

            enriched: list[str] = []
            if self.ref is not None:
                try:
                    enriched = enrich(fields, self.ref, source_name=source_name)
                except Exception:
                    enriched = []
            elif source_name and not fields.get("Community"):
                from .reference import clean_filename_community
                inferred = clean_filename_community(source_name)
                if inferred:
                    fields["Community"] = inferred
                    enriched = ["community"]

            row, flags = V.transform(fields, extras)
            ok, vflags = V.validate(row)
            flags.extend(vflags)

            row["source_file"] = source_name
            row["source_sheet"] = sheet.name
            row["source_row"] = row_no
            row["validation_flags"] = flags or None
            row["enriched_fields"] = enriched or None
            row["extras"] = V.json_safe(extras) or None
            row["identity_hash"] = V.identity_hash(row)

            if not ok:
                row["status"] = "INVALID"
                result.invalid_rows += 1
                result.errors.append({
                    "sheet_name": sheet.name, "batch_number": batch_no + 1,
                    "source_row": row_no, "severity": "WARNING", "code": "INVALID_RECORD",
                    "message": "; ".join(flags) or "record failed validation",
                    "payload": None,
                })
                return

            if row["identity_hash"] in seen:
                row["status"] = "DUPLICATE"
                result.duplicate_rows += 1
                return
            seen.add(row["identity_hash"])
            # Check outreach readiness: record must have BOTH name and at least one contact detail (phone or email)
            has_name = bool(row.get("name") and str(row.get("name")).strip())
            has_contact = bool(row.get("mobile_1") or row.get("email_address"))

            if has_name and has_contact:
                row["status"] = "VALID"
                result.valid_rows += 1
            else:
                row["status"] = "INCOMPLETE"
                if not has_name and not has_contact:
                    flags.append("incomplete_missing_name_and_contact")
                elif not has_name:
                    flags.append("incomplete_missing_name")
                elif not has_contact:
                    flags.append("incomplete_missing_contact")
                row["validation_flags"] = flags

            batch.append(row)
            if len(batch) >= self.batch_size:
                flush()
                if on_progress:
                    on_progress(result, sheet.name)

        for r in buffered:
            handle(r)
        for r in row_iter:
            handle(r)
        flush()
        if on_progress:
            on_progress(result, sheet.name)
