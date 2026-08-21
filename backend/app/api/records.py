"""Record search / filter / detail + dashboard stats + mapping introspection."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database.session import get_db
from ..models.models import (
    ProcessingError, ProcessingJob, Record, RecordStatus, SourceFile,
)
from ..schemas.schemas import (
    AliasRequest, ColumnMappingOut, DashboardStats, FilterOptions, JobOut, Page, RecordOut,
)

router = APIRouter()

SORTABLE = {
    "id": Record.id, "name": Record.name, "community": Record.community,
    "sub_community": Record.sub_community, "building_cluster": Record.building_cluster,
    "unit_number": Record.unit_number, "size": Record.size,
    "bedroom": Record.bedroom, "procedure_value": Record.procedure_value,
    "mobile_1": Record.mobile_1, "status": Record.status,
    "created_at": Record.created_at, "record_date": Record.record_date,
}

SEARCHABLE = (Record.name, Record.community, Record.sub_community,
              Record.building_cluster, Record.unit_number, Record.mobile_1,
              Record.mobile_2, Record.mobile_3, Record.email_address,
              Record.plot_number, Record.pi_number, Record.project,
              Record.developer)


def _build_records_query(
    q: str | None = None,
    community: str | None = None,
    sub_community: str | None = None,
    building_cluster: str | None = None,
    property_type: str | None = None,
    bedroom: str | None = None,
    developer: str | None = None,
    nationality: str | None = None,
    source_file: str | None = None,
    job_id: int | None = None,
    record_status: str | None = None,
    has_mobile: bool | None = None,
    has_email: bool | None = None,
):
    stmt = select(Record)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(*[c.ilike(like) for c in SEARCHABLE]))

    for col, val in (
        (Record.community, community), (Record.sub_community, sub_community),
        (Record.building_cluster, building_cluster),
        (Record.bedroom, bedroom), (Record.developer, developer),
        (Record.nationality, nationality), (Record.source_file, source_file),
    ):
        if val:
            stmt = stmt.where(col == val)

    if record_status:
        st_upper = record_status.upper()
        if st_upper in ("ALL_RECORDS", "ALL_WITH_INCOMPLETE", "SHOW_ALL"):
            pass  # show all records including incomplete
        elif st_upper in ("INCOMPLETE", "MISSING_CONTACT"):
            stmt = stmt.where(Record.status == "INCOMPLETE")
        else:
            stmt = stmt.where(Record.status == st_upper)
    else:
        # Default: show only VALID (outreach-ready with both name and contact info)
        stmt = stmt.where(Record.status == "VALID")

    if property_type:
        stmt = stmt.where(Record.property_type.ilike(property_type))

    if job_id is not None:
        stmt = stmt.where(Record.job_id == job_id)
    if has_mobile is True:
        stmt = stmt.where(Record.mobile_1.is_not(None))
    elif has_mobile is False:
        stmt = stmt.where(Record.mobile_1.is_(None))
    if has_email is True:
        stmt = stmt.where(Record.email_address.is_not(None))
    elif has_email is False:
        stmt = stmt.where(Record.email_address.is_(None))

    return stmt


@router.get("/records", response_model=Page[RecordOut])
def list_records(
    q: str | None = Query(None, description="Free-text search across name, location, contact."),
    community: str | None = None,
    sub_community: str | None = None,
    building_cluster: str | None = None,
    property_type: str | None = None,
    bedroom: str | None = None,
    developer: str | None = None,
    nationality: str | None = None,
    source_file: str | None = None,
    job_id: int | None = None,
    record_status: str | None = Query(None, alias="status"),
    has_mobile: bool | None = None,
    has_email: bool | None = None,
    sort_by: str = Query("id"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    if sort_by not in SORTABLE:
        raise HTTPException(400, f"sort_by must be one of {sorted(SORTABLE)}")

    stmt = _build_records_query(
        q=q, community=community, sub_community=sub_community,
        building_cluster=building_cluster, property_type=property_type,
        bedroom=bedroom, developer=developer, nationality=nationality,
        source_file=source_file, job_id=job_id, record_status=record_status,
        has_mobile=has_mobile, has_email=has_email,
    )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTABLE[sort_by]
    order_clause = col.desc().nullslast() if sort_dir == "desc" else col.asc().nullslast()
    stmt = stmt.order_by(order_clause, Record.id.desc())
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    pages = (total + page_size - 1) // page_size
    return Page[RecordOut](
        items=[RecordOut.model_validate(r) for r in rows], total=total, page=page,
        page_size=page_size, total_pages=pages, has_next=page < pages, has_prev=page > 1,
    )


@router.get("/records/export")
def export_records(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    q: str | None = None,
    community: str | None = None,
    sub_community: str | None = None,
    building_cluster: str | None = None,
    property_type: str | None = None,
    bedroom: str | None = None,
    developer: str | None = None,
    nationality: str | None = None,
    source_file: str | None = None,
    job_id: int | None = None,
    record_status: str | None = Query(None, alias="status"),
    has_mobile: bool | None = None,
    has_email: bool | None = None,
    sort_by: str = Query("id"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50000, ge=1, le=100000),
    db: Session = Depends(get_db),
):
    """Export filtered dataset to CSV or Excel (.xlsx). Exactly respects active search and filters."""
    import csv
    import io
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse

    if sort_by not in SORTABLE:
        sort_by = "id"

    stmt = _build_records_query(
        q=q, community=community, sub_community=sub_community,
        building_cluster=building_cluster, property_type=property_type,
        bedroom=bedroom, developer=developer, nationality=nationality,
        source_file=source_file, job_id=job_id, record_status=record_status,
        has_mobile=has_mobile, has_email=has_email,
    )

    col = SORTABLE[sort_by]
    order_clause = col.desc().nullslast() if sort_dir == "desc" else col.asc().nullslast()
    stmt = stmt.order_by(order_clause, Record.id.desc()).limit(limit)
    rows = db.scalars(stmt).all()

    headers = [
        "Record ID", "Name", "Community", "Sub-Community", "Building / Cluster",
        "Unit Number", "Plot Number", "Plot Reg. No", "DMNO", "DMsubno",
        "Bedroom", "Property Type", "Developer", "Project", "Party Type (Buyer/Seller)",
        "Size (Sq.Ft)", "Procedure Value (AED)",
        "Mobile 1 (Primary)", "Mobile 2", "Mobile 3", "Email Address",
        "Nationality", "PI Number", "Status", "Source File", "Record Date",
    ]

    def extract_row_values(r: Record) -> list:
        return [
            r.id,
            r.name or "",
            r.community or "",
            r.sub_community or "",
            r.building_cluster or "",
            r.unit_number or "",
            r.plot_number or "",
            r.plot_reg_no or "",
            r.dmno or "",
            r.dmsubno or "",
            r.bedroom or "",
            r.property_type or "",
            r.developer or "",
            r.project or "",
            r.party_type or "",
            r.size if r.size is not None else "",
            r.procedure_value if r.procedure_value is not None else "",
            r.mobile_1 or "",
            r.mobile_2 or "",
            r.mobile_3 or "",
            r.email_address or "",
            r.nationality or "",
            r.pi_number or "",
            r.status or "",
            r.source_file or "",
            r.record_date.strftime("%Y-%m-%d") if r.record_date else "",
        ]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if format == "xlsx":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Datalink Export"

        # Header styling
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center")

        ws.append(headers)
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align

        # Append data rows
        for r in rows:
            ws.append(extract_row_values(r))

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 45)

        ws.freeze_panes = "A2"

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"datalink_records_{stamp}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    else:
        # CSV Export with UTF-8 BOM for Excel compatibility
        output = io.StringIO()
        output.write("\ufeff")  # UTF-8 BOM
        writer = csv.writer(output)
        writer.writerow(headers)

        for r in rows:
            writer.writerow(extract_row_values(r))

        output.seek(0)
        filename = f"datalink_records_{stamp}.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.get("/records/filters", response_model=FilterOptions)
def filter_options(db: Session = Depends(get_db)):
    """Distinct values for the dashboard filter dropdowns."""
    def distinct(col, limit=500):
        return [v for (v,) in db.execute(
            select(col).where(col.is_not(None)).distinct().order_by(col).limit(limit)
        ).all() if v]

    return FilterOptions(
        communities=distinct(Record.community),
        sub_communities=distinct(Record.sub_community),
        property_types=distinct(Record.property_type),
        bedrooms=distinct(Record.bedroom),
        developers=distinct(Record.developer),
        source_files=distinct(Record.source_file),
        statuses=distinct(Record.status),
    )


from ..schemas.schemas import (
    ColumnMappingOut, DashboardStats, FilterOptions, JobOut, Page, RecordOut, RecordUpdate,
)

@router.get("/records/{record_id}", response_model=RecordOut)
def get_record(record_id: int, db: Session = Depends(get_db)):
    rec = db.get(Record, record_id)
    if not rec:
        raise HTTPException(404, f"Record {record_id} not found.")
    return RecordOut.model_validate(rec)


@router.put("/records/{record_id}", response_model=RecordOut)
def update_record(record_id: int, body: RecordUpdate, db: Session = Depends(get_db)):
    rec = db.get(Record, record_id)
    if not rec:
        raise HTTPException(404, f"Record {record_id} not found.")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(rec, field):
            setattr(rec, field, value)

    db.commit()
    db.refresh(rec)
    return RecordOut.model_validate(rec)


# --------------------------------------------------------------------------
@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    total_records = db.scalar(select(func.count(Record.id))) or 0

    by_status = dict(db.execute(
        select(Record.status, func.count(Record.id)).group_by(Record.status)).all())
    jobs_by_status = dict(db.execute(
        select(ProcessingJob.status, func.count(ProcessingJob.id))
        .group_by(ProcessingJob.status)).all())

    top = [{"community": c, "count": n} for c, n in db.execute(
        select(Record.community, func.count(Record.id))
        .where(Record.community.is_not(None))
        .group_by(Record.community).order_by(func.count(Record.id).desc()).limit(10)
    ).all()]

    completeness: dict[str, float] = {}
    if total_records:
        for label, col in (
            ("name", Record.name), ("community", Record.community),
            ("sub_community", Record.sub_community),
            ("building_cluster", Record.building_cluster),
            ("unit_number", Record.unit_number), ("size", Record.size),
            ("bedroom", Record.bedroom), ("mobile_1", Record.mobile_1),
            ("email_address", Record.email_address), ("developer", Record.developer),
            ("project", Record.project), ("nationality", Record.nationality),
            ("property_type", Record.property_type), ("record_date", Record.record_date),
            ("procedure_value", Record.procedure_value),
            ("party_type", Record.party_type), ("pi_number", Record.pi_number),
        ):
            n = db.scalar(select(func.count()).select_from(Record)
                          .where(col.is_not(None))) or 0
            completeness[label] = round(100.0 * n / total_records, 1)

    recent = db.scalars(
        select(ProcessingJob).order_by(ProcessingJob.id.desc()).limit(10)).all()
    recent_out: list[JobOut] = []
    for j in recent:
        o = JobOut.model_validate(j)
        o.filename = j.source_file.filename if j.source_file else None
        recent_out.append(o)
    last_out = recent_out[0] if recent_out else None

    valid = by_status.get(RecordStatus.VALID, 0)
    success_rate = round(100.0 * valid / total_records, 1) if total_records else 0.0

    return DashboardStats(
        success_rate=success_rate,
        community_distribution=[{"name": c["community"], "count": c["count"]}
                                for c in top],
        recent_jobs=recent_out,
        total_files=db.scalar(select(func.count(SourceFile.id))) or 0,
        total_jobs=db.scalar(select(func.count(ProcessingJob.id))) or 0,
        total_records=total_records,
        valid_records=by_status.get(RecordStatus.VALID, 0),
        invalid_records=by_status.get(RecordStatus.INVALID, 0),
        duplicate_records=db.scalar(
            select(func.coalesce(func.sum(ProcessingJob.duplicate_rows), 0))) or 0,
        total_errors=db.scalar(select(func.count(ProcessingError.id))) or 0,
        jobs_by_status=jobs_by_status,
        records_by_status=by_status,
        top_communities=top,
        field_completeness=completeness,
        last_job=last_out,
    )


@router.get("/column-mappings", response_model=ColumnMappingOut)
def column_mappings():
    """Expose the mapping layer so the dashboard can show why a column landed where."""
    from engine.mapping import FIELD_TO_COLUMN

    path = Path(__file__).resolve().parents[3] / "engine" / "resources" / "column_mapping.json"
    cfg = json.loads(path.read_text(encoding="utf8"))
    return ColumnMappingOut(
        target_fields=cfg["target_fields"],
        field_to_column=FIELD_TO_COLUMN,
        aliases=cfg["aliases"],
        composite_fields=cfg.get("composite_fields", {}),
        exclude_columns=cfg.get("exclude_columns", []),
        do_not_map=cfg.get("do_not_map", {}),
        alias_count=sum(len(v) for v in cfg["aliases"].values()),
    )


def _sync_alias_files(cfg: dict) -> None:
    """Save updated mapping config to disk and reload in-memory engine structures."""
    root_path = Path(__file__).resolve().parents[3] / "column_mapping.json"
    engine_path = Path(__file__).resolve().parents[3] / "engine" / "resources" / "column_mapping.json"

    formatted = json.dumps(cfg, indent=2, ensure_ascii=False)
    root_path.write_text(formatted, encoding="utf8")
    engine_path.write_text(formatted, encoding="utf8")

    # Reload engine.mapping in memory dynamically
    import engine.mapping
    engine.mapping._CFG = cfg
    engine.mapping.ALIAS = {}
    for _t, _srcs in cfg["aliases"].items():
        for _src in _srcs:
            _k = engine.mapping.norm_header(_src)
            engine.mapping.ALIAS.setdefault(_k, []).append(_t)


@router.post("/column-mappings/alias", response_model=ColumnMappingOut)
def add_alias(body: AliasRequest):
    """Add a new custom header alias for a target field and persist permanently."""
    path = Path(__file__).resolve().parents[3] / "engine" / "resources" / "column_mapping.json"
    cfg = json.loads(path.read_text(encoding="utf8"))

    target = body.target_field.strip()
    alias_str = body.alias.strip()
    if not target or not alias_str:
        raise HTTPException(400, "Both target_field and alias must be non-empty strings.")

    if target not in cfg["target_fields"] and target not in cfg["aliases"]:
        raise HTTPException(404, f"Target field '{target}' not found in canonical target list.")

    aliases_list = cfg["aliases"].setdefault(target, [])
    # Case-insensitive duplicate check
    if not any(a.lower() == alias_str.lower() for a in aliases_list):
        aliases_list.append(alias_str)

    _sync_alias_files(cfg)
    return column_mappings()


@router.delete("/column-mappings/alias", response_model=ColumnMappingOut)
def remove_alias(body: AliasRequest):
    """Remove a custom header alias permanently."""
    path = Path(__file__).resolve().parents[3] / "engine" / "resources" / "column_mapping.json"
    cfg = json.loads(path.read_text(encoding="utf8"))

    target = body.target_field.strip()
    alias_str = body.alias.strip()

    if target in cfg["aliases"]:
        cfg["aliases"][target] = [a for a in cfg["aliases"][target] if a.lower() != alias_str.lower()]

    _sync_alias_files(cfg)
    return column_mappings()

