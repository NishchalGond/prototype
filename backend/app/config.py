"""Central configuration. All values overridable via .env / environment."""
import logging
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

log = logging.getLogger("config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    # --- environment ----------------------------------------------------
    # "production" tightens the startup checks below: a real SECRET_KEY and a
    # non-SQLite DATABASE_URL both become mandatory instead of best-effort.
    APP_ENV: str = "development"

    # --- security -------------------------------------------------------
    # No default on purpose. A checked-in fallback here is indistinguishable
    # from having no authentication at all, because anyone holding the repo can
    # sign their own admin token. _finalise() below supplies a random per-boot
    # key in development and refuses to start without one in production.
    SECRET_KEY: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # Bootstrap administrator, seeded on first boot only (see main.lifespan).
    ADMIN_EMAIL: str = "admin@datalink.ae"
    ADMIN_PASSWORD: str | None = None

    # --- database -------------------------------------------------------
    # PostgreSQL is the target. SQLite fallback keeps the pipeline runnable
    # before Postgres is installed locally; schema is identical (JSON column
    # maps to JSONB on PG, TEXT on SQLite).
    DATABASE_URL: str = f"sqlite:///{(ROOT / 'prototype.db').as_posix()}"
    READ_DATABASE_URL: str | None = None

    # --- processing -----------------------------------------------------
    BATCH_SIZE: int = 1000
    MAX_UPLOAD_MB: int = 512

    # Uploaded workbooks are re-read whenever a job is restarted, so this must
    # outlive the container. On Railway, mount a volume and point UPLOAD_DIR at
    # it (e.g. /data/uploads); /tmp is wiped on every deploy, which leaves
    # SourceFile.stored_path referring to files that no longer exist.
    UPLOAD_DIR: Path = ROOT / "uploads"
    LOG_DIR: Path = ROOT / "logs"

    # A job whose worker died (redeploy, OOM, crash) leaves a row stuck in a
    # running state with nothing left to advance it. Anything that has not been
    # touched in this many minutes is reaped at startup. See api.jobs.reap.
    JOB_STALE_MINUTES: int = 30

    # Record grain: "owner"    -> one row per owner-property pair (keeps every owner)
    #               "property" -> one row per property, owners collapsed into Mobile 1..3
    # See API_CONTRACT.md / DECISIONS.md. Default preserves data.
    RECORD_GRAIN: str = "owner"

    # Enrich Developer/Community from the UAE builders reference workbook.
    ENABLE_ENRICHMENT: bool = True
    REFERENCE_WORKBOOK: Path = ROOT / "Builders data" / "UAE_Development_Builders.xlsx"

    # Property-attribute dataset used to fill Property Type (and Bedroom/Size
    # at unit precision) for rows whose register never carried one. Any CSV or
    # Excel export with community / building / property_type columns works --
    # see engine/property_reference.py for the recognised column spellings.
    # Absent file = enrichment simply fills less; nothing fails.
    # Points at the Property Finder scrape (90,807 Dubai listings). A directory
    # is read whole and de-duplicated on listing id, so the overlapping partial
    # dumps in it cost nothing. Note the folder name is spelled "propertyfiinder"
    # on disk; kept as-is so the default works without a rename.
    PROPERTY_REFERENCE: Path = ROOT / "propertyfiinder"

    # Duplicate detection strategy, see engine/dedup.py
    DEDUP_STRATEGY: str = "identity"

    # Match incoming rows against every register already ingested, not just the
    # file being processed. Off restores the old single-file behaviour, which is
    # occasionally what you want when back-filling a register you intend to
    # reconcile by hand.
    CROSS_REGISTER_DEDUP: bool = True

    # --- api ------------------------------------------------------------
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://prototype-azure-theta.vercel.app",
        "https://prototype-b0ejqriyk-lpj1.vercel.app",
    ]
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # --- connection pooling ----------------------------------------------
    # Every pooled connection is a backend process on the database server, and
    # these ceilings are per application process: N uvicorn workers multiply
    # them. The previous 20+40 write and 25+50 read defaults allowed 135
    # connections from a single worker, which exceeds PostgreSQL's default
    # max_connections of 100 on its own -- the failure mode at ~60 users was
    # the database refusing connections, not slow queries.
    #
    # These defaults suit one worker against a small managed instance. Raising
    # worker count means lowering these, or putting PgBouncer / RDS Proxy in
    # front and pointing the app at that instead.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_READ_POOL_SIZE: int = 10
    DB_READ_MAX_OVERFLOW: int = 20

    # --- derived ---------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in ("production", "prod")


def _finalise(s: Settings) -> Settings:
    """Validate the settings that must not be wrong in production."""
    if s.is_production:
        # 32 bytes is the RFC 7518 floor for HS256; PyJWT warns below it.
        if not s.SECRET_KEY or len(s.SECRET_KEY.strip()) < 32:
            raise RuntimeError(
                "SECRET_KEY is required when APP_ENV=production and must be at "
                "least 32 characters (RFC 7518 minimum for HS256). Generate one "
                "with `python -c \"import secrets; print(secrets.token_urlsafe(48))\"` "
                "and set it in the environment."
            )
        if s.DATABASE_URL.strip().startswith("sqlite"):
            raise RuntimeError(
                "DATABASE_URL points at SQLite while APP_ENV=production. On a "
                "container host that file is ephemeral and every row is lost on "
                "the next deploy. Set a PostgreSQL URL."
            )
        if str(s.UPLOAD_DIR).startswith("/tmp"):
            # Not fatal: the app still serves, and a fresh upload still works.
            # But restarting an older job will fail to find its file.
            log.warning(
                "UPLOAD_DIR is %s, which most container hosts wipe on deploy. "
                "Mount a volume and point UPLOAD_DIR at it to keep uploaded "
                "workbooks available for reprocessing.", s.UPLOAD_DIR,
            )
    elif not s.SECRET_KEY:
        # Dev convenience: the app still runs with no configuration, but the key
        # is random per boot, so tokens simply expire on restart rather than
        # being forgeable by anyone who has read the source.
        s.SECRET_KEY = secrets.token_urlsafe(48)
        log.warning(
            "SECRET_KEY not set; generated an ephemeral development key. "
            "Existing tokens stop working on restart. Set SECRET_KEY to persist them."
        )
    return s


settings = _finalise(Settings())
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
