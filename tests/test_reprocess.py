"""Reprocessing: a corrected rule must be able to reach data already stored.

Every correctness fix in this codebase changes what the pipeline WOULD produce,
not what it already produced. Without lineage and a re-derive path, each fix
stranded the existing table and the database drifted permanently behind the
code. These tests pin the mechanism that closes that gap.
"""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.maintenance import _stale_job_ids
from backend.app.core.dedup_index import DedupIndex
from backend.app.models.models import Base, ProcessingJob, Record, SourceFile
from engine import ENGINE_VERSION
from engine.processor import Processor

HEADER = "Name,Community,Building/Cluster,Unit Number,Total Size Sqm.,Mobile 1\n"
ROW = "Mohammed Al Rashid,DAMAC HILLS 2,Cluster A,1204,100,+971501234567\n"


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'reprocess.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _ingest(db, tmp_path, *, job_id=1, name="register.csv"):
    path = tmp_path / name
    path.write_text(HEADER + ROW, encoding="utf-8")

    def on_batch(rows):
        for r in rows:
            db.add(Record(job_id=job_id, **r))
        db.commit()
        return len(rows)

    Processor(batch_size=100, enable_enrichment=False,
              dedup_index=DedupIndex(db, exclude_job_id=job_id)
              ).process(path, source_name=name, on_batch=on_batch)
    return path


# --- lineage ----------------------------------------------------------------

def test_every_written_record_carries_the_engine_version(db, tmp_path):
    _ingest(db, tmp_path)
    versions = {r.engine_version for r in db.scalars(select(Record))}
    assert versions == {ENGINE_VERSION}


def test_the_engine_version_is_a_positive_integer():
    # Stored and compared numerically by the reprocess planner.
    assert isinstance(ENGINE_VERSION, int) and ENGINE_VERSION >= 1


# --- detecting stale rows ---------------------------------------------------

def test_rows_written_by_an_older_engine_are_stale(db, tmp_path):
    _ingest(db, tmp_path, job_id=7)
    db.query(Record).update({Record.engine_version: ENGINE_VERSION - 1})
    db.commit()
    assert _stale_job_ids(db) == [7]


def test_rows_predating_lineage_are_stale(db, tmp_path):
    # NULL means "written before versioning existed", which is exactly the
    # data a fix most needs to reach. coalesce() in the planner covers it.
    _ingest(db, tmp_path, job_id=3)
    db.query(Record).update({Record.engine_version: None})
    db.commit()
    assert _stale_job_ids(db) == [3]


def test_current_rows_are_not_stale(db, tmp_path):
    _ingest(db, tmp_path)
    assert _stale_job_ids(db) == []


def test_stale_jobs_are_returned_oldest_first(db, tmp_path):
    for job_id in (5, 2, 9):
        _ingest(db, tmp_path, job_id=job_id, name=f"reg{job_id}.csv")
    db.query(Record).update({Record.engine_version: None})
    db.commit()
    # A partial run must make predictable progress rather than reprocessing an
    # arbitrary slice each time.
    assert _stale_job_ids(db) == [2, 5, 9]
    assert _stale_job_ids(db, limit=2) == [2, 5]


def test_a_job_is_stale_if_any_of_its_rows_are(db, tmp_path):
    _ingest(db, tmp_path, job_id=4)
    _ingest(db, tmp_path, job_id=4, name="second.csv")
    first = db.scalars(select(Record).order_by(Record.id)).first()
    first.engine_version = ENGINE_VERSION - 1
    db.commit()
    assert _stale_job_ids(db) == [4]


# --- re-deriving ------------------------------------------------------------

def test_reprocessing_replaces_rows_rather_than_adding_to_them(db, tmp_path):
    """The property that makes reprocessing safe to repeat.

    Re-running an ingest without clearing its rows first would double the
    corpus on every pass, which is why the restart path deletes before it
    rewrites.
    """
    _ingest(db, tmp_path, job_id=1)
    before = db.scalar(select(func.count(Record.id)))

    # What the restart path does: clear the job's rows, then re-derive.
    db.query(Record).filter(Record.job_id == 1).delete()
    db.commit()
    _ingest(db, tmp_path, job_id=1)

    assert db.scalar(select(func.count(Record.id))) == before


def test_re_deriving_applies_the_corrected_rules(db, tmp_path):
    """The point of the whole mechanism, end to end.

    The fixture states its size in square metres via the column header and its
    community as "DAMAC HILLS 2". A pre-fix engine stored 100 sq ft and
    "DAMAC Hills"; the current one must produce the corrected values.
    """
    _ingest(db, tmp_path)
    row = db.scalars(select(Record)).one()
    assert row.size == 1076.39            # 100 sq.m converted, not stored raw
    assert row.community == "DAMAC Hills 2"   # not collapsed into DAMAC Hills
    assert row.engine_version == ENGINE_VERSION


def test_reprocessing_leaves_nothing_stale(db, tmp_path):
    _ingest(db, tmp_path, job_id=1)
    db.query(Record).update({Record.engine_version: None})
    db.commit()
    assert _stale_job_ids(db) == [1]

    db.query(Record).filter(Record.job_id == 1).delete()
    db.commit()
    _ingest(db, tmp_path, job_id=1)
    assert _stale_job_ids(db) == []
