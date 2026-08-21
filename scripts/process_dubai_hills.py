"""Batch-process all Dubai Hills XLSX files directly into Supabase.

Steps:
1. Truncate all existing data (clean state)
2. Walk every .xlsx in Dubai Hills folder
3. Process each through the engine (map -> clean -> validate -> enrich -> dedupe)
4. Insert batches directly into Supabase via psycopg2
5. Report summary of processed / valid / incomplete / duplicate / error / skipped
"""
from __future__ import annotations

import json, os, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg2
from psycopg2.extras import Json, execute_values

from engine.processor import Processor, ProcessResult

# ── config ──────────────────────────────────────────────────────────────
DATA_DIR      = ROOT / "Dubai Hills"
REF_PATH      = ROOT / "Builders data" / "UAE_Development_Builders.xlsx"
BATCH_SIZE    = 1000
DB_URL        = os.getenv("DATABASE_URL", "")

if not DB_URL:
    print("ERROR: DATABASE_URL not set in .env"); sys.exit(1)

# ── helpers ─────────────────────────────────────────────────────────────
def pg_connect():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    return conn

def truncate_all(conn):
    """Wipe all data tables for a clean start."""
    cur = conn.cursor()
    cur.execute("TRUNCATE records, processing_errors, processing_jobs, source_files RESTART IDENTITY CASCADE")
    conn.commit()
    cur.close()
    print("  ✓ All tables truncated")

# Columns in the records table (must match the model)
RECORD_COLS = [
    "name", "community", "sub_community", "building_cluster", "unit_number",
    "size", "plot_reg_no", "plot_number", "dmno", "dmsubno", "bedroom",
    "party_type", "mobile_1", "mobile_2", "mobile_3", "email_address",
    "pi_number", "nationality", "property_type", "record_date", "procedure_value",
    "developer", "project",
    "job_id", "source_file", "source_sheet", "source_row",
    "status", "identity_hash", "validation_flags", "enriched_fields",
    "owner_count", "extras", "created_at",
]

def insert_source_file(conn, filepath: Path) -> int:
    import hashlib
    sha = hashlib.sha256(filepath.read_bytes()).hexdigest()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO source_files
               (filename, stored_path, size_bytes, content_sha256, is_encrypted, uploaded_at)
           VALUES (%s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (filepath.name, str(filepath), filepath.stat().st_size, sha, False,
         datetime.now(timezone.utc))
    )
    fid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return fid

def insert_job(conn, source_file_id: int) -> int:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO processing_jobs
               (source_file_id, status, batch_size,
                total_rows, processed_rows, valid_rows, invalid_rows,
                duplicate_rows, skipped_rows, error_count, progress_percent,
                created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (source_file_id, 'PROCESSING', BATCH_SIZE,
         0, 0, 0, 0, 0, 0, 0, 0.0,
         datetime.now(timezone.utc))
    )
    jid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return jid

def update_job(conn, job_id: int, result: ProcessResult, status: str, message: str = None):
    cur = conn.cursor()
    cur.execute(
        """UPDATE processing_jobs
           SET status=%s, total_rows=%s, processed_rows=%s,
               valid_rows=%s, invalid_rows=%s, duplicate_rows=%s, skipped_rows=%s,
               error_count=%s, progress_percent=100.0,
               mapping_report=%s, finished_at=%s, message=%s
           WHERE id=%s""",
        (status, result.total_rows, result.processed_rows,
         result.valid_rows, result.invalid_rows, result.duplicate_rows, result.skipped_rows,
         len(result.errors), Json(result.mapping_report) if result.mapping_report else None,
         datetime.now(timezone.utc), message, job_id)
    )
    conn.commit()
    cur.close()

def bulk_insert_records(conn, rows: list[dict], job_id: int) -> int:
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    values = []
    for r in rows:
        r["job_id"] = job_id
        r["created_at"] = now
        # Convert list/dict fields to Json for psycopg2
        for k in ("validation_flags", "enriched_fields", "extras"):
            v = r.get(k)
            if v is not None:
                r[k] = Json(v)
        values.append(tuple(r.get(c) for c in RECORD_COLS))

    cur = conn.cursor()
    cols_str = ", ".join(RECORD_COLS)
    placeholders = ", ".join(["%s"] * len(RECORD_COLS))
    sql = f"INSERT INTO records ({cols_str}) VALUES ({placeholders})"
    cur.executemany(sql, values)
    conn.commit()
    cur.close()
    return len(values)

def insert_errors(conn, job_id: int, errors: list[dict]):
    if not errors:
        return
    cur = conn.cursor()
    for e in errors:
        cur.execute(
            """INSERT INTO processing_errors
               (job_id, sheet_name, batch_number, source_row, severity, code, message, payload, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (job_id, e.get("sheet_name"), e.get("batch_number"), e.get("source_row"),
             e.get("severity", "ERROR"), e.get("code", "UNKNOWN"), e.get("message", ""),
             Json(e.get("payload")) if e.get("payload") else None,
             datetime.now(timezone.utc))
        )
    conn.commit()
    cur.close()


# ── main ────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    conn = pg_connect()

    # Step 1: Clean slate
    print("\n═══ STEP 1: Clean database ═══")
    truncate_all(conn)

    # Step 2: Collect all xlsx files
    xlsx_files = sorted(DATA_DIR.rglob("*.xlsx"))
    # Skip temp files (ones starting with ~$)
    xlsx_files = [f for f in xlsx_files if not f.name.startswith("~$") and not f.name.startswith("._")]
    print(f"\n═══ STEP 2: Found {len(xlsx_files)} Excel files ═══")

    # Step 3: Initialize processor with enrichment
    processor = Processor(
        batch_size=BATCH_SIZE,
        enable_enrichment=True,
        reference_path=REF_PATH,
        record_grain="owner",
    )
    print(f"  Reference data loaded: {len(processor.ref)} developments")

    # Step 4: Process each file
    grand = {
        "files_ok": 0, "files_error": 0,
        "total_rows": 0, "valid": 0, "incomplete": 0,
        "invalid": 0, "duplicate": 0, "skipped": 0, "errors": 0,
    }
    global_seen: set[str] = set()   # cross-file dedup
    failed_files: list[str] = []

    print(f"\n═══ STEP 3: Processing {len(xlsx_files)} files ═══\n")
    for idx, fpath in enumerate(xlsx_files, 1):
        rel = fpath.relative_to(DATA_DIR)
        print(f"[{idx:2d}/{len(xlsx_files)}] {rel} ", end="", flush=True)

        try:
            sf_id = insert_source_file(conn, fpath)
            job_id = insert_job(conn, sf_id)

            all_rows: list[dict] = []

            def on_batch(rows):
                all_rows.extend(rows)
                return len(rows)

            result = processor.process(
                fpath,
                source_name=fpath.name,
                on_batch=on_batch,
                seen_hashes=global_seen,
            )

            # Insert all records
            inserted = bulk_insert_records(conn, all_rows, job_id)

            # Count statuses
            n_valid = sum(1 for r in all_rows if r.get("status") == "VALID")
            n_incomplete = sum(1 for r in all_rows if r.get("status") == "INCOMPLETE")
            n_invalid = sum(1 for r in all_rows if r.get("status") == "INVALID")
            n_dup = sum(1 for r in all_rows if r.get("status") == "DUPLICATE")

            # Insert errors
            insert_errors(conn, job_id, result.errors)

            status = "COMPLETED" if not result.errors else "COMPLETED_WITH_ERRORS"
            update_job(conn, job_id, result, status)

            grand["files_ok"] += 1
            grand["total_rows"] += result.total_rows
            grand["valid"] += n_valid
            grand["incomplete"] += n_incomplete
            grand["invalid"] += n_invalid
            grand["duplicate"] += n_dup
            grand["skipped"] += result.skipped_rows
            grand["errors"] += len(result.errors)

            err_tag = f" [{len(result.errors)} warnings]" if result.errors else ""
            print(f"→ {inserted} rows (V:{n_valid} I:{n_incomplete} D:{n_dup} X:{n_invalid}){err_tag}")

        except Exception as exc:
            grand["files_error"] += 1
            failed_files.append(f"{rel}: {type(exc).__name__}: {exc}")
            print(f"✗ FAILED: {exc}")
            traceback.print_exc()
            try:
                conn.rollback()
            except Exception:
                conn = pg_connect()

    elapsed = time.time() - t0

    # ── Final Report ────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("               PROCESSING COMPLETE")
    print("═" * 60)
    print(f"  Time elapsed:      {elapsed:.1f}s")
    print(f"  Files processed:   {grand['files_ok']} OK / {grand['files_error']} FAILED")
    print(f"  Total rows:        {grand['total_rows']}")
    print(f"  ─────────────────────────────")
    print(f"  VALID (outreach):  {grand['valid']}")
    print(f"  INCOMPLETE:        {grand['incomplete']}")
    print(f"  DUPLICATE:         {grand['duplicate']}")
    print(f"  INVALID:           {grand['invalid']}")
    print(f"  Skipped:           {grand['skipped']}")
    print(f"  Errors/Warnings:   {grand['errors']}")
    print(f"  Global unique IDs: {len(global_seen)}")

    if failed_files:
        print(f"\n  ✗ Failed files:")
        for f in failed_files:
            print(f"    - {f}")

    # ── Verify counts match DB ──────────────────────────────────────────
    print("\n═══ STEP 4: Verifying database ═══")
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM records GROUP BY status ORDER BY status")
    db_counts = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM records")
    total_db = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM source_files")
    total_sf = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM processing_jobs")
    total_jobs = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"  Source files in DB:  {total_sf}")
    print(f"  Processing jobs:    {total_jobs}")
    print(f"  Total records:      {total_db}")
    for status, count in db_counts:
        print(f"    {status:20s} {count:,}")

    print("\n✓ Done!")

if __name__ == "__main__":
    main()
