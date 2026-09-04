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
    DailyMeeting,
    Department,
    Employee,
    Role,
    Task,
    TaskClassification,
    create_app,
    db,
)


class DailyMeetingDocumentTests(unittest.TestCase):
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

        self.department = Department(name="경영기획팀", active=True)
        self.admin_role = Role(
            name="관리자",
            data_scope="all",
            permissions={"task_manage_all": True},
            is_system=True,
        )
        db.session.add_all([self.department, self.admin_role])
        db.session.flush()
        self.admin = Employee(
            name="관리자",
            department=self.department,
            position="부서장",
            login_id="admin1",
            password_hash="",
            status="재직",
            approval_status="승인완료",
            role=self.admin_role,
            must_change_password=False,
        )
        self.admin.set_password("AdminPass123")
        db.session.add(self.admin)
        db.session.flush()
        self.task = Task(
            title="채용 프로세스 정비",
            content="신규 채용 진행사항 점검",
            department=self.department,
            assignee=self.admin,
            start_date=date(2026, 9, 4),
            target_date=date(2026, 9, 11),
            status="진행중",
            progress=20,
            repeat_cycle="없음",
            creator=self.admin,
        )
        self.task.classifications.append(TaskClassification(name="주요"))
        db.session.add(self.task)
        db.session.commit()
        self.client = self.app.test_client()
        self.client.post("/login", data={"login_id": "admin1", "password": "AdminPass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_list_offers_agenda_and_minutes_writing_modes(self):
        response = self.client.get("/meetings")
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="agenda"'.encode(), response.data)
        self.assertIn('value="minutes"'.encode(), response.data)
        self.assertIn("일일 회의 아젠다".encode(), response.data)
        self.assertIn("일일 회의 회의록".encode(), response.data)

    def test_agenda_can_be_created_without_related_task(self):
        response = self.client.post(
            "/meetings",
            data={
                "document_type": "agenda",
                "meeting_date": "2026-09-04",
                "title": "경영사업본부 아침 회의 아젠다",
                "agenda_content": "1. 채용 진행현황\n2. 자금 집행계획",
            },
        )
        self.assertEqual(response.status_code, 302)
        meeting = db.session.scalar(db.select(DailyMeeting))
        self.assertEqual(meeting.document_type, "agenda")
        self.assertEqual(meeting.agenda_content, "1. 채용 진행현황\n2. 자금 집행계획")
        self.assertEqual(meeting.tasks, [])
        detail = self.client.get(response.headers["Location"])
        self.assertIn("회의 안건 및 사전 공유사항".encode(), detail.data)
        self.assertIn(b"data-download-image", detail.data)
        self.assertIn(b"window.print()", detail.data)

    def test_minutes_can_be_created_with_written_sections_and_task(self):
        response = self.client.post(
            "/meetings",
            data={
                "document_type": "minutes",
                "meeting_date": "2026-09-04",
                "title": "9월 4일 일일 회의록",
                "discussion_notes": "채용 일정과 담당자를 논의함",
                "decisions": "공고를 금일까지 게시",
                "action_items": "김영재: 공고 검토 / 9월 4일",
                "task_ids": [str(self.task.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        meeting = db.session.scalar(db.select(DailyMeeting))
        self.assertEqual(meeting.document_type, "minutes")
        self.assertEqual(meeting.tasks, [self.task])
        detail = self.client.get(response.headers["Location"])
        self.assertIn("주요 논의사항".encode(), detail.data)
        self.assertIn("결정사항".encode(), detail.data)
        self.assertIn("후속 조치사항".encode(), detail.data)
        self.assertIn(self.task.title.encode(), detail.data)

    def test_document_can_be_edited_and_audited(self):
        meeting = DailyMeeting(
            meeting_date=date(2026, 9, 4),
            document_type="agenda",
            title="수정 전 아젠다",
            agenda_content="수정 전 내용",
            author=self.admin,
            department=self.department,
        )
        db.session.add(meeting)
        db.session.commit()

        response = self.client.post(
            f"/meetings/{meeting.id}/edit",
            data={
                "document_type": "minutes",
                "meeting_date": "2026-09-05",
                "title": "수정된 회의록",
                "discussion_notes": "수정된 논의내용",
                "decisions": "수정된 결정사항",
                "action_items": "후속 조치",
            },
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(meeting)
        self.assertEqual(meeting.document_type, "minutes")
        self.assertIsNone(meeting.agenda_content)
        self.assertEqual(meeting.decisions, "수정된 결정사항")
        log = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "MEETING_UPDATE",
                AuditLog.target == f"meeting:{meeting.id}",
            )
        )
        self.assertIsNotNone(log)

    def test_empty_document_is_not_created(self):
        response = self.client.post(
            "/meetings",
            data={"document_type": "agenda", "meeting_date": "2026-09-04"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.session.scalar(db.select(db.func.count(DailyMeeting.id))), 0)
        self.assertIn("회의 내용 또는 관련 주요업무".encode(), response.data)

    def test_png_export_uses_local_browser_rendering(self):
        with self.client.get("/static/app.js") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"downloadElementAsPng", response.data)
            self.assertIn(b'canvas.toBlob', response.data)
            self.assertNotIn(b"https://", response.data)


if __name__ == "__main__":
    unittest.main()
