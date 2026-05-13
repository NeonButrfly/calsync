from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TotpEnrollment(BaseModel):
    secret: str
    otpauth_uri: str
    qr_png_bytes: bytes


class RecoveryCodeRecord(BaseModel):
    code_hash: str
    created_at: datetime
    used_at: datetime | None = None
