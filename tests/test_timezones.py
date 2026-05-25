from __future__ import annotations

from datetime import UTC, datetime

from calsync.web.timezones import format_display_datetime


def test_format_display_datetime_includes_year_for_non_current_year_values() -> None:
    rendered = format_display_datetime(datetime(2012, 5, 28, 20, 0, tzinfo=UTC))

    assert "2012" in rendered
    assert rendered.endswith("AKST")


def test_format_display_datetime_omits_year_for_current_year_values() -> None:
    current_year = datetime.now(UTC).year
    rendered = format_display_datetime(datetime(current_year, 5, 28, 20, 0, tzinfo=UTC))

    assert str(current_year) not in rendered
    assert rendered.endswith("AKST")
