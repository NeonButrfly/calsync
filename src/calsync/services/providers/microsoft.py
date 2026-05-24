from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.config import Settings, get_settings
from calsync.models import ProviderAccount, ProviderCalendar
from calsync.schemas.providers import DiscoveredCalendar, NormalizedEvent


MICROSOFT_PROVIDER_TYPE = "microsoft"
MICROSOFT_WRITABLE_SCOPES = {
    "Calendars.ReadWrite",
    "Calendars.ReadWrite.Shared",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/Calendars.ReadWrite.Shared",
}


def infer_microsoft_account_capabilities(
    account: ProviderAccount,
) -> tuple[str, bool, bool]:
    metadata = dict(account.provider_metadata or {})
    scopes = _metadata_scope_values(metadata.get("microsoft_scopes"))
    can_write = bool(
        metadata.get("can_write") is True
        or metadata.get("supports_write") is True
        or metadata.get("supports_writes") is True
        or any(scope in MICROSOFT_WRITABLE_SCOPES for scope in scopes)
    )
    return "oauth", True, can_write


class MicrosoftProviderAdapter:
    provider_type = MICROSOFT_PROVIDER_TYPE
    auth_mode = "oauth"
    supports_write_back = True

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: Session | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session

    def discover_calendars(
        self,
        account: ProviderAccount,
    ) -> list[DiscoveredCalendar]:
        raise NotImplementedError("Microsoft calendar discovery is not implemented yet.")

    def fetch_events(
        self,
        account: ProviderAccount,
        calendar: ProviderCalendar,
    ) -> list[NormalizedEvent]:
        raise NotImplementedError("Microsoft event fetch is not implemented yet.")


def _metadata_scope_values(raw_scopes: object) -> tuple[str, ...]:
    if isinstance(raw_scopes, str):
        return tuple(scope for scope in raw_scopes.split() if scope)
    if isinstance(raw_scopes, (list, tuple, set)):
        return tuple(str(scope).strip() for scope in raw_scopes if str(scope).strip())
    return ()
