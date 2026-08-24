"""job control signal and heartbeat

Adds durable job control (control_signal, heartbeat_at) so pause/cancel and
crash detection no longer depend on in-process state, and puts ON DELETE
CASCADE on records.job_id so deleting a job cannot orphan its rows.

Revision ID: 7e5c3be6d419
Revises: 8fd7756ae068
Create Date: 2026-08-24 13:52:23.757394
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '7e5c3be6d419'
down_revision: Union[str, Sequence[str], None] = '8fd7756ae068'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _job_fk_name() -> str | None:
    """Actual name of the records.job_id foreign key in this database.

    Autogenerate emitted drop_constraint(None, ...), which only works under
    SQLite batch mode (it rebuilds the whole table). PostgreSQL needs the real
    constraint name, which is server-generated (typically records_job_id_fkey),
    so it is looked up rather than assumed.
    """
    bind = op.get_bind()
    for fk in sa.inspect(bind).get_foreign_keys("records"):
        if fk.get("constrained_columns") == ["job_id"]:
            return fk.get("name")
    return None


def upgrade() -> None:
    with op.batch_alter_table("processing_jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("control_signal", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    name = _job_fk_name()
    with op.batch_alter_table("records", schema=None) as batch_op:
        if name:
            batch_op.drop_constraint(name, type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_records_job_id_processing_jobs", "processing_jobs",
            ["job_id"], ["id"], ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("records", schema=None) as batch_op:
        batch_op.drop_constraint("fk_records_job_id_processing_jobs", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_records_job_id_processing_jobs", "processing_jobs", ["job_id"], ["id"])

    with op.batch_alter_table("processing_jobs", schema=None) as batch_op:
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("control_signal")
