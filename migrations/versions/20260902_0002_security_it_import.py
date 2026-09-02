"""Add source metadata for the security IT workbook import.

Revision ID: 20260902_0002
Revises: 20260902_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260902_0002"
down_revision = "20260902_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("source_ref", sa.String(100), nullable=True))
    op.add_column("tasks", sa.Column("source_name", sa.String(255), nullable=True))
    op.add_column("tasks", sa.Column("source_sheet", sa.String(255), nullable=True))
    op.add_column("tasks", sa.Column("source_category", sa.String(100), nullable=True))
    op.add_column("tasks", sa.Column("source_detail", sa.String(150), nullable=True))
    op.add_column("tasks", sa.Column("source_assignees", sa.String(250), nullable=True))
    op.add_column("tasks", sa.Column("source_frequency", sa.String(50), nullable=True))
    op.create_index("ix_tasks_source_ref", "tasks", ["source_ref"], unique=True)


def downgrade():
    op.drop_index("ix_tasks_source_ref", table_name="tasks")
    op.drop_column("tasks", "source_frequency")
    op.drop_column("tasks", "source_assignees")
    op.drop_column("tasks", "source_detail")
    op.drop_column("tasks", "source_category")
    op.drop_column("tasks", "source_sheet")
    op.drop_column("tasks", "source_name")
    op.drop_column("tasks", "source_ref")
