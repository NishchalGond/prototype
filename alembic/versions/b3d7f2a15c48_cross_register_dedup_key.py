"""cross-register dedup: property_key generated column

Revision ID: b3d7f2a15c48
Revises: 9c41ab7de205
Create Date: 2026-08-29

Tier-2 (fuzzy) deduplication blocks on community|building|unit. Until now that
key was computed in Python and compared only against rows from the same file,
so the same owner arriving in two builder registers was stored twice, both
VALID -- the exact duplicate this platform exists to collapse.

Matching across the whole corpus means looking the key up in the database for
each incoming batch, which needs it stored and indexed rather than derived at
query time. The expression mirrors engine/dedup.py:extract_property_key().

Rows written before this migration get the value automatically: a STORED
generated column is computed for every existing row during the ALTER.

OPERATIONAL NOTE -- same caveat as 9c41ab7de205. Adding a STORED generated
column rewrites the table under an ACCESS EXCLUSIVE lock. Past a few million
rows, run this outside a maintenance window via
scripts/apply_search_indexes_online.py, which builds indexes CONCURRENTLY.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b3d7f2a15c48'
down_revision: Union[str, Sequence[str], None] = '9c41ab7de205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kept verbatim in sync with backend/app/models/models.py:PROPERTY_KEY_EXPR.
_UNIT = "coalesce(nullif(trim(unit_number), ''), nullif(trim(plot_number), ''))"
PROPERTY_KEY_EXPR = (
    "CASE WHEN trim(coalesce(community, '')) <> '' "
    f"AND {_UNIT} IS NOT NULL "
    "THEN upper(trim(community)) || '|' || "
    "upper(trim(coalesce(building_cluster, ''))) || '|' || "
    f"upper({_UNIT}) END"
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite dev databases are rebuilt from the models by init_db(), which
        # carries the same expression.
        return

    op.execute(
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS property_key text "
        "GENERATED ALWAYS AS (%s) STORED" % PROPERTY_KEY_EXPR)

    # Partial: rows with no locatable property never participate in Tier-2
    # matching, and excluding them keeps the index proportional to the rows
    # that do.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_records_property_key "
        "ON records (property_key) WHERE property_key IS NOT NULL")

    # Tier-2 also probes by phone, and the existing mobile_1 index covers the
    # lookup but not the name it needs alongside it.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_records_mobile_1_name "
        "ON records (mobile_1) INCLUDE (name) "
        "WHERE mobile_1 IS NOT NULL AND name IS NOT NULL")

    op.execute("ANALYZE records")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_records_mobile_1_name")
    op.execute("DROP INDEX IF EXISTS ix_records_property_key")
    op.execute("ALTER TABLE records DROP COLUMN IF EXISTS property_key")
