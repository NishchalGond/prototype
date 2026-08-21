"""FastAPI application entrypoint.

Run:  uvicorn backend.app.main:app --reload --port 8000   (from the project root)
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
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
    
    # Auto-seed default admin if database has no admin
    db = SessionLocal()
    try:
        from sqlalchemy import select
        has_admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
        if not has_admin:
            admin = User(
                email="admin@datalink.ae",
                hashed_password=hash_password("admin321"),
                full_name="Lead Data Administrator",
                role=UserRole.ADMIN,
                is_active=True,
                can_export=True,
            )
            db.add(admin)
            db.commit()
            log.info("Initialized default administrator account (admin@datalink.ae / admin321)")
    except Exception as e:
        log.warning("Could not auto-seed admin: %s", e)
    finally:
        db.close()

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
    return {"status": "ok", "version": app.version}


app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["auth"])
app.include_router(jobs.router, prefix=settings.API_PREFIX, tags=["jobs"])
app.include_router(records.router, prefix=settings.API_PREFIX, tags=["records"])
