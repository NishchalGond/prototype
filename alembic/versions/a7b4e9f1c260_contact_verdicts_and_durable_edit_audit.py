"""feedback loop: contact verdicts, and an edit audit that survives reprocessing

Revision ID: a7b4e9f1c260
Revises: f5c8d2e60a19
Create Date: 2026-08-29

Two changes, both about a human's verdict outranking the pipeline's.

1. Lead gains contact_verdict. A salesperson who dials and hears "wrong number"
   has produced the best available evidence about that number -- better than any
   regex, better than has_valid_mobile, better than a portal. It used to land in
   a free-text outcome field and die there. Stored on the lead, it is keyed by
   identity_hash and so survives the reprocessing that rewrites records, which
   is what stops the engine resurrecting a number a human already disproved.

2. record_edits_audit.record_id becomes ON DELETE SET NULL, with identity_hash
   alongside it. It was CASCADE, so reprocessing a job deleted every manual
   correction made to its rows AND the record of who made them. A hand-
   correction is no more derivable from a source file than a phone call is.

Existing audit rows get a NULL identity_hash: nothing can reconstruct which
identity they belonged to after the fact, and inventing one would be worse than
saying so. They stay attached to their current record and simply cannot be
relinked if it is ever reprocessed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7b4e9f1c260'
down_revision: Union[str, Sequence[str], None] = 'f5c8d2e60a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("contact_verdict", sa.String(24), nullable=True))
    op.add_column("leads", sa.Column("contact_verdict_at",
                                     sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_contact_verdict", "leads", ["contact_verdict"])

    op.add_column("record_edits_audit",
                  sa.Column("identity_hash", sa.String(64), nullable=True))
    op.create_index("ix_record_edits_audit_identity_hash", "record_edits_audit",
                    ["identity_hash"])

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite cannot ALTER a foreign key, and dev databases are rebuilt from
        # the models by init_db(), which already carries SET NULL.
        return

    # Backfill from the records still present, so existing corrections can be
    # relinked after a future reprocess. Rows whose record is already gone stay
    # NULL -- there is nothing left to derive the identity from.
    op.execute("""
        UPDATE record_edits_audit a
           SET identity_hash = r.identity_hash
          FROM records r
         WHERE r.id = a.record_id AND a.identity_hash IS NULL
    """)

    # CASCADE -> SET NULL. The column has to become nullable to hold it.
    op.execute("ALTER TABLE record_edits_audit ALTER COLUMN record_id DROP NOT NULL")
    op.execute("""
        ALTER TABLE record_edits_audit
        DROP CONSTRAINT IF EXISTS record_edits_audit_record_id_fkey
    """)
    op.create_foreign_key("record_edits_audit_record_id_fkey", "record_edits_audit",
                          "records", ["record_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Rows detached by a reprocess cannot go back into a NOT NULL CASCADE
        # column, so they are dropped. This is lossy by nature.
        op.execute("DELETE FROM record_edits_audit WHERE record_id IS NULL")
        op.execute("""
            ALTER TABLE record_edits_audit
            DROP CONSTRAINT IF EXISTS record_edits_audit_record_id_fkey
        """)
        op.create_foreign_key("record_edits_audit_record_id_fkey",
                              "record_edits_audit", "records", ["record_id"],
                              ["id"], ondelete="CASCADE")
        op.execute("ALTER TABLE record_edits_audit ALTER COLUMN record_id SET NOT NULL")

    op.drop_index("ix_record_edits_audit_identity_hash", table_name="record_edits_audit")
    op.drop_column("record_edits_audit", "identity_hash")
    op.drop_index("ix_leads_contact_verdict", table_name="leads")
    op.drop_column("leads", "contact_verdict_at")
    op.drop_column("leads", "contact_verdict")
