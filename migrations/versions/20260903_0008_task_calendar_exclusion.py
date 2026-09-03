"""Allow tasks, including auto-calendar types, to be excluded from the calendar.

Revision ID: 20260903_0008
Revises: 20260903_0007
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_0008"
down_revision = "20260903_0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("calendar_excluded", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("calendar_excluded")
