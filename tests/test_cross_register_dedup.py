# Cross-register deduplication test suite
"""Deduplication must span registers, not just the file being ingested.

Before this, `seen_hashes` was preloaded filtered by `source_file == <this
file>` and the Tier-2 structures lived only for one `process()` call, so the
same owner arriving in two builder registers was stored twice, both VALID.
Consolidating multi-builder registers is the platform's stated purpose, which
makes that the one duplicate that matters most.
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.dedup_index import DedupIndex
from backend.app.models.models import Base, Record
from engine.processor import Processor

HEADER = "Name,Community,Building/Cluster,Unit Number,Mobile 1,Developer\n"
OWNER = "Mohammed Al Rashid,Dubai Marina,Marina Heights,1204,+971501234567,EMAAR\n"
# Same person, same unit, written the way a different register writes it.
OWNER_VARIANT = "Mohd. Al-Rashid,Dubai Marina,Marina Heights,1204,+971501234567,Emaar Properties\n"
OTHER = "Sara Haddad,Dubai Marina,Marina Heights,1806,+971509876543,EMAAR\n"


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'dedup.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _register(tmp_path, filename, body):
    path = tmp_path / filename
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def _ingest(db, path, *, job_id, cross_register=True):
    """Run one file through the engine, persisting rows as the API does."""
    def on_batch(rows):
        for r in rows:
            db.add(Record(job_id=job_id, **r))
        db.commit()
        return len(rows)

    processor = Processor(
        batch_size=100,
        enable_enrichment=False,
        dedup_index=DedupIndex(db, exclude_job_id=job_id) if cross_register else None,
    )
    return processor.process(path, source_name=path.name, on_batch=on_batch)


def _statuses(db, source_file):
    return [r.status for r in db.scalars(
        select(Record).where(Record.source_file == source_file)
        .order_by(Record.id)).all()]


def test_same_owner_in_a_second_register_is_a_duplicate(db, tmp_path):
    _ingest(db, _register(tmp_path, "builder_a.csv", OWNER), job_id=1)
    assert _statuses(db, "builder_a.csv") == ["VALID"]

    _ingest(db, _register(tmp_path, "builder_b.csv", OWNER), job_id=2)
    assert _statuses(db, "builder_b.csv") == ["DUPLICATE"]


def test_name_variant_on_the_same_unit_is_caught_by_the_fuzzy_tier(db, tmp_path):
    _ingest(db, _register(tmp_path, "builder_a.csv", OWNER), job_id=1)
    _ingest(db, _register(tmp_path, "builder_b.csv", OWNER_VARIANT), job_id=2)

    row = db.scalars(select(Record)
                     .where(Record.source_file == "builder_b.csv")).one()
    assert row.status == "DUPLICATE"
    # The row records what it matched and how closely, so a reviewer can judge.
    assert row.fuzzy_match_score >= 0.85
    assert row.fuzzy_matched_id is not None
    assert any("fuzzy_duplicate" in f for f in row.validation_flags)


def test_a_different_owner_in_the_same_building_is_kept(db, tmp_path):
    _ingest(db, _register(tmp_path, "builder_a.csv", OWNER), job_id=1)
    _ingest(db, _register(tmp_path, "builder_b.csv", OTHER), job_id=2)
    assert _statuses(db, "builder_b.csv") == ["VALID"]


def test_duplicates_within_one_file_are_still_caught(db, tmp_path):
    _ingest(db, _register(tmp_path, "one.csv", OWNER + OWNER + OTHER), job_id=1)
    assert _statuses(db, "one.csv") == ["VALID", "DUPLICATE", "VALID"]


def test_cross_register_dedup_can_be_switched_off(db, tmp_path):
    _ingest(db, _register(tmp_path, "builder_a.csv", OWNER), job_id=1)
    _ingest(db, _register(tmp_path, "builder_b.csv", OWNER), job_id=2,
            cross_register=False)
    # Old behaviour: the second register cannot see the first.
    assert _statuses(db, "builder_b.csv") == ["VALID"]


def test_a_job_does_not_deduplicate_against_its_own_rows(db, tmp_path):
    # exclude_job_id matters on a retry: without it, a resumed job matches the
    # rows its own first attempt wrote and marks every one a duplicate.
    _ingest(db, _register(tmp_path, "a.csv", OWNER), job_id=7)
    idx = DedupIndex(db, exclude_job_id=7)
    assert idx.seen_hashes([r.identity_hash for r in db.scalars(select(Record))]) == set()


def test_probe_returns_matches_from_other_jobs(db, tmp_path):
    _ingest(db, _register(tmp_path, "a.csv", OWNER), job_id=1)
    stored = db.scalars(select(Record)).one()
    idx = DedupIndex(db, exclude_job_id=2)
    assert idx.seen_hashes([stored.identity_hash]) == {stored.identity_hash}
    assert idx.seen_properties([stored.property_key])[stored.property_key][1] == stored.name
    assert idx.seen_phones([stored.mobile_1])[stored.mobile_1][1] == stored.name
