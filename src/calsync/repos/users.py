from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import AdminUser


def get_admin_by_username(session: Session, username: str) -> AdminUser | None:
    return session.scalar(select(AdminUser).where(AdminUser.username == username))


def get_admin_by_email(session: Session, email: str) -> AdminUser | None:
    return session.scalar(select(AdminUser).where(AdminUser.email == email))


def create_admin_user(
    session: Session,
    *,
    username: str,
    email: str,
    password_hash: str | None = None,
    mfa_secret_encrypted: str | None = None,
    recovery_codes_json: str | None = None,
) -> AdminUser:
    user = AdminUser(
        username=username,
        email=email,
        password_hash=password_hash,
        mfa_secret_encrypted=mfa_secret_encrypted,
        mfa_enrolled=bool(mfa_secret_encrypted),
        recovery_codes_json=recovery_codes_json,
    )
    session.add(user)
    session.flush()
    return user
