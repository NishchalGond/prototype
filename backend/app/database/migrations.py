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

# Revision that corresponds to the schema the ORIGINAL create_all produced.
BASELINE_REVISION = "8fd7756ae068"

# `create_all` builds whatever the models currently describe, which is head --
# not the baseline. So a database it just created is NOT a legacy database, and
# stamping it at the baseline makes Alembic replay migrations whose columns are
# already there ("duplicate column name: control_signal").
#
# Each entry is (revision, table, column). column=None means "this table
# existing is enough". Ordered oldest to newest; adoption stamps the newest
# revision whose marker is present, which is the only revision consistent with
# what is actually in the database.
SCHEMA_MARKERS = [
    ("8fd7756ae068", "records", None),
    ("7e5c3be6d419", "processing_jobs", "control_signal"),
    ("9c41ab7de205", "records", "search_text"),
    ("b3d7f2a15c48", "records", "property_key"),
    ("c8e2f4a91d37", "records", "engine_version"),
    ("e4a71b93c5f2", "leads", None),
    ("f5c8d2e60a19", "erasure_requests", None),
    ("a7b4e9f1c260", "leads", "contact_verdict"),
    ("d9f3c07b8e41", "privileged_action_audit", None),
]


def _detect_revision(inspector, tables: set[str]) -> str | None:
    """Newest revision whose schema marker is already present, or None."""
    found = None
    for revision, table, column in SCHEMA_MARKERS:
        if table not in tables:
            continue
        if column is not None:
            cols = {c["name"] for c in inspector.get_columns(table)}
            if column not in cols:
                continue
        found = revision
    return found


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    # env.py reads the URL from settings; set here too so offline use matches.
    cfg.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL).replace("%", "%%"))
    return cfg


def current_revision() -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def stamp_head() -> None:
    """Record that the database already matches the newest revision.

    For a schema create_all just built from the current models: the tables are
    at head, and only the version row is missing.
    """
    command.stamp(_alembic_config(), "head")
    log.info("schema stamped at head")


def upgrade_to_head() -> None:
    """Bring the database up to the latest revision. Safe to call repeatedly."""
    cfg = _alembic_config()

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    versioned = current_revision() is not None

    if not versioned and {"records", "processing_jobs"} <= tables:
        # Tables but no version row. Two very different situations look
        # identical here: a legacy deployment from the create_all era, and a
        # database create_all built moments ago from the current models. The
        # markers tell them apart; assuming the former replays migrations over
        # columns that already exist and fails.
        detected = _detect_revision(inspector, tables) or BASELINE_REVISION
        log.warning(
            "Database has tables but no Alembic version. Schema matches %s; "
            "stamping that and applying anything newer.", detected,
        )
        command.stamp(cfg, detected)

    command.upgrade(cfg, "head")
    log.info("migrations applied; schema at revision %s", current_revision())
