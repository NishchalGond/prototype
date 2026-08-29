"""record lineage: engine_version

Revision ID: c8e2f4a91d37
Revises: b3d7f2a15c48
Create Date: 2026-08-29

Records carried no indication of which pipeline rules produced them, so a
corrected cleaning rule could not reach the data it had already got wrong. Every
fix stranded the existing table and the only remedy was re-uploading files by
hand.

engine_version is stamped on each row at write time. A rule change bumps
engine.ENGINE_VERSION, and every row below it is then identifiable as stale and
re-derivable from its stored source file.

Existing rows are left NULL rather than back-stamped. They were produced by the
pre-fix engine and NULL says exactly that; writing the current version onto them
would claim they had been reprocessed when they had not, and would hide from
the reprocess planner the very rows that most need it.

Unlike the two migrations before it, this one adds a plain nullable column with
no default, which PostgreSQL records as a catalogue-only change: no table
rewrite, no lock held for the length of the table. It is safe to run online.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c8e2f4a91d37'
down_revision: Union[str, Sequence[str], None] = 'b3d7f2a15c48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("records", sa.Column("engine_version", sa.Integer(),
                                       nullable=True))
    # The reprocess planner's only question is "which rows are not at the
    # current version", asked over the whole table. Partial: rows already at
    # the current version are the overwhelming majority in a healthy database
    # and are never the ones being looked for.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_records_engine_version "
            "ON records (engine_version)")
    else:
        op.create_index("ix_records_engine_version", "records",
                        ["engine_version"])


def downgrade() -> None:
    op.drop_index("ix_records_engine_version", table_name="records")
    op.drop_column("records", "engine_version")
