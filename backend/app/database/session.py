import threading
from collections.abc import Iterator
from contextlib import nullcontext

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from ..config import settings
from ..models.models import Base

def _clean_url(u: str) -> str:
    raw = "".join(str(u or "").split()).strip("'\"")
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[11:]
    return raw

db_url = _clean_url(settings.DATABASE_URL)
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

read_db_url = _clean_url(settings.READ_DATABASE_URL or settings.DATABASE_URL)
_is_read_sqlite = read_db_url.startswith("sqlite")

read_engine = create_engine(
    read_db_url,
    echo=False,
    future=True,
    poolclass=NullPool if _is_read_sqlite else None,
    pool_pre_ping=not _is_read_sqlite,
    **({} if _is_read_sqlite else {"pool_size": 25, "max_overflow": 50, "pool_timeout": 30}),
    connect_args={"check_same_thread": False, "timeout": 60}
    if _is_read_sqlite else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
ReadSessionLocal = sessionmaker(bind=read_engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db() -> Iterator[Session]:
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()
