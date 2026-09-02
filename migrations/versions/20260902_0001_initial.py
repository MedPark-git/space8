"""Initial PostgreSQL schema for management-task.

Revision ID: 20260902_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "20260902_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("data_scope", sa.String(20), nullable=False, server_default="own"),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "menus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("url", sa.String(200), nullable=False, server_default="#"),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("menus.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("board_type", sa.String(30), nullable=False, server_default="일반"),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("employee_no", sa.String(30), nullable=True, unique=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("position", sa.String(50), nullable=True),
        sa.Column("email", sa.String(150), nullable=True, unique=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("login_id", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="재직"),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("reregistered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_employees_login_id", "employees", ["login_id"])
    op.create_table(
        "role_menu",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("menu_id", sa.Integer(), sa.ForeignKey("menus.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "role_board",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="진행중"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeat_cycle", sa.String(20), nullable=False, server_default="없음"),
        sa.Column("repeat_detail", sa.String(100), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tasks_department_id", "tasks", ["department_id"])
    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])
    op.create_index("ix_tasks_target_date", "tasks", ["target_date"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_table(
        "task_classifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(30), nullable=False),
        sa.UniqueConstraint("task_id", "name", name="uq_task_classification"),
    )
    op.create_table(
        "task_status_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
    )
    op.create_index("ix_task_status_logs_task_id", "task_status_logs", ["task_id"])
    op.create_table(
        "task_daily_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_daily_logs_task_id", "task_daily_logs", ["task_id"])
    op.create_index("ix_task_daily_logs_work_date", "task_daily_logs", ["work_date"])
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="개인"),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("is_holiday", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
    )
    op.create_index("ix_schedules_schedule_date", "schedules", ["schedule_date"])
    op.create_table(
        "daily_meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_daily_meetings_meeting_date", "daily_meetings", ["meeting_date"])
    op.create_table(
        "daily_meeting_items",
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("daily_meetings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("related_type", sa.String(30), nullable=False),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("uploader_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target", sa.String(150), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("attachments")
    op.drop_table("daily_meeting_items")
    op.drop_table("daily_meetings")
    op.drop_table("schedules")
    op.drop_table("task_daily_logs")
    op.drop_table("task_status_logs")
    op.drop_table("task_classifications")
    op.drop_table("tasks")
    op.drop_table("role_board")
    op.drop_table("role_menu")
    op.drop_table("employees")
    op.drop_table("boards")
    op.drop_table("menus")
    op.drop_table("departments")
    op.drop_table("roles")
