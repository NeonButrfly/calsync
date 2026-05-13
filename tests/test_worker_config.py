from __future__ import annotations

from pathlib import Path

from calsync.config import Settings


def test_worker_uses_same_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 3080


def test_settings_accept_blank_public_url_and_ignore_compose_only_values(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "compose.env"
    env_path.write_text(
        "\n".join(
            [
                "PUBLIC_BASE_URL=",
                "POSTGRES_DB=calsync",
                "POSTGRES_USER=calsync",
                "POSTGRES_PASSWORD=calsync",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_path)

    assert settings.public_base_url is None


def test_env_example_documents_port_override() -> None:
    content = Path(".env.example").read_text(encoding="utf-8")

    assert "APP_HOST=0.0.0.0" in content
    assert "APP_PORT=3080" in content
    assert "PUBLIC_BASE_URL=" in content


def test_docker_compose_uses_configurable_port_mapping() -> None:
    content = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert '${APP_PORT:-3080}:${APP_PORT:-3080}' in content
    assert '--host ${APP_HOST:-0.0.0.0}' in content
    assert '--port ${APP_PORT:-3080}' in content
    assert '${CALSYNC_DATABASE_URL:-postgresql+psycopg://calsync:calsync@db:5432/calsync}' in content
    assert '${DATABASE_URL:-' not in content
    assert 'migrate:' in content
    assert 'service_completed_successfully' in content
    assert 'python -m uvicorn calsync.main:app' in content
    assert 'python -m calsync.worker' in content
    assert '- alembic' in content
    assert '- upgrade' in content
    assert '- head' in content


def test_dockerfile_installs_editable_source_tree() -> None:
    content = Path("Dockerfile").read_text(encoding="utf-8")

    assert "pip install --no-cache-dir --editable ." in content
