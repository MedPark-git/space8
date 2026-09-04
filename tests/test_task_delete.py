import os
import unittest
from datetime import date

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
    Task,
    TaskClassification,
    TaskDailyLog,
    create_app,
    db,
)


class TaskDeleteTests(unittest.TestCase):
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

        self.security = Department(name="보안전산팀", active=True)
        self.finance = Department(name="재무운영팀", active=True)
        roles = {
            "관리자": Role(
                name="관리자",
                data_scope="all",
                permissions={"task_manage_all": True},
                is_system=True,
            ),
            "부서장": Role(
                name="부서장",
                data_scope="all",
                permissions={"task_manage_department": True},
                is_system=True,
            ),
            "팀장": Role(
                name="팀장",
                data_scope="all",
                permissions={"task_manage_department": True},
                is_system=True,
            ),
            "팀원": Role(
                name="팀원",
                data_scope="department",
                permissions={"task_manage_department": True},
                is_system=True,
            ),
        }
        db.session.add_all([self.security, self.finance, *roles.values()])
        db.session.flush()

        self.users = {}
        for login_id, name, department, role_name in (
            ("admin1", "관리자", self.finance, "관리자"),
            ("head1", "보안 부서장", self.security, "부서장"),
            ("lead1", "보안 팀장", self.security, "팀장"),
            ("member1", "보안 팀원", self.security, "팀원"),
            ("member2", "보안 팀원2", self.security, "팀원"),
            ("financelead", "재무 팀장", self.finance, "팀장"),
        ):
            employee = Employee(
                name=name,
                department=department,
                position=role_name if role_name != "관리자" else "부서장",
                login_id=login_id,
                password_hash="",
                status="재직",
                role=roles[role_name],
                must_change_password=False,
            )
            employee.set_password("UserPass123")
            db.session.add(employee)
            self.users[login_id] = employee
        db.session.flush()

        self.security_task = self.create_task("보안 삭제 대상", self.security, self.users["member1"])
        self.finance_task = self.create_task("재무 삭제 대상", self.finance, self.users["financelead"])
        db.session.add(
            TaskDailyLog(
                task=self.security_task,
                work_date=date.today(),
                content="삭제 전 업무 기록",
                author=self.users["member1"],
            )
        )
        db.session.commit()
        self.security_task_id = self.security_task.id
        self.finance_task_id = self.finance_task.id
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_task(self, title, department, assignee):
        task = Task(
            title=title,
            content="업무 내용",
            department=department,
            assignee=assignee,
            start_date=date.today(),
            target_date=date.today(),
            status="진행중",
            progress=0,
            repeat_cycle="없음",
            creator=self.users["admin1"],
        )
        task.classifications.append(TaskClassification(name="일반"))
        db.session.add(task)
        db.session.flush()
        return task

    def login(self, login_id):
        self.client.post("/logout")
        response = self.client.post(
            "/login",
            data={"login_id": login_id, "password": "UserPass123"},
        )
        self.assertEqual(response.status_code, 302)

    def test_team_lead_can_soft_delete_own_department_task_and_history_is_preserved(self):
        self.login("lead1")
        page = self.client.get("/tasks")
        self.assertIn(f'/tasks/{self.security_task_id}/delete'.encode(), page.data)
        self.assertNotIn(f'/tasks/{self.finance_task_id}/delete'.encode(), page.data)

        response = self.client.post(
            f"/tasks/{self.security_task_id}/delete",
            data={"return_to": "/tasks"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        task = db.session.get(Task, self.security_task_id)
        self.assertIsNotNone(task)
        self.assertIsNotNone(task.deleted_at)
        self.assertEqual(task.deleted_by_id, self.users["lead1"].id)
        self.assertEqual(
            db.session.scalar(
                db.select(db.func.count(TaskDailyLog.id)).where(
                    TaskDailyLog.task_id == self.security_task_id
                )
            ),
            1,
        )
        self.assertNotIn("보안 삭제 대상".encode(), response.data)
        self.assertEqual(self.client.get(f"/tasks/{self.security_task_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/tasks/{self.security_task_id}/edit").status_code, 404)
        audit = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "TASK_DELETE",
                AuditLog.target == f"task:{self.security_task_id}",
            )
        )
        self.assertIsNotNone(audit)
        self.assertTrue(audit.details["history_preserved"])

    def test_department_head_can_delete_own_department_task(self):
        self.login("head1")
        response = self.client.post(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_admin_can_delete_another_department_task(self):
        self.login("admin1")
        response = self.client.post(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_team_member_cannot_delete_even_with_department_manage_permission(self):
        self.login("member1")
        page = self.client.get("/tasks")
        self.assertNotIn(f'/tasks/{self.security_task_id}/delete'.encode(), page.data)
        response = self.client.post(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_team_lead_cannot_delete_another_department_task(self):
        self.login("lead1")
        response = self.client.post(f"/tasks/{self.finance_task_id}/delete")
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Task, self.finance_task_id).deleted_at)

    def test_delete_endpoint_rejects_get_requests(self):
        self.login("admin1")
        response = self.client.get(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 405)

    def test_member_can_bulk_add_major_without_removing_existing_classification(self):
        self.login("member1")
        response = self.client.post(
            "/tasks/bulk-major",
            data={"task_ids": [str(self.security_task_id)], "return_to": "/tasks"},
        )

        self.assertEqual(response.status_code, 302)
        task = db.session.get(Task, self.security_task_id)
        self.assertEqual(set(task.type_names), {"일반", "주요"})
        self.assertTrue(task.calendar_auto_included)
        audit = db.session.scalar(
            db.select(AuditLog).where(AuditLog.action == "TASK_BULK_MAJOR_ADD")
        )
        self.assertEqual(audit.details["added_task_ids"], [self.security_task_id])

    def test_bulk_major_is_idempotent(self):
        self.login("member1")
        payload = {"task_ids": [str(self.security_task_id)]}
        self.assertEqual(self.client.post("/tasks/bulk-major", data=payload).status_code, 302)
        self.assertEqual(self.client.post("/tasks/bulk-major", data=payload).status_code, 302)

        task = db.session.get(Task, self.security_task_id)
        self.assertEqual(task.type_names.count("주요"), 1)

    def test_department_manager_cannot_bulk_add_major_to_another_department(self):
        self.login("lead1")
        response = self.client.post(
            "/tasks/bulk-major",
            data={"task_ids": [str(self.finance_task_id)]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("주요", db.session.get(Task, self.finance_task_id).type_names)

    def test_member_can_bulk_register_task_in_calendar(self):
        self.login("member1")
        response = self.client.post(
            "/tasks/bulk-calendar",
            data={"task_ids": [str(self.security_task_id)], "return_to": "/tasks"},
        )

        self.assertEqual(response.status_code, 302)
        task = db.session.get(Task, self.security_task_id)
        self.assertTrue(task.calendar_selected)
        self.assertTrue(task.calendar_included)
        audit = db.session.scalar(
            db.select(AuditLog).where(AuditLog.action == "TASK_BULK_CALENDAR_ADD")
        )
        self.assertEqual(audit.details["registered_task_ids"], [self.security_task_id])

    def test_bulk_calendar_registration_is_idempotent(self):
        self.login("member1")
        payload = {"task_ids": [str(self.security_task_id)]}
        self.assertEqual(self.client.post("/tasks/bulk-calendar", data=payload).status_code, 302)
        self.assertEqual(self.client.post("/tasks/bulk-calendar", data=payload).status_code, 302)
        self.assertTrue(db.session.get(Task, self.security_task_id).calendar_selected)

    def test_department_manager_cannot_bulk_register_other_department_calendar(self):
        self.login("lead1")
        response = self.client.post(
            "/tasks/bulk-calendar",
            data={"task_ids": [str(self.finance_task_id)]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(db.session.get(Task, self.finance_task_id).calendar_selected)

    def test_member_can_remove_manually_registered_task_from_calendar(self):
        task = db.session.get(Task, self.security_task_id)
        task.calendar_selected = True
        task.calendar_registered_by_id = self.users["member1"].id
        db.session.commit()
        self.login("member1")

        response = self.client.post(
            "/tasks/bulk-calendar-remove",
            data={"task_ids": [str(self.security_task_id)], "return_to": "/tasks"},
        )

        self.assertEqual(response.status_code, 302)
        task = db.session.get(Task, self.security_task_id)
        self.assertFalse(task.calendar_selected)
        self.assertTrue(task.calendar_excluded)
        self.assertFalse(task.calendar_included)
        audit = db.session.scalar(
            db.select(AuditLog).where(AuditLog.action == "TASK_BULK_CALENDAR_REMOVE")
        )
        self.assertEqual(audit.details["removed_task_ids"], [self.security_task_id])
        self.assertTrue(audit.details["tasks_preserved"])

    def test_major_and_executive_tasks_can_be_removed_from_calendar(self):
        major_task = db.session.get(Task, self.security_task_id)
        major_task.created_by_id = self.users["member1"].id
        major_task.classifications.append(TaskClassification(name="주요"))
        executive_task = self.create_task("대표이사 수명 캘린더 삭제", self.security, self.users["member1"])
        executive_task.created_by_id = self.users["member1"].id
        executive_task.classifications.append(TaskClassification(name="대표이사님 수명업무"))
        db.session.commit()
        executive_task_id = executive_task.id
        self.assertTrue(major_task.calendar_included)
        self.assertTrue(executive_task.calendar_included)
        self.login("member1")

        response = self.client.post(
            "/tasks/bulk-calendar-remove",
            data={"task_ids": [str(self.security_task_id), str(executive_task_id)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(db.session.get(Task, self.security_task_id).calendar_included)
        self.assertFalse(db.session.get(Task, executive_task_id).calendar_included)
        calendar_page = self.client.get("/calendar")
        self.assertNotIn("보안 삭제 대상".encode(), calendar_page.data)
        self.assertNotIn("대표이사 수명 캘린더 삭제".encode(), calendar_page.data)

    def test_team_member_cannot_remove_another_members_calendar_registration(self):
        task = db.session.get(Task, self.security_task_id)
        task.calendar_selected = True
        task.calendar_registered_by_id = self.users["member1"].id
        db.session.commit()
        self.login("member2")

        response = self.client.post(
            "/tasks/bulk-calendar-remove",
            data={"task_ids": [str(self.security_task_id)]},
        )

        self.assertEqual(response.status_code, 403)
        task = db.session.get(Task, self.security_task_id)
        self.assertTrue(task.calendar_included)
        self.assertEqual(task.calendar_registered_by_id, self.users["member1"].id)

    def test_calendar_page_shows_delete_icon_for_own_task_registration(self):
        task = db.session.get(Task, self.security_task_id)
        task.calendar_selected = True
        task.calendar_registered_by_id = self.users["member1"].id
        db.session.commit()
        self.login("member1")

        page = self.client.get("/calendar")
        action = f'/calendar/tasks/{self.security_task_id}/remove'.encode()
        self.assertIn(action, page.data)
        response = self.client.post(
            f"/calendar/tasks/{self.security_task_id}/remove",
            data={"return_to": "/calendar"},
        )

        self.assertEqual(response.status_code, 302)
        task = db.session.get(Task, self.security_task_id)
        self.assertFalse(task.calendar_included)
        self.assertTrue(task.calendar_excluded)
        self.assertIsNotNone(
            db.session.scalar(
                db.select(AuditLog).where(AuditLog.action == "TASK_CALENDAR_REMOVE")
            )
        )

    def test_calendar_legend_is_above_month_navigation(self):
        self.login("member1")
        page = self.client.get("/calendar")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data.count(b'class="calendar-legend"'), 1)
        self.assertLess(
            page.data.index(b'class="calendar-legend"'),
            page.data.index(b'class="calendar-head"'),
        )
        self.assertIn("일정 상태 색상 안내".encode(), page.data)

    def test_calendar_page_hides_delete_icon_and_blocks_other_team_member(self):
        task = db.session.get(Task, self.security_task_id)
        task.calendar_selected = True
        task.calendar_registered_by_id = self.users["member1"].id
        db.session.commit()
        self.login("member2")

        page = self.client.get("/calendar")
        action = f'/calendar/tasks/{self.security_task_id}/remove'.encode()
        self.assertNotIn(action, page.data)
        response = self.client.post(f"/calendar/tasks/{self.security_task_id}/remove")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(db.session.get(Task, self.security_task_id).calendar_included)

    def test_schedule_creator_can_soft_delete_from_calendar_page(self):
        schedule = Schedule(
            title="팀원 등록 일정",
            schedule_date=date.today(),
            department_id=self.security.id,
            assignee_id=self.users["member1"].id,
            scope="개인",
            memo="삭제 테스트",
            created_by_id=self.users["member1"].id,
        )
        db.session.add(schedule)
        db.session.commit()
        schedule_id = schedule.id
        self.login("member1")

        page = self.client.get("/calendar")
        action = f'/calendar/schedules/{schedule_id}/delete'.encode()
        self.assertIn(action, page.data)
        response = self.client.post(
            f"/calendar/schedules/{schedule_id}/delete",
            data={"return_to": "/calendar"},
        )

        self.assertEqual(response.status_code, 302)
        schedule = db.session.get(Schedule, schedule_id)
        self.assertIsNotNone(schedule.deleted_at)
        self.assertEqual(schedule.deleted_by_id, self.users["member1"].id)
        self.assertNotIn("팀원 등록 일정".encode(), self.client.get("/calendar").data)
        audit = db.session.scalar(
            db.select(AuditLog).where(AuditLog.action == "SCHEDULE_DELETE")
        )
        self.assertTrue(audit.details["history_preserved"])

    def test_team_member_cannot_delete_another_creators_registered_schedule(self):
        schedule = Schedule(
            title="다른 팀원 등록 일정",
            schedule_date=date.today(),
            department_id=self.security.id,
            assignee_id=self.users["member1"].id,
            scope="개인",
            created_by_id=self.users["member1"].id,
        )
        db.session.add(schedule)
        db.session.commit()
        schedule_id = schedule.id
        self.login("member2")

        page = self.client.get("/calendar")
        self.assertNotIn(f'/calendar/schedules/{schedule_id}/delete'.encode(), page.data)
        response = self.client.post(f"/calendar/schedules/{schedule_id}/delete")

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Schedule, schedule_id).deleted_at)

    def test_removed_auto_calendar_task_can_be_registered_again(self):
        task = db.session.get(Task, self.security_task_id)
        task.classifications.append(TaskClassification(name="주요"))
        task.calendar_excluded = True
        db.session.commit()
        self.login("member1")

        response = self.client.post(
            "/tasks/bulk-calendar",
            data={"task_ids": [str(self.security_task_id)]},
        )

        self.assertEqual(response.status_code, 302)
        task = db.session.get(Task, self.security_task_id)
        self.assertFalse(task.calendar_excluded)
        self.assertFalse(task.calendar_selected)
        self.assertTrue(task.calendar_included)
        self.assertEqual(task.calendar_registration_label, "자동 등록")

    def test_department_manager_cannot_remove_other_department_calendar(self):
        finance_task = db.session.get(Task, self.finance_task_id)
        finance_task.calendar_selected = True
        db.session.commit()
        self.login("lead1")

        response = self.client.post(
            "/tasks/bulk-calendar-remove",
            data={"task_ids": [str(self.finance_task_id)]},
        )

        self.assertEqual(response.status_code, 403)
        finance_task = db.session.get(Task, self.finance_task_id)
        self.assertTrue(finance_task.calendar_selected)
        self.assertFalse(finance_task.calendar_excluded)

    def test_team_lead_can_delete_major_and_executive_tasks(self):
        major_task = db.session.get(Task, self.security_task_id)
        major_task.classifications.append(TaskClassification(name="주요"))
        executive_task = self.create_task("대표이사 수명 삭제 대상", self.security, self.users["member1"])
        executive_task.classifications.append(TaskClassification(name="대표이사님 수명업무"))
        db.session.commit()
        executive_task_id = executive_task.id
        self.login("lead1")

        response = self.client.post(
            "/tasks/bulk-delete",
            data={"task_ids": [str(self.security_task_id), str(executive_task_id)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Task, self.security_task_id).deleted_at)
        self.assertIsNotNone(db.session.get(Task, executive_task_id).deleted_at)

    def test_team_lead_can_bulk_delete_own_department_tasks(self):
        extra_task = self.create_task("보안 일괄 삭제 대상", self.security, self.users["member1"])
        db.session.commit()
        extra_task_id = extra_task.id
        self.login("lead1")

        response = self.client.post(
            "/tasks/bulk-delete",
            data={"task_ids": [str(self.security_task_id), str(extra_task_id)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Task, self.security_task_id).deleted_at)
        self.assertIsNotNone(db.session.get(Task, extra_task_id).deleted_at)
        self.assertEqual(
            db.session.scalar(
                db.select(db.func.count(AuditLog.id)).where(AuditLog.action == "TASK_DELETE")
            ),
            2,
        )
        bulk_audit = db.session.scalar(
            db.select(AuditLog).where(AuditLog.action == "TASK_BULK_DELETE")
        )
        self.assertEqual(bulk_audit.details["deleted"], 2)
        self.assertTrue(bulk_audit.details["history_preserved"])

    def test_bulk_delete_rejects_mixed_departments_without_partial_delete(self):
        self.login("lead1")
        response = self.client.post(
            "/tasks/bulk-delete",
            data={"task_ids": [str(self.security_task_id), str(self.finance_task_id)]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Task, self.security_task_id).deleted_at)
        self.assertIsNone(db.session.get(Task, self.finance_task_id).deleted_at)

    def test_member_cannot_bulk_delete_tasks(self):
        self.login("member1")
        response = self.client.post(
            "/tasks/bulk-delete",
            data={"task_ids": [str(self.security_task_id)]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_task_list_shows_bulk_actions_by_permission(self):
        self.login("admin1")
        admin_page = self.client.get("/tasks")
        self.assertIn(b'data-bulk-calendar', admin_page.data)
        self.assertIn(b'data-bulk-calendar-remove', admin_page.data)
        self.assertIn(b'data-bulk-major', admin_page.data)
        self.assertIn(b'data-bulk-delete', admin_page.data)

        self.login("member1")
        member_page = self.client.get("/tasks")
        self.assertIn(b'data-bulk-calendar', member_page.data)
        self.assertIn(b'data-bulk-calendar-remove', member_page.data)
        self.assertIn(b'data-bulk-major', member_page.data)
        self.assertNotIn(b'data-bulk-delete', member_page.data)


if __name__ == "__main__":
    unittest.main()
