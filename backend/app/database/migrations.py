"""Run Alembic migrations at startup, including first-time adoption.

The database that is already deployed was created by `Base.metadata.create_all`,
so it has all the tables but no `alembic_version` row. Running `upgrade head`
against it directly would try to re-create existing tables and fail.

This module handles that case: if the schema is clearly already present but
unversioned, it stamps the baseline revision first (recording "this database is
already at the baseline" without executing it), then applies anything newer.
A genuinely empty database just runs every migration from scratch.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from ..config import settings
from .session import engine

log = logging.getLogger("migrations")

ROOT = Path(__file__).resolve().parents[3]

# Revision that corresponds to the schema create_all produced.
BASELINE_REVISION = "8fd7756ae068"


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    # env.py reads the URL from settings; set here too so offline use matches.
    cfg.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL).replace("%", "%%"))
    return cfg


def current_revision() -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def upgrade_to_head() -> None:
    """Bring the database up to the latest revision. Safe to call repeatedly."""
    cfg = _alembic_config()

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    versioned = current_revision() is not None

    if not versioned and {"records", "processing_jobs"} <= tables:
        # Pre-existing database from the create_all era: adopt it at the
        # baseline rather than replaying table creation over live data.
        log.warning(
            "Database has tables but no Alembic version. Stamping baseline %s "
            "and applying newer migrations.", BASELINE_REVISION,
        )
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")
    log.info("migrations applied; schema at revision %s", current_revision())
