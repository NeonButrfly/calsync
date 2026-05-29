from pathlib import Path


def test_docs_cover_first_family_scheduling_console() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "#39" in readme_content
    assert "first real scheduling console" in readme_content
    assert "edit flow for existing appointments" in readme_content
    assert "http://127.0.0.1:3080/" in readme_content

    assert "#39" in ops_content
    assert "web scheduling console" in ops_content
    assert "post /appointments" in ops_content
    assert "professional web scheduling console" in ops_content

    assert "#39" in prompt_content
    assert "polished scheduling console" in prompt_content
    assert "professional product surface" in prompt_content


def test_docs_cover_first_alexa_skill_slice() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()
    interaction_model_content = Path(
        "workers/edge-calsync/alexa/interaction-model.json"
    ).read_text(encoding="utf-8").lower()

    assert "#38" in readme_content
    assert "post /alexa" in readme_content
    assert "alexa_allowed_skill_ids" in readme_content

    assert "#38" in ops_content
    assert "createappointmentintent" in ops_content
    assert "linked access token" in ops_content

    assert "#38" in prompt_content
    assert "post /alexa" in prompt_content
    assert "shared-household alexa adapter" in prompt_content

    assert "createappointmentintent" in interaction_model_content
    assert "listappointmentsintent" in interaction_model_content
