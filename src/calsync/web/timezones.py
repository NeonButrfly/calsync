from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ALASKA_TIMEZONE = ZoneInfo("America/Anchorage")


def resolve_display_timezone(timezone_name: str | None) -> ZoneInfo:
    if timezone_name and timezone_name != "UTC":
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ALASKA_TIMEZONE
    return ALASKA_TIMEZONE


def format_display_datetime(
    value: datetime | None,
    timezone_name: str | None = None,
) -> str:
    if value is None:
        return ""

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)

    local_value = value.astimezone(resolve_display_timezone(timezone_name))
    time_text = local_value.strftime("%I:%M %p").lstrip("0") or "12:00 AM"
    # Keep the displayed clock adjusted to Alaska local time while using one
    # stable operator-facing label instead of mixing seasonal abbreviations.
    timezone_label = "AKST"
    return (
        f"{local_value.strftime('%a')} {local_value.strftime('%b')} "
        f"{local_value.day} at {time_text} {timezone_label}"
    )
