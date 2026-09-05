"""Add per-document task content snapshots.

Revision ID: 20260905_0017
Revises: 20260904_0016
"""
from alembic import op
import sqlalchemy as sa


revision = "20260905_0017"
down_revision = "20260904_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_task_contents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_kind", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_kind",
            "document_id",
            "task_id",
            name="uq_document_task_content",
        ),
    )
    op.create_index(
        "ix_document_task_contents_document",
        "document_task_contents",
        ["document_kind", "document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_task_contents_task_id"),
        "document_task_contents",
        ["task_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_document_task_contents_task_id"), table_name="document_task_contents")
    op.drop_index("ix_document_task_contents_document", table_name="document_task_contents")
    op.drop_table("document_task_contents")
