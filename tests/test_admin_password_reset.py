import os
import unittest
from datetime import timedelta

from werkzeug.security import generate_password_hash


os.environ.setdefault("ALLOW_IN_MEMORY_DB", "1")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD_HASH", generate_password_hash("StartupAdmin123", method="scrypt"))

from app import (  # noqa: E402
    ACCOUNT_LOCK_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
    AuditLog,
    Department,
    Employee,
    Role,
    TEMP_PASSWORD_MIN_LENGTH,
    create_app,
    db,
    utcnow,
)


class AdminPasswordResetTests(unittest.TestCase):
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

        department = Department(name="보안전산팀", active=True)
        admin_role = Role(name="관리자", data_scope="all", permissions={}, is_system=True)
        employee_role = Role(name="임직원", data_scope="own", permissions={}, is_system=True)
        db.session.add_all([department, admin_role, employee_role])
        db.session.flush()

        self.admin = Employee(
            name="관리자",
            department=department,
            position="팀장",
            login_id="admin1",
            password_hash="",
            status="재직",
            role=admin_role,
            must_change_password=False,
        )
        self.employee = Employee(
            name="잠금사용자",
            department=department,
            position="팀원",
            login_id="member1",
            password_hash="",
            status="재직",
            role=employee_role,
            failed_login_count=4,
            locked_until=utcnow() + timedelta(minutes=10),
            must_change_password=False,
        )
        self.admin.set_password("AdminPass123")
        self.employee.set_password("MemberPass123")
        db.session.add_all([self.admin, self.employee])
        db.session.commit()
        self.admin_id = self.admin.id
        self.employee_id = self.employee.id
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, login_id, password):
        return self.client.post("/login", data={"login_id": login_id, "password": password})

    def test_admin_reset_changes_password_unlocks_account_and_requires_change(self):
        self.assertEqual(self.login("admin1", "AdminPass123").status_code, 302)

        page = self.client.get("/admin/employees")
        self.assertEqual(page.status_code, 200)
        self.assertIn("비밀번호 초기화 및 잠금 해제".encode(), page.data)

        response = self.client.post(
            "/admin/employees",
            data={
                "action": "password_reset",
                "employee_id": self.employee_id,
                "new_password": "Temp1234",
                "confirm_password": "Temp1234",
            },
        )
        self.assertEqual(response.status_code, 302)

        employee = db.session.get(Employee, self.employee_id)
        self.assertTrue(employee.check_password("Temp1234"))
        self.assertEqual(employee.failed_login_count, 0)
        self.assertIsNone(employee.locked_until)
        self.assertTrue(employee.must_change_password)
        audit = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "EMPLOYEE_PASSWORD_RESET",
                AuditLog.target == f"employee:{self.employee_id}",
            )
        )
        self.assertIsNotNone(audit)
        self.assertNotIn("Temp1234", str(audit.details))

        self.client.post("/logout")
        self.assertEqual(self.login("member1", "Temp1234").status_code, 302)
        redirect_response = self.client.get("/")
        self.assertEqual(redirect_response.status_code, 302)
        self.assertIn("/change-password", redirect_response.location)

    def test_non_admin_cannot_reset_password(self):
        employee = db.session.get(Employee, self.employee_id)
        employee.locked_until = None
        employee.failed_login_count = 0
        db.session.commit()
        self.assertEqual(self.login("member1", "MemberPass123").status_code, 302)
        response = self.client.post(
            "/admin/employees",
            data={
                "action": "password_reset",
                "employee_id": self.admin_id,
                "new_password": "ChangedPass123",
                "confirm_password": "ChangedPass123",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(db.session.get(Employee, self.admin_id).check_password("AdminPass123"))

    def test_five_failures_lock_account_for_fifteen_minutes(self):
        employee = db.session.get(Employee, self.employee_id)
        employee.locked_until = None
        employee.failed_login_count = 0
        db.session.commit()

        for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
            response = self.login("member1", "WrongPassword123")
            self.assertEqual(response.status_code, 401)

        employee = db.session.get(Employee, self.employee_id)
        self.assertIsNotNone(employee.locked_until)
        remaining = employee.locked_until.replace(tzinfo=None) - utcnow().replace(tzinfo=None)
        self.assertGreater(remaining.total_seconds(), (ACCOUNT_LOCK_MINUTES - 1) * 60)
        self.assertEqual(self.login("member1", "MemberPass123").status_code, 429)

    def test_invalid_reset_does_not_change_password_or_unlock(self):
        self.assertEqual(self.login("admin1", "AdminPass123").status_code, 302)
        response = self.client.post(
            "/admin/employees",
            data={
                "action": "password_reset",
                "employee_id": self.employee_id,
                "new_password": "Temporary123",
                "confirm_password": "Different123",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("일치하지 않습니다".encode(), response.data)
        employee = db.session.get(Employee, self.employee_id)
        self.assertTrue(employee.check_password("MemberPass123"))
        self.assertIsNotNone(employee.locked_until)

    def test_seven_character_temporary_password_is_rejected(self):
        self.assertEqual(TEMP_PASSWORD_MIN_LENGTH, 8)
        self.assertEqual(self.login("admin1", "AdminPass123").status_code, 302)
        response = self.client.post(
            "/admin/employees",
            data={
                "action": "password_reset",
                "employee_id": self.employee_id,
                "new_password": "Temp123",
                "confirm_password": "Temp123",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("8자 이상".encode(), response.data)
        employee = db.session.get(Employee, self.employee_id)
        self.assertTrue(employee.check_password("MemberPass123"))
        self.assertIsNotNone(employee.locked_until)


if __name__ == "__main__":
    unittest.main()
