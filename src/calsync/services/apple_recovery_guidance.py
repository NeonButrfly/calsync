from __future__ import annotations

from collections.abc import Mapping


def describe_legacy_apple_recovery_action(
    legacy_apple_recovery_hints: Mapping[str, object],
    *,
    opener: str = "Open Apple setup",
) -> str:
    if bool(legacy_apple_recovery_hints.get("can_reuse_saved_password")):
        return f"{opener} and validate or save the loaded recovered calendar"
    if bool(legacy_apple_recovery_hints.get("encrypted_secret_present")):
        return (
            f"{opener}, then either restore the original CalSync encryption key or "
            "save a fresh app-specific password"
        )
    return (
        f"{opener}, confirm the loaded recovered calendar, and save a fresh "
        "app-specific password"
    )
