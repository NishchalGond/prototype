"""Right to erasure, and the reason it is harder than a DELETE.

Records are derived: reprocessing rebuilds them from the source file stored at
upload, and that file still contains the person. A redaction that is not backed
by a standing request is undone by the next engine fix.
"""
import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.erasure import PERSONAL_FIELDS, _redact, apply_erasures
from backend.app.api.leads import _get_or_create_lead
from backend.app.models.models import (
    Base, ErasureRequest, Lead, LeadStage, ProcessingJob, Record, SourceFile,
    User, UserRole,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'erasure.db'}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def admin(db):
    u = User(email="admin@example.com", full_name="Admin", hashed_password="x",
             role=UserRole.ADMIN, is_active=True)
    db.add(u)
    db.commit()
    return u


def _job(db, job_id=1):
    if db.get(ProcessingJob, job_id):
        return job_id
    src = SourceFile(filename="r.csv", stored_path="/tmp/r.csv", size_bytes=1,
                     content_sha256="d" * 64)
    db.add(src)
    db.flush()
    db.add(ProcessingJob(id=job_id, source_file_id=src.id, status="COMPLETED"))
    db.commit()
    return job_id


def _record(db, *, job_id=1, identity_hash="h1"):
    _job(db, job_id)
    r = Record(job_id=job_id, source_file="r.csv", identity_hash=identity_hash,
               status="VALID", name="Mohammed Al Rashid",
               mobile_1="+971501234567", email_address="m@example.com",
               nationality="United Arab Emirates",
               extras={"PASSPORT EXPIRY": "2030-01-01"},
               community="Dubai Marina", unit_number="1204",
               procedure_value=2_400_000.0)
    db.add(r)
    db.commit()
    return r


def _request(db, admin, identity_hash="h1"):
    req = ErasureRequest(identity_hash=identity_hash,
                         requested_by_user_id=admin.id,
                         requested_by_email=admin.email, reason="PDPL request")
    db.add(req)
    db.commit()
    return req


# --- what erasure removes, and what it keeps --------------------------------

def test_personal_fields_are_cleared(db, admin):
    record = _record(db)
    _redact(db, ["h1"])
    db.commit()
    db.refresh(record)
    for field in PERSONAL_FIELDS:
        assert getattr(record, field) is None, field


def test_the_property_record_survives(db, admin):
    # The unit and the transaction describe real estate, not the data subject.
    # Erasing the business record of a sale is not what was asked for.
    record = _record(db)
    _redact(db, ["h1"])
    db.commit()
    db.refresh(record)
    assert record.community == "Dubai Marina"
    assert record.unit_number == "1204"
    assert record.procedure_value == 2_400_000.0


def test_unmapped_source_columns_go_too(db, admin):
    # extras carries whatever the register had; the owner files put passport
    # and date-of-birth details there.
    record = _record(db)
    assert record.extras
    _redact(db, ["h1"])
    db.commit()
    db.refresh(record)
    assert record.extras is None


def test_only_the_requested_identity_is_touched(db, admin):
    target = _record(db, identity_hash="erase-me")
    other = _record(db, identity_hash="keep-me")
    _redact(db, ["erase-me"])
    db.commit()
    db.refresh(target)
    db.refresh(other)
    assert target.name is None
    assert other.name == "Mohammed Al Rashid"


# --- surviving the pipeline -------------------------------------------------

def test_reprocessing_would_restore_the_person_without_a_standing_request(db, admin):
    """The failure this design exists to prevent.

    Redaction alone is undone by the next reprocess, because the source file
    still contains them.
    """
    _record(db)
    _redact(db, ["h1"])
    db.commit()

    db.execute(delete(Record).where(Record.job_id == 1))
    db.commit()
    rebuilt = _record(db)                       # as an ingest would rewrite it

    assert rebuilt.name == "Mohammed Al Rashid"  # back again
    assert apply_erasures(db, job_id=1) == 0     # nothing standing to stop it


def test_a_standing_request_re_erases_after_a_reprocess(db, admin):
    _record(db)
    _request(db, admin)
    _redact(db, ["h1"])
    db.commit()

    db.execute(delete(Record).where(Record.job_id == 1))
    db.commit()
    rebuilt = _record(db)
    assert rebuilt.name == "Mohammed Al Rashid"

    assert apply_erasures(db, job_id=1) == 1
    db.refresh(rebuilt)
    assert rebuilt.name is None
    assert rebuilt.mobile_1 is None


def test_a_request_covers_files_uploaded_later(db, admin):
    # Someone erased today can appear in a register uploaded next month. The
    # request has to cover that too, or it only ever covered the files that
    # existed when it was made.
    _request(db, admin, identity_hash="h1")
    later = _record(db, job_id=2, identity_hash="h1")
    assert apply_erasures(db, job_id=2) == 1
    db.refresh(later)
    assert later.name is None


def test_re_applying_when_nothing_is_standing_is_a_no_op(db, admin):
    _record(db)
    assert apply_erasures(db, job_id=1) == 0


def test_re_applying_twice_redacts_once(db, admin):
    _record(db)
    _request(db, admin)
    assert apply_erasures(db, job_id=1) == 1
    assert apply_erasures(db, job_id=1) == 0     # already clear


# --- erasure and outreach ---------------------------------------------------

def test_an_erased_person_is_suppressed_from_outreach(db, admin):
    from backend.app.api.records import _build_records_query

    record = _record(db)
    lead = _get_or_create_lead(db, record)
    lead.stage = LeadStage.DO_NOT_CONTACT       # what erase_record sets
    _request(db, admin)
    _redact(db, ["h1"])
    db.commit()

    assert db.scalars(_build_records_query()).all() == []
