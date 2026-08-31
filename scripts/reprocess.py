# Re-applies cleaning and normalization transformations to existing records
"""Re-run every stored source file through the current engine.

Use after an engine change that alters cleaning/mapping output, so the stored
dataset matches the current rules instead of the rules in force at upload time.

    python scripts/reprocess.py            # all files
    python scripts/reprocess.py --job 5    # one job

Records are replaced per source file inside a transaction; source_files and the
upload artefacts are never touched.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings                      # noqa: E402
from backend.app.database.session import SessionLocal, init_db  # noqa: E402
from backend.app.models.models import (                      # noqa: E402
    JobStatus, ProcessingError, ProcessingJob, Record, SourceFile,
)
from engine.detection import UnreadableFile                  # noqa: E402
from engine.processor import Processor                       # noqa: E402
from sqlalchemy import delete, select                        # noqa: E402


def reprocess(job_ids: list[int] | None = None) -> None:
    init_db()
    db = SessionLocal()
    processor = Processor(
        batch_size=settings.BATCH_SIZE,
        enable_enrichment=settings.ENABLE_ENRICHMENT,
        reference_path=settings.REFERENCE_WORKBOOK,
        record_grain=settings.RECORD_GRAIN,
    )
    try:
        stmt = select(ProcessingJob).order_by(ProcessingJob.id)
        if job_ids:
            stmt = stmt.where(ProcessingJob.id.in_(job_ids))
        jobs = db.scalars(stmt).all()
        print(f"reprocessing {len(jobs)} job(s)\n")

        for job in jobs:
            src = db.get(SourceFile, job.source_file_id)
            if src is None or not Path(src.stored_path).exists():
                print(f"  job {job.id}: source file missing, skipped")
                continue

            before = db.scalar(
                select(Record.id).where(Record.job_id == job.id).limit(1))
            db.execute(delete(Record).where(Record.job_id == job.id))
            db.execute(delete(ProcessingError).where(ProcessingError.job_id == job.id))
            db.commit()

            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

            def on_batch(rows: list[dict], _job=job) -> int:
                for r in rows:
                    r["job_id"] = _job.id
                try:
                    db.bulk_insert_mappings(Record, rows)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                return len(rows)

            t0 = time.time()
            try:
                res = processor.process(
                    Path(src.stored_path), source_name=src.filename,
                    on_batch=on_batch, seen_hashes=set(),
                )
            except UnreadableFile as exc:
                job.status = JobStatus.FAILED
                job.message = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.add(ProcessingError(job_id=job.id, severity="ERROR",
                                       code="UNREADABLE_FILE", message=str(exc)))
                db.commit()
                print(f"  job {job.id}: {src.filename[:44]:46} BLOCKED")
                continue

            job.total_rows = res.total_rows
            job.processed_rows = res.processed_rows
            job.valid_rows = res.valid_rows
            job.invalid_rows = res.invalid_rows
            job.duplicate_rows = res.duplicate_rows
            job.skipped_rows = res.skipped_rows
            job.mapping_report = res.mapping_report
            job.progress_percent = 100.0
            job.error_count = len(res.errors)
            for e in res.errors[:5000]:
                db.add(ProcessingError(job_id=job.id, **e))
            hard = sum(1 for e in res.errors if e.get("severity") == "ERROR")
            job.status = (JobStatus.COMPLETED_WITH_ERRORS
                          if (hard or job.invalid_rows) else JobStatus.COMPLETED)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()

            print(f"  job {job.id}: {src.filename[:44]:46} "
                  f"rows={res.total_rows:6} ok={res.valid_rows:6} "
                  f"dup={res.duplicate_rows:5} skip={res.skipped_rows:5} "
                  f"err={len(res.errors):3} {time.time()-t0:.0f}s"
                  f"{'' if before else '  (was empty)'}")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=int, action="append", dest="jobs")
    args = ap.parse_args()
    reprocess(args.jobs)
