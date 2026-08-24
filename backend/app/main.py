"""FastAPI application entrypoint.

Run:  uvicorn backend.app.main:app --reload --port 8000   (from the project root)
"""
from __future__ import annotations

import logging
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))          # make `engine` importable

from backend.app.api import auth, jobs, records              # noqa: E402
from backend.app.config import settings                       # noqa: E402
from backend.app.database.session import SessionLocal, init_db  # noqa: E402
from backend.app.models.models import User, UserRole          # noqa: E402
from backend.app.core.security import hash_password           # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(settings.LOG_DIR / "backend.log", encoding="utf8")],
)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    
    # Bootstrap an administrator only when the database has none. The password
    # is never a literal in the source: a shipped default is a published
    # credential the moment the repo is readable.
    db = SessionLocal()
    try:
        from sqlalchemy import select
        has_admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
        if has_admin:
            pass
        elif settings.ADMIN_PASSWORD:
            db.add(User(
                email=settings.ADMIN_EMAIL.lower().strip(),
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                full_name="Lead Data Administrator",
                role=UserRole.ADMIN,
                is_active=True,
                can_export=True,
            ))
            db.commit()
            log.info("Bootstrapped administrator %s from ADMIN_PASSWORD.",
                     settings.ADMIN_EMAIL)
        elif not settings.is_production:
            # Dev only: keep the app usable with zero configuration, but with a
            # password that is unique per machine and printed once, not guessable.
            generated = secrets.token_urlsafe(16)
            db.add(User(
                email=settings.ADMIN_EMAIL.lower().strip(),
                hashed_password=hash_password(generated),
                full_name="Lead Data Administrator",
                role=UserRole.ADMIN,
                is_active=True,
                can_export=True,
            ))
            db.commit()
            log.warning(
                "No admin found and ADMIN_PASSWORD is unset. Created a development "
                "administrator:\n    email:    %s\n    password: %s\n"
                "This is shown once. Set ADMIN_PASSWORD to choose your own.",
                settings.ADMIN_EMAIL, generated,
            )
        else:
            log.error(
                "No administrator exists and ADMIN_PASSWORD is not set, so none was "
                "created. Set ADMIN_PASSWORD and redeploy, or run "
                "`python scripts/create_admin.py` against this database."
            )
    except Exception as e:
        log.warning("Could not bootstrap admin: %s", e)
    finally:
        db.close()

    # Close out jobs whose worker died with the previous process, so the
    # dashboard never polls a job that nothing is advancing any more.
    try:
        reaped = jobs.reap_stale_jobs()
        if reaped:
            log.warning("marked %d abandoned job(s) as FAILED at startup", reaped)
    except Exception as e:
        log.warning("Could not reap stale jobs: %s", e)

    log.info("database ready: %s", settings.DATABASE_URL.split("://")[0])
    log.info("batch size=%s grain=%s enrichment=%s",
             settings.BATCH_SIZE, settings.RECORD_GRAIN, settings.ENABLE_ENRICHMENT)
    yield


app = FastAPI(
    title="Prototype Data Processing API",
    version="1.0.0",
    description=(
        "Backend for the Excel/CSV ingestion prototype: upload, batch processing, "
        "cleaning, validation, deduplication and search over the 23 standard fields."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "code": "INTERNAL_ERROR"},
    )


@app.get("/health", tags=["meta"])
def health():
    """Liveness + database reachability.

    A health check that only proves the process is running will report OK while
    every request underneath it fails, which lets a platform keep routing
    traffic to an instance that cannot serve anything. Returns 503 when the
    database is unreachable so restarts and alerts actually fire.
    """
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:
        log.warning("health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "version": app.version,
                     "database": "unreachable"},
        )
    return {"status": "ok", "version": app.version, "database": "ok"}


app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["auth"])
app.include_router(jobs.router, prefix=settings.API_PREFIX, tags=["jobs"])
app.include_router(records.router, prefix=settings.API_PREFIX, tags=["records"])
