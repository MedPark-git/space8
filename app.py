import calendar
import hashlib
import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import quote_plus, urlparse

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from openpyxl import Workbook, load_workbook
from sqlalchemy import UniqueConstraint, and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
migrate = Migrate(compare_type=True)
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "로그인이 필요합니다."

TASK_TYPES = ("대표이사수명", "루틴", "개인", "주요")
TASK_STATUSES = ("진행중", "완료", "지연", "보류")
REPEAT_CYCLES = ("없음", "일간", "주간", "월간", "분기", "연간")
STATUS_CLASS = {"진행중": "progress", "완료": "done", "지연": "delayed", "보류": "hold"}


def utcnow():
    return datetime.now(timezone.utc)


def build_database_uri():
    if os.getenv("DATABASE_URL"):
        uri = os.environ["DATABASE_URL"]
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql+psycopg://", 1)
        elif uri.startswith("postgresql://"):
            uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
        return uri
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    if all(os.getenv(key) for key in required):
        user = quote_plus(os.environ["DB_USER"])
        password = quote_plus(os.environ["DB_PASSWORD"])
        host = os.environ["DB_HOST"]
        port = os.environ["DB_PORT"]
        name = quote_plus(os.environ["DB_NAME"])
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
    if os.getenv("ALLOW_IN_MEMORY_DB") == "1":
        return "sqlite:///:memory:"
    raise RuntimeError("PostgreSQL 연결 환경변수(DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD)가 필요합니다.")


def build_secret_key():
    if os.getenv("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    database_secret = os.getenv("DB_PASSWORD")
    if database_secret:
        return hashlib.sha256(f"management-task:{database_secret}".encode()).hexdigest()
    if os.getenv("ALLOW_IN_MEMORY_DB") == "1":
        return "test-only-secret-key"
    raise RuntimeError("안전한 세션 키를 생성할 수 없습니다.")


role_menu = db.Table(
    "role_menu",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("menu_id", db.Integer, db.ForeignKey("menus.id", ondelete="CASCADE"), primary_key=True),
)

role_board = db.Table(
    "role_board",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("board_id", db.Integer, db.ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True),
)

daily_meeting_item = db.Table(
    "daily_meeting_items",
    db.Column("meeting_id", db.Integer, db.ForeignKey("daily_meetings.id", ondelete="CASCADE"), primary_key=True),
    db.Column("task_id", db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    data_scope = db.Column(db.String(20), nullable=False, default="own")
    permissions = db.Column(db.JSON, nullable=False, default=dict)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    menus = db.relationship("Menu", secondary=role_menu, back_populates="roles")
    boards = db.relationship("Board", secondary=role_board, back_populates="roles")

    def allows(self, permission):
        return self.name == "시스템관리자" or bool((self.permissions or {}).get(permission))


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    parent = db.relationship("Department", remote_side=[id], backref="children")


class Employee(UserMixin, db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    employee_no = db.Column(db.String(30), unique=True, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    position = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    login_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="재직")
    hire_date = db.Column(db.Date, nullable=True)
    termination_date = db.Column(db.Date, nullable=True)
    reregistered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    failed_login_count = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    department = db.relationship("Department", backref="employees")
    role = db.relationship("Role", backref="employees")

    @property
    def is_active(self):
        return self.status == "재직"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Menu(db.Model):
    __tablename__ = "menus"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(200), nullable=False, default="#")
    parent_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    parent = db.relationship("Menu", remote_side=[id], backref="children")
    roles = db.relationship("Role", secondary=role_menu, back_populates="menus")


class Board(db.Model):
    __tablename__ = "boards"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    board_type = db.Column(db.String(30), nullable=False, default="일반")
    options = db.Column(db.JSON, nullable=False, default=dict)
    active = db.Column(db.Boolean, nullable=False, default=True)
    roles = db.relationship("Role", secondary=role_board, back_populates="boards")


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    content = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    target_date = db.Column(db.Date, nullable=False, index=True)
    completed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="진행중", index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)
    repeat_cycle = db.Column(db.String(20), nullable=False, default="없음")
    repeat_detail = db.Column(db.String(100), nullable=True)
    source_ref = db.Column(db.String(100), unique=True, nullable=True, index=True)
    source_name = db.Column(db.String(255), nullable=True)
    source_sheet = db.Column(db.String(255), nullable=True)
    source_category = db.Column(db.String(100), nullable=True)
    source_detail = db.Column(db.String(150), nullable=True)
    source_assignees = db.Column(db.String(250), nullable=True)
    source_frequency = db.Column(db.String(50), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    department = db.relationship("Department", backref="tasks")
    assignee = db.relationship("Employee", foreign_keys=[assignee_id], backref="assigned_tasks")
    creator = db.relationship("Employee", foreign_keys=[created_by_id], backref="created_tasks")
    classifications = db.relationship("TaskClassification", cascade="all, delete-orphan", backref="task")
    daily_logs = db.relationship("TaskDailyLog", cascade="all, delete-orphan", backref="task")

    @property
    def type_names(self):
        return [item.name for item in self.classifications]

    @property
    def remaining_days(self):
        if self.status == "완료":
            return None
        return (self.target_date - date.today()).days

    @property
    def status_class(self):
        return STATUS_CLASS.get(self.status, "progress")

    @property
    def display_assignees(self):
        return self.source_assignees or self.assignee.name

    @property
    def is_source_import(self):
        return bool(self.source_ref)


class TaskClassification(db.Model):
    __tablename__ = "task_classifications"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(30), nullable=False)
    __table_args__ = (UniqueConstraint("task_id", "name", name="uq_task_classification"),)


class TaskStatusLog(db.Model):
    __tablename__ = "task_status_logs"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=False)
    changed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    changer = db.relationship("Employee")


class TaskDailyLog(db.Model):
    __tablename__ = "task_daily_logs"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    author = db.relationship("Employee")


class Schedule(db.Model):
    __tablename__ = "schedules"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    schedule_date = db.Column(db.Date, nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    scope = db.Column(db.String(20), nullable=False, default="개인")
    memo = db.Column(db.Text, nullable=True)
    is_holiday = db.Column(db.Boolean, nullable=False, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    task = db.relationship("Task")
    department = db.relationship("Department")
    assignee = db.relationship("Employee", foreign_keys=[assignee_id])
    creator = db.relationship("Employee", foreign_keys=[created_by_id])


class DailyMeeting(db.Model):
    __tablename__ = "daily_meetings"
    id = db.Column(db.Integer, primary_key=True)
    meeting_date = db.Column(db.Date, nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    author = db.relationship("Employee")
    department = db.relationship("Department")
    tasks = db.relationship("Task", secondary=daily_meeting_item)


class Attachment(db.Model):
    __tablename__ = "attachments"
    id = db.Column(db.Integer, primary_key=True)
    related_type = db.Column(db.String(30), nullable=False)
    related_id = db.Column(db.Integer, nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120), nullable=True)
    file_data = db.Column(db.LargeBinary, nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    uploader = db.relationship("Employee")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False)
    target = db.Column(db.String(150), nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    user = db.relationship("Employee")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Employee, int(user_id))


def audit(action, target, details=None, user_id=None):
    uid = user_id if user_id is not None else (current_user.id if current_user.is_authenticated else None)
    db.session.add(
        AuditLog(
            user_id=uid,
            action=action,
            target=target,
            details=details or {},
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr) if request else None,
        )
    )


def admin_required(permission):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.role.allows(permission):
                abort(403)
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def visible_task_query(user):
    query = select(Task)
    scope = user.role.data_scope
    if scope == "all":
        return query
    if scope == "department":
        return query.where(
            or_(Task.department_id == user.department_id, Task.assignee_id == user.id, Task.created_by_id == user.id)
        )
    return query.where(or_(Task.assignee_id == user.id, Task.created_by_id == user.id))


def can_view_task_detail(task):
    return (
        current_user.role.data_scope == "all"
        or task.department_id == current_user.department_id
        or task.assignee_id == current_user.id
        or task.created_by_id == current_user.id
    )


def can_edit_task(task):
    return current_user.role.allows("task_manage_all") or task.assignee_id == current_user.id or task.created_by_id == current_user.id


def refresh_overdue_tasks():
    overdue = db.session.scalars(
        select(Task).where(Task.target_date < date.today(), Task.status == "진행중")
    ).all()
    if not overdue:
        return
    for task in overdue:
        task.status = "지연"
        db.session.add(
            TaskStatusLog(task_id=task.id, previous_status="진행중", new_status="지연", changed_by_id=None)
        )
    db.session.commit()


def import_security_it_tasks():
    seed_path = os.path.join(os.path.dirname(__file__), "seed", "security_it_tasks_260902.json")
    with open(seed_path, encoding="utf-8") as seed_file:
        payload = json.load(seed_file)

    department = db.session.scalar(select(Department).where(Department.name == "보안전산팀"))
    admin_user = db.session.scalar(
        select(Employee).where(Employee.login_id == os.getenv("BOOTSTRAP_ADMIN_ID", "admin"))
    )
    if not department or not admin_user:
        raise RuntimeError("보안전산팀 업무를 등록할 부서 또는 관리자 계정을 찾을 수 없습니다.")

    recurring_frequencies = {"일", "주1회", "월1회", "월2회", "분기별", "년1회", "년1회이상", "지속"}
    repeat_cycles = {
        "일": "일간",
        "주1회": "주간",
        "월1회": "월간",
        "월2회": "월간",
        "분기별": "분기",
        "년1회": "연간",
        "년1회이상": "연간",
    }
    target_dates = {
        "일": date(2026, 9, 2),
        "주1회": date(2026, 9, 9),
        "월1회": date(2026, 9, 30),
        "월2회": date(2026, 9, 30),
        "분기별": date(2026, 9, 30),
        "년1회": date(2026, 12, 31),
        "년1회이상": date(2026, 12, 31),
        "지속": date(2026, 12, 31),
        "변경 시": date(2026, 12, 31),
        "불시": date(2026, 12, 31),
        "단발성": date(2026, 12, 31),
    }
    existing_refs = set(
        db.session.scalars(
            select(Task.source_ref).where(Task.source_ref.in_([item["source_ref"] for item in payload["tasks"]]))
        ).all()
    )
    created_count = 0
    for item in payload["tasks"]:
        if item["source_ref"] in existing_refs:
            continue
        frequency = item["frequency"]
        title_detail = item["detail"] or item["content"]
        task = Task(
            title=f'{item["category"]} · {title_detail}'[:250],
            content=item["content"],
            department_id=department.id,
            assignee_id=admin_user.id,
            start_date=date(2026, 9, 2),
            target_date=target_dates.get(frequency, date(2026, 12, 31)),
            status="진행중",
            progress=0,
            repeat_cycle=repeat_cycles.get(frequency, "없음"),
            repeat_detail=frequency,
            source_ref=item["source_ref"],
            source_name=item["source_name"],
            source_sheet=item["source_sheet"],
            source_category=item["category"],
            source_detail=item["detail"],
            source_assignees=", ".join(item["assignees"]),
            source_frequency=frequency,
            created_by_id=admin_user.id,
        )
        classification = "루틴" if frequency in recurring_frequencies else "주요"
        task.classifications = [TaskClassification(name=classification)]
        db.session.add(task)
        created_count += 1

    imported_count = db.session.scalar(
        select(func.count(Task.id)).where(Task.source_name == "경영_보안전산팀 업무분장_260902.xlsx")
    ) or 0
    final_count = imported_count
    if final_count != payload["expected_count"]:
        db.session.rollback()
        raise RuntimeError(
            f'보안전산팀 업무 등록 건수가 일치하지 않습니다: {final_count}/{payload["expected_count"]}'
        )
    if created_count:
        db.session.add(
            AuditLog(
                user_id=admin_user.id,
                action="SECURITY_IT_WORKBOOK_IMPORT",
                target="경영_보안전산팀 업무분장_260902.xlsx",
                details={"created": created_count, "total": final_count, "deduplicated": 8},
                ip_address=None,
            )
        )
    db.session.commit()


def seed_reference_data():
    role_specs = [
        ("시스템관리자", "all", {"admin": True, "task_manage_all": True, "meeting_all": True}, True),
        ("대표이사", "all", {"task_manage_all": True, "meeting_all": True}, True),
        ("팀장", "department", {"task_manage_department": True, "meeting_all": True}, True),
        ("팀원", "department", {"task_create": True}, True),
    ]
    roles = {}
    for name, scope, permissions, is_system in role_specs:
        role = db.session.scalar(select(Role).where(Role.name == name))
        if not role:
            role = Role(name=name, data_scope=scope, permissions=permissions, is_system=is_system)
            db.session.add(role)
        roles[name] = role

    root = db.session.scalar(select(Department).where(Department.name == "경영사업본부"))
    if not root:
        root = Department(name="경영사업본부")
        db.session.add(root)
        db.session.flush()
    for name in ("재무운영팀", "인사총무팀", "보안전산팀"):
        if not db.session.scalar(select(Department).where(Department.name == name)):
            db.session.add(Department(name=name, parent=root))
    db.session.flush()

    menu_specs = [
        ("통합현황", "/", 10),
        ("업무현황", "/tasks", 20),
        ("업무등록", "/tasks/new", 30),
        ("일정", "/calendar", 40),
        ("일일회의", "/meetings", 50),
        ("업무일지", "/journals", 60),
        ("관리자", "/admin/employees", 90),
    ]
    for name, url, order in menu_specs:
        if not db.session.scalar(select(Menu).where(Menu.name == name)):
            menu = Menu(name=name, url=url, sort_order=order)
            menu.roles = list(roles.values()) if name != "관리자" else [roles["시스템관리자"]]
            db.session.add(menu)
    if not db.session.scalar(select(Board).where(Board.name == "공지사항")):
        board = Board(name="공지사항", board_type="공지", options={"allow_comments": False})
        board.roles = list(roles.values())
        db.session.add(board)

    bootstrap_id = os.getenv("BOOTSTRAP_ADMIN_ID", "admin")
    bootstrap_hash = os.getenv("BOOTSTRAP_ADMIN_PASSWORD_HASH")
    if bootstrap_hash and not db.session.scalar(select(Employee).where(Employee.login_id == bootstrap_id)):
        dept = db.session.scalar(select(Department).where(Department.name == "보안전산팀")) or root
        db.session.add(
            Employee(
                name=os.getenv("BOOTSTRAP_ADMIN_NAME", "시스템관리자"),
                employee_no="SYSTEM-001",
                department=dept,
                position="관리자",
                login_id=bootstrap_id,
                password_hash=bootstrap_hash,
                role=roles["시스템관리자"],
                status="재직",
                hire_date=date.today(),
                must_change_password=True,
            )
        )

    password_reset_hash = os.getenv("ADMIN_PASSWORD_RESET_HASH")
    if password_reset_hash:
        admin_user = db.session.scalar(select(Employee).where(Employee.login_id == bootstrap_id))
        if not admin_user:
            raise RuntimeError(f"비밀번호를 변경할 관리자 계정({bootstrap_id})을 찾을 수 없습니다.")
        if admin_user.password_hash != password_reset_hash:
            admin_user.password_hash = password_reset_hash
            admin_user.failed_login_count = 0
            admin_user.locked_until = None
            admin_user.must_change_password = False
            db.session.add(
                AuditLog(
                    user_id=admin_user.id,
                    action="ADMIN_PASSWORD_RESET",
                    target=f"employee:{admin_user.id}",
                    details={"source": "one_time_environment"},
                    ip_address=None,
                )
            )
    db.session.commit()
    import_security_it_tasks()


def run_startup_tasks(app):
    if app.config.get("TESTING"):
        return
    with app.app_context():
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        try:
            if uri.startswith("postgresql"):
                db.session.execute(text("SELECT pg_advisory_lock(2026090201)"))
                db.session.commit()
            upgrade(directory=os.path.join(app.root_path, "migrations"))
            seed_reference_data()
        finally:
            if uri.startswith("postgresql"):
                try:
                    db.session.execute(text("SELECT pg_advisory_unlock(2026090201)"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=build_secret_key(),
        SQLALCHEMY_DATABASE_URI=build_database_uri(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))),
    )
    if test_config:
        app.config.update(test_config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(app.root_path, "migrations"))
    csrf.init_app(app)
    login_manager.init_app(app)

    @app.before_request
    def enforce_authentication():
        public_endpoints = {"login", "health", "static"}
        if request.endpoint not in public_endpoints and not current_user.is_authenticated:
            return redirect(url_for("login", next=request.full_path))
        if current_user.is_authenticated:
            if not current_user.is_active:
                logout_user()
                return redirect(url_for("login"))
            if current_user.must_change_password and request.endpoint not in {"change_password", "logout", "static"}:
                return redirect(url_for("change_password"))
            refresh_overdue_tasks()

    @app.context_processor
    def inject_globals():
        menus = []
        if current_user.is_authenticated:
            menus = db.session.scalars(
                select(Menu)
                .join(role_menu)
                .where(role_menu.c.role_id == current_user.role_id, Menu.active.is_(True))
                .order_by(Menu.sort_order)
            ).all()
        return {
            "visible_menus": menus,
            "TASK_TYPES": TASK_TYPES,
            "TASK_STATUSES": TASK_STATUSES,
            "REPEAT_CYCLES": REPEAT_CYCLES,
            "STATUS_CLASS": STATUS_CLASS,
            "today": date.today(),
        }

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            admin_ready = bool(
                db.session.scalar(
                    select(func.count(Employee.id))
                    .join(Role, Employee.role_id == Role.id)
                    .where(Role.name == "시스템관리자", Employee.status == "재직")
                )
            )
            reset_hash = os.getenv("ADMIN_PASSWORD_RESET_HASH")
            reset_ready = True
            if reset_hash:
                reset_user = db.session.scalar(
                    select(Employee).where(Employee.login_id == os.getenv("BOOTSTRAP_ADMIN_ID", "admin"))
                )
                reset_ready = bool(reset_user and reset_user.password_hash == reset_hash)
            import_ready = (
                db.session.scalar(
                    select(func.count(Task.id)).where(
                        Task.source_name == "경영_보안전산팀 업무분장_260902.xlsx"
                    )
                )
                == 116
            )
            ready = admin_ready and reset_ready and import_ready
            return jsonify(
                status="ok",
                database="connected",
                application_ready=admin_ready,
                credential_sync_ready=reset_ready,
                security_it_import_ready=import_ready,
            ), (200 if ready else 503)
        except Exception:
            return jsonify(status="error", database="unavailable"), 503

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            login_id = request.form.get("login_id", "").strip()
            password = request.form.get("password", "")
            user = db.session.scalar(select(Employee).where(Employee.login_id == login_id))
            now = utcnow()
            if user and user.locked_until and user.locked_until > now:
                flash("로그인 실패 횟수 초과로 계정이 잠겼습니다. 잠시 후 다시 시도해 주세요.", "danger")
                return render_template("auth.html", mode="login"), 429
            if not user or not user.is_active or not user.check_password(password):
                if user:
                    user.failed_login_count += 1
                    if user.failed_login_count >= 5:
                        user.locked_until = now + timedelta(minutes=15)
                        user.failed_login_count = 0
                    db.session.commit()
                flash("아이디 또는 비밀번호를 확인해 주세요.", "danger")
                return render_template("auth.html", mode="login"), 401
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = now
            db.session.commit()
            login_user(user, remember=False, duration=app.config["PERMANENT_SESSION_LIFETIME"])
            audit("LOGIN", f"employee:{user.id}", user_id=user.id)
            db.session.commit()
            next_url = request.args.get("next", "")
            if next_url and urlparse(next_url).netloc == "":
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        return render_template("auth.html", mode="login")

    @app.post("/logout")
    @login_required
    def logout():
        audit("LOGOUT", f"employee:{current_user.id}")
        db.session.commit()
        logout_user()
        return redirect(url_for("login"))

    @app.route("/change-password", methods=["GET", "POST"])
    @login_required
    def change_password():
        if request.method == "POST":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not current_user.check_password(current_password):
                flash("현재 비밀번호가 일치하지 않습니다.", "danger")
            elif len(new_password) < 10 or not any(c.isalpha() for c in new_password) or not any(c.isdigit() for c in new_password):
                flash("새 비밀번호는 영문과 숫자를 포함하여 10자 이상이어야 합니다.", "danger")
            elif new_password != confirm_password:
                flash("새 비밀번호 확인이 일치하지 않습니다.", "danger")
            else:
                current_user.set_password(new_password)
                current_user.must_change_password = False
                audit("PASSWORD_CHANGE", f"employee:{current_user.id}")
                db.session.commit()
                flash("비밀번호가 변경되었습니다.", "success")
                return redirect(url_for("dashboard"))
        return render_template("auth.html", mode="change")

    @app.get("/")
    @login_required
    def dashboard():
        tasks = db.session.scalars(visible_task_query(current_user).order_by(Task.target_date, Task.id)).all()

        def task_summary(type_name):
            subset = [task for task in tasks if type_name in task.type_names]
            active_days = [task.remaining_days for task in subset if task.remaining_days is not None and task.remaining_days >= 0]
            return {
                "total": len(subset),
                "today": sum(1 for task in subset if task.start_date <= date.today() <= task.target_date),
                "remaining": min(active_days) if active_days else None,
                "done": sum(1 for task in subset if task.status == "완료"),
                "delayed": sum(1 for task in subset if task.status == "지연"),
                "hold": sum(1 for task in subset if task.status == "보류"),
            }

        department_counts = dict(
            db.session.execute(
                select(Department.name, func.count(Task.id))
                .outerjoin(Task, Task.department_id == Department.id)
                .where(Department.active.is_(True))
                .group_by(Department.id, Department.name)
                .order_by(Department.id)
            ).all()
        )
        type_counts = {name: sum(1 for task in tasks if name in task.type_names) for name in TASK_TYPES}
        return render_template(
            "dashboard.html",
            routine=task_summary("루틴"),
            major=task_summary("주요"),
            tasks=tasks[:20],
            department_counts=department_counts,
            type_counts=type_counts,
        )

    @app.get("/tasks")
    @login_required
    def task_list():
        query = visible_task_query(current_user)
        keyword = request.args.get("q", "").strip()
        department_id = request.args.get("department_id", type=int)
        assignee_id = request.args.get("assignee_id", type=int)
        status = request.args.get("status", "")
        task_type = request.args.get("task_type", "")
        start = request.args.get("start", "")
        end = request.args.get("end", "")
        if keyword:
            query = query.where(
                or_(
                    Task.title.ilike(f"%{keyword}%"),
                    Task.content.ilike(f"%{keyword}%"),
                    Task.source_category.ilike(f"%{keyword}%"),
                    Task.source_detail.ilike(f"%{keyword}%"),
                    Task.source_assignees.ilike(f"%{keyword}%"),
                    Task.source_frequency.ilike(f"%{keyword}%"),
                )
            )
        if department_id:
            query = query.where(Task.department_id == department_id)
        if assignee_id:
            query = query.where(Task.assignee_id == assignee_id)
        if status in TASK_STATUSES:
            query = query.where(Task.status == status)
        if task_type in TASK_TYPES:
            query = query.join(TaskClassification).where(TaskClassification.name == task_type)
        if start:
            query = query.where(Task.target_date >= date.fromisoformat(start))
        if end:
            query = query.where(Task.target_date <= date.fromisoformat(end))
        page = max(request.args.get("page", 1, type=int), 1)
        pagination = db.paginate(query.order_by(Task.target_date, Task.id), page=page, per_page=20, error_out=False)
        return render_template(
            "tasks.html",
            mode="list",
            pagination=pagination,
            departments=db.session.scalars(select(Department).where(Department.active.is_(True)).order_by(Department.name)).all(),
            employees=db.session.scalars(select(Employee).where(Employee.status == "재직").order_by(Employee.name)).all(),
        )

    @app.route("/tasks/new", methods=["GET", "POST"])
    @login_required
    def task_new():
        return task_form_handler(None)

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def task_edit(task_id):
        task = db.get_or_404(Task, task_id)
        if not can_edit_task(task):
            abort(403)
        return task_form_handler(task)

    def task_form_handler(task):
        departments = db.session.scalars(select(Department).where(Department.active.is_(True)).order_by(Department.name)).all()
        employees = db.session.scalars(select(Employee).where(Employee.status == "재직").order_by(Employee.name)).all()
        if request.method == "POST":
            types = [name for name in request.form.getlist("task_types") if name in TASK_TYPES]
            if not types:
                flash("업무 분류를 하나 이상 선택해 주세요.", "danger")
            else:
                old_status = task.status if task else None
                target = task or Task(created_by_id=current_user.id)
                target.title = request.form.get("title", "").strip()
                target.content = request.form.get("content", "").strip()
                target.department_id = int(request.form["department_id"])
                target.assignee_id = int(request.form["assignee_id"])
                target.start_date = date.fromisoformat(request.form["start_date"])
                target.target_date = date.fromisoformat(request.form["target_date"])
                target.status = request.form.get("status", "진행중") if request.form.get("status") in TASK_STATUSES else "진행중"
                target.progress = min(max(int(request.form.get("progress", 0)), 0), 100)
                target.repeat_cycle = request.form.get("repeat_cycle", "없음") if request.form.get("repeat_cycle") in REPEAT_CYCLES else "없음"
                target.repeat_detail = request.form.get("repeat_detail", "").strip()
                if target.status == "완료":
                    target.completed_date = target.completed_date or date.today()
                    target.progress = 100
                else:
                    target.completed_date = None
                if target.target_date < target.start_date:
                    flash("목표일은 착수일보다 빠를 수 없습니다.", "danger")
                elif not target.title:
                    flash("업무 제목을 입력해 주세요.", "danger")
                else:
                    db.session.add(target)
                    db.session.flush()
                    target.classifications.clear()
                    target.classifications.extend(TaskClassification(name=name) for name in types)
                    if old_status != target.status:
                        db.session.add(
                            TaskStatusLog(
                                task_id=target.id,
                                previous_status=old_status,
                                new_status=target.status,
                                changed_by_id=current_user.id,
                            )
                        )
                    audit("TASK_UPDATE" if task else "TASK_CREATE", f"task:{target.id}", {"title": target.title})
                    db.session.commit()
                    flash("업무가 저장되었습니다.", "success")
                    return redirect(url_for("task_detail", task_id=target.id))
        return render_template("tasks.html", mode="form", task=task, departments=departments, employees=employees)

    @app.route("/tasks/<int:task_id>", methods=["GET", "POST"])
    @login_required
    def task_detail(task_id):
        task = db.get_or_404(Task, task_id)
        if not can_view_task_detail(task):
            return render_template("tasks.html", mode="masked", task=task), 200
        if request.method == "POST":
            if not can_edit_task(task):
                abort(403)
            content = request.form.get("daily_log", "").strip()
            work_date = date.fromisoformat(request.form.get("work_date", date.today().isoformat()))
            if content:
                db.session.add(TaskDailyLog(task_id=task.id, work_date=work_date, content=content, author_id=current_user.id))
                audit("DAILY_LOG_CREATE", f"task:{task.id}")
                db.session.commit()
                flash("일일업무 기록이 저장되었습니다.", "success")
                return redirect(url_for("task_detail", task_id=task.id))
        status_logs = db.session.scalars(
            select(TaskStatusLog).where(TaskStatusLog.task_id == task.id).order_by(TaskStatusLog.changed_at.desc())
        ).all()
        return render_template("tasks.html", mode="detail", task=task, status_logs=status_logs, can_edit=can_edit_task(task))

    @app.get("/tasks/excel-template")
    @login_required
    def task_excel_template():
        wb = Workbook()
        ws = wb.active
        ws.title = "업무등록"
        headers = ["제목", "내용", "분류", "부서", "담당자 로그인ID", "착수일", "목표일", "상태", "진행률", "반복주기"]
        ws.append(headers)
        ws.append(["월간 비용 마감", "마감자료 취합", "루틴|주요", "재무운영팀", "admin", date.today(), date.today() + timedelta(days=7), "진행중", 10, "월간"])
        ws.freeze_panes = "A2"
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = max(len(str(cell.value or "")) for cell in column) + 3
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name="management_task_upload_template.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.post("/tasks/excel-upload")
    @login_required
    def task_excel_upload():
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".xlsx"):
            flash(".xlsx 형식의 파일을 선택해 주세요.", "danger")
            return redirect(url_for("task_list"))
        raw = file.read()
        try:
            wb = load_workbook(io.BytesIO(raw), data_only=True)
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
            expected = ["제목", "내용", "분류", "부서", "담당자 로그인ID", "착수일", "목표일", "상태", "진행률", "반복주기"]
            if headers[: len(expected)] != expected:
                raise ValueError("템플릿 헤더가 일치하지 않습니다.")
            created = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue
                department = db.session.scalar(select(Department).where(Department.name == str(row[3]).strip()))
                employee = db.session.scalar(select(Employee).where(Employee.login_id == str(row[4]).strip()))
                if not department or not employee:
                    raise ValueError(f"{created + 2}행의 부서 또는 담당자를 찾을 수 없습니다.")
                start_date = row[5].date() if isinstance(row[5], datetime) else (row[5] if isinstance(row[5], date) else date.fromisoformat(str(row[5])))
                target_date = row[6].date() if isinstance(row[6], datetime) else (row[6] if isinstance(row[6], date) else date.fromisoformat(str(row[6])))
                task = Task(
                    title=str(row[0]).strip(),
                    content=str(row[1] or "").strip(),
                    department=department,
                    assignee=employee,
                    start_date=start_date,
                    target_date=target_date,
                    status=str(row[7] or "진행중") if str(row[7] or "진행중") in TASK_STATUSES else "진행중",
                    progress=min(max(int(row[8] or 0), 0), 100),
                    repeat_cycle=str(row[9] or "없음") if str(row[9] or "없음") in REPEAT_CYCLES else "없음",
                    created_by_id=current_user.id,
                )
                types = [item.strip() for item in str(row[2]).split("|") if item.strip() in TASK_TYPES]
                if not types:
                    raise ValueError(f"{created + 2}행의 업무 분류가 올바르지 않습니다.")
                task.classifications = [TaskClassification(name=name) for name in types]
                db.session.add(task)
                created += 1
            db.session.add(
                Attachment(
                    related_type="task_excel_upload",
                    related_id=None,
                    filename=file.filename,
                    content_type=file.content_type,
                    file_data=raw,
                    uploader_id=current_user.id,
                )
            )
            audit("TASK_EXCEL_UPLOAD", file.filename, {"created": created})
            db.session.commit()
            flash(f"엑셀에서 업무 {created}건을 등록했습니다.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"엑셀 등록 실패: {exc}", "danger")
        return redirect(url_for("task_list"))

    @app.get("/calendar")
    @login_required
    def task_calendar():
        today = date.today()
        year = request.args.get("year", today.year, type=int)
        month = request.args.get("month", today.month, type=int)
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        tasks = db.session.scalars(
            visible_task_query(current_user).where(Task.target_date.between(first, last)).order_by(Task.target_date)
        ).all()
        schedules_query = select(Schedule).where(Schedule.schedule_date.between(first, last))
        if current_user.role.data_scope != "all":
            schedules_query = schedules_query.where(
                or_(Schedule.scope == "전사", Schedule.department_id == current_user.department_id, Schedule.assignee_id == current_user.id)
            )
        schedules = db.session.scalars(schedules_query.order_by(Schedule.schedule_date)).all()
        day_items = {}
        for task in tasks:
            day_items.setdefault(task.target_date, []).append(("task", task))
        for schedule in schedules:
            day_items.setdefault(schedule.schedule_date, []).append(("schedule", schedule))
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
        previous = first - timedelta(days=1)
        next_month = last + timedelta(days=1)
        return render_template("calendar.html", year=year, month=month, weeks=weeks, day_items=day_items, previous=previous, next_month=next_month)

    @app.route("/meetings", methods=["GET", "POST"])
    @login_required
    def meetings():
        if request.method == "POST":
            task_ids = [int(item) for item in request.form.getlist("task_ids")]
            meeting_date = date.fromisoformat(request.form.get("meeting_date", date.today().isoformat()))
            selected_tasks = db.session.scalars(visible_task_query(current_user).where(Task.id.in_(task_ids))).all() if task_ids else []
            if not selected_tasks:
                flash("회의에 등록할 주요 업무를 선택해 주세요.", "danger")
            else:
                meeting = DailyMeeting(
                    meeting_date=meeting_date,
                    author_id=current_user.id,
                    department_id=current_user.department_id,
                    tasks=selected_tasks,
                )
                db.session.add(meeting)
                db.session.flush()
                audit("MEETING_CREATE", f"meeting:{meeting.id}", {"task_count": len(selected_tasks)})
                db.session.commit()
                return redirect(url_for("meeting_detail", meeting_id=meeting.id))
        candidate_tasks = db.session.scalars(
            visible_task_query(current_user)
            .join(TaskClassification)
            .where(TaskClassification.name == "주요", Task.status != "완료")
            .order_by(Task.target_date)
        ).all()
        meeting_rows = db.session.scalars(select(DailyMeeting).order_by(DailyMeeting.meeting_date.desc(), DailyMeeting.id.desc()).limit(50)).all()
        if current_user.role.data_scope != "all":
            meeting_rows = [row for row in meeting_rows if row.department_id == current_user.department_id or row.author_id == current_user.id]
        return render_template("meetings.html", mode="list", candidate_tasks=candidate_tasks, meetings=meeting_rows)

    @app.get("/meetings/<int:meeting_id>")
    @login_required
    def meeting_detail(meeting_id):
        meeting = db.get_or_404(DailyMeeting, meeting_id)
        if current_user.role.data_scope != "all" and meeting.department_id != current_user.department_id:
            abort(403)
        return render_template("meetings.html", mode="detail", meeting=meeting)

    @app.get("/journals")
    @login_required
    def journals():
        work_date = date.fromisoformat(request.args.get("work_date", date.today().isoformat()))
        employee_id = request.args.get("employee_id", current_user.id, type=int)
        if current_user.role.data_scope == "own":
            employee_id = current_user.id
        elif current_user.role.data_scope == "department":
            employee = db.session.get(Employee, employee_id)
            if not employee or employee.department_id != current_user.department_id:
                employee_id = current_user.id
        employee = db.get_or_404(Employee, employee_id)
        logs = db.session.scalars(
            select(TaskDailyLog)
            .join(Task)
            .where(TaskDailyLog.work_date == work_date, or_(Task.assignee_id == employee_id, TaskDailyLog.author_id == employee_id))
            .order_by(TaskDailyLog.created_at)
        ).all()
        tasks = db.session.scalars(
            select(Task)
            .join(TaskClassification)
            .where(Task.assignee_id == employee_id, TaskClassification.name.in_(["주요", "개인"]), Task.start_date <= work_date, Task.target_date >= work_date)
            .distinct()
            .order_by(Task.target_date)
        ).all()
        employees_query = select(Employee).where(Employee.status == "재직")
        if current_user.role.data_scope == "department":
            employees_query = employees_query.where(Employee.department_id == current_user.department_id)
        elif current_user.role.data_scope == "own":
            employees_query = employees_query.where(Employee.id == current_user.id)
        employees = db.session.scalars(employees_query.order_by(Employee.name)).all()
        return render_template("journals.html", work_date=work_date, employee=employee, employees=employees, tasks=tasks, logs=logs)

    @app.route("/admin/<section>", methods=["GET", "POST"])
    @admin_required("admin")
    def admin(section):
        allowed = {"employees", "roles", "menus", "boards", "schedules", "departments", "audits"}
        if section not in allowed:
            abort(404)
        if request.method == "POST":
            try:
                handle_admin_post(section)
                db.session.commit()
                flash("관리자 설정이 저장되었습니다.", "success")
            except (ValueError, IntegrityError) as exc:
                db.session.rollback()
                flash(f"저장할 수 없습니다: {exc}", "danger")
            return redirect(url_for("admin", section=section))
        data = load_admin_data(section)
        return render_template("admin.html", section=section, **data)

    def handle_admin_post(section):
        action = request.form.get("action", "create")
        if section == "employees":
            if action in {"terminate", "reactivate"}:
                employee = db.get_or_404(Employee, int(request.form["employee_id"]))
                if employee.id == current_user.id and action == "terminate":
                    raise ValueError("현재 로그인한 관리자 계정은 종료할 수 없습니다.")
                employee.status = "퇴사" if action == "terminate" else "재직"
                employee.termination_date = date.today() if action == "terminate" else None
                employee.reregistered_at = utcnow() if action == "reactivate" else employee.reregistered_at
                audit("EMPLOYEE_TERMINATE" if action == "terminate" else "EMPLOYEE_REACTIVATE", f"employee:{employee.id}")
                return
            password = request.form.get("password", "")
            if len(password) < 10:
                raise ValueError("초기 비밀번호는 10자 이상이어야 합니다.")
            employee = Employee(
                name=request.form["name"].strip(),
                employee_no=request.form.get("employee_no", "").strip() or None,
                department_id=int(request.form["department_id"]),
                position=request.form.get("position", "").strip(),
                email=request.form.get("email", "").strip() or None,
                phone=request.form.get("phone", "").strip() or None,
                login_id=request.form["login_id"].strip(),
                role_id=int(request.form["role_id"]),
                status="재직",
                hire_date=date.fromisoformat(request.form["hire_date"]) if request.form.get("hire_date") else date.today(),
                password_hash="",
                must_change_password=True,
            )
            employee.set_password(password)
            db.session.add(employee)
            db.session.flush()
            audit("EMPLOYEE_CREATE", f"employee:{employee.id}")
        elif section == "roles":
            permissions = {name: True for name in request.form.getlist("permissions")}
            role = Role(name=request.form["name"].strip(), data_scope=request.form["data_scope"], permissions=permissions)
            db.session.add(role)
            db.session.flush()
            audit("ROLE_CREATE", f"role:{role.id}")
        elif section == "menus":
            menu = Menu(
                name=request.form["name"].strip(),
                url=request.form.get("url", "#").strip(),
                sort_order=int(request.form.get("sort_order", 0)),
                parent_id=int(request.form["parent_id"]) if request.form.get("parent_id") else None,
            )
            menu.roles = db.session.scalars(select(Role).where(Role.id.in_([int(v) for v in request.form.getlist("role_ids")]))).all()
            db.session.add(menu)
            db.session.flush()
            audit("MENU_CREATE", f"menu:{menu.id}")
        elif section == "boards":
            board = Board(
                name=request.form["name"].strip(),
                board_type=request.form.get("board_type", "일반"),
                options={"allow_comments": request.form.get("allow_comments") == "on"},
            )
            board.roles = db.session.scalars(select(Role).where(Role.id.in_([int(v) for v in request.form.getlist("role_ids")]))).all()
            db.session.add(board)
            db.session.flush()
            audit("BOARD_CREATE", f"board:{board.id}")
        elif section == "schedules":
            schedule = Schedule(
                title=request.form["title"].strip(),
                schedule_date=date.fromisoformat(request.form["schedule_date"]),
                scope=request.form.get("scope", "전사"),
                department_id=int(request.form["department_id"]) if request.form.get("department_id") else None,
                assignee_id=int(request.form["assignee_id"]) if request.form.get("assignee_id") else None,
                memo=request.form.get("memo", "").strip(),
                is_holiday=request.form.get("is_holiday") == "on",
                created_by_id=current_user.id,
            )
            db.session.add(schedule)
            db.session.flush()
            audit("SCHEDULE_CREATE", f"schedule:{schedule.id}")
        elif section == "departments":
            department = Department(
                name=request.form["name"].strip(),
                parent_id=int(request.form["parent_id"]) if request.form.get("parent_id") else None,
            )
            db.session.add(department)
            db.session.flush()
            audit("DEPARTMENT_CREATE", f"department:{department.id}")

    def load_admin_data(section):
        common = {
            "roles": db.session.scalars(select(Role).order_by(Role.id)).all(),
            "departments": db.session.scalars(select(Department).order_by(Department.id)).all(),
            "employees": db.session.scalars(select(Employee).order_by(Employee.status, Employee.name)).all(),
        }
        if section == "menus":
            common["menus"] = db.session.scalars(select(Menu).order_by(Menu.sort_order)).all()
        elif section == "boards":
            common["boards"] = db.session.scalars(select(Board).order_by(Board.name)).all()
        elif section == "schedules":
            common["schedules"] = db.session.scalars(select(Schedule).order_by(Schedule.schedule_date.desc()).limit(100)).all()
        elif section == "audits":
            common["audits"] = db.session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()
        return common

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="이 화면을 볼 권한이 없습니다."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="요청한 화면을 찾을 수 없습니다."), 404

    return app


app = create_app()
run_startup_tasks(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
