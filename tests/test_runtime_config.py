from pathlib import Path

import yaml


def test_api_container_mounts_runtime_token_store() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    api_volumes = compose["services"]["api"].get("volumes", [])

    assert "./.runtime:/app/.runtime" in api_volumes
