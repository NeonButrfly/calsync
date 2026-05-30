from io import BytesIO
from zipfile import ZipFile

from calsync.services.legacy_backup_recovery import LegacyBackupRecoveryService


def _legacy_sql_dump() -> bytes:
    return (
        "COPY public.provider_accounts (id, provider_type, provider_account_id, display_name, access_token_encrypted, refresh_token_encrypted, provider_metadata, created_at, updated_at, credential_secret_encrypted, auth_mode, can_read, can_write, requires_reconnect) FROM stdin;\n"
        "apple-account\ticloud_caldav\tkaymayers9@gmail.com\tkaymayers9@gmail.com\t\\\\N\t\\\\N\t{\"auth_status\": \"connected\", \"principal_url\": \"https://caldav.icloud.com/112135872/principal/\", \"calendar_home_url\": \"https://p52-caldav.icloud.com:443/112135872/calendars/\"}\t2026-05-14 19:47:44.895745+00\t2026-05-26 05:02:56.813761+00\tsecret\tcaldav\tt\tt\tf\n"
        "\\.\n"
        "COPY public.provider_calendars (id, provider_account_pk, provider_calendar_id, name, timezone, enabled, provider_metadata, created_at, updated_at, calendar_role) FROM stdin;\n"
        "family-cal\tapple-account\thttps://p52-caldav.icloud.com:443/112135872/calendars/06810ae4-a07b-49d9-9541-98123e74c806/\tFamily\t\\\\N\tf\t{\"href\": \"https://p52-caldav.icloud.com:443/112135872/calendars/06810ae4-a07b-49d9-9541-98123e74c806/\"}\t2026-05-14 19:47:45.997212+00\t2026-05-14 20:03:09.020352+00\twritable_booking_target\n"
        "calendar-cal\tapple-account\thttps://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/\tCalendar\t\\\\N\tt\t{\"href\": \"https://p52-caldav.icloud.com:443/112135872/calendars/6824BCB8-8CEE-4733-9208-4741C62E266C/\"}\t2026-05-14 19:47:45.997212+00\t2026-05-14 20:03:09.020352+00\tpersonal_reference\n"
        "\\.\n"
    ).encode("utf-8")


def test_legacy_backup_recovery_parses_zipped_apple_hints() -> None:
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("calsync-db-backup.sql", _legacy_sql_dump())

    recovery = LegacyBackupRecoveryService().extract_apple_hints(
        backup_bytes=payload.getvalue(),
        filename="calsync-db-backup.zip",
    )

    assert recovery["source_filename"] == "calsync-db-backup.zip"
    assert recovery["account_username"] == "kaymayers9@gmail.com"
    assert recovery["account_label"] == "kaymayers9@gmail.com"
    assert (
        recovery["calendar_home_url"]
        == "https://p52-caldav.icloud.com:443/112135872/calendars/"
    )
    assert recovery["principal_url"] == "https://caldav.icloud.com/112135872/principal/"
    assert recovery["recommended_calendar_name"] == "Family"
    assert (
        recovery["recommended_calendar_url"]
        == "https://p52-caldav.icloud.com:443/112135872/calendars/06810ae4-a07b-49d9-9541-98123e74c806/"
    )
    assert recovery["calendar_count"] == 2
    assert recovery["calendars"][0]["calendar_name"] == "Family"
    assert recovery["calendars"][0]["is_writable_hint"] is True
    assert recovery["calendars"][1]["calendar_name"] == "Calendar"
