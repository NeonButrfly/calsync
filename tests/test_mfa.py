from io import BytesIO

import pyotp
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from calsync.models import AdminUser, Base
from calsync.repos.users import create_admin_user
from calsync.services.auth import (
    build_totp_enrollment,
    store_totp_secret,
    verify_totp,
    verify_totp_for_user,
)


ENCRYPTION_KEY = "phase1-mfa-test-key"


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with SessionLocal() as db_session:
        yield db_session


@pytest.fixture()
def admin_user(session: Session) -> AdminUser:
    return create_admin_user(
        session,
        username="admin",
        email="admin@example.com",
    )


def test_totp_secret_generation_and_otpauth_uri_formatting_work() -> None:
    enrollment = build_totp_enrollment("admin@example.com")

    assert enrollment.secret
    assert enrollment.otpauth_uri.startswith("otpauth://totp/")
    assert "issuer=CalSync" in enrollment.otpauth_uri
    assert "admin%40example.com" in enrollment.otpauth_uri


def test_qr_generation_works() -> None:
    enrollment = build_totp_enrollment("admin@example.com")

    with Image.open(BytesIO(enrollment.qr_png_bytes)) as qr_image:
        assert qr_image.format == "PNG"
        assert qr_image.size[0] > 0
        assert qr_image.size[1] > 0


def test_successful_totp_verification_works() -> None:
    enrollment = build_totp_enrollment("admin@example.com")
    code = pyotp.TOTP(enrollment.secret).now()

    assert verify_totp(enrollment.secret, code) is True


def test_failed_totp_verification_fails() -> None:
    enrollment = build_totp_enrollment("admin@example.com")

    assert verify_totp(enrollment.secret, "000000") is False


def test_totp_secret_is_encrypted_at_rest_and_verifies_for_user(
    session: Session,
    admin_user: AdminUser,
) -> None:
    enrollment = build_totp_enrollment(admin_user.email)
    store_totp_secret(
        session,
        admin_user,
        enrollment.secret,
        encryption_key=ENCRYPTION_KEY,
    )
    session.flush()
    code = pyotp.TOTP(enrollment.secret).now()

    assert admin_user.mfa_secret_encrypted is not None
    assert admin_user.mfa_secret_encrypted != enrollment.secret
    assert enrollment.secret not in admin_user.mfa_secret_encrypted
    assert verify_totp_for_user(
        admin_user,
        code,
        encryption_key=ENCRYPTION_KEY,
    ) is True
