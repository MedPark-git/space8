# Management Task

경영사업본부 루틴업무·주요업무 현황 대시보드입니다.

## Runtime

- Python 3.11 / Flask
- PostgreSQL / SQLAlchemy / Alembic
- Gunicorn

AI SPACE가 주입하는 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`를 사용합니다.

최초 관리자 생성을 위해 첫 배포에만 `BOOTSTRAP_ADMIN_PASSWORD_HASH`를 설정합니다. 평문 비밀번호는 소스와 환경변수에 저장하지 않습니다.
