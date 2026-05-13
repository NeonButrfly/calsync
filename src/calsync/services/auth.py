from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime
import json
import secrets
import string
from collections.abc import Sequence
from io import BytesIO

import pyotp
import qrcode
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from calsync.crypto import decrypt_text, encrypt_text
from calsync.models import AdminUser, utcnow
from calsync.schemas.auth import RecoveryCodeRecord, TotpEnrollment


PASSWORD_CONTEXT = CryptContext(schemes=["argon2"], deprecated="auto")
RECOVERY_CODE_ALPHABET = string.ascii_uppercase + string.digits
RECOVERY_CODE_LENGTH = 10
DEFAULT_RECOVERY_CODE_COUNT = 8
DEFAULT_TOTP_ISSUER = "CalSync"


def validate_password_strength(password: str) -> list[str]:
    errors: list[str] = []

    if len(password) < 12:
        errors.append("Password must be at least 12 characters long.")
    if not any(character.islower() for character in password):
        errors.append("Password must include a lowercase letter.")
    if not any(character.isupper() for character in password):
        errors.append("Password must include an uppercase letter.")
    if not any(character.isdigit() for character in password):
        errors.append("Password must include a digit.")
    if all(character.isalnum() for character in password):
        errors.append("Password must include a symbol.")

    return errors


def hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_CONTEXT.verify(password, password_hash)


def render_qr_png(payload: str) -> bytes:
    qr_image = qrcode.make(payload)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_totp_enrollment(
    login_name: str,
    *,
    issuer_name: str = DEFAULT_TOTP_ISSUER,
) -> TotpEnrollment:
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    otpauth_uri = totp.provisioning_uri(
        name=login_name,
        issuer_name=issuer_name,
    )
    return TotpEnrollment(
        secret=secret,
        otpauth_uri=otpauth_uri,
        qr_png_data_url=build_png_data_url(render_qr_png(otpauth_uri)),
    )


def verify_totp(secret: str, code: str, *, valid_window: int = 1) -> bool:
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=valid_window)


def verify_totp_once(
    secret: str,
    code: str,
    *,
    for_time: datetime | None = None,
    valid_window: int = 1,
    last_accepted_counter: int | None = None,
) -> int | None:
    normalized_code = code.strip()
    if not normalized_code:
        return None

    totp = pyotp.TOTP(secret)
    reference_time = for_time or datetime.now(UTC)
    current_counter = totp.timecode(reference_time)

    for counter_offset in range(-valid_window, valid_window + 1):
        counter = current_counter + counter_offset
        if last_accepted_counter is not None and counter <= last_accepted_counter:
            continue
        if totp.at(reference_time, counter_offset=counter_offset) == normalized_code:
            return counter

    return None


def store_totp_secret(
    session: Session,
    user: AdminUser,
    secret: str,
    *,
    encryption_key: str,
) -> None:
    user.mfa_secret_encrypted = encrypt_text(encryption_key, secret)
    session.add(user)


def load_totp_secret(user: AdminUser, *, encryption_key: str) -> str | None:
    if not user.mfa_secret_encrypted:
        return None
    return decrypt_text(encryption_key, user.mfa_secret_encrypted)


def verify_totp_for_user(
    user: AdminUser,
    code: str,
    *,
    encryption_key: str,
    valid_window: int = 1,
) -> bool:
    secret = load_totp_secret(user, encryption_key=encryption_key)
    if secret is None:
        return False
    return verify_totp(secret, code, valid_window=valid_window)


def verify_totp_for_user_once(
    user: AdminUser,
    code: str,
    *,
    encryption_key: str,
    for_time: datetime | None = None,
    valid_window: int = 1,
    last_accepted_counter: int | None = None,
) -> int | None:
    secret = load_totp_secret(user, encryption_key=encryption_key)
    if secret is None:
        return None
    return verify_totp_once(
        secret,
        code,
        for_time=for_time,
        valid_window=valid_window,
        last_accepted_counter=last_accepted_counter,
    )


def generate_recovery_codes(
    *,
    count: int = DEFAULT_RECOVERY_CODE_COUNT,
) -> list[str]:
    return [_generate_recovery_code() for _ in range(count)]


def store_recovery_codes(
    session: Session,
    user: AdminUser,
    recovery_codes: Sequence[str],
) -> list[RecoveryCodeRecord]:
    now = utcnow()
    stored_codes = [
        RecoveryCodeRecord(
            code_hash=PASSWORD_CONTEXT.hash(_normalize_recovery_code(recovery_code)),
            created_at=now,
        )
        for recovery_code in recovery_codes
    ]
    user.recovery_codes_json = json.dumps(
        [stored_code.model_dump(mode="json") for stored_code in stored_codes]
    )
    session.add(user)
    return stored_codes


def consume_recovery_code(
    session: Session,
    user: AdminUser,
    recovery_code: str,
) -> bool:
    normalized_code = _normalize_recovery_code(recovery_code)
    stored_codes = _load_recovery_code_records(user)

    for stored_code in stored_codes:
        if stored_code.used_at is not None:
            continue
        if not PASSWORD_CONTEXT.verify(normalized_code, stored_code.code_hash):
            continue

        stored_code.used_at = utcnow()
        user.recovery_codes_json = json.dumps(
            [record.model_dump(mode="json") for record in stored_codes]
        )
        session.add(user)
        return True

    return False


def _load_recovery_code_records(user: AdminUser) -> list[RecoveryCodeRecord]:
    if not user.recovery_codes_json:
        return []
    payload = json.loads(user.recovery_codes_json)
    return [RecoveryCodeRecord.model_validate(entry) for entry in payload]


def build_png_data_url(png_bytes: bytes) -> str:
    encoded_png = b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded_png}"


def _normalize_recovery_code(recovery_code: str) -> str:
    return recovery_code.strip().upper()


def _generate_recovery_code() -> str:
    parts = []
    for _ in range(2):
        parts.append(
            "".join(
                secrets.choice(RECOVERY_CODE_ALPHABET)
                for _ in range(RECOVERY_CODE_LENGTH // 2)
            )
        )
    return "-".join(parts)
