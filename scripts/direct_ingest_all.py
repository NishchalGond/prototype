"""
Direct Ingestion CLI Script
Processes and ingests all Excel/CSV files directly into Supabase PostgreSQL
without going through the HTTP API.

Features:
- Runs full 7-stage engine cleaning, normalization, deduplication & enrichment.
- Populates source_files, processing_jobs, and records tables directly in Supabase.
- Full live progress terminal logging per file and batch.
- Automatically reflects in the web dashboard instantly.
"""
import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import select, func
from backend.app.database.session import SessionLocal, init_db
from backend.app.models.models import SourceFile, ProcessingJob, Record, ProcessingError, JobStatus
from backend.app.config import settings
from engine.processor import Processor


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_file(db, file_path: Path, processor: Processor, seen_hashes: set) -> tuple[int, int]:
    file_path = Path(file_path)
    file_hash = sha256_file(file_path)
    file_size = file_path.stat().st_size
    filename = file_path.name

    # 1. Create or get SourceFile record
    src = db.scalar(select(SourceFile).where(SourceFile.content_sha256 == file_hash))
    if not src:
        src = SourceFile(
            filename=filename,
            stored_path=str(file_path.resolve()),
            size_bytes=file_size,
            content_sha256=file_hash,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(src)
        db.commit()
        db.refresh(src)

    # 2. Create ProcessingJob record
    job = ProcessingJob(
        source_file_id=src.id,
        status=JobStatus.PROCESSING,
        batch_size=settings.BATCH_SIZE,
        started_at=datetime.now(timezone.utc),
        progress_percent=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 3. Batch callback
    def on_batch(rows: list[dict]) -> int:
        for r in rows:
            r["job_id"] = job.id
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
        if res.total_rows and res.total_rows > 0:
            job.progress_percent = min(round(100.0 * res.processed_rows / res.total_rows, 1), 99.0)
        db.commit()

    # 4. Execute Engine
    result = processor.process(
        file_path,
        source_name=filename,
        on_batch=on_batch,
        on_progress=on_progress,
        seen_hashes=seen_hashes,
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
    job.finished_at = datetime.now(timezone.utc)
    job.current_sheet = None

    hard = sum(1 for e in result.errors if e.get("severity") == "ERROR")
    job.status = JobStatus.COMPLETED_WITH_ERRORS if (hard or job.invalid_rows) else JobStatus.COMPLETED

    for e in result.errors[:500]:
        db.add(ProcessingError(job_id=job.id, **e))
    job.error_count = len(result.errors)

    db.commit()
    return result.total_rows, result.valid_rows


def main():
    print("=" * 70)
    print("  DIRECT DATABASE INGESTION ENGINE (SUPABASE POSTGRESQL)")
    print("=" * 70)

    # Initialize Database tables
    init_db()
    db = SessionLocal()

    # Collect files from Raw Batches folder
    batches_dir = ROOT / "Dubai Hills Raw Work" / "Raw Batches"
    if not batches_dir.exists():
        batches_dir = ROOT / "Dubai Hills"

    files = sorted(
        [f for f in batches_dir.glob("**/*") if f.is_file() and f.suffix.lower() in (".xlsx", ".xls", ".csv")
         and not f.name.startswith("~$") and not f.name.startswith("._") and not f.name.startswith("0-")
         and "done" not in f.name.lower()]
    )

    print(f"\n📂 Target directory: {batches_dir}")
    print(f"📊 Total files to ingest: {len(files)}")
    print(f"🔗 Database URL: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'connected'}")
    print("-" * 70)

    processor = Processor(
        batch_size=settings.BATCH_SIZE,
        enable_enrichment=settings.ENABLE_ENRICHMENT,
        reference_path=settings.REFERENCE_WORKBOOK,
        record_grain=settings.RECORD_GRAIN,
    )

    # Load existing identity hashes for cross-file deduplication
    print("\n⏳ Fetching existing identity hashes for global deduplication...")
    seen_hashes = set(db.scalars(select(Record.identity_hash)).all())
    print(f"   Found {len(seen_hashes):,} existing identity hashes in database.\n")

    grand_total_rows = 0
    grand_valid_rows = 0
    t0 = time.time()

    for idx, f in enumerate(files, 1):
        file_name = f.name
        file_size_kb = f.stat().st_size / 1024
        print(f"[{idx:02d}/{len(files):02d}] Ingesting: {file_name:<45} ({file_size_kb:6.1f} KB)...", end=" ", flush=True)

        try:
            t_file = time.time()
            total_r, valid_r = ingest_file(db, f, processor, seen_hashes)
            dur = time.time() - t_file
            grand_total_rows += total_r
            grand_valid_rows += valid_r
            print(f"✅ {total_r:6,d} rows ({valid_r:6,d} valid) in {dur:.2f}s")
        except Exception as exc:
            print(f"❌ ERROR: {exc}")

    db.close()
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print("  INGESTION COMPLETE")
    print("=" * 70)
    print(f"  Total Files Processed: {len(files):,}")
    print(f"  Total Rows Ingested:   {grand_total_rows:,}")
    print(f"  Total Valid Records:   {grand_valid_rows:,}")
    print(f"  Elapsed Time:          {elapsed:.2f} seconds ({grand_total_rows/max(elapsed,0.1):.1f} rows/sec)")
    print("=" * 70)
    print("\n🌐 Refresh your browser at http://localhost:3000 or your Vercel URL to see all records!")


if __name__ == "__main__":
    main()
