from __future__ import annotations


CALENDAR_ROLE_AVAILABILITY_ONLY = "availability_only"
CALENDAR_ROLE_CONFLICT_ONLY = "conflict_only"
CALENDAR_ROLE_WRITABLE_BOOKING_TARGET = "writable_booking_target"
CALENDAR_ROLE_PERSONAL_REFERENCE = "personal_reference"
CALENDAR_ROLE_HIDDEN = "hidden"

CALENDAR_ROLES = (
    CALENDAR_ROLE_AVAILABILITY_ONLY,
    CALENDAR_ROLE_CONFLICT_ONLY,
    CALENDAR_ROLE_WRITABLE_BOOKING_TARGET,
    CALENDAR_ROLE_PERSONAL_REFERENCE,
    CALENDAR_ROLE_HIDDEN,
)


def calendar_role_check_constraint(column_name: str) -> str:
    allowed_roles = ", ".join(f"'{role}'" for role in CALENDAR_ROLES)
    return f"{column_name} IN ({allowed_roles})"
