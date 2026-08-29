"""roles: hierarchy, forced password change, privileged action audit

Revision ID: d9f3c07b8e41
Revises: a7b4e9f1c260
Create Date: 2026-08-29

Adds DEVELOPER, CEO and CCO above ADMIN, and the two things that make a
hierarchy real rather than decorative.

must_change_password: an account is created with a starting password, not the
person's password. It is enforced in get_current_user, so the API refuses
everything except /auth/me and /auth/password until the owner replaces it.
Nobody can read a password either way -- only bcrypt hashes are stored -- so a
reset issues a one-time password rather than revealing anything.

privileged_action_audit: who created, reset, promoted or deactivated whom. The
DEVELOPER role is hidden from every listing, which is a reasonable thing to
want and an unreasonable thing to leave untraced; an unlogged superuser makes a
breach impossible to investigate and an invisible one makes it impossible to
notice. The account is hidden from listings, never from this table.

Existing accounts are NOT forced to change their password. They chose or were
given it under the old rules and there is no evidence it is compromised;
flagging everyone would lock out the whole team on deploy for no security gain.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd9f3c07b8e41'
down_revision: Union[str, Sequence[str], None] = 'a7b4e9f1c260'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(),
                                     nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("password_changed_at",
                                     sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "privileged_action_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Denormalised so the trail outlives the actor -- including an actor who
        # deletes themselves.
        sa.Column("actor_email", sa.String(320), nullable=False),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("target_email", sa.String(320), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_privileged_action_audit_actor_user_id",
                    "privileged_action_audit", ["actor_user_id"])
    op.create_index("ix_privileged_action_audit_actor_email",
                    "privileged_action_audit", ["actor_email"])
    op.create_index("ix_privileged_action_audit_action",
                    "privileged_action_audit", ["action"])
    op.create_index("ix_privileged_action_audit_target_user_id",
                    "privileged_action_audit", ["target_user_id"])
    op.create_index("ix_privileged_action_audit_occurred_at",
                    "privileged_action_audit", ["occurred_at"])


def downgrade() -> None:
    # Any DEVELOPER, CEO or CCO account becomes a role the application no
    # longer recognises, which would fail every permission check. Demoted to
    # ADMIN so the database stays usable if this is rolled back.
    op.execute("UPDATE users SET role = 'ADMIN' "
               "WHERE role IN ('DEVELOPER', 'CEO', 'CCO')")
    op.drop_table("privileged_action_audit")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "must_change_password")
