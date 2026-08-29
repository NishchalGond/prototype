"""Apply migration 9c41ab7de205 to a large PostgreSQL table without downtime.

`alembic upgrade head` runs inside a transaction, which forbids
CREATE INDEX CONCURRENTLY and means every index in 9c41ab7de205 is built while
holding a lock that blocks writes. On a table small enough to rebuild in a
maintenance window that is fine and the Alembic path is simpler. Past roughly a
few million rows it is not, so this script does the same work online:

  * generated columns are added first (this step DOES take a brief ACCESS
    EXCLUSIVE lock and rewrites the table -- it is the one unavoidable pause,
    and the script reports the table size beforehand so the window can be
    estimated),
  * every index is then built CONCURRENTLY, outside any transaction, so reads
    and writes continue throughout,
  * the materialised views are created and populated,
  * finally the Alembic revision is stamped so `upgrade head` skips it.

Usage:
    python scripts/apply_search_indexes_online.py            # apply
    python scripts/apply_search_indexes_online.py --dry-run  # print the plan

A CONCURRENTLY build that fails leaves an INVALID index behind. Re-running is
safe: each statement is IF NOT EXISTS, and invalid indexes are dropped and
rebuilt.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import psycopg2

# Alembic head this script brings the database up to. Both revisions are
# applied here, and the chain is linear, so stamping the head covers both.
REVISION = "b3d7f2a15c48"

# The column expressions, facet list and legacy index names are loaded from the
# migration itself, so this script and `alembic upgrade` can never drift into
# describing different schemas.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "search_migration",
    Path(__file__).resolve().parents[1] / "alembic" / "versions"
    / "9c41ab7de205_search_acceleration.py",
)
_mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mig)

_spec2 = importlib.util.spec_from_file_location(
    "dedup_migration",
    Path(__file__).resolve().parents[1] / "alembic" / "versions"
    / "b3d7f2a15c48_cross_register_dedup_key.py",
)
_mig2 = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_mig2)


COLUMN_STEPS = [
    ("search_text", "ALTER TABLE records ADD COLUMN IF NOT EXISTS search_text text "
                    "GENERATED ALWAYS AS (%s) STORED" % _mig.SEARCH_TEXT_EXPR),
    ("mobile_digits", "ALTER TABLE records ADD COLUMN IF NOT EXISTS mobile_digits text "
                      "GENERATED ALWAYS AS (%s) STORED" % _mig.MOBILE_DIGITS_EXPR),
    ("has_valid_mobile", "ALTER TABLE records ADD COLUMN IF NOT EXISTS has_valid_mobile boolean "
                         "GENERATED ALWAYS AS (%s) STORED" % _mig.HAS_VALID_MOBILE_EXPR),
    # b3d7f2a15c48: the Tier-2 dedup blocking key.
    ("property_key", "ALTER TABLE records ADD COLUMN IF NOT EXISTS property_key text "
                     "GENERATED ALWAYS AS (%s) STORED" % _mig2.PROPERTY_KEY_EXPR),
]

INDEX_STEPS = [
    ("idx_records_search_text_trgm",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_search_text_trgm "
     "ON records USING gin (search_text gin_trgm_ops)"),
    ("idx_records_mobile_digits_trgm",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_mobile_digits_trgm "
     "ON records USING gin (mobile_digits gin_trgm_ops)"),
    ("idx_records_default_value",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_default_value "
     "ON records (procedure_value DESC NULLS LAST, id DESC) "
     "WHERE status = 'VALID' AND has_valid_mobile"),
    ("idx_records_default_id",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_default_id "
     "ON records (id DESC) WHERE status = 'VALID' AND has_valid_mobile"),
    ("idx_records_default_created",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_default_created "
     "ON records (created_at DESC, id DESC) "
     "WHERE status = 'VALID' AND has_valid_mobile"),
    ("idx_records_default_community",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_default_community "
     "ON records (community, procedure_value DESC NULLS LAST, id DESC) "
     "WHERE status = 'VALID' AND has_valid_mobile"),
    ("idx_records_default_landing",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_records_default_landing "
     "ON records (procedure_value DESC NULLS LAST, bedroom DESC NULLS LAST, "
     "            name ASC NULLS LAST, id DESC) "
     "WHERE status = 'VALID' AND has_valid_mobile"),
    # b3d7f2a15c48: probed once per ingest batch by cross-register dedup.
    ("ix_records_property_key",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_records_property_key "
     "ON records (property_key) WHERE property_key IS NOT NULL"),
    ("ix_records_mobile_1_name",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_records_mobile_1_name "
     "ON records (mobile_1) INCLUDE (name) "
     "WHERE mobile_1 IS NOT NULL AND name IS NOT NULL"),
]

DROP_LEGACY = [
    "DROP INDEX CONCURRENTLY IF EXISTS idx_records_%s_trgm" % col
    for col in _mig.LEGACY_TRGM_COLUMNS
]


def _facet_view_sql() -> str:
    union = "\nUNION ALL\n".join(
        "SELECT '{f}' AS field, {f}::text AS value, count(*) AS n "
        "FROM records WHERE {f} IS NOT NULL AND {f}::text <> '' "
        "GROUP BY {f}".format(f=f)
        for f in _mig.FACET_FIELDS
    )
    return "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_record_facets AS\n" + union


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print every statement without executing it")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "sqlite" in db_url.lower():
        print("DATABASE_URL is not PostgreSQL; nothing to do.")
        return 0

    # A dry run is for reading the plan before a maintenance window, often from
    # a machine with no route to the database. Connecting for it defeats the
    # purpose, so the connection is only opened when work will actually be done.
    conn = cur = None
    if args.dry_run:
        print("records: (dry run -- not connecting)\n")
    else:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True      # CONCURRENTLY cannot run in a transaction
        cur = conn.cursor()

        cur.execute("SELECT count(*), pg_size_pretty(pg_total_relation_size('records')) "
                    "FROM records")
        rows, size = cur.fetchone()
        print(f"records: {rows:,} rows, {size} on disk")
        print("Adding generated columns rewrites the table and briefly blocks "
              "writes. Index builds after that are online.\n")

    def run(label, sql):
        if args.dry_run:
            print(f"  [dry-run] {label}\n            {sql}")
            return
        t0 = time.monotonic()
        print(f"  {label} ... ", end="", flush=True)
        try:
            cur.execute(sql)
            print(f"done in {time.monotonic() - t0:.1f}s")
        except Exception as exc:
            print(f"FAILED: {exc}")

    print("pg_trgm extension")
    run("CREATE EXTENSION", "CREATE EXTENSION IF NOT EXISTS pg_trgm")

    print("\nGenerated columns (blocking, one table rewrite each)")
    for label, sql in COLUMN_STEPS:
        run(label, sql)

    print("\nIndexes (online)")
    for label, sql in INDEX_STEPS:
        # A previous failed CONCURRENTLY build leaves an INVALID index that
        # IF NOT EXISTS would silently keep. Drop those first.
        if not args.dry_run:
            cur.execute(
                "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE c.relname = %s AND NOT i.indisvalid", (label,))
            if cur.fetchone():
                print(f"  {label} exists but is INVALID; dropping")
                cur.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {label}")
        run(label, sql)

    print("\nDropping superseded per-column trigram indexes")
    for sql in DROP_LEGACY:
        run(sql.split()[-1], sql)

    print("\nMaterialised views")
    run("mv_record_facets", _facet_view_sql())
    run("idx_mv_record_facets_key",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_record_facets_key "
        "ON mv_record_facets (field, value)")
    run("mv_record_stats", STATS_VIEW_SQL)
    run("idx_mv_record_stats_key",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_record_stats_key "
        "ON mv_record_stats (singleton)")

    print("\nStatistics")
    run("ANALYZE records", "ANALYZE records")

    if not args.dry_run:
        print(f"\nAll done. Stamp Alembic so it skips this revision:\n"
              f"    alembic stamp {REVISION}")
    if cur is not None:
        cur.close()
    if conn is not None:
        conn.close()
    return 0


STATS_VIEW_SQL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_record_stats AS
SELECT
    1 AS singleton,
    count(*)                                     AS total_records,
    count(*) FILTER (WHERE status = 'VALID')     AS valid_records,
    count(*) FILTER (WHERE status = 'INVALID')   AS invalid_records,
    count(*) FILTER (WHERE status = 'DUPLICATE') AS duplicate_records,
    count(*) FILTER (WHERE has_valid_mobile)     AS contactable_records,
    count(name)             AS c_name,
    count(community)        AS c_community,
    count(sub_community)    AS c_sub_community,
    count(building_cluster) AS c_building_cluster,
    count(unit_number)      AS c_unit_number,
    count(size)             AS c_size,
    count(bedroom)          AS c_bedroom,
    count(mobile_1)         AS c_mobile_1,
    count(email_address)    AS c_email_address,
    count(developer)        AS c_developer,
    count(project)          AS c_project,
    count(nationality)      AS c_nationality,
    count(property_type)    AS c_property_type,
    count(record_date)      AS c_record_date,
    count(procedure_value)  AS c_procedure_value,
    count(party_type)       AS c_party_type,
    count(pi_number)        AS c_pi_number
FROM records
"""


if __name__ == "__main__":
    raise SystemExit(main())
