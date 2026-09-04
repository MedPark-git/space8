"""Split daily meetings into agenda and minutes documents.

Revision ID: 20260904_0013
Revises: 20260904_0012
"""
from alembic import op
import sqlalchemy as sa


revision = "20260904_0013"
down_revision = "20260904_0012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("daily_meetings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "document_type",
                sa.String(length=20),
                nullable=False,
                server_default="agenda",
            )
        )
        batch_op.add_column(
            sa.Column("title", sa.String(length=200), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("agenda_content", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("discussion_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("decisions", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("action_items", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch_op.create_index(
            "ix_daily_meetings_document_type",
            ["document_type"],
            unique=False,
        )

    op.execute(
        sa.text(
            "UPDATE daily_meetings "
            "SET title = CAST(meeting_date AS VARCHAR) || ' 일일 회의 아젠다' "
            "WHERE title = ''"
        )
    )


def downgrade():
    with op.batch_alter_table("daily_meetings") as batch_op:
        batch_op.drop_index("ix_daily_meetings_document_type")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("action_items")
        batch_op.drop_column("decisions")
        batch_op.drop_column("discussion_notes")
        batch_op.drop_column("agenda_content")
        batch_op.drop_column("title")
        batch_op.drop_column("document_type")
