"""Add automatic recurring task series metadata.

Revision ID: 20260904_0012
Revises: 20260903_0011
"""
from alembic import op
import sqlalchemy as sa


revision = "20260904_0012"
down_revision = "20260903_0011"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("recurrence_root_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "recurrence_sequence",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.create_foreign_key(
            "fk_tasks_recurrence_root_id_tasks",
            "tasks",
            ["recurrence_root_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_tasks_recurrence_root_id",
            ["recurrence_root_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_task_recurrence_sequence",
            ["recurrence_root_id", "recurrence_sequence"],
        )


def downgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("uq_task_recurrence_sequence", type_="unique")
        batch_op.drop_index("ix_tasks_recurrence_root_id")
        batch_op.drop_constraint("fk_tasks_recurrence_root_id_tasks", type_="foreignkey")
        batch_op.drop_column("recurrence_sequence")
        batch_op.drop_column("recurrence_root_id")
