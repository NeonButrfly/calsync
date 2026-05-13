from __future__ import annotations

import os
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Iterator
from http.cookies import SimpleCookie
from json import dumps, loads
from pathlib import Path
from typing import Any
import hmac
from hashlib import sha256

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from calsync.db import get_db_session


DEFAULT_ENCRYPTION_KEY = "calsync-phase1-dev-encryption-key"
DEFAULT_SESSION_SECRET = "calsync-phase1-dev-session-secret"
SESSION_COOKIE_NAME = "calsync_session"

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def get_templates() -> Jinja2Templates:
    return _templates


def get_db(request: Request) -> Iterator[Session]:
    settings = request.app.state.settings
    yield from get_db_session(settings)


def get_encryption_key(request: Request) -> str:
    return _get_app_secret(
        request.app,
        attr_name="encryption_key",
        env_name="CALSYNC_ENCRYPTION_KEY",
        default=DEFAULT_ENCRYPTION_KEY,
    )


def get_session_secret(settings: Any) -> str:
    configured_secret = getattr(settings, "session_secret", None)
    if configured_secret:
        return str(configured_secret)

    return os.environ.get("CALSYNC_SESSION_SECRET", DEFAULT_SESSION_SECRET)


def _get_app_secret(
    app: Any,
    *,
    attr_name: str,
    env_name: str,
    default: str,
) -> str:
    configured_secret = getattr(app.state, attr_name, None)
    if configured_secret:
        return str(configured_secret)

    settings = getattr(app.state, "settings", None)
    if settings is not None:
        settings_value = getattr(settings, attr_name, None)
        if settings_value:
            return str(settings_value)

    return os.environ.get(env_name, default)


class SignedCookieSessionMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        secret_key: str,
        cookie_name: str = SESSION_COOKIE_NAME,
    ) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.secret_key = secret_key.encode("utf-8")

    async def dispatch(self, request: Request, call_next) -> Response:
        original_cookie_present = False
        original_session = {}
        cookie_header = request.headers.get("cookie")
        if cookie_header:
            original_cookie_present, original_session = self._load_session(cookie_header)

        request.scope["session"] = dict(original_session)
        response = await call_next(request)
        current_session = request.scope.get("session", {})
        if current_session:
            response.set_cookie(
                self.cookie_name,
                self._dump_session(current_session),
                httponly=True,
                samesite="lax",
            )
        elif original_cookie_present:
            response.delete_cookie(self.cookie_name)

        return response

    def _load_session(self, cookie_header: str) -> tuple[bool, dict[str, object]]:
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(self.cookie_name)
        if morsel is None:
            return False, {}

        payload = morsel.value
        try:
            encoded_session, provided_signature = payload.split(".", maxsplit=1)
        except ValueError:
            return True, {}

        expected_signature = self._sign(encoded_session)
        if not hmac.compare_digest(provided_signature, expected_signature):
            return True, {}

        try:
            session_bytes = urlsafe_b64decode(_with_padding(encoded_session))
            session_data = loads(session_bytes.decode("utf-8"))
        except (ValueError, TypeError):
            return True, {}

        if not isinstance(session_data, dict):
            return True, {}

        return True, session_data

    def _dump_session(self, session_data: dict[str, object]) -> str:
        payload = dumps(session_data, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        encoded_session = urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        return f"{encoded_session}.{self._sign(encoded_session)}"

    def _sign(self, encoded_session: str) -> str:
        return hmac.new(
            self.secret_key,
            encoded_session.encode("utf-8"),
            sha256,
        ).hexdigest()


def _with_padding(value: str) -> str:
    padding = (-len(value)) % 4
    return value + ("=" * padding)
