from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import AdminUser
from calsync.repos.state import get_app_state, set_app_state
from calsync.repos.users import (
    create_admin_user,
    get_admin_by_email,
    get_admin_by_username,
)
from calsync.schemas.auth import TotpEnrollment
from calsync.services.auth import (
    build_totp_enrollment,
    generate_recovery_codes,
    hash_password,
    store_recovery_codes,
    store_totp_secret,
    validate_password_strength,
    verify_totp,
)


SETUP_COMPLETED_STATE_KEY = "setup_completed"
PENDING_SETUP_ATTEMPTS_ATTR = "pending_setup_attempts"
PENDING_SETUP_SESSION_KEY = "pending_setup_attempt_id"


@dataclass(slots=True)
class PendingSetup:
    enrollment: TotpEnrollment
    recovery_codes: list[str]


@dataclass(slots=True)
class SetupSubmission:
    username: str
    email: str
    password: str
    password_confirmation: str
    totp_code: str
    recovery_acknowledged: bool


@dataclass(slots=True)
class SetupResult:
    errors: list[str]
    user: AdminUser | None = None


def is_setup_complete(session: Session) -> bool:
    state = get_app_state(session, SETUP_COMPLETED_STATE_KEY)
    if state is not None and state.value_text == "true":
        return True

    return session.scalar(select(AdminUser.id).limit(1)) is not None


def require_setup_incomplete(session: Session) -> None:
    if is_setup_complete(session):
        raise HTTPException(status_code=404)


def get_or_create_pending_setup(
    app: Any,
    session_state: dict[str, object],
) -> PendingSetup:
    pending_setup_attempts = _get_pending_setup_attempts(app)
    attempt_id = session_state.get(PENDING_SETUP_SESSION_KEY)
    if isinstance(attempt_id, str) and attempt_id in pending_setup_attempts:
        return pending_setup_attempts[attempt_id]

    pending_setup = PendingSetup(
        enrollment=build_totp_enrollment("admin"),
        recovery_codes=generate_recovery_codes(),
    )
    attempt_id = token_urlsafe(16)
    pending_setup_attempts[attempt_id] = pending_setup
    session_state[PENDING_SETUP_SESSION_KEY] = attempt_id
    return pending_setup


def clear_pending_setup(
    app: Any,
    session_state: dict[str, object],
) -> None:
    pending_setup_attempts = _get_pending_setup_attempts(app)
    attempt_id = session_state.pop(PENDING_SETUP_SESSION_KEY, None)
    if isinstance(attempt_id, str):
        pending_setup_attempts.pop(attempt_id, None)


def _get_pending_setup_attempts(app: Any) -> dict[str, PendingSetup]:
    pending_setup_attempts = getattr(app.state, PENDING_SETUP_ATTEMPTS_ATTR, None)
    if pending_setup_attempts is None:
        pending_setup_attempts = {}
        setattr(app.state, PENDING_SETUP_ATTEMPTS_ATTR, pending_setup_attempts)
    return pending_setup_attempts


def complete_first_run_setup(
    session: Session,
    app: Any,
    session_state: dict[str, object],
    *,
    submission: SetupSubmission,
    encryption_key: str,
) -> SetupResult:
    require_setup_incomplete(session)
    pending_setup = get_or_create_pending_setup(app, session_state)

    errors = _validate_setup_submission(
        session,
        pending_setup,
        submission=submission,
    )
    if errors:
        return SetupResult(errors=errors)

    user = create_admin_user(
        session,
        username=submission.username.strip(),
        email=submission.email.strip().lower(),
        password_hash=hash_password(submission.password),
    )
    store_totp_secret(
        session,
        user,
        pending_setup.enrollment.secret,
        encryption_key=encryption_key,
    )
    user.mfa_enrolled = True
    store_recovery_codes(session, user, pending_setup.recovery_codes)
    set_app_state(
        session,
        key=SETUP_COMPLETED_STATE_KEY,
        value_text="true",
    )
    session.commit()
    clear_pending_setup(app, session_state)
    return SetupResult(errors=[], user=user)


def _validate_setup_submission(
    session: Session,
    pending_setup: PendingSetup,
    *,
    submission: SetupSubmission,
) -> list[str]:
    errors: list[str] = []

    username = submission.username.strip()
    email = submission.email.strip().lower()
    if not username:
        errors.append("Username is required.")
    if not email:
        errors.append("Email is required.")

    errors.extend(validate_password_strength(submission.password))
    if submission.password != submission.password_confirmation:
        errors.append("Password confirmation must match.")

    if get_admin_by_username(session, username) is not None:
        errors.append("That username is already in use.")
    if get_admin_by_email(session, email) is not None:
        errors.append("That email is already in use.")

    if not verify_totp(pending_setup.enrollment.secret, submission.totp_code):
        errors.append("Enter a valid MFA code to finish setup.")

    if not submission.recovery_acknowledged:
        errors.append("Acknowledge that you stored at least one recovery code.")

    return errors
