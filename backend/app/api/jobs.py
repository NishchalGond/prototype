"""Upload + job lifecycle endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, status,
)
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..core.security import get_current_user, require_role
from ..core.dedup_index import DedupIndex
from ..database.maintenance import refresh_dashboard_caches
from .leads import relink_leads
from ..database.session import WRITE_LOCK, SessionLocal, get_db
from ..models.models import (
    JobSignal, JobStatus, ProcessingError, ProcessingJob, Record, SourceFile,
    User, UserRole,
)
from ..schemas.schemas import (
    JobDetail, JobOut, Page, ProcessingErrorOut, SheetInfoOut, UploadResponse,
)

log = logging.getLogger("api.jobs")
router = APIRouter()

_ALLOWED_SUFFIX = {".xlsx", ".xlsm", ".xls", ".csv"}

# Ingestion is a write path: uploading, starting, pausing and cancelling all
# change stored data, so viewers get read access only.
_OPERATOR = require_role([UserRole.ADMIN, UserRole.DATA_PROCESSOR])


def _job_out(job: ProcessingJob) -> JobOut:
    data = JobOut.model_validate(job)
    data.filename = job.source_file.filename if job.source_file else None
    return data


# --------------------------------------------------------------------------
@router.post("/upload/inspect")
async def inspect_file_endpoint(
    file: UploadFile = File(...),
    _user: User = Depends(_OPERATOR),
):
    """Inspect file column headers without registering a job."""
    from engine.inspection import inspect_source
    from engine.mapping import build_plan
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

        # Build per-column raw_header → mapped_target pairs by running
        # build_plan on each non-reference sheet (same logic the processor uses)
        preview_cols = []
        for sheet in info.sheets:
            if sheet.is_reference:
                continue
            n_cols = sheet.n_cols
            # Use the header list we already have; samples not needed here
            samples = {i: [] for i in range(n_cols)}
            plan = build_plan(sheet.header, sheet.headerless, n_cols, samples)
            for idx, raw_header in enumerate(sheet.header):
                mapped = plan.index_to_target.get(idx, "")
                preview_cols.append({
                    "raw_header": raw_header,
                    "mapped_target": mapped,
                })
            # Each sheet is usually one file; break after first content sheet
            break

        return {
            "filename": file.filename,
            "detected_format": info.detected_format,
            "total_rows_estimate": info.total_rows,
            "header_count": len(preview_cols),
            "mapped_count": len([c for c in preview_cols if c.get("mapped_target")]),
            "mapped_columns_preview": preview_cols,
            "sheets": [
                {
                    "name": s.name,
                    "total_rows": s.total_rows,
                    "n_cols": s.n_cols,
                    "is_reference": s.is_reference,
                    "mapped_targets": s.mapped_targets,
                    "header": s.header,
                }
                for s in info.sheets
            ],
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
    _user: User = Depends(_OPERATOR),
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
    _user: User = Depends(_OPERATOR),
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
    job.control_signal = None
    job.message = None
    job.valid_rows = job.invalid_rows = job.duplicate_rows = 0
    job.skipped_rows = job.processed_rows = job.error_count = 0
    job.progress_percent = 0.0
    db.commit()
    background.add_task(run_job, job_id)
    db.refresh(job)
    return _job_out(job)


@router.post("/jobs/{job_id}/mapping-overrides")
def set_mapping_overrides(
    job_id: int,
    payload: dict,
    _user: User = Depends(_OPERATOR),
    db: Session = Depends(get_db),
):
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
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(ProcessingJob)
    if status_filter:
        stmt = stmt.where(ProcessingJob.status == status_filter.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # _job_out touches job.source_file; without selectinload a 50-row page
    # costs 51 queries.
    rows = db.scalars(
        stmt.options(selectinload(ProcessingJob.source_file))
        .order_by(ProcessingJob.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    pages = (total + page_size - 1) // page_size
    return Page[JobOut](
        items=[_job_out(j) for j in rows], total=total, page=page, page_size=page_size,
        total_pages=pages, has_next=page < pages, has_prev=page > 1,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(
    job_id: int,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.get(ProcessingJob, job_id,
                 options=[selectinload(ProcessingJob.source_file)])
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
    _user: User = Depends(get_current_user),
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


@router.get("/jobs/{job_id}/errors/aggregate")
def get_job_errors_aggregate(
    job_id: int,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate error code and sheet breakdowns to diagnose systematic mapping issues."""
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found.")

    # Breakdown by error code
    by_code = dict(
        db.execute(
            select(ProcessingError.code, func.count(ProcessingError.id))
            .where(ProcessingError.job_id == job_id)
            .group_by(ProcessingError.code)
            .order_by(func.count(ProcessingError.id).desc())
        ).all()
    )

    # Breakdown by sheet
    by_sheet = dict(
        db.execute(
            select(func.coalesce(ProcessingError.sheet_name, "File Level"), func.count(ProcessingError.id))
            .where(ProcessingError.job_id == job_id)
            .group_by(ProcessingError.sheet_name)
            .order_by(func.count(ProcessingError.id).desc())
        ).all()
    )

    # Breakdown by severity
    by_severity = dict(
        db.execute(
            select(ProcessingError.severity, func.count(ProcessingError.id))
            .where(ProcessingError.job_id == job_id)
            .group_by(ProcessingError.severity)
        ).all()
    )

    total = db.scalar(select(func.count(ProcessingError.id)).where(ProcessingError.job_id == job_id)) or 0

    return {
        "job_id": job_id,
        "total_errors": total,
        "by_code": by_code,
        "by_sheet": by_sheet,
        "by_severity": by_severity,
    }


@router.get("/errors/summary")
def get_global_errors_summary(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Global error summary across all ingested datasets to identify common column mismatches."""
    by_code = dict(
        db.execute(
            select(ProcessingError.code, func.count(ProcessingError.id))
            .group_by(ProcessingError.code)
            .order_by(func.count(ProcessingError.id).desc())
            .limit(20)
        ).all()
    )
    total = db.scalar(select(func.count(ProcessingError.id))) or 0
    return {"total_logged_errors": total, "top_error_codes": by_code}



# --------------------------------------------------------------------------
# Job control
#
# Signals live on the job row, not in process memory. A dict only reaches the
# worker when the control request happens to be served by the same process that
# is running the job -- with more than one uvicorn worker that is a coin flip,
# and it is always lost on restart.
# --------------------------------------------------------------------------
def _signal(job_id: int, signal: str, new_status: str, db: Session) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found.")
    if job.status in JobStatus.TERMINAL:
        raise HTTPException(
            409, f"Job {job_id} is already {job.status} and cannot be {signal.lower()}d.")
    job.control_signal = signal
    job.status = new_status
    if signal == JobSignal.CANCEL:
        job.message = "Job cancelled by user."
        job.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/pause", response_model=JobOut)
def pause_job(
    job_id: int,
    _user: User = Depends(_OPERATOR),
    db: Session = Depends(get_db),
):
    """Pause an actively running processing job."""
    return _job_out(_signal(job_id, JobSignal.PAUSE, JobStatus.PAUSED, db))


@router.post("/jobs/{job_id}/resume", response_model=JobOut)
def resume_job(
    job_id: int,
    _user: User = Depends(_OPERATOR),
    db: Session = Depends(get_db),
):
    """Resume a paused processing job."""
    return _job_out(_signal(job_id, JobSignal.RESUME, JobStatus.PROCESSING, db))


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: int,
    _user: User = Depends(_OPERATOR),
    db: Session = Depends(get_db),
):
    """Cancel a running or paused processing job."""
    return _job_out(_signal(job_id, JobSignal.CANCEL, JobStatus.CANCELLED, db))


def reap_stale_jobs() -> int:
    """Fail jobs whose worker is gone. Called once at startup.

    A redeploy, OOM kill or crash leaves rows in an ACTIVE status with nothing
    left to advance them; the dashboard then polls a job that will never move
    again. Anything whose heartbeat predates the cutoff is closed out as FAILED
    so the state is at least truthful.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.JOB_STALE_MINUTES)
    db = SessionLocal()
    try:
        stale = db.scalars(
            select(ProcessingJob).where(
                ProcessingJob.status.in_(JobStatus.ACTIVE),
                or_(ProcessingJob.heartbeat_at.is_(None),
                    ProcessingJob.heartbeat_at < cutoff),
            )
        ).all()
        for job in stale:
            job.status = JobStatus.FAILED
            job.control_signal = None
            job.finished_at = datetime.now(timezone.utc)
            job.message = (
                "Processing stopped unexpectedly (the worker did not report in "
                f"for over {settings.JOB_STALE_MINUTES} minutes, usually a restart "
                "or a crash). Start the job again to reprocess it."
            )
            job.error_count = (job.error_count or 0) + 1
            db.add(ProcessingError(job_id=job.id, severity="ERROR",
                                   code="WORKER_LOST",
                                   message="Job abandoned by a stopped worker."))
        if stale:
            db.commit()
            log.warning("reaped %d stale job(s): %s",
                        len(stale), [j.id for j in stale])
        return len(stale)
    finally:
        db.close()


# --------------------------------------------------------------------------
# background worker
# --------------------------------------------------------------------------
def run_job(job_id: int) -> None:
    """Process one job. Runs in a FastAPI background task with its own session."""
    import time
    from engine.detection import UnreadableFile
    from engine.processor import Processor

    db = SessionLocal()
    try:
        # Claim the job before touching it. A compare-and-set on the status
        # is what makes it safe for the API's background task and any number of
        # worker processes to call this for the same id: exactly one UPDATE
        # matches a row still sitting in UPLOADED, and everyone else returns.
        # Cheaper than a lock, and it needs no coordination between processes.
        claimed = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id,
                   ProcessingJob.status == JobStatus.UPLOADED)
            .values(status=JobStatus.READING)
        ).rowcount
        db.commit()
        if not claimed:
            return

        job = db.get(ProcessingJob, job_id)
        if job is None:
            return
        src = db.get(SourceFile, job.source_file_id)
        job.started_at = datetime.now(timezone.utc)
        job.heartbeat_at = datetime.now(timezone.utc)
        job.control_signal = None
        job.progress_percent = 0.0
        db.commit()

        def read_signal() -> str | None:
            """Current control request, read fresh from the row.

            Deliberately a narrow SELECT rather than db.refresh(job): the job
            object is mid-transaction with counters the worker owns, and
            refreshing it would clobber them with stale values.
            """
            return db.scalar(select(ProcessingJob.control_signal)
                             .where(ProcessingJob.id == job_id))

        def clear_signal() -> None:
            db.query(ProcessingJob).filter(ProcessingJob.id == job_id).update(
                {ProcessingJob.control_signal: None})
            db.commit()

        processor = Processor(
            batch_size=job.batch_size or settings.BATCH_SIZE,
            enable_enrichment=settings.ENABLE_ENRICHMENT,
            reference_path=settings.REFERENCE_WORKBOOK,
            record_grain=settings.RECORD_GRAIN,
            property_reference_path=settings.PROPERTY_REFERENCE,
            # Dedup against everything already ingested, not just this file.
            # exclude_job_id stops a re-run of this job from matching the rows
            # its own earlier attempt wrote and calling every one a duplicate.
            dedup_index=(DedupIndex(db, exclude_job_id=job_id)
                         if settings.CROSS_REGISTER_DEDUP else None),
        )

        def on_batch(rows: list[dict]) -> int:
            """One transaction per batch: a failure rolls back only this batch."""
            sig = read_signal()
            if sig == JobSignal.CANCEL:
                raise InterruptedError("Job cancelled by user.")
            while sig == JobSignal.PAUSE:
                time.sleep(0.5)
                # keep reporting in, so a paused job is not mistaken for a dead one
                db.query(ProcessingJob).filter(ProcessingJob.id == job_id).update(
                    {ProcessingJob.heartbeat_at: datetime.now(timezone.utc)})
                db.commit()
                sig = read_signal()
                if sig == JobSignal.CANCEL:
                    raise InterruptedError("Job cancelled by user.")
            if sig == JobSignal.RESUME:
                clear_signal()

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
            sig = read_signal()
            if sig == JobSignal.CANCEL:
                raise InterruptedError("Job cancelled by user.")

            job.heartbeat_at = datetime.now(timezone.utc)
            job.status = JobStatus.PAUSED if sig == JobSignal.PAUSE else JobStatus.PROCESSING
            job.current_sheet = sheet_name
            job.total_rows = res.total_rows
            job.processed_rows = res.processed_rows
            job.valid_rows = res.valid_rows
            job.invalid_rows = res.invalid_rows
            job.duplicate_rows = res.duplicate_rows
            job.skipped_rows = res.skipped_rows

            if res.total_rows and res.total_rows > 0:
                job.progress_percent = min(round(100.0 * res.processed_rows / res.total_rows, 1), 99.0)
            else:
                job.progress_percent = 0.0
            db.commit()

        # No preloaded hash set. It used to be filtered to this filename, which
        # meant duplicates were only ever detected within a single register, and
        # loading every hash for a 20M-row corpus is not something a worker
        # process can hold anyway. DedupIndex probes the database per batch
        # instead, so matches now span every register ingested to date.
        result = processor.process(
            Path(src.stored_path), source_name=src.filename,
            on_batch=on_batch, on_progress=on_progress,
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
        job.control_signal = None
        db.commit()

        # An ingest is the only thing that changes the dashboard's cached
        # aggregates, so it is the only thing that needs to refresh them. Runs
        # after the commit so the rebuild sees this job's rows, and cannot fail
        # the job -- refresh_dashboard_caches swallows its own errors and stale
        # tiles are corrected by the next refresh.
        refresh_dashboard_caches()

        # Reprocessing deleted and rewrote this job's records, detaching any
        # leads that pointed at the old row ids. Reattach them by identity_hash
        # so outreach history follows the data it belongs to.
        try:
            relink_leads(db, job_id)
        except Exception:
            log.exception("lead relink failed for job %s", job_id)

    except InterruptedError as exc:
        db.rollback()
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status = JobStatus.CANCELLED
            job.message = "Job stopped by user."
            job.finished_at = datetime.now(timezone.utc)
            job.control_signal = None
            db.commit()
    except UnreadableFile as exc:
        db.rollback()
        job = db.get(ProcessingJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            job.control_signal = None
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
            job.control_signal = None
            job.error_count = (job.error_count or 0) + 1
            db.add(ProcessingError(job_id=job_id, severity="ERROR",
                                   code="JOB_CRASHED", message=str(exc)[:2000]))
            db.commit()
    finally:
        db.close()