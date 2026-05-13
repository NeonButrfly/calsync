from __future__ import annotations

import typer

from calsync.config import Settings
from calsync.db import create_session_factory
from calsync.services.auth import validate_password_strength
from calsync.services.bootstrap import reset_admin_mfa, reset_admin_password


app = typer.Typer(
    help="Local operator commands for CalSync administration.",
    add_completion=False,
)


@app.command("reset-admin-password")
def reset_admin_password_command(
    identifier: str = typer.Option(..., "--identifier", help="Admin username or email."),
    password: str = typer.Option(
        ...,
        prompt="New password",
        confirmation_prompt=True,
        hide_input=True,
        help="New admin password.",
    ),
) -> None:
    password_errors = validate_password_strength(password)
    if password_errors:
        raise typer.BadParameter(" ".join(password_errors), param_hint="--password")

    session_factory = create_session_factory(Settings())
    with session_factory() as session:
        try:
            user = reset_admin_password(
                session,
                identifier=identifier,
                password=password,
            )
        except LookupError as error:
            raise typer.Exit(code=_print_error(str(error))) from error

    typer.echo(
        f"Admin password reset for {user.username}. Existing sessions were invalidated."
    )


@app.command("reset-admin-mfa")
def reset_admin_mfa_command(
    identifier: str = typer.Option(..., "--identifier", help="Admin username or email."),
) -> None:
    session_factory = create_session_factory(Settings())
    with session_factory() as session:
        try:
            user = reset_admin_mfa(
                session,
                identifier=identifier,
            )
        except LookupError as error:
            raise typer.Exit(code=_print_error(str(error))) from error

    typer.echo(
        f"Admin MFA reset for {user.username}. Existing sessions were invalidated."
    )


def _print_error(message: str) -> int:
    typer.echo(message, err=True)
    return 1


if __name__ == "__main__":
    app()
