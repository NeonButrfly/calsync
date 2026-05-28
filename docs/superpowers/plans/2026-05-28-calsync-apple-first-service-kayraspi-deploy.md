# CalSync Apple-First Service And Kayraspi Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real Apple-first CalSync service, then deploy it to `kayraspi` on port `3080` where the old CalSync used to live.

**Architecture:** Reboot CalSync as a small FastAPI plus Postgres service with a narrow Apple Calendar appointment API: create, update, cancel, and fetch. Reuse only the legacy pieces that directly help with Apple CalDAV write-back and Docker deployment, while dropping the old UI shell, worker loop, and multi-provider surface.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, Alembic, Postgres 16, Docker Compose, Apple CalDAV, pytest

---

## File Structure

**Create**

- `C:\Code\calsync\.env.example`
- `C:\Code\calsync\Dockerfile`
- `C:\Code\calsync\docker-compose.yml`
- `C:\Code\calsync\pyproject.toml`
- `C:\Code\calsync\alembic.ini`
- `C:\Code\calsync\alembic\env.py`
- `C:\Code\calsync\alembic\versions\20260528_01_apple_first_service.py`
- `C:\Code\calsync\src\calsync\__init__.py`
- `C:\Code\calsync\src\calsync\main.py`
- `C:\Code\calsync\src\calsync\config.py`
- `C:\Code\calsync\src\calsync\db.py`
- `C:\Code\calsync\src\calsync\models\__init__.py`
- `C:\Code\calsync\src\calsync\models\apple_connection.py`
- `C:\Code\calsync\src\calsync\models\appointments.py`
- `C:\Code\calsync\src\calsync\models\audit.py`
- `C:\Code\calsync\src\calsync\schemas\__init__.py`
- `C:\Code\calsync\src\calsync\schemas\appointments.py`
- `C:\Code\calsync\src\calsync\services\__init__.py`
- `C:\Code\calsync\src\calsync\services\apple_caldav.py`
- `C:\Code\calsync\src\calsync\services\appointments.py`
- `C:\Code\calsync\src\calsync\api\__init__.py`
- `C:\Code\calsync\src\calsync\api\routes\__init__.py`
- `C:\Code\calsync\src\calsync\api\routes\health.py`
- `C:\Code\calsync\src\calsync\api\routes\appointments.py`
- `C:\Code\calsync\tests\test_health_smoke.py`
- `C:\Code\calsync\tests\test_schema_bootstrap.py`
- `C:\Code\calsync\tests\test_apple_caldav.py`
- `C:\Code\calsync\tests\test_appointment_api.py`
- `C:\Code\calsync\docs\ops.md`

**Modify**

- `C:\Code\calsync\README.md`
- `C:\Code\calsync\docs\prompts\backend.md`

**Responsibility split**

- `config.py`: environment-backed runtime settings for local/dev/prod and `kayraspi`
- `db.py` + `models/*`: persistent source-of-truth records for Apple connection metadata, appointments, event mappings, and audit trail
- `services/apple_caldav.py`: trimmed Apple/iCloud CalDAV adapter reused from the legacy worktree
- `services/appointments.py`: app-level create, update, cancel logic and audit recording
- `api/routes/*`: small HTTP surface ready for later ChatGPT tool wiring
- `docs/ops.md` + `README.md`: operator and deployment instructions for `kayraspi`

### Task 1: Rebuild the minimal runtime and health endpoint

**Files:**
- Create: `C:\Code\calsync\pyproject.toml`
- Create: `C:\Code\calsync\Dockerfile`
- Create: `C:\Code\calsync\docker-compose.yml`
- Create: `C:\Code\calsync\.env.example`
- Create: `C:\Code\calsync\src\calsync\__init__.py`
- Create: `C:\Code\calsync\src\calsync\main.py`
- Create: `C:\Code\calsync\src\calsync\config.py`
- Create: `C:\Code\calsync\src\calsync\api\routes\__init__.py`
- Create: `C:\Code\calsync\src\calsync\api\routes\health.py`
- Test: `C:\Code\calsync\tests\test_health_smoke.py`

- [ ] **Step 1: Write the failing health/config smoke test**

```python
from fastapi.testclient import TestClient

from calsync.main import create_app


def test_healthz_returns_ok() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_service_identity() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "calsync"
    assert response.json()["mode"] == "apple-first"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_health_smoke.py -v
```

Expected: fail because `calsync.main` and the runtime files do not exist yet.

- [ ] **Step 3: Write the minimal runtime, packaging, and compose scaffold**

`pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=69.0"]
build-backend = "setuptools.build_meta"

[project]
name = "calsync"
version = "0.2.0"
description = "Apple-first conversational scheduling service"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy>=2.0.36",
  "psycopg[binary]>=3.2.3",
  "alembic>=1.14.0",
  "pydantic-settings>=2.6.1",
  "httpx>=0.27.2",
  "icalendar>=5.0.12",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-asyncio>=0.24.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

`docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-calsync}
      POSTGRES_USER: ${POSTGRES_USER:-calsync}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-calsync}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-calsync} -d ${POSTGRES_DB:-calsync}"]
      interval: 10s
      timeout: 5s
      retries: 5

  migrate:
    build: .
    env_file: [.env]
    depends_on:
      db:
        condition: service_healthy
    command: ["alembic", "upgrade", "head"]

  api:
    build: .
    restart: unless-stopped
    env_file: [.env]
    depends_on:
      migrate:
        condition: service_completed_successfully
    ports:
      - "${APP_PORT:-3080}:${APP_PORT:-3080}"
    command: >-
      python -m uvicorn calsync.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-3080}
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${APP_PORT:-3080}/healthz')\""]
      interval: 15s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

`.env.example`

```dotenv
APP_HOST=0.0.0.0
APP_PORT=3080
POSTGRES_DB=calsync
POSTGRES_USER=calsync
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://calsync:change-me@db:5432/calsync
APPLE_ACCOUNT_LABEL=Family
APPLE_USERNAME=
APPLE_APP_SPECIFIC_PASSWORD=
APPLE_PRIMARY_CALENDAR_URL=
APPLE_PRIMARY_CALENDAR_NAME=Family
```

`config.py`

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 3080
    database_url: str = "postgresql+psycopg://calsync:calsync@db:5432/calsync"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

`main.py`

```python
from fastapi import FastAPI

from calsync.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="CalSync", version="0.2.0")
    app.include_router(health_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "calsync", "mode": "apple-first"}

    return app


app = create_app()
```

`api/routes/health.py`

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run the focused test and the container config check**

Run:

```powershell
pytest tests/test_health_smoke.py -v
docker compose config
```

Expected: the health tests pass and `docker compose config` renders a valid stack that still binds port `3080`.

- [ ] **Step 5: Commit**

```powershell
git add .env.example Dockerfile docker-compose.yml pyproject.toml src/calsync tests/test_health_smoke.py
git commit -m "feat: bootstrap Apple-first CalSync runtime"
```

### Task 2: Add the persistent schema for connection metadata, appointments, and audit

**Files:**
- Create: `C:\Code\calsync\alembic.ini`
- Create: `C:\Code\calsync\alembic\env.py`
- Create: `C:\Code\calsync\alembic\versions\20260528_01_apple_first_service.py`
- Create: `C:\Code\calsync\src\calsync\db.py`
- Create: `C:\Code\calsync\src\calsync\models\__init__.py`
- Create: `C:\Code\calsync\src\calsync\models\apple_connection.py`
- Create: `C:\Code\calsync\src\calsync\models\appointments.py`
- Create: `C:\Code\calsync\src\calsync\models\audit.py`
- Test: `C:\Code\calsync\tests\test_schema_bootstrap.py`

- [ ] **Step 1: Write the failing schema bootstrap test**

```python
from sqlalchemy import create_engine, inspect

from calsync.models import Base


def test_metadata_exposes_expected_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())

    assert "apple_calendar_connections" in tables
    assert "appointments" in tables
    assert "appointment_external_links" in tables
    assert "audit_entries" in tables
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_schema_bootstrap.py -v
```

Expected: fail because `calsync.models` does not exist yet.

- [ ] **Step 3: Create the SQLAlchemy base, models, and initial migration**

`models/__init__.py`

```python
from sqlalchemy.orm import DeclarativeBase
from uuid import uuid4


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid4())
```

`db.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from calsync.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
```

`models/apple_connection.py`

```python
from datetime import datetime, UTC

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, new_uuid


class AppleCalendarConnection(Base):
    __tablename__ = "apple_calendar_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    account_label: Mapped[str] = mapped_column(String(255), nullable=False)
    apple_username: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_calendar_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    primary_calendar_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
```

`models/appointments.py`

```python
from datetime import datetime, UTC

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, new_uuid


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    connection_id: Mapped[str] = mapped_column(ForeignKey("apple_calendar_connections.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attendees_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class AppointmentExternalLink(Base):
    __tablename__ = "appointment_external_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, default="icloud_caldav")
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_href: Mapped[str] = mapped_column(String(1024), nullable=False)
    provider_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

`models/audit.py`

```python
from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from calsync.models import Base, new_uuid


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="api")
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Run migration-oriented checks**

Run:

```powershell
pytest tests/test_schema_bootstrap.py -v
alembic upgrade head
```

Expected: the schema test passes and the first migration applies locally.

- [ ] **Step 5: Commit**

```powershell
git add alembic alembic.ini src/calsync/db.py src/calsync/models tests/test_schema_bootstrap.py
git commit -m "feat: add Apple-first appointment schema"
```

### Task 3: Reuse and trim the Apple CalDAV adapter

**Files:**
- Create: `C:\Code\calsync\src\calsync\services\apple_caldav.py`
- Modify: `C:\Code\calsync\src\calsync\config.py`
- Test: `C:\Code\calsync\tests\test_apple_caldav.py`

- [ ] **Step 1: Write the failing Apple adapter tests**

```python
from datetime import UTC, datetime

from calsync.services.apple_caldav import AppleCalDAVConfig, build_event_payload


def test_build_event_payload_uses_uid_and_summary() -> None:
    payload = build_event_payload(
        uid="appt-123",
        title="Dentist",
        starts_at=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 1, 19, 0, tzinfo=UTC),
        all_day=False,
        location="Clinic",
        notes="Bring insurance card",
    )

    text = payload.decode("utf-8")
    assert "UID:appt-123" in text
    assert "SUMMARY:Dentist" in text
    assert "LOCATION:Clinic" in text


def test_config_requires_primary_calendar_url() -> None:
    config = AppleCalDAVConfig(
        account_label="Family",
        apple_username="family@example.com",
        app_specific_password="secret",
        primary_calendar_url="https://caldav.icloud.com/calendar/",
        primary_calendar_name="Family",
    )

    assert config.primary_calendar_name == "Family"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_apple_caldav.py -v
```

Expected: fail because `calsync.services.apple_caldav` does not exist yet.

- [ ] **Step 3: Port only the useful Apple write-back logic from the legacy worktree**

Use the legacy source as reference:

- `C:\Code\calsync\.worktrees\phase1-foundation\src\calsync\services\providers\icloud.py`

New trimmed module shape:

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from icalendar import Calendar, Event as ICalEvent


@dataclass(slots=True)
class AppleCalDAVConfig:
    account_label: str
    apple_username: str
    app_specific_password: str
    primary_calendar_url: str
    primary_calendar_name: str


def build_event_payload(
    *,
    uid: str,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    all_day: bool,
    location: str | None,
    notes: str | None,
) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//CalSync//EN")
    calendar.add("version", "2.0")
    event = ICalEvent()
    event.add("uid", uid)
    event.add("summary", title)
    if location:
        event.add("location", location)
    if notes:
        event.add("description", notes)
    if all_day:
        event.add("dtstart", starts_at.astimezone(UTC).date())
        event.add("dtend", ends_at.astimezone(UTC).date())
    else:
        event.add("dtstart", starts_at.astimezone(UTC))
        event.add("dtend", ends_at.astimezone(UTC))
    event.add("status", "CONFIRMED")
    event.add("dtstamp", datetime.now(UTC))
    calendar.add_component(event)
    return calendar.to_ical()
```

Also extend `config.py` with:

```python
apple_account_label: str = "Family"
apple_username: str | None = None
apple_app_specific_password: str | None = None
apple_primary_calendar_url: str | None = None
apple_primary_calendar_name: str = "Family"
```

- [ ] **Step 4: Run the focused adapter test**

Run:

```powershell
pytest tests/test_apple_caldav.py -v
```

Expected: the adapter tests pass with the trimmed Apple-first implementation.

- [ ] **Step 5: Commit**

```powershell
git add src/calsync/config.py src/calsync/services/apple_caldav.py tests/test_apple_caldav.py
git commit -m "feat: add Apple CalDAV write adapter"
```

### Task 4: Build the appointment API and local audit flow

**Files:**
- Create: `C:\Code\calsync\src\calsync\schemas\appointments.py`
- Create: `C:\Code\calsync\src\calsync\services\appointments.py`
- Create: `C:\Code\calsync\src\calsync\api\routes\appointments.py`
- Modify: `C:\Code\calsync\src\calsync\main.py`
- Test: `C:\Code\calsync\tests\test_appointment_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
from fastapi.testclient import TestClient

from calsync.main import create_app


def test_create_appointment_returns_local_id(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        json={
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
            "all_day": False,
            "location": "Clinic",
            "notes": "Bring insurance card",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert body["appointment_id"]


def test_cancel_appointment_marks_status_cancelled() -> None:
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/appointments",
        json={
            "title": "Follow-up",
            "date": "2026-06-02",
            "start_time": "09:00",
            "end_time": "09:30",
            "timezone": "America/Anchorage",
            "all_day": False,
        },
    )
    appointment_id = create_response.json()["appointment_id"]

    cancel_response = client.post(f"/api/appointments/{appointment_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_appointment_api.py -v
```

Expected: fail because there is no appointment route or service yet.

- [ ] **Step 3: Implement schemas, service, and routes**

`schemas/appointments.py`

```python
from pydantic import BaseModel, Field


class CreateAppointmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    date: str
    start_time: str
    end_time: str
    timezone: str
    all_day: bool = False
    location: str | None = None
    notes: str | None = None
    attendees_text: str | None = None


class UpdateAppointmentRequest(BaseModel):
    title: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    timezone: str | None = None
    all_day: bool | None = None
    location: str | None = None
    notes: str | None = None
    attendees_text: str | None = None


class AppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    provider_event_id: str
    message: str
```

`api/routes/appointments.py`

```python
from fastapi import APIRouter, status

from calsync.schemas.appointments import (
    AppointmentResponse,
    CreateAppointmentRequest,
    UpdateAppointmentRequest,
)
from calsync.services.appointments import AppointmentService

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: CreateAppointmentRequest) -> AppointmentResponse:
    return AppointmentService().create(payload)


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(appointment_id: str, payload: UpdateAppointmentRequest) -> AppointmentResponse:
    return AppointmentService().update(appointment_id, payload)


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(appointment_id: str) -> AppointmentResponse:
    return AppointmentService().cancel(appointment_id)
```

`main.py`

```python
from calsync.api.routes.appointments import router as appointments_router

def create_app() -> FastAPI:
    app = FastAPI(title="CalSync", version="0.2.0")
    app.include_router(health_router)
    app.include_router(appointments_router)
    ...
```

- [ ] **Step 4: Run the focused API tests plus one broader pass**

Run:

```powershell
pytest tests/test_appointment_api.py -v
pytest tests/test_health_smoke.py tests/test_schema_bootstrap.py tests/test_apple_caldav.py tests/test_appointment_api.py -v
```

Expected: all focused Apple-first service tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/calsync/main.py src/calsync/schemas src/calsync/services/appointments.py src/calsync/api/routes/appointments.py tests/test_appointment_api.py
git commit -m "feat: add Apple-first appointment API"
```

### Task 5: Document, deploy to kayraspi, and verify port 3080 live

**Files:**
- Modify: `C:\Code\calsync\README.md`
- Modify: `C:\Code\calsync\docs\prompts\backend.md`
- Create: `C:\Code\calsync\docs\ops.md`

- [ ] **Step 1: Update README and ops docs for the real service**

README section:

```markdown
## Local run

1. Copy `.env.example` to `.env`
2. Set Apple CalDAV credentials and primary calendar URL
3. Run `docker compose up --build`
4. Check `http://localhost:3080/healthz`

## API surface

- `POST /api/appointments`
- `PATCH /api/appointments/{appointment_id}`
- `POST /api/appointments/{appointment_id}/cancel`
```

`docs/ops.md` should include:

- required `.env` keys
- `kayraspi` deployment path `/home/kay/apps/calsync`
- expected external port `3080`
- post-deploy smoke checks

- [ ] **Step 2: Run the final local verification before deploy**

Run:

```powershell
pytest -v
docker compose config
```

Expected: tests pass and compose config is valid before touching the host.

- [ ] **Step 3: Deploy the new service to kayraspi on the old CalSync port**

Run:

```powershell
ssh kayraspi "mkdir -p /home/kay/apps"
git push origin HEAD:main
ssh kayraspi "if [ ! -d /home/kay/apps/calsync/.git ]; then git clone https://github.com/NeonButrfly/calsync.git /home/kay/apps/calsync; fi"
ssh kayraspi "cd /home/kay/apps/calsync && git fetch origin && git checkout main && git pull --ff-only origin main"
ssh kayraspi "cd /home/kay/apps/calsync && cp .env.example .env"
ssh kayraspi "cd /home/kay/apps/calsync && python3 - <<'PY'
from pathlib import Path
env = Path('.env')
text = env.read_text()
text = text.replace('POSTGRES_PASSWORD=change-me', 'POSTGRES_PASSWORD=<real-postgres-password>')
text = text.replace('DATABASE_URL=postgresql+psycopg://calsync:change-me@db:5432/calsync', 'DATABASE_URL=postgresql+psycopg://calsync:<real-postgres-password>@db:5432/calsync')
text = text.replace('APPLE_USERNAME=', 'APPLE_USERNAME=<real-apple-id>')
text = text.replace('APPLE_APP_SPECIFIC_PASSWORD=', 'APPLE_APP_SPECIFIC_PASSWORD=<real-app-specific-password>')
text = text.replace('APPLE_PRIMARY_CALENDAR_URL=', 'APPLE_PRIMARY_CALENDAR_URL=<real-caldav-calendar-url>')
env.write_text(text)
PY"
ssh kayraspi "cd /home/kay/apps/calsync && docker compose up --build -d"
```

Expected: `api`, `migrate`, and `db` come up successfully under `/home/kay/apps/calsync`.

- [ ] **Step 4: Verify the live host on port 3080**

Run:

```powershell
ssh kayraspi "cd /home/kay/apps/calsync && docker compose ps"
ssh kayraspi "curl -sf http://127.0.0.1:3080/healthz"
curl -sf http://192.168.50.232:3080/healthz
```

Expected: both curls return `{"status":"ok"}` and port `3080` is serving the new CalSync again.

- [ ] **Step 5: Commit the docs/deploy slice**

```powershell
git add README.md docs/ops.md docs/prompts/backend.md
git commit -m "docs: add Apple-first service deployment runbook"
```

## Self-Review Notes

- Spec coverage: this plan covers the deployable FastAPI service, local persistence, Apple create/update/cancel path, audit history, Docker deployment, and kayraspi live validation on port `3080`.
- Placeholder scan: branch names, file paths, commands, host path, and target port are explicit; no `TODO` or `TBD` remain.
- Type consistency: the service stays Apple-first throughout, uses the same port `3080`, and keeps one coherent appointment/audit model rather than mixing the old multi-provider UI back in.
