"""Backfill snapshots for existing meeting and journal task links.

Revision ID: 20260905_0018
Revises: 20260905_0017
"""
from alembic import op
import sqlalchemy as sa


revision = "20260905_0018"
down_revision = "20260905_0017"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO document_task_contents
                (document_kind, document_id, task_id, content, created_at, updated_at)
            SELECT
                'meeting',
                link.meeting_id,
                link.task_id,
                COALESCE(task.content, ''),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM daily_meeting_items AS link
            JOIN tasks AS task ON task.id = link.task_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM document_task_contents AS snapshot
                WHERE snapshot.document_kind = 'meeting'
                  AND snapshot.document_id = link.meeting_id
                  AND snapshot.task_id = link.task_id
            )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO document_task_contents
                (document_kind, document_id, task_id, content, created_at, updated_at)
            SELECT
                'journal',
                link.journal_id,
                link.task_id,
                COALESCE(task.content, ''),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM work_journal_document_items AS link
            JOIN tasks AS task ON task.id = link.task_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM document_task_contents AS snapshot
                WHERE snapshot.document_kind = 'journal'
                  AND snapshot.document_id = link.journal_id
                  AND snapshot.task_id = link.task_id
            )
            """
        )
    )


def downgrade():
    # Snapshot rows are intentionally retained on this intermediate downgrade.
    # Revision 0017 removes the entire snapshot table on a full downgrade.
    pass
