"""outreach: leads and activity history

Revision ID: e4a71b93c5f2
Revises: c8e2f4a91d37
Create Date: 2026-08-29

The platform could find a contactable owner and had nowhere to record that
anyone called them. These two tables are the missing half.

Neither hangs off records with ON DELETE CASCADE, which is the point.
Reprocessing deletes and rewrites a job's records wholesale, and records are
derived data that can always be rebuilt from the source file. Call history
cannot: it exists nowhere else. leads.record_id is therefore ON DELETE SET
NULL, with identity_hash as the durable key that survives a reprocess, and
activities hang off the lead rather than the record.

Both tables are small -- a row exists only where someone actually worked a
lead -- so they need none of the machinery the 20M-row records table does.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e4a71b93c5f2'
down_revision: Union[str, Sequence[str], None] = 'c8e2f4a91d37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Durable identity. Survives the record renumbering a reprocess causes.
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("record_id", sa.Integer(),
                  sa.ForeignKey("records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("owner_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    # One lead per identity, so a second contact attaches to the same history.
    op.create_index("ix_leads_identity_hash", "leads", ["identity_hash"], unique=True)
    op.create_index("ix_leads_record_id", "leads", ["record_id"])
    op.create_index("ix_leads_stage", "leads", ["stage"])
    op.create_index("ix_leads_owner_user_id", "leads", ["owner_user_id"])
    op.create_index("ix_leads_next_action_at", "leads", ["next_action_at"])
    # The morning call list: my open leads, soonest first.
    op.create_index("ix_leads_queue", "leads",
                    ["owner_user_id", "stage", "next_action_at"])

    op.create_table(
        "lead_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Denormalised so history stays readable after a user is deleted.
        sa.Column("user_email", sa.String(320), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_activities_lead_id", "lead_activities", ["lead_id"])
    op.create_index("ix_lead_activities_user_id", "lead_activities", ["user_id"])
    op.create_index("ix_lead_activities_kind", "lead_activities", ["kind"])
    op.create_index("ix_lead_activities_occurred_at", "lead_activities", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("lead_activities")
    op.drop_table("leads")
