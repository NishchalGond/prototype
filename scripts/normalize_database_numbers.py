"""Batch normalization script for existing database records.

Normalizes:
- Mobile numbers (E.164 +971 standard, strips float artifacts and formats)
- Procedure values (cleaned positive rounded floats)
- Sizes (cleaned positive rounded floats)
- Unit numbers & Plot numbers (strips .0 float artifacts and whitespace)
- Recomputes identity hash and validation flags
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import func, select
from sqlalchemy.orm import defer
from backend.app.database.session import SessionLocal
from backend.app.models.models import Record, RecordStatus
from engine import cleaning as C
from engine import validation as V


def normalize_all_records(batch_size: int = 1000, dry_run: bool = False):
    db = SessionLocal()
    try:
        print("Connecting to database...", flush=True)
        total = db.scalar(select(func.count(Record.id))) or 0
        min_id = db.scalar(select(func.min(Record.id))) or 1
        print(f"Total records in database: {total:,} (Min ID: {min_id})", flush=True)

        last_id = min_id - 1
        processed_count = 0
        updated_count = 0

        while True:
            records = db.scalars(
                select(Record)
                .options(defer(Record.extras))
                .where(Record.id > last_id)
                .order_by(Record.id)
                .limit(batch_size)
            ).all()

            if not records:
                break

            batch_changed = False
            for rec in records:
                changed = False

                # 1. Phone numbers
                for mobile_slot in ("mobile_1", "mobile_2", "mobile_3"):
                    raw_val = getattr(rec, mobile_slot)
                    if raw_val:
                        cleaned_val, _ = C.clean_phone(raw_val)
                        if cleaned_val != raw_val:
                            setattr(rec, mobile_slot, cleaned_val)
                            changed = True

                # 2. Procedure value
                if rec.procedure_value is not None:
                    cleaned_val = C.clean_number(rec.procedure_value)
                    if cleaned_val != rec.procedure_value:
                        rec.procedure_value = cleaned_val
                        changed = True

                # 3. Size
                if rec.size is not None:
                    cleaned_val = C.clean_size(rec.size)
                    if cleaned_val != rec.size:
                        rec.size = cleaned_val
                        changed = True

                # 4. Unit number & Plot number
                if rec.unit_number is not None:
                    cleaned_val = C.clean_unit(rec.unit_number)
                    if cleaned_val != rec.unit_number:
                        rec.unit_number = cleaned_val
                        changed = True

                if rec.plot_number is not None:
                    cleaned_val = C.clean_unit(rec.plot_number)
                    if cleaned_val != rec.plot_number:
                        rec.plot_number = cleaned_val
                        changed = True

                # 5. DMNO / DMSUBNO / PI
                for code_slot in ("dmno", "dmsubno", "pi_number"):
                    raw_val = getattr(rec, code_slot)
                    if raw_val:
                        cleaned_val = C.clean_text(raw_val)
                        if cleaned_val != raw_val:
                            setattr(rec, code_slot, cleaned_val)
                            changed = True

                # 6. Re-evaluate status & validation flags
                row_dict = {
                    "name": rec.name,
                    "mobile_1": rec.mobile_1,
                    "mobile_2": rec.mobile_2,
                    "mobile_3": rec.mobile_3,
                    "email_address": rec.email_address,
                    "community": rec.community,
                    "sub_community": rec.sub_community,
                    "building_cluster": rec.building_cluster,
                    "unit_number": rec.unit_number,
                    "plot_number": rec.plot_number,
                    "pi_number": rec.pi_number,
                    "developer": rec.developer,
                    "project": rec.project,
                    "bedroom": rec.bedroom,
                    "procedure_value": rec.procedure_value,
                    "property_type": rec.property_type,
                    "party_type": rec.party_type,
                }
                is_valid, flags = V.validate(row_dict)
                has_property = V.is_valid_property_context(row_dict)
                has_contact = bool(rec.mobile_1 or rec.email_address)
                has_name = bool(rec.name and str(rec.name).strip())

                new_status = rec.status
                if not is_valid:
                    new_status = RecordStatus.INVALID
                elif rec.status != RecordStatus.DUPLICATE:
                    if has_name and has_contact and has_property:
                        new_status = RecordStatus.VALID
                    else:
                        new_status = RecordStatus.INCOMPLETE

                if new_status != rec.status:
                    rec.status = new_status
                    changed = True

                if changed:
                    rec.identity_hash = V.identity_hash(row_dict)
                    rec.validation_flags = flags
                    updated_count += 1
                    batch_changed = True

            if not dry_run and batch_changed:
                try:
                    db.commit()
                except Exception as e:
                    print(f"Commit error ({e}), reconnecting and retrying...", flush=True)
                    db.rollback()
                    db.close()
                    db = SessionLocal()
                    continue

            db.expunge_all()

            last_id = records[-1].id
            processed_count += len(records)
            print(f"Processed {min(processed_count, total):,} / {total:,} records (Updated: {updated_count:,})...", flush=True)

        if not dry_run:
            db.commit()
        print(f"Done! Successfully normalized {updated_count:,} records (Dry run: {dry_run}).", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    normalize_all_records(dry_run=is_dry)
