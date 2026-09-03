"""Add recoverable deletion metadata to registered schedules.

Revision ID: 20260903_0010
Revises: 20260903_0009
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_0010"
down_revision = "20260903_0009"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("deleted_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_schedules_deleted_by_id_employees",
            "employees",
            ["deleted_by_id"],
            ["id"],
        )
        batch_op.create_index("ix_schedules_deleted_at", ["deleted_at"], unique=False)


def downgrade():
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_index("ix_schedules_deleted_at")
        batch_op.drop_constraint("fk_schedules_deleted_by_id_employees", type_="foreignkey")
        batch_op.drop_column("deleted_by_id")
        batch_op.drop_column("deleted_at")
