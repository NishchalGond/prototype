"""pdpl: erasure requests

Revision ID: f5c8d2e60a19
Revises: e4a71b93c5f2
Create Date: 2026-08-29

Redacting a record is not erasure on its own. Records are derived data, rebuilt
from the source file stored at upload, and that file still contains the person
-- so the next reprocess restores what was deleted. Storing the request is what
makes erasure survive the pipeline: apply_erasures() re-runs after every ingest.

Keyed by identity_hash for the same reason leads are: it is the only identifier
that outlives rows being deleted and rewritten.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f5c8d2e60a19'
down_revision: Union[str, Sequence[str], None] = 'e4a71b93c5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "erasure_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Denormalised so the register stays complete after a user is deleted.
        sa.Column("requested_by_email", sa.String(320), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_redacted", sa.Integer(), nullable=False,
                  server_default="0"),
    )
    # Unique: a second request from the same person refreshes the standing one
    # rather than creating a duplicate that could be missed on re-apply.
    op.create_index("ix_erasure_requests_identity_hash", "erasure_requests",
                    ["identity_hash"], unique=True)
    op.create_index("ix_erasure_requests_requested_by_user_id",
                    "erasure_requests", ["requested_by_user_id"])


def downgrade() -> None:
    # Dropping this loses the record of who asked to be erased, while the
    # redaction it caused stays applied. Export the table before running it.
    op.drop_table("erasure_requests")
