import threading
from collections.abc import Iterator
from contextlib import nullcontext

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from ..config import settings
from ..models.models import Base

db_url = str(settings.DATABASE_URL or "").strip().strip("'").strip('"')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

_is_sqlite = db_url.startswith("sqlite")

# Background jobs each hold a session open for the job's full duration (can be
# a minute+ on large files), and the dashboard polls /api/jobs/{id} on top of
# that. With SQLite's file-backed connections, pooling buys nothing and a
# fixed-size pool (default 5 + 10 overflow) exhausts under a handful of
# concurrent jobs -- observed directly as "QueuePool limit ... connection
# timed out" once 13 jobs ran alongside status polling. NullPool opens a
# fresh connection per checkout instead, which is cheap for a local file and
# has no ceiling to hit. PostgreSQL connections are not free, so it keeps a
# real pool, sized for the same concurrency this app actually produces.
engine = create_engine(
    db_url,
    echo=False,
    future=True,
    poolclass=NullPool if _is_sqlite else None,
    pool_pre_ping=not _is_sqlite,
    **({} if _is_sqlite else {"pool_size": 20, "max_overflow": 40, "pool_timeout": 30}),
    connect_args={"check_same_thread": False, "timeout": 60}
    if _is_sqlite else {},
)

# SQLite allows exactly one writer. Jobs run concurrently in background tasks,
# so batch inserts are serialised here. On PostgreSQL this is a no-op guard.
WRITE_LOCK = threading.Lock() if _is_sqlite else nullcontext()

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        # concurrent jobs write in parallel; without this SQLite raises
        # "database is locked" instead of waiting for the writer to finish
        cur.execute("PRAGMA busy_timeout=60000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
