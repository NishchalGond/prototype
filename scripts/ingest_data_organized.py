"""
Data Ingestion CLI for Y:\1-Data_Organized
Ingests multi-builder spreadsheets (.xlsx, .xls, .csv) into Local PostgreSQL.
Enforces a hard ceiling of ~2.956M records and monitors disk space safety.
"""
import os
import sys
import time
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import select, text, func
from backend.app.database.session import SessionLocal, init_db
from backend.app.models.models import SourceFile, ProcessingJob, Record, ProcessingError, JobStatus
from backend.app.config import settings
from engine.processor import Processor

# Hard Target Ceiling requested by user
TARGET_MAX_RECORDS = 2_956_000
MIN_FREE_DISK_GB = 15.0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_disk_safety() -> tuple[bool, float]:
    """Ensure PostgreSQL data drive (D: or C:) has ample free space."""
    target_drive = "D:\\" if Path("D:\\").exists() else "C:\\"
    try:
        _, _, free_bytes = shutil.disk_usage(target_drive)
        free_gb = free_bytes / (1024 ** 3)
        return free_gb >= MIN_FREE_DISK_GB, free_gb
    except Exception:
        return True, 999.0


def ingest_file(db, file_path: Path, processor: Processor, seen_hashes: set) -> tuple[int, int, int]:
    file_path = Path(file_path)
    file_hash = sha256_file(file_path)
    file_size = file_path.stat().st_size
    filename = file_path.name

    # Check if already ingested
    src = db.scalar(select(SourceFile).where(SourceFile.content_sha256 == file_hash))
    if src:
        existing_job = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.source_file_id == src.id, ProcessingJob.status == JobStatus.COMPLETED)
            .order_by(ProcessingJob.id.desc()).limit(1)
        )
        if existing_job:
            return -1, existing_job.total_rows or 0, existing_job.valid_rows or 0

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

    # Batch insert callback
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

    # Process file through engine
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

    for e in result.errors[:200]:
        db.add(ProcessingError(job_id=job.id, **e))
    job.error_count = len(result.errors)

    db.commit()
    return 1, result.total_rows, result.valid_rows


def refresh_materialized_views(db):
    try:
        db.execute(text("REFRESH MATERIALIZED VIEW mv_record_stats;"))
        db.execute(text("REFRESH MATERIALIZED VIEW mv_record_facets;"))
        db.commit()
        print("  [Analytics Views Refreshed]", flush=True)
    except Exception as e:
        print(f"  [Notice: view refresh skipped: {e}]", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Ingest spreadsheets up to target record cap into PostgreSQL")
    parser.add_argument("--dir", default=r"Y:\1-Data_Organized", help="Source folder path")
    parser.add_argument("--subfolder", default="", help="Specific subfolder to process")
    parser.add_argument("--max-records", type=int, default=TARGET_MAX_RECORDS, help="Target record ceiling")
    args = parser.parse_args()

    max_target = args.max_records
    target_dir = Path(args.dir)
    if args.subfolder:
        target_dir = target_dir / args.subfolder

    if not target_dir.exists():
        print(f"Directory not found: {target_dir}")
        sys.exit(1)

    init_db()
    db = SessionLocal()

    # Initial checks
    current_count = db.scalar(select(func.count(Record.id))) or 0
    safe, free_gb = check_disk_safety()

    print("=" * 70)
    print("  DATALINK ENGINE: CONTROLLED BULK INGESTION")
    print(f"  Source Directory:    {target_dir}")
    print(f"  Current DB Records:  {current_count:,}")
    print(f"  Target Max Records:  {max_target:,} (~2.956M)")
    print(f"  Disk Free Space:     {free_gb:.1f} GB (Safe threshold: {MIN_FREE_DISK_GB} GB)")
    print("=" * 70)

    if current_count >= max_target:
        print(f"\nTarget cap of {max_target:,} records is ALREADY reached ({current_count:,} records).")
        print("No further ingestion required. Database is fully populated and safe.")
        refresh_materialized_views(db)
        db.close()
        return

    # Collect files
    print("\nScanning for remaining spreadsheets...", flush=True)
    files = sorted([
        f for f in target_dir.glob("**/*")
        if f.is_file() 
        and f.suffix.lower() in (".xlsx", ".xls", ".csv")
        and not f.name.startswith("~$")
        and not f.name.startswith("._")
    ])

    print(f"Found {len(files):,} spreadsheet files to check.\n", flush=True)

    processor = Processor(
        batch_size=settings.BATCH_SIZE,
        enable_enrichment=settings.ENABLE_ENRICHMENT,
        reference_path=settings.REFERENCE_WORKBOOK,
        record_grain=settings.RECORD_GRAIN,
    )

    print("Loading existing identity hashes for deduplication...", flush=True)
    seen_hashes = set(db.scalars(select(Record.identity_hash)).all())
    print(f"Loaded {len(seen_hashes):,} existing identity hashes.\n", flush=True)

    total_files_processed = 0
    total_files_skipped = 0
    grand_total_rows = 0
    grand_valid_rows = 0
    t0 = time.time()

    for idx, f in enumerate(files, 1):
        # 1. Check Disk Safety
        safe, free_gb = check_disk_safety()
        if not safe:
            print(f"\n[SAFETY STOP]: Free disk space dropped to {free_gb:.1f} GB (below {MIN_FREE_DISK_GB} GB). Stopping ingestion to protect disk.", flush=True)
            break

        # 2. Check Record Cap
        curr_records = db.scalar(select(func.count(Record.id))) or 0
        if curr_records >= max_target:
            print(f"\n🎉 [TARGET REACHED]: Database now has {curr_records:,} records (Target: {max_target:,}). Stopping ingestion cleanly!", flush=True)
            break

        file_size_kb = f.stat().st_size / 1024
        print(f"[{idx:04d}/{len(files):04d}] {f.name[:45]:<45} ({file_size_kb:7.1f} KB)... ", end="", flush=True)
        try:
            t_f = time.time()
            status_code, total_r, valid_r = ingest_file(db, f, processor, seen_hashes)
            dur = time.time() - t_f
            if status_code == -1:
                total_files_skipped += 1
                print(f"SKIPPED (already in DB with {total_r:,} rows)")
            else:
                total_files_processed += 1
                grand_total_rows += total_r
                grand_valid_rows += valid_r
                print(f"DONE: {total_r:,} rows ({valid_r:,} valid) [{dur:.1f}s]")
        except Exception as e:
            print(f"FAILED: {e}")
            db.rollback()

        # Periodically refresh views every 20 files
        if total_files_processed > 0 and total_files_processed % 20 == 0:
            refresh_materialized_views(db)

    # Final refresh
    refresh_materialized_views(db)
    final_count = db.scalar(select(func.count(Record.id))) or 0
    db.close()
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print("  INGESTION SUMMARY")
    print("=" * 70)
    print(f"  Final Record Count in DB: {final_count:,} (Target: {max_target:,})")
    print(f"  Files Newly Ingested:     {total_files_processed:,}")
    print(f"  Files Skipped (in DB):    {total_files_skipped:,}")
    print(f"  Total Time Elapsed:       {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
