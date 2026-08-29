"""Refresh of the cached aggregates that back the dashboard.

`mv_record_facets` (filter dropdown contents) and `mv_record_stats` (the stat
tiles and field-completeness percentages) exist so ~60 concurrent users do not
each trigger a full scan of a 20M-row table on every dashboard poll. The
trade-off is staleness, so the refresh is driven by the only event that changes
the underlying numbers: a processing job finishing.

REFRESH ... CONCURRENTLY is deliberate. A plain REFRESH takes an ACCESS
EXCLUSIVE lock on the view, which blocks every dashboard read for the duration
of the rebuild. CONCURRENTLY builds the new contents alongside the old and swaps
them, so readers never block. It requires the unique indexes created in
migration 9c41ab7de205 and cannot run inside a transaction block.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from .session import IS_POSTGRES, engine

log = logging.getLogger(__name__)

MATERIALIZED_VIEWS = ("mv_record_facets", "mv_record_stats")


def refresh_dashboard_caches(*, concurrent: bool = True) -> bool:
    """Rebuild the dashboard materialised views. Returns True if all refreshed.

    Never raises. A refresh failure means the dashboard shows slightly stale
    numbers, which must not be allowed to fail the ingest that triggered it, nor
    the request that asked for it.

    Pass concurrent=False for the very first refresh after creating a view: a
    materialised view that has never been populated cannot be refreshed
    concurrently.
    """
    if not IS_POSTGRES:
        return False

    mode = "CONCURRENTLY " if concurrent else ""
    ok = True
    for view in MATERIALIZED_VIEWS:
        try:
            # autocommit: REFRESH MATERIALIZED VIEW CONCURRENTLY is rejected
            # inside a transaction block.
            with engine.connect().execution_options(
                isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {mode}{view}"))
        except Exception as exc:
            ok = False
            log.warning("Could not refresh %s: %s", view, exc)
    return ok
