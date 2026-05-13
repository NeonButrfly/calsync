from calsync.services.auth import validate_password_strength


def test_weak_password_is_rejected() -> None:
    errors = validate_password_strength("short1!")

    assert any("at least 12 characters" in error for error in errors)
