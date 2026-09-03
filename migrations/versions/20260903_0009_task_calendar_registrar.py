"""Track who registered each task in the calendar.

Revision ID: 20260903_0009
Revises: 20260903_0008
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_0009"
down_revision = "20260903_0008"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("calendar_registered_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_calendar_registered_by_id_employees",
            "employees",
            ["calendar_registered_by_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint(
            "fk_tasks_calendar_registered_by_id_employees", type_="foreignkey"
        )
        batch_op.drop_column("calendar_registered_by_id")
