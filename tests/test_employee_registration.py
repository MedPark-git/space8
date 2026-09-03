import os
import unittest

from werkzeug.security import generate_password_hash


os.environ.setdefault("ALLOW_IN_MEMORY_DB", "1")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")
os.environ.setdefault(
    "BOOTSTRAP_ADMIN_PASSWORD_HASH",
    generate_password_hash("StartupAdmin123", method="scrypt"),
)

from app import (  # noqa: E402
    AuditLog,
    Department,
    Employee,
    Role,
    Schedule,
    create_app,
    db,
)


class EmployeeRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "WTF_CSRF_ENABLED": False,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.department = Department(name="보안전산팀", active=True)
        self.admin_role = Role(
            name="관리자",
            data_scope="all",
            permissions={"admin": True, "task_manage_all": True},
            is_system=True,
        )
        self.member_role = Role(
            name="팀원",
            data_scope="department",
            permissions={"task_manage_department": True},
            is_system=True,
        )
        db.session.add_all([self.department, self.admin_role, self.member_role])
        db.session.flush()

        self.admin = Employee(
            name="관리자",
            department=self.department,
            position="부서장",
            login_id="admin1",
            password_hash="",
            role=self.admin_role,
            status="재직",
            approval_status="승인완료",
            must_change_password=False,
        )
        self.member = Employee(
            name="기존팀원",
            department=self.department,
            position="팀원",
            login_id="member1",
            password_hash="",
            role=self.member_role,
            status="재직",
            approval_status="승인완료",
            must_change_password=False,
        )
        self.admin.set_password("AdminPass123")
        self.member.set_password("MemberPass123")
        db.session.add_all([self.admin, self.member])
        db.session.commit()
        self.admin_id = self.admin.id
        self.department_id = self.department.id
        self.admin_role_id = self.admin_role.id
        self.member_role_id = self.member_role.id
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def registration_payload(self, **overrides):
        payload = {
            "login_id": "newmember",
            "name": "신청직원",
            "department_id": str(self.department_id),
            "position": "팀원",
            "employee_no": "",
            "hire_date": "",
            "email": "",
            "phone": "",
            "password": "Register123",
            "confirm_password": "Register123",
        }
        payload.update(overrides)
        return payload

    def register(self, **overrides):
        return self.client.post("/register", data=self.registration_payload(**overrides))

    def login(self, login_id, password):
        return self.client.post("/login", data={"login_id": login_id, "password": password})

    def test_login_links_registration_and_mentions_amaranth_account(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("임직원 계정 등록 신청".encode(), response.data)
        self.assertIn("아마란스 계정".encode(), response.data)
        self.assertIn(b'href="/register"', response.data)

    def test_registration_hides_permission_and_forces_member_role(self):
        page = self.client.get("/register")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(b'name="role_id"', page.data)
        self.assertNotIn("권한".encode(), page.data)
        self.assertIn("입사일(선택)".encode(), page.data)
        self.assertIn("아마란스에서 사용하는 계정 ID".encode(), page.data)

        response = self.register(role_id=str(self.admin_role_id))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))

        employee = db.session.scalar(db.select(Employee).where(Employee.login_id == "newmember"))
        self.assertIsNotNone(employee)
        self.assertEqual(employee.role_id, self.member_role_id)
        self.assertEqual(employee.approval_status, "승인대기")
        self.assertIsNone(employee.hire_date)
        self.assertFalse(employee.must_change_password)
        self.assertIsNotNone(employee.approval_requested_at)
        audit = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "EMPLOYEE_REGISTRATION_REQUEST",
                AuditLog.target == f"employee:{employee.id}",
            )
        )
        self.assertIsNotNone(audit)
        self.assertIsNone(audit.user_id)

    def test_pending_account_cannot_login_until_admin_approves(self):
        self.assertEqual(self.register().status_code, 302)
        response = self.login("newmember", "Register123")
        self.assertEqual(response.status_code, 403)
        self.assertIn("관리자 승인 대기".encode(), response.data)

        self.assertEqual(self.login("admin1", "AdminPass123").status_code, 302)
        employee = db.session.scalar(db.select(Employee).where(Employee.login_id == "newmember"))
        response = self.client.post(
            "/admin/employees",
            data={"action": "approve", "employee_id": employee.id},
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(employee)
        self.assertEqual(employee.approval_status, "승인완료")
        self.assertEqual(employee.approved_by_id, self.admin_id)
        self.assertIsNotNone(employee.approved_at)
        audit = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "EMPLOYEE_REGISTRATION_APPROVE",
                AuditLog.target == f"employee:{employee.id}",
            )
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user_id, self.admin_id)

        self.client.post("/logout")
        self.assertEqual(self.login("newmember", "Register123").status_code, 302)

    def test_non_admin_cannot_approve_registration(self):
        self.assertEqual(self.register().status_code, 302)
        employee = db.session.scalar(db.select(Employee).where(Employee.login_id == "newmember"))
        self.assertEqual(self.login("member1", "MemberPass123").status_code, 302)
        response = self.client.post(
            "/admin/employees",
            data={"action": "approve", "employee_id": employee.id},
        )
        self.assertEqual(response.status_code, 403)
        db.session.refresh(employee)
        self.assertEqual(employee.approval_status, "승인대기")

    def test_admin_can_still_register_approved_account_without_hire_date(self):
        self.assertEqual(self.login("admin1", "AdminPass123").status_code, 302)
        response = self.client.post(
            "/admin/employees",
            data={
                "action": "create",
                "login_id": "directuser",
                "name": "직접등록",
                "employee_no": "",
                "department_id": str(self.department_id),
                "position": "팀원",
                "email": "",
                "role_id": str(self.member_role_id),
                "phone": "",
                "hire_date": "",
                "password": "DirectPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        employee = db.session.scalar(db.select(Employee).where(Employee.login_id == "directuser"))
        self.assertIsNotNone(employee)
        self.assertEqual(employee.approval_status, "승인완료")
        self.assertEqual(employee.approved_by_id, self.admin_id)
        self.assertIsNone(employee.hire_date)
        self.assertTrue(employee.must_change_password)

    def test_pending_account_is_not_available_as_task_or_schedule_assignee(self):
        self.assertEqual(self.register().status_code, 302)
        pending = db.session.scalar(db.select(Employee).where(Employee.login_id == "newmember"))
        self.assertEqual(self.login("admin1", "AdminPass123").status_code, 302)

        task_page = self.client.get("/tasks/new")
        self.assertEqual(task_page.status_code, 200)
        self.assertNotIn("신청직원".encode(), task_page.data)

        response = self.client.post(
            "/admin/schedules",
            data={
                "title": "승인 전 개인 일정",
                "schedule_date": "2026-09-03",
                "scope": "개인",
                "department_id": str(self.department_id),
                "assignee_id": str(pending.id),
                "memo": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("승인 완료된 재직 임직원".encode(), response.data)
        self.assertIsNone(
            db.session.scalar(db.select(Schedule).where(Schedule.title == "승인 전 개인 일정"))
        )

    def test_invalid_registration_does_not_create_account(self):
        response = self.register(password="short1", confirm_password="short1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("10자 이상".encode(), response.data)
        self.assertIsNone(db.session.scalar(db.select(Employee).where(Employee.login_id == "newmember")))


if __name__ == "__main__":
    unittest.main()
