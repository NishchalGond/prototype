"""Ingest worker. Runs jobs outside the web process.

    python worker.py

Ingest ran inside uvicorn via BackgroundTasks, which cost three things at
scale: a 20M-row job competed for CPU with every dashboard poll, a deploy
killed jobs mid-flight, and ingest could not be scaled without scaling the API
with it.

There is no Redis and no Celery here because the jobs table already is a
queue -- it has the states, the control signals, the heartbeat and the reaper.
Adding a broker would mean a second source of truth for the same thing.

Claiming is a compare-and-set inside run_job(), so this is safe to run at any
count, alongside the API's own background tasks, without coordination: only
one caller's UPDATE matches a row still in UPLOADED. Scale by starting more
processes.

    web:    python run.py
    worker: python worker.py
"""
from __future__ import annotations

import logging
import os
import signal
import time

from sqlalchemy import select

from backend.app.api.jobs import reap_stale_jobs, run_job
from backend.app.database.session import SessionLocal
from backend.app.models.models import JobStatus, ProcessingJob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("worker")

# Idle poll interval. A queued job waits at most this long to start, and an
# idle worker costs one indexed SELECT per tick. After running something the
# loop polls again immediately, so a backlog drains at full speed.
POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "2"))

_stop = False


def _handle_stop(signum, _frame):
    """Stop after the current job rather than mid-write.

    A job killed mid-batch leaves rows written and its counters stale, which
    the reaper then has to clean up. Finishing the one in flight is worth the
    few seconds it delays a redeploy.
    """
    global _stop
    _stop = True
    log.info("signal %s received; finishing the current job then exiting", signum)


def next_queued_job_id() -> int | None:
    db = SessionLocal()
    try:
        return db.scalar(
            select(ProcessingJob.id)
            .where(ProcessingJob.status == JobStatus.UPLOADED)
            .order_by(ProcessingJob.id)      # oldest first
            .limit(1)
        )
    finally:
        db.close()


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    # Same call the API makes at startup: close out jobs whose worker died, so
    # a restart does not leave rows stuck ACTIVE forever.
    reaped = reap_stale_jobs()
    if reaped:
        log.warning("reaped %d stale job(s) on startup", reaped)

    log.info("worker ready; polling every %.1fs", POLL_SECONDS)
    while not _stop:
        job_id = next_queued_job_id()
        if job_id is None:
            time.sleep(POLL_SECONDS)
            continue
        log.info("running job %d", job_id)
        try:
            # Returns immediately if another process claimed it first.
            run_job(job_id)
        except Exception:
            # run_job already records failure on the job row; a crash here must
            # not take the worker down and stall every job behind it.
            log.exception("job %d raised", job_id)

    log.info("worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
