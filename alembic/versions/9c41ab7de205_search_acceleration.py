"""search acceleration: generated columns, covering indexes, cached aggregates

Revision ID: 9c41ab7de205
Revises: 7ba9686c4678
Create Date: 2026-08-29

Targets a 20M-row `records` table served to ~60 concurrent sales users. Three
things were O(table) on every dashboard interaction and are addressed here:

  1. Free-text search ran ILIKE '%q%' across 13 columns. Only six had trigram
     indexes, and one unindexable branch inside an OR forces a sequential scan
     of the whole table, so the existing indexes never fired. Replaced by one
     generated `search_text` blob with a single GIN trigram index.

  2. The default view's "verified valid mobile" rule ran three regex matches
     against every row, every page load. Now a stored boolean computed once at
     write time, and indexable.

  3. filter_options did SELECT DISTINCT per dropdown and dashboard_stats did
     full-table COUNT and GROUP BY on every poll. Both now read from
     materialised views refreshed on a schedule.

OPERATIONAL NOTE -- read before running against a large production table.
Adding a STORED generated column rewrites the table and holds an ACCESS
EXCLUSIVE lock for the duration (minutes at 20M rows). The index builds below
are also blocking, because Alembic runs migrations inside a transaction and
CREATE INDEX CONCURRENTLY cannot run there. On a table small enough to rewrite
inside a maintenance window, run this as-is. Past that, run
scripts/apply_search_indexes_online.py, which performs the same work with
CONCURRENTLY outside a transaction and then stamps this revision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9c41ab7de205'
down_revision: Union[str, Sequence[str], None] = '7ba9686c4678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEARCH_FIELDS = (
    "name", "community", "sub_community", "building_cluster", "unit_number",
    "mobile_1", "mobile_2", "mobile_3", "email_address", "plot_number",
    "pi_number", "project", "developer", "property_type", "nationality",
)
SEARCH_TEXT_EXPR = "lower(" + " || ' ' || ".join(
    "coalesce(%s, '')" % f for f in SEARCH_FIELDS) + ")"

MOBILE_BLOB = " || ' ' || ".join(
    "coalesce(%s, '')" % f for f in ("mobile_1", "mobile_2", "mobile_3"))
MOBILE_DIGITS_EXPR = "regexp_replace(%s, '[^0-9]', '', 'g')" % MOBILE_BLOB

HAS_VALID_MOBILE_EXPR = (
    "(mobile_1 IS NOT NULL AND mobile_1 <> '' "
    "AND lower(mobile_1) <> 'n/a' AND ("
    r"mobile_1 ~ '^\+9715[024568][0-9]{7}$' OR "
    r"mobile_1 ~ '^\+971[234679][0-9]{7}$' OR "
    r"mobile_1 ~ '^\+[1-9][0-9]{9,14}$'))"
)

# The dropdowns. Each is a distinct-values query that would otherwise scan the
# table on every dashboard load.
FACET_FIELDS = ("community", "sub_community", "property_type", "bedroom",
                "developer", "source_file", "status", "nationality")

# Superseded by idx_records_search_text_trgm. Each cost write throughput on
# ingest and ~100MB+ of disk at 20M rows, while never being reachable by the
# OR-of-ILIKE query shape they were built for.
LEGACY_TRGM_COLUMNS = ("name", "community", "building_cluster", "developer",
                       "project", "mobile_1")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite dev databases are rebuilt from the models by init_db(), which
        # already carries the simplified generated-column expressions. Nothing
        # here (trigram indexes, materialised views, partial indexes with NULLS
        # LAST) has a SQLite equivalent worth emulating.
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ---- generated columns ------------------------------------------------
    op.execute(
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS search_text text "
        "GENERATED ALWAYS AS (%s) STORED" % SEARCH_TEXT_EXPR)
    op.execute(
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS mobile_digits text "
        "GENERATED ALWAYS AS (%s) STORED" % MOBILE_DIGITS_EXPR)
    op.execute(
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS has_valid_mobile boolean "
        "GENERATED ALWAYS AS (%s) STORED" % HAS_VALID_MOBILE_EXPR)

    # ---- the one index free-text search actually uses ----------------------
    # gin_trgm_ops answers search_text LIKE '%token%' for any token of three or
    # more characters. A multi-token query becomes a BitmapAnd of several probes
    # into this single index rather than 13 separate column scans.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_search_text_trgm "
        "ON records USING gin (search_text gin_trgm_ops)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_mobile_digits_trgm "
        "ON records USING gin (mobile_digits gin_trgm_ops)")

    for col in LEGACY_TRGM_COLUMNS:
        op.execute("DROP INDEX IF EXISTS idx_records_%s_trgm" % col)

    # ---- the default view --------------------------------------------------
    # Partial indexes covering exactly the rows the default dashboard shows.
    # Because the predicate matches the default filter, these hold a fraction of
    # the table and the planner can walk them already in sort order, turning
    # "filter 20M rows then sort" into "read the first 50 index entries".
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_default_value "
        "ON records (procedure_value DESC NULLS LAST, id DESC) "
        "WHERE status = 'VALID' AND has_valid_mobile")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_default_id "
        "ON records (id DESC) "
        "WHERE status = 'VALID' AND has_valid_mobile")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_default_created "
        "ON records (created_at DESC, id DESC) "
        "WHERE status = 'VALID' AND has_valid_mobile")
    # Filtering the default view to one community is the most common sales
    # query, so it gets the community prefix rather than a separate lookup.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_default_community "
        "ON records (community, procedure_value DESC NULLS LAST, id DESC) "
        "WHERE status = 'VALID' AND has_valid_mobile")
    # The landing page's exact sort. list_records special-cases sort_by=name +
    # asc into a four-key ordering (value, bedroom, name, id) so high-value rows
    # with a visible bedroom surface first. Any index missing one of those keys
    # leaves PostgreSQL sorting the whole filtered set, so this one matches the
    # ORDER BY term for term -- it is the single most frequently executed query
    # in the system and deserves its own index.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_default_landing "
        "ON records (procedure_value DESC NULLS LAST, bedroom DESC NULLS LAST, "
        "            name ASC NULLS LAST, id DESC) "
        "WHERE status = 'VALID' AND has_valid_mobile")

    # ---- cached facets -----------------------------------------------------
    # Dropdown contents change only when a file is ingested, so they need not be
    # recomputed per request. Counts come along for free and let the UI show
    # "Dubai Marina (12,481)".
    facet_union = "\nUNION ALL\n".join(
        "SELECT '{f}' AS field, {f}::text AS value, count(*) AS n "
        "FROM records WHERE {f} IS NOT NULL AND {f}::text <> '' "
        "GROUP BY {f}".format(f=f)
        for f in FACET_FIELDS
    )
    op.execute("CREATE MATERIALIZED VIEW IF NOT EXISTS mv_record_facets AS\n" + facet_union)
    # REFRESH CONCURRENTLY requires a unique index; without one every refresh
    # takes an exclusive lock and stalls the dashboard.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_record_facets_key "
        "ON mv_record_facets (field, value)")

    # ---- cached dashboard aggregates --------------------------------------
    op.execute("""
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
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_record_stats_key "
        "ON mv_record_stats (singleton)")

    # Fresh statistics on the new columns; without this the planner has no
    # selectivity estimate for has_valid_mobile and may ignore the partial
    # indexes it was just given.
    op.execute("ANALYZE records")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_record_stats")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_record_facets")
    for idx in ("idx_records_default_value", "idx_records_default_id",
                "idx_records_default_created", "idx_records_default_community",
                "idx_records_default_landing",
                "idx_records_search_text_trgm", "idx_records_mobile_digits_trgm"):
        op.execute("DROP INDEX IF EXISTS %s" % idx)
    for col in ("search_text", "mobile_digits", "has_valid_mobile"):
        op.execute("ALTER TABLE records DROP COLUMN IF EXISTS %s" % col)

    for col in LEGACY_TRGM_COLUMNS:
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_%s_trgm "
            "ON records USING gin (%s gin_trgm_ops)" % (col, col))
