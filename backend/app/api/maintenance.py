"""Reprocessing: re-deriving stored records with the current engine rules.

A correctness fix in cleaning, enrichment or deduplication changes what the
pipeline WOULD produce, not what it already produced. Without a way to re-derive,
every such fix stranded the rows already in the table and the only remedy was
re-uploading files by hand -- which nobody does across hundreds of registers, so
the database drifts permanently behind the code.

Records carry engine_version (see engine/__init__.py). Bumping it marks
everything below it stale, and these endpoints turn that into an operation:

    GET  /api/maintenance/engine-status   what is stale, and how much
    POST /api/maintenance/reprocess       re-derive it, oldest job first

Reprocessing reuses the existing job restart path, which already deletes a job's
rows before rewriting them, so re-deriving is idempotent rather than additive.
The source files it reads from are the ones stored at upload, so this needs no
input from the user and can be re-run safely at any time.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from engine import ENGINE_VERSION

from ..core.security import require_role
from ..database.session import get_db
from ..models.models import (
    JobStatus, ProcessingError, ProcessingJob, Record, SourceFile, User,
    UserRole,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

# Reprocessing rewrites records in bulk. Operators can upload and run jobs;
# re-deriving the whole corpus is an administrator's decision.
_ADMIN = require_role(list(UserRole.at_least(UserRole.ADMIN)))

# Statuses that mean a job is already occupying a worker. Re-queueing one would
# race its own rows.
_BUSY = (JobStatus.READING, JobStatus.PROCESSING, JobStatus.VALIDATING,
         JobStatus.SAVING)

# Ceiling on how many jobs one call may queue. With worker.py running, queued
# jobs no longer compete with the API for CPU, so this is a blast-radius limit
# rather than a throughput one: a mistaken call re-derives a handful of jobs,
# not the whole corpus. The endpoint is safe to call repeatedly.
DEFAULT_BATCH = 5
MAX_BATCH = 50


def _stale_job_ids(db: Session, limit: int | None = None) -> list[int]:
    """Jobs holding at least one record below the current engine version.

    Ordered oldest-first so a partial run makes predictable progress rather
    than reprocessing an arbitrary slice each time.
    """
    stmt = (
        select(Record.job_id)
        .where(func.coalesce(Record.engine_version, 0) < ENGINE_VERSION)
        .group_by(Record.job_id)
        .order_by(Record.job_id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/engine-status")
def engine_status(
    _user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    """How much of the corpus was produced by which engine version."""
    by_version = [
        {"engine_version": v, "records": n, "current": v == ENGINE_VERSION}
        for v, n in db.execute(
            select(Record.engine_version, func.count(Record.id))
            .group_by(Record.engine_version)
            .order_by(Record.engine_version)
        ).all()
    ]
    total = sum(r["records"] for r in by_version)
    stale = sum(r["records"] for r in by_version if not r["current"])
    stale_jobs = _stale_job_ids(db)

    return {
        "current_engine_version": ENGINE_VERSION,
        "total_records": total,
        "stale_records": stale,
        "stale_percent": round(100.0 * stale / total, 1) if total else 0.0,
        "stale_jobs": len(stale_jobs),
        "by_version": by_version,
        # NULL means the row predates versioning entirely.
        "note": "engine_version null = written before lineage tracking",
    }


@router.post("/reprocess")
def reprocess(
    background: BackgroundTasks,
    limit: int = Query(DEFAULT_BATCH, ge=1, le=MAX_BATCH,
                       description="How many stale jobs to queue in this call."),
    dry_run: bool = Query(False, description="Report what would run, run nothing."),
    _user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    """Re-derive stale records from their stored source files.

    Queues up to `limit` stale jobs, oldest first. Each queued job deletes its
    own records and rewrites them, so calling this repeatedly converges rather
    than duplicating. Jobs currently running, and jobs whose source file is
    gone or encrypted, are skipped and reported.
    """
    candidates = _stale_job_ids(db, limit=None)
    queued: list[int] = []
    skipped: list[dict] = []

    for job_id in candidates:
        if len(queued) >= limit:
            break
        job = db.get(ProcessingJob, job_id)
        if job is None:
            skipped.append({"job_id": job_id, "reason": "job record missing"})
            continue
        if job.status in _BUSY:
            skipped.append({"job_id": job_id, "reason": f"already {job.status}"})
            continue

        src = db.get(SourceFile, job.source_file_id)
        if src is None:
            # Without the original file there is nothing to re-derive from.
            # Reported rather than silently passed over, because it means the
            # rows can never be corrected and someone has to decide what to do.
            skipped.append({"job_id": job_id, "reason": "source file record missing"})
            continue
        if src.is_encrypted:
            skipped.append({"job_id": job_id, "reason": "source is password-protected"})
            continue

        # Same contract as POST /jobs/{id}/start?force=true: replace the job's
        # rows rather than adding to them.
        db.execute(delete(Record).where(Record.job_id == job_id))
        db.execute(delete(ProcessingError).where(ProcessingError.job_id == job_id))
        job.status = JobStatus.UPLOADED
        job.control_signal = None
        job.message = f"Reprocessing for engine version {ENGINE_VERSION}."
        job.valid_rows = job.invalid_rows = job.duplicate_rows = 0
        job.skipped_rows = job.processed_rows = job.error_count = 0
        job.progress_percent = 0.0
        queued.append(job_id)

    if dry_run:
        db.rollback()
        return {
            "dry_run": True,
            "current_engine_version": ENGINE_VERSION,
            "stale_jobs_total": len(candidates),
            "would_queue": queued,
            "skipped": skipped,
        }

    db.commit()
    # Queued only after the commit: a task that starts before the reset lands
    # would read the job's pre-reset state.
    from .jobs import run_job
    for job_id in queued:
        background.add_task(run_job, job_id)

    log.info("reprocess queued %d job(s) for engine version %d",
             len(queued), ENGINE_VERSION)
    return {
        "dry_run": False,
        "current_engine_version": ENGINE_VERSION,
        "stale_jobs_total": len(candidates),
        "queued": queued,
        "skipped": skipped,
        "remaining_after_this_run": max(0, len(candidates) - len(queued)),
    }
