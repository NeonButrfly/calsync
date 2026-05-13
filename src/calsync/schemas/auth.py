from __future__ import annotations

from base64 import b64decode
from datetime import datetime

from pydantic import BaseModel


class TotpEnrollment(BaseModel):
    secret: str
    otpauth_uri: str
    qr_png_data_url: str

    @property
    def qr_png_bytes(self) -> bytes:
        prefix = "data:image/png;base64,"
        if not self.qr_png_data_url.startswith(prefix):
            raise ValueError("TOTP enrollment QR payload must be a PNG data URL.")
        return b64decode(self.qr_png_data_url[len(prefix) :])


class RecoveryCodeRecord(BaseModel):
    code_hash: str
    created_at: datetime
    used_at: datetime | None = None
