# Outreach verdict and contact feedback integration test suite
"""Outreach as a data-quality sensor.

A salesperson who dials and hears "wrong number" has produced better evidence
about that number than any rule in the pipeline. has_valid_mobile only says a
number is well FORMED; only a call can say it is WRONG. These tests pin the
loop that carries that verdict back into the data, and keeps it there across
reprocessing.
"""
import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.leads import _get_or_create_lead, relink_leads
from backend.app.api.records import _build_records_query
from backend.app.models.models import (
    Base, ContactVerdict, Lead, ProcessingJob, Record, RecordEditAudit,
    SourceFile, User, UserRole,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'verdicts.db'}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(db):
    u = User(email="agent@example.com", full_name="Agent", hashed_password="x",
             role=UserRole.DATA_PROCESSOR, is_active=True)
    db.add(u)
    db.commit()
    return u


def _record(db, *, job_id=1, identity_hash="h1", name="Mohammed Al Rashid"):
    if not db.get(ProcessingJob, job_id):
        src = SourceFile(filename="r.csv", stored_path="/tmp/r.csv", size_bytes=1,
                         content_sha256="d" * 64)
        db.add(src)
        db.flush()
        db.add(ProcessingJob(id=job_id, source_file_id=src.id, status="COMPLETED"))
        db.commit()
    r = Record(job_id=job_id, source_file="r.csv", identity_hash=identity_hash,
               status="VALID", name=name, community="Dubai Marina",
               mobile_1="+971501234567")
    db.add(r)
    db.commit()
    return r


def _verdict(db, record, verdict):
    lead = _get_or_create_lead(db, record)
    lead.contact_verdict = verdict
    db.commit()
    return lead


# --- a disproved number leaves the desk's list ------------------------------

@pytest.mark.parametrize("verdict", ContactVerdict.SUPPRESSING)
def test_a_disproved_contact_is_suppressed(db, user, verdict):
    record = _record(db)
    _verdict(db, record, verdict)
    assert db.scalars(_build_records_query()).all() == []


def test_a_confirmed_contact_stays_visible(db, user):
    record = _record(db)
    _verdict(db, record, ContactVerdict.REACHED)
    assert [r.id for r in db.scalars(_build_records_query()).all()] == [record.id]


def test_no_answer_is_not_a_verdict_against_the_number(db, user):
    # Nobody picking up is not evidence the number is wrong. Suppressing those
    # would quietly delete the hard half of the list.
    assert ContactVerdict.UNREACHABLE not in ContactVerdict.SUPPRESSING
    record = _record(db)
    _verdict(db, record, ContactVerdict.UNREACHABLE)
    assert [r.id for r in db.scalars(_build_records_query()).all()] == [record.id]


def test_the_verdict_outranks_a_well_formed_number(db, user):
    # The record has a perfectly valid E.164 mobile. The call proved it wrong,
    # and the call wins.
    record = _record(db)
    assert record.mobile_1 == "+971501234567"
    _verdict(db, record, ContactVerdict.WRONG_NUMBER)
    assert db.scalars(_build_records_query()).all() == []


def test_the_verdict_survives_a_reprocess(db, user):
    record = _record(db)
    _verdict(db, record, ContactVerdict.WRONG_NUMBER)

    db.execute(delete(Record).where(Record.job_id == 1))
    db.commit()
    _record(db, identity_hash="h1")      # engine rewrites it from source

    # Without a durable verdict the pipeline would hand the same dead number
    # back to the desk.
    assert db.scalars(_build_records_query()).all() == []


def test_only_the_judged_identity_is_suppressed(db, user):
    bad = _record(db, identity_hash="bad")
    good = _record(db, identity_hash="good", name="Sara Haddad")
    _verdict(db, bad, ContactVerdict.WRONG_NUMBER)
    assert [r.id for r in db.scalars(_build_records_query()).all()] == [good.id]


# --- manual corrections outlive reprocessing --------------------------------

def test_edit_history_survives_a_reprocess(db, user):
    """Previously CASCADE: reprocessing deleted every hand-correction to a job's
    rows, and the record of who made them. A correction is no more derivable
    from a source file than a phone call is.
    """
    record = _record(db)
    db.add(RecordEditAudit(record_id=record.id, identity_hash=record.identity_hash,
                           user_id=user.id, user_email=user.email,
                           field_name="name", old_value="M Al Rashid",
                           new_value="Mohammed Al Rashid"))
    db.commit()

    db.execute(delete(Record).where(Record.job_id == 1))
    db.commit()

    audit = db.scalar(select(RecordEditAudit))
    assert audit is not None, "edit history was deleted with the record"
    assert audit.record_id is None
    assert audit.identity_hash == "h1"


def test_edit_history_is_relinked_after_a_reprocess(db, user):
    record = _record(db)
    db.add(RecordEditAudit(record_id=record.id, identity_hash=record.identity_hash,
                           user_id=user.id, user_email=user.email,
                           field_name="name", old_value="a", new_value="b"))
    db.commit()

    db.execute(delete(Record).where(Record.job_id == 1))
    db.commit()
    rewritten = _record(db, identity_hash="h1")

    relink_leads(db, job_id=1)
    audit = db.scalar(select(RecordEditAudit))
    assert audit.record_id == rewritten.id


# --- the mapping trap this closes -------------------------------------------

def test_usage_column_no_longer_lands_in_property_type():
    # 29 sampled rows had "Airport" in Property Type, via a USAGE column whose
    # values are area zones rather than dwelling types.
    from engine.mapping import DO_NOT_MAP, norm_header
    assert norm_header("USAGE") in DO_NOT_MAP


# --- a verdict must be reversible and attributable --------------------------

def test_a_verdict_records_who_made_it(db, user):
    # A verdict hides a record from the whole desk. Unattributed, it is a claim
    # nobody can check.
    record = _record(db)
    lead = _get_or_create_lead(db, record)
    lead.contact_verdict = ContactVerdict.WRONG_NUMBER
    lead.contact_verdict_by = user.email
    db.commit()
    assert db.scalar(select(Lead)).contact_verdict_by == "agent@example.com"


def test_clearing_a_verdict_brings_the_record_back(db, user):
    record = _record(db)
    lead = _verdict(db, record, ContactVerdict.WRONG_NUMBER)
    assert db.scalars(_build_records_query()).all() == []

    # What DELETE /leads/{id}/verdict does. People mis-click, and without a way
    # back a single wrong tap buries a valuable property permanently.
    lead.contact_verdict = None
    lead.contact_verdict_at = None
    lead.contact_verdict_by = None
    db.commit()

    assert [r.id for r in db.scalars(_build_records_query()).all()] == [record.id]
