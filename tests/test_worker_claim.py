"""Only one runner may take a job.

run_job is reachable from three places at once: the API's background task, the
reprocess endpoint, and any number of worker processes. Without a claim, two of
them running the same job would write its rows twice and fight over its
counters. A compare-and-set on the status is the whole mechanism.
"""
import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from backend.app.models.models import Base, JobStatus, ProcessingJob, SourceFile


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'worker.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _queued_job(db):
    src = SourceFile(filename="r.csv", stored_path="/tmp/r.csv", size_bytes=1,
                     content_sha256="d" * 64)
    db.add(src)
    db.commit()
    job = ProcessingJob(source_file_id=src.id, status=JobStatus.UPLOADED)
    db.add(job)
    db.commit()
    return job.id


def _claim(db, job_id):
    """The compare-and-set from run_job()."""
    n = db.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == job_id,
               ProcessingJob.status == JobStatus.UPLOADED)
        .values(status=JobStatus.READING)
    ).rowcount
    db.commit()
    return n


def test_the_first_caller_claims_the_job(db):
    assert _claim(db, _queued_job(db)) == 1


def test_a_second_caller_gets_nothing(db):
    job_id = _queued_job(db)
    assert _claim(db, job_id) == 1
    # The API background task and a worker both firing on the same id.
    assert _claim(db, job_id) == 0


def test_a_job_already_running_cannot_be_claimed(db):
    job_id = _queued_job(db)
    db.get(ProcessingJob, job_id).status = JobStatus.PROCESSING
    db.commit()
    assert _claim(db, job_id) == 0


def test_a_finished_job_cannot_be_claimed(db):
    job_id = _queued_job(db)
    db.get(ProcessingJob, job_id).status = JobStatus.COMPLETED
    db.commit()
    assert _claim(db, job_id) == 0


def test_the_worker_takes_the_oldest_queued_job_first(db, monkeypatch):
    import worker
    ids = [_queued_job(db) for _ in range(3)]
    db.get(ProcessingJob, ids[0]).status = JobStatus.COMPLETED   # already done
    db.commit()

    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    assert worker.next_queued_job_id() == ids[1]


def test_the_worker_finds_nothing_when_the_queue_is_empty(db, monkeypatch):
    import worker
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    assert worker.next_queued_job_id() is None
