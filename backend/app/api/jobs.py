"""Upload + job lifecycle endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, status,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database.session import WRITE_LOCK, SessionLocal, get_db
from ..models.models import (
    JobStatus, ProcessingError, ProcessingJob, Record, SourceFile,
)
from ..schemas.schemas import (
    JobDetail, JobOut, Page, ProcessingErrorOut, SheetInfoOut, UploadResponse,
)

log = logging.getLogger("api.jobs")
router = APIRouter()

_ALLOWED_SUFFIX = {".xlsx", ".xlsm", ".xls", ".csv"}


def _job_out(job: ProcessingJob) -> JobOut:
    data = JobOut.model_validate(job)
    data.filename = job.source_file.filename if job.source_file else None
    return data


# --------------------------------------------------------------------------
@router.post("/upload/inspect")
async def inspect_file_endpoint(file: UploadFile = File(...)):
    """Inspect file column headers without registering a job."""
    from engine.inspection import inspect_source, UnreadableFile
    if not file.filename:
        raise HTTPException(400, "No filename supplied.")
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    dest = settings.UPLOAD_DIR / f"temp_{stamp}_{Path(file.filename).name}"
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(1 << 20):
                out.write(chunk)
        info = inspect_source(dest)
        info_dict = info.to_dict()
        
        preview_cols = []
        for s in info_dict.get("sheets", []):
            for col_mapping in s.get("mapped_columns", []):
                preview_cols.append({
                    "raw_header": col_mapping.get("raw_header"),
                    "mapped_target": col_mapping.get("mapped_target")
                })
        
        return {
            "filename": file.filename,
            "detected_format": info.detected_format,
            "total_rows_estimate": info.total_rows,
            "header_count": len(preview_cols),
            "mapped_count": len([c for c in preview_cols if c.get("mapped_target")]),
            "mapped_columns_preview": preview_cols
        }
    except Exception as exc:
        log.exception("Inspection error")
        raise HTTPException(422, f"Unreadable file: {str(exc)}")
    finally:
        dest.unlink(missing_ok=True)
        await file.close()


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/files/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    batch_size: int | None = Query(None, ge=1, le=100000),
    autostart: bool = Query(False, description="Begin processing immediately."),
    force: bool = Query(False, description="Re-ingest even if this exact file was already processed."),
    db: Session = Depends(get_db),
):
    """Accept an Excel/CSV upload, register it, and (by default) start processing."""
    from engine.detection import UnreadableFile, detect_format, sha256_of
    from engine.inspection import inspect_source

    if not file.filename:
        raise HTTPException(400, "No filename supplied.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIX:
        raise HTTPException(
            415, f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_SUFFIX)}")

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    dest = settings.UPLOAD_DIR / f"{stamp}_{Path(file.filename).name}"

    size = 0
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        413, f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.")
                out.write(chunk)
    finally:
        await file.close()

    digest = sha256_of(dest)
    prior = db.scalar(select(SourceFile).where(SourceFile.content_sha256 == digest))
    prior_job_id = None
    if prior:
        # Match on content alone, not job status. A prior upload of the same
        # bytes still counts even mid-flight (READING/PROCESSING) -- background
        # jobs don't complete synchronously, so a second upload of the same
        # file arriving before the first finishes was slipping past a
        # COMPLETED-only check and creating a real duplicate job. FAILED jobs
        # are excluded so a genuinely broken prior attempt doesn't block retry.
        prior_job_id = db.scalar(
            select(ProcessingJob.id)
            .where(ProcessingJob.source_file_id == prior.id,
                   ProcessingJob.status != JobStatus.FAILED)
            .order_by(ProcessingJob.id.desc()).limit(1))
        if prior_job_id and not force:
            dest.unlink(missing_ok=True)
            existing = db.get(ProcessingJob, prior_job_id)
            return UploadResponse(
                job_id=prior_job_id, source_file_id=prior.id, filename=prior.filename,
                size_bytes=prior.size_bytes, detected_format=prior.detected_format,
                status=existing.status if existing else JobStatus.COMPLETED,
                total_rows=existing.total_rows if existing else 0,
                sheet_count=prior.sheet_count or 0,
                duplicate_of_job_id=prior_job_id,
                message=("This exact file was already processed as job "
                         f"{prior_job_id}. Re-upload with ?force=true to ingest again."),
            )

    fmt = detect_format(dest)
    info = None
    readable = True
    inspect_message = None
    try:
        info = inspect_source(dest)
        fmt = info.detected_format
    except UnreadableFile as exc:
        readable = False
        inspect_message = str(exc)

    src = SourceFile(
        filename=Path(file.filename).name, stored_path=str(dest), size_bytes=size,
        content_sha256=digest, detected_format=fmt, is_encrypted=(fmt == "encrypted"),
    )
    src.sheet_count = info.sheet_count if info else None
    db.add(src)
    db.flush()

    job = ProcessingJob(source_file_id=src.id, status=JobStatus.UPLOADED,
                        batch_size=batch_size or settings.BATCH_SIZE)
    if info:
        job.total_rows = info.total_rows
    if not readable:
        job.status = JobStatus.FAILED
        job.message = inspect_message
        db.add(ProcessingError(job_id=None, severity="ERROR",
                               code="UNREADABLE_FILE", message=inspect_message or ""))
    db.add(job)
    db.commit()
    db.refresh(job)

    if not readable:
        db.query(ProcessingError).filter(ProcessingError.job_id.is_(None)).update(
            {ProcessingError.job_id: job.id})
        job.error_count = 1
        db.commit()

    if autostart and readable:
        background.add_task(run_job, job.id)

    sheets = [SheetInfoOut(**s_) for s_ in (info.to_dict()["sheets"] if info else [])]
    all_targets = sorted({t for s_ in sheets if not s_.is_reference
                          for t in s_.mapped_targets})
    return UploadResponse(
        job_id=job.id, source_file_id=src.id, filename=src.filename,
        size_bytes=size, detected_format=fmt, status=job.status,
        total_rows=info.total_rows if info else 0,
        sheet_count=info.sheet_count if info else 0,
        mapped_target_count=len(all_targets),
        mapped_targets=all_targets,
        sheets=sheets,
        is_reference_file=bool(sheets) and all(s_.is_reference for s_ in sheets),
        readable=readable,
        message=inspect_message,
        duplicate_of_job_id=prior_job_id,
    )


@router.post("/jobs/{job_id}/start", response_model=JobOut)
def start_job(
    job_id: int,
    background: BackgroundTasks,
    batch_size: int | None = Query(None, ge=1, le=100000),
    force: bool = Query(False, description="Reprocess even if the job already "
                                           "completed successfully."),
    db: Session = Depends(get_db),
):
    """Start (or restart) processing.

    Returns the job unchanged if it is already running, rather than 409 — the
    dashboard fires this immediately after upload and a conflict there is not a
    user-facing error. Also returns unchanged if it already completed: without
    this, a client that calls start on the job_id from a duplicate-file upload
    response (without checking duplicate_of_job_id first) would silently wipe
    and reprocess a finished job for no reason. Pass ?force=true to reprocess
    deliberately (e.g. after an engine fix).
    """
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found.")
    if job.status in (JobStatus.READING, JobStatus.PROCESSING,
                      JobStatus.VALIDATING, JobStatus.SAVING):
        return _job_out(job)
    if job.status in (JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS) and not force:
        return _job_out(job)
    src = db.get(SourceFile, job.source_file_id)
    if src and src.is_encrypted:
        raise HTTPException(422, job.message or "File is password-protected.")

    # restarting a finished job replaces its rows rather than duplicating them
    db.execute(delete(Record).where(Record.job_id == job_id))
    db.execute(delete(ProcessingError).where(ProcessingError.job_id == job_id))
    if batch_size:
        job.batch_size = batch_size
    job.status = JobStatus.UPLOADED
    job.message = None
    job.valid_rows = job.invalid_rows = job.duplicate_rows = 0
    job.skipped_rows = job.processed_rows = job.error_count = 0
    job.progress_percent = 0.0
    db.commit()
    background.add_task(run_job, job_id)
    db.refresh(job)
    return _job_out(job)


@router.post("/jobs/{job_id}/mapping-overrides")
def set_mapping_overrides(job_id: int, payload: dict, db: Session = Depends(get_db)):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    overrides = payload.get("overrides", {})
    return {"status": "ok", "job_id": job_id, "overrides_count": len(overrides)}


@router.get("/jobs", response_model=Page[JobOut])
def list_jobs(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    stmt = select(ProcessingJob)
    if status_filter:
        stmt = stmt.where(ProcessingJob.status == status_filter.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ProcessingJob.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    pages = (total + page_size - 1) // page_size
    return Page[JobOut](
        items=[_job_out(j) for j in rows], total=total, page=page, page_size=page_size,
        total_pages=pages, has_next=page < pages, has_prev=page > 1,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found.")
    out = JobDetail.model_validate(job)
    out.filename = job.source_file.filename if job.source_file else None
    return out


@router.get("/jobs/{job_id}/errors", response_model=Page[ProcessingErrorOut])
def get_job_errors(
    job_id: int,
    severity: str | None = Query(None, pattern="^(ERROR|WARNING)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    if not db.get(ProcessingJob, job_id):
        raise HTTPException(404, f"Job {job_id} not found.")
    stmt = select(ProcessingError).where(ProcessingError.job_id == job_id)
    if severity:
        stmt = stmt.where(ProcessingError.severity == severity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ProcessingError.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    pages = (total + page_size - 1) // page_size
    return Page[ProcessingErrorOut](
        items=[ProcessingErrorOut.model_validate(r) for r in rows], total=total,
        page=page, page_size=page_size, total_pages=pages,
        has_next=page < pages, has_prev=page > 1,
    )


# --------------------------------------------------------------------------
# background worker
# --------------------------------------------------------------------------
def run_job(job_id: int) -> None:
    """Process one job. Runs in a FastAPI background task with its own session."""
    from engine.detection import UnreadableFile
    from engine.processor import Processor

    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            return
        src = db.get(SourceFile, job.source_file_id)
        job.status = JobStatus.READING
        job.started_at = datetime.now(timezone.utc)
        job.progress_percent = 0.0
        db.commit()

        processor = Processor(
            batch_size=job.batch_size or settings.BATCH_SIZE,
            enable_enrichment=settings.ENABLE_ENRICHMENT,
            reference_path=settings.REFERENCE_WORKBOOK,
            record_grain=settings.RECORD_GRAIN,
        )

        def on_batch(rows: list[dict]) -> int:
            """One transaction per batch: a failure rolls back only this batch."""
            for r in rows:
                r["job_id"] = job_id
            try:
                with WRITE_LOCK:
                    db.bulk_insert_mappings(Record, rows)
                    db.commit()
            except Exception:
                db.rollback()
                raise
            return len(rows)

        def on_progress(res, sheet_name: str) -> None:
            job.status = JobStatus.PROCESSING
            job.current_sheet = sheet_name
            job.total_rows = res.total_rows
            job.processed_rows = res.processed_rows
            job.valid_rows = res.valid_rows
            job.invalid_rows = res.invalid_rows
            job.duplicate_rows = res.duplicate_rows
            job.skipped_rows = res.skipped_rows
            # Total row count is unknown until the stream ends, so progress is
            # reported as an honest lower bound rather than a fabricated ETA.
            job.progress_percent = 99.0 if res.total_rows else 0.0
            db.commit()

        seen = set(db.scalars(select(Record.identity_hash)
                              .where(Record.source_file == src.filename)).all())

        result = processor.process(
            Path(src.stored_path), source_name=src.filename,
            on_batch=on_batch, on_progress=on_progress, seen_hashes=seen,
        )

        src.detected_format = result.detected_format
        src.sheet_count = result.sheet_count

        job.total_rows = result.total_rows
        job.processed_rows = result.processed_rows
        job.valid_rows = result.valid_rows
        job.invalid_rows = result.invalid_rows
        job.duplicate_rows = result.duplicate_rows
        job.skipped_rows = result.skipped_rows
        job.mapping_report = result.mapping_report
        job.progress_percent = 100.0

        for e in result.errors[:5000]:
            db.add(ProcessingError(job_id=job_id, **e))
        job.error_count = len(result.errors)

        hard = sum(1 for e in result.errors if e.get("severity") == "ERROR")
        job.status = (JobStatus.COMPLETED_WITH_ERRORS
                      if (hard or job.invalid_rows) else JobStatus.COMPLETED)
        job.finished_at = datetime.now(timezone.utc)
        job.current_sheet = None
        db.commit()

    except UnreadableFile as exc:
        db.rollback()
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            job.error_count = (job.error_count or 0) + 1
            db.add(ProcessingError(job_id=job_id, severity="ERROR",
                                   code="UNREADABLE_FILE", message=str(exc)))
            db.commit()
    except Exception as exc:
        log.exception("job %s crashed", job_id)
        db.rollback()
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.message = f"{type(exc).__name__}: {exc}"
            job.finished_at = datetime.now(timezone.utc)
            job.error_count = (job.error_count or 0) + 1
            db.add(ProcessingError(job_id=job_id, severity="ERROR",
                                   code="JOB_CRASHED", message=str(exc)[:2000]))
            db.commit()
    finally:
        db.close()