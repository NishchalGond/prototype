"""Central configuration. All values overridable via .env / environment."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    # --- database -------------------------------------------------------
    # PostgreSQL is the target. SQLite fallback keeps the pipeline runnable
    # before Postgres is installed locally; schema is identical (JSON column
    # maps to JSONB on PG, TEXT on SQLite).
    DATABASE_URL: str = f"sqlite:///{(ROOT / 'prototype.db').as_posix()}"
    READ_DATABASE_URL: str | None = None

    # --- processing -----------------------------------------------------
    BATCH_SIZE: int = 1000
    MAX_UPLOAD_MB: int = 512
    UPLOAD_DIR: Path = Path("/tmp/uploads")
    LOG_DIR: Path = Path("/tmp/logs")

    # Record grain: "owner"    -> one row per owner-property pair (keeps every owner)
    #               "property" -> one row per property, owners collapsed into Mobile 1..3
    # See API_CONTRACT.md / DECISIONS.md. Default preserves data.
    RECORD_GRAIN: str = "owner"

    # Enrich Developer/Community from the UAE builders reference workbook.
    ENABLE_ENRICHMENT: bool = True
    REFERENCE_WORKBOOK: Path = ROOT / "Builders data" / "UAE_Development_Builders.xlsx"

    # Duplicate detection strategy, see engine/dedup.py
    DEDUP_STRATEGY: str = "identity"

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


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
