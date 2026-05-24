from pathlib import Path

import pytest
import pyotp
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError

from calsync.config import Settings, get_settings
from calsync.main import create_app
from calsync.models import Base, ProviderAccount, ProviderCalendar
from calsync.repos.providers import (
    get_provider_account,
    set_provider_calendar_role,
    upsert_provider_account,
)
from calsync.repos.state import set_app_state
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
)
from calsync.services.sync import discover_calendars


@pytest.fixture()
def migrated_session_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    database_path = tmp_path / "calendar-roles.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")

    try:
        engine = create_engine(database_url, future=True)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        get_settings.cache_clear()


@pytest.fixture()
def authenticated_read_only_calendar_client(tmp_path: Path) -> TestClient:
    yield from _build_authenticated_calendar_client(tmp_path, can_write=False)


@pytest.fixture()
def authenticated_writable_calendar_client(tmp_path: Path) -> TestClient:
    yield from _build_authenticated_calendar_client(tmp_path, can_write=True)


@pytest.fixture()
def authenticated_google_writable_account_with_read_only_calendar_client(
    tmp_path: Path,
) -> TestClient:
    database_path = tmp_path / "calendar-roles-google-read-only-page.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://testserver",
        session_secret="calendar-role-google-test-session-secret",
        encryption_key="calendar-role-google-test-encryption-key",
    )
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        set_app_state(session, key="setup_completed", value_text="true")
        admin_user = create_admin_user(
            session,
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("StrongPassword1!"),
        )
        totp_secret = pyotp.random_base32()
        store_totp_secret(
            session,
            admin_user,
            totp_secret,
            encryption_key=settings.encryption_key,
        )
        admin_user.mfa_enrolled = True
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))

        account = ProviderAccount(
            provider_type="google",
            provider_account_id="google-acct-roles",
            display_name="Writable Google Account",
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar",
                ]
            },
        )
        session.add(account)
        session.flush()
        session.add(
            ProviderCalendar(
                provider_account_pk=account.id,
                provider_calendar_id="google-reader",
                name="Google Reader Calendar",
                enabled=True,
                provider_metadata={"access_role": "reader"},
            )
        )
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_engine = engine

    with TestClient(app, base_url="http://testserver") as client:
        _authenticate_client(client)
        yield client


def _build_authenticated_calendar_client(
    tmp_path: Path,
    *,
    can_write: bool,
) -> TestClient:
    database_path = tmp_path / "calendar-roles-page.sqlite3"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        public_base_url="http://testserver",
        session_secret="calendar-role-test-session-secret",
        encryption_key="calendar-role-test-encryption-key",
    )
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        set_app_state(session, key="setup_completed", value_text="true")
        admin_user = create_admin_user(
            session,
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("StrongPassword1!"),
        )
        totp_secret = pyotp.random_base32()
        store_totp_secret(
            session,
            admin_user,
            totp_secret,
            encryption_key=settings.encryption_key,
        )
        admin_user.mfa_enrolled = True
        store_recovery_codes(session, admin_user, generate_recovery_codes(count=2))

        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="mock-acct-roles",
            display_name="Mock Account",
            can_write=can_write,
            provider_metadata={"seed": "calendar-roles"},
        )
        session.add(account)
        session.flush()
        discover_calendars(session, account.id)
        session.commit()

    app = create_app(settings)
    app.state.test_totp_secret = totp_secret
    app.state.test_engine = engine

    with TestClient(app, base_url="http://testserver") as client:
        _authenticate_client(client)
        yield client


def test_provider_account_capabilities_round_trip(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="google",
            provider_account_id="acct-1",
            display_name="Primary",
            auth_mode="service_account",
            can_read=True,
            can_write=True,
            requires_reconnect=True,
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        reloaded = read_session.get(ProviderAccount, account_id)

        assert reloaded is not None
        assert reloaded.auth_mode == "service_account"
        assert reloaded.can_read is True
        assert reloaded.can_write is True
        assert reloaded.requires_reconnect is True


def test_provider_calendar_role_round_trip(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="acct-2",
            display_name="Mock Account",
            can_write=True,
        )
        write_session.add(account)
        write_session.flush()

        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="cal-1",
            name="Bookings",
            calendar_role="writable_booking_target",
        )
        write_session.add(calendar)
        write_session.commit()
        calendar_id = calendar.id

    with migrated_session_factory() as read_session:
        reloaded = read_session.get(ProviderCalendar, calendar_id)

        assert reloaded is not None
        assert reloaded.calendar_role == "writable_booking_target"


def test_provider_calendar_role_rejects_unknown_values(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="acct-3",
            display_name="Constraint Test",
        )
        write_session.add(account)
        write_session.flush()

        write_session.add(
            ProviderCalendar(
                provider_account_pk=account.id,
                provider_calendar_id="cal-invalid",
                name="Bad Role",
                calendar_role="typo_role",
            )
        )

        with pytest.raises(IntegrityError):
            write_session.commit()


def test_set_provider_calendar_role_rejects_writable_booking_target_for_read_only_account(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        account = ProviderAccount(
            provider_type="mock",
            provider_account_id="acct-read-only",
            display_name="Read Only Account",
            can_write=False,
        )
        session.add(account)
        session.flush()
        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="cal-read-only",
            name="Reference Calendar",
        )
        session.add(calendar)
        session.flush()

        with pytest.raises(ValueError, match="does not support writable booking targets"):
            set_provider_calendar_role(
                session,
                calendar=calendar,
                calendar_role="writable_booking_target",
            )


def test_set_provider_calendar_role_rejects_writable_booking_target_for_google_reader_calendar(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        account = ProviderAccount(
            provider_type="google",
            provider_account_id="google-reader-account",
            display_name="Writable Google Account",
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar",
                ]
            },
        )
        session.add(account)
        session.flush()
        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="google-reader-calendar",
            name="Read Only Google Calendar",
            provider_metadata={"access_role": "reader"},
        )
        session.add(calendar)
        session.flush()

        with pytest.raises(ValueError, match="does not support writable booking targets"):
            set_provider_calendar_role(
                session,
                calendar=calendar,
                calendar_role="writable_booking_target",
            )


def test_set_provider_calendar_role_allows_writable_booking_target_for_google_writer_calendar(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        account = ProviderAccount(
            provider_type="google",
            provider_account_id="google-writer-account",
            display_name="Writable Google Account",
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar",
                ]
            },
        )
        session.add(account)
        session.flush()
        calendar = ProviderCalendar(
            provider_account_pk=account.id,
            provider_calendar_id="google-writer-calendar",
            name="Writable Google Calendar",
            provider_metadata={"access_role": "writer"},
        )
        session.add(calendar)
        session.flush()

        updated = set_provider_calendar_role(
            session,
            calendar=calendar,
            calendar_role="writable_booking_target",
        )

        assert updated.calendar_role == "writable_booking_target"


def test_calendars_page_does_not_offer_writable_booking_target_for_read_only_accounts(
    authenticated_read_only_calendar_client: TestClient,
) -> None:
    response = authenticated_read_only_calendar_client.get("/admin/calendars")

    assert response.status_code == 200
    assert "What this calendar is for" in response.text
    assert "Check availability" in response.text
    assert "Conflict checking only" in response.text
    assert "Personal reference" in response.text
    assert "Hidden" in response.text
    assert "Receive new bookings" not in response.text
    assert 'name="calendar_role"' in response.text


def test_calendars_page_hides_writable_booking_target_for_google_reader_calendar(
    authenticated_google_writable_account_with_read_only_calendar_client: TestClient,
) -> None:
    response = (
        authenticated_google_writable_account_with_read_only_calendar_client.get(
            "/admin/calendars"
        )
    )

    assert response.status_code == 200
    assert "Writable Google Account" in response.text
    assert "Google Reader Calendar" in response.text
    assert "Receive new bookings" not in response.text
    assert 'name="calendar_role"' in response.text


def test_calendar_role_update_persists_from_admin_page_for_write_capable_account(
    authenticated_writable_calendar_client: TestClient,
) -> None:
    with _db_session(authenticated_writable_calendar_client) as session:
        calendar = session.scalar(
            select(ProviderCalendar).where(
                ProviderCalendar.provider_calendar_id == "work",
            )
        )
        assert calendar is not None
        calendar_id = calendar.id

    response = authenticated_writable_calendar_client.post(
        f"/admin/calendars/{calendar_id}/role",
        data={"calendar_role": "writable_booking_target"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/calendars"

    with _db_session(authenticated_writable_calendar_client) as session:
        refreshed_calendar = session.get(ProviderCalendar, calendar_id)
        assert refreshed_calendar is not None
        assert refreshed_calendar.calendar_role == "writable_booking_target"


def test_provider_role_migration_backfills_defaults_for_existing_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "calendar-roles-upgrade.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    try:
        command.upgrade(alembic_config, "20260523_01")

        engine = create_engine(database_url, future=True)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO provider_accounts (
                        id,
                        provider_type,
                        provider_account_id,
                        display_name,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :provider_type,
                        :provider_account_id,
                        :display_name,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": "acct-existing",
                    "provider_type": "google",
                    "provider_account_id": "acct-legacy",
                    "display_name": "Legacy Account",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO provider_calendars (
                        id,
                        provider_account_pk,
                        provider_calendar_id,
                        name,
                        enabled,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :provider_account_pk,
                        :provider_calendar_id,
                        :name,
                        :enabled,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": "cal-existing",
                    "provider_account_pk": "acct-existing",
                    "provider_calendar_id": "cal-legacy",
                    "name": "Legacy Calendar",
                    "enabled": True,
                },
            )

        command.upgrade(alembic_config, "head")

        session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with session_factory() as read_session:
            account = read_session.get(ProviderAccount, "acct-existing")
            calendar = read_session.get(ProviderCalendar, "cal-existing")

            assert account is not None
            assert account.auth_mode == "oauth"
            assert account.can_read is True
            assert account.can_write is False
            assert account.requires_reconnect is False

            assert calendar is not None
            assert calendar.calendar_role == "personal_reference"
    finally:
        get_settings.cache_clear()


def test_icloud_account_defaults(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    encrypted_secret = "existing-encrypted-secret"

    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            credential_secret_encrypted=encrypted_secret,
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        existing_account = read_session.get(ProviderAccount, account_id)
        assert existing_account is not None

        updated = upsert_provider_account(
            read_session,
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            provider_metadata={"principal_url": "https://caldav.icloud.com/123/principal/"},
        )
        read_session.commit()

        assert updated.id == account_id
        assert updated.auth_mode == "caldav"
        assert updated.can_read is True
        assert updated.can_write is False
        assert updated.credential_secret_encrypted == encrypted_secret


def test_upsert_provider_account_preserves_existing_metadata_keys(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            provider_metadata={
                "principal_url": "https://caldav.icloud.com/123/principal/",
                "calendar_home_url": "https://caldav.icloud.com/123/calendars/",
                "auth_status": "connected",
            },
        )
        write_session.add(account)
        write_session.commit()

    with migrated_session_factory() as read_session:
        updated = upsert_provider_account(
            read_session,
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            provider_metadata={"last_auth_error": None},
        )
        read_session.commit()

        assert updated.provider_metadata == {
            "principal_url": "https://caldav.icloud.com/123/principal/",
            "calendar_home_url": "https://caldav.icloud.com/123/calendars/",
            "auth_status": "connected",
            "last_auth_error": None,
        }


def test_google_account_capabilities(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as session:
        account = upsert_provider_account(
            session,
            provider_type="google",
            provider_account_id="google-sub",
            display_name="owner@example.com",
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar",
                ]
            },
        )
        session.commit()

        assert account.auth_mode == "oauth"
        assert account.can_read is True
        assert account.can_write is True


def test_get_provider_account_hydrates_google_capabilities_from_current_scopes(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="google",
            provider_account_id="google-sub",
            display_name="owner@example.com",
            can_write=True,
            provider_metadata={
                "google_scopes": [
                    "openid",
                    "email",
                    "https://www.googleapis.com/auth/calendar.readonly",
                ]
            },
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        hydrated = get_provider_account(read_session, account_id)

        assert hydrated is not None
        assert hydrated.auth_mode == "oauth"
        assert hydrated.can_read is True
        assert hydrated.can_write is False


def test_get_provider_account_hydrates_microsoft_capabilities_from_current_scopes(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="microsoft",
            provider_account_id="microsoft-sub",
            display_name="owner@example.com",
            can_write=False,
            provider_metadata={
                "microsoft_scopes": (
                    "openid profile offline_access "
                    "https://graph.microsoft.com/Calendars.ReadWrite"
                )
            },
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        hydrated = get_provider_account(read_session, account_id)

        assert hydrated is not None
        assert hydrated.auth_mode == "oauth"
        assert hydrated.can_read is True
        assert hydrated.can_write is True


def test_get_provider_account_hydrates_icloud_defaults(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    encrypted_secret = "existing-encrypted-secret"

    with migrated_session_factory() as write_session:
        account = ProviderAccount(
            provider_type="icloud_caldav",
            provider_account_id="kay@icloud.com",
            display_name="Kay iCloud",
            auth_mode="oauth",
            can_read=False,
            can_write=True,
            credential_secret_encrypted=encrypted_secret,
            provider_metadata={},
        )
        write_session.add(account)
        write_session.commit()
        account_id = account.id

    with migrated_session_factory() as read_session:
        hydrated = get_provider_account(read_session, account_id)

        assert hydrated is not None
        assert hydrated.auth_mode == "caldav"
        assert hydrated.can_read is True
        assert hydrated.can_write is False
        assert hydrated.credential_secret_encrypted == encrypted_secret


def _db_session(client: TestClient) -> Session:
    return Session(client.app.state.test_engine)


def _authenticate_client(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"identifier": "admin", "password": "StrongPassword1!"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    totp_code = pyotp.TOTP(client.app.state.test_totp_secret).now()
    verify_response = client.post(
        "/login/mfa",
        data={"code": totp_code},
        follow_redirects=False,
    )
    assert verify_response.status_code == 303
