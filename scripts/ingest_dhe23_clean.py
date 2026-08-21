"""
Full Clean Ingestion for DHE 23.xlsx
Processes both Sheet1 and GOLF place (~52,725 rows total)
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg2
from backend.app.database.session import SessionLocal
from backend.app.models.models import Record, ProcessingJob, SourceFile, JobStatus
from engine.processor import Processor
from sqlalchemy import select

def main():
    print("=" * 60)
    print("  INGESTING DHE 23.xlsx (ALL 52,725 ROWS)")
    print("=" * 60)

    # 1. Clean previous partial jobs for DHE 23 using raw SQL
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM records WHERE job_id IN (
            SELECT id FROM processing_jobs WHERE source_file_id IN (
                SELECT id FROM source_files WHERE filename = 'DHE 23.xlsx'
            )
        ) OR source_file = 'DHE 23.xlsx';

        DELETE FROM processing_errors WHERE job_id IN (
            SELECT id FROM processing_jobs WHERE source_file_id IN (
                SELECT id FROM source_files WHERE filename = 'DHE 23.xlsx'
            )
        );

        DELETE FROM processing_jobs WHERE source_file_id IN (
            SELECT id FROM source_files WHERE filename = 'DHE 23.xlsx'
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

    db = SessionLocal()
    fpath = ROOT / "Dubai Hills Raw Work" / "Raw Batches" / "Batch 01 (5 files - Club Villas, DHE)" / "DHE 23.xlsx"
    if not fpath.exists():
        fpath = ROOT / "Dubai Hills" / "DHE 23.xlsx"

    src = db.scalar(select(SourceFile).where(SourceFile.filename == "DHE 23.xlsx"))
    if not src:
        src = SourceFile(
            filename="DHE 23.xlsx",
            stored_path=str(fpath.resolve()),
            size_bytes=fpath.stat().st_size,
            content_sha256="dhe23_full_clean",
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(src)
        db.commit()
        db.refresh(src)

    job = ProcessingJob(
        source_file_id=src.id,
        status=JobStatus.PROCESSING,
        batch_size=1000,
        started_at=datetime.now(timezone.utc),
        progress_percent=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id
    print(f"Created Job #{job_id} for DHE 23.xlsx. Ingesting rows...")

    seen = set(db.scalars(select(Record.identity_hash)).all())

    def on_batch(rows: list[dict]) -> int:
        for r in rows:
            r["job_id"] = job_id
        db.bulk_insert_mappings(Record, rows)
        db.commit()
        return len(rows)

    def on_progress(res, sheet_name: str) -> None:
        job.current_sheet = sheet_name
        job.total_rows = res.total_rows
        job.processed_rows = res.processed_rows
        job.valid_rows = res.valid_rows
        job.invalid_rows = res.invalid_rows
        job.duplicate_rows = res.duplicate_rows
        job.skipped_rows = res.skipped_rows
        if res.total_rows:
            job.progress_percent = min(round(100.0 * res.processed_rows / res.total_rows, 1), 99.0)
        db.commit()

    t0 = time.time()
    processor = Processor(batch_size=1000)
    res = processor.process(fpath, source_name="DHE 23.xlsx", on_batch=on_batch, on_progress=on_progress, seen_hashes=seen)

    job.total_rows = res.total_rows
    job.processed_rows = res.processed_rows
    job.valid_rows = res.valid_rows
    job.invalid_rows = res.invalid_rows
    job.duplicate_rows = res.duplicate_rows
    job.skipped_rows = res.skipped_rows
    job.mapping_report = res.mapping_report
    job.progress_percent = 100.0
    job.status = JobStatus.COMPLETED
    job.finished_at = datetime.now(timezone.utc)
    job.current_sheet = None
    db.commit()

    dur = time.time() - t0
    print(f"\n✅ DHE 23.xlsx Successfully Ingested in {dur:.2f}s!")
    print(f"   Total Rows:       {res.total_rows:,}")
    print(f"   Valid Records:    {res.valid_rows:,}")
    print(f"   Duplicates Saved: {res.duplicate_rows:,}")
    print(f"   Invalid Rows:     {res.invalid_rows:,}")

    db.close()

if __name__ == "__main__":
    main()
