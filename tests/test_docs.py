from pathlib import Path
import json


def test_docs_cover_first_family_scheduling_console() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "#39" in readme_content
    assert "#40" in readme_content
    assert "polished scheduling workspace" in readme_content
    assert "selected appointment detail" in readme_content
    assert "http://127.0.0.1:3080/" in readme_content

    assert "#39" in ops_content
    assert "#40" in ops_content
    assert "web scheduling workspace" in ops_content
    assert "post /appointments" in ops_content
    assert "professional web scheduling workspace" in ops_content
    assert "get /api/appointments/{appointment_id}" in ops_content

    assert "#39" in prompt_content
    assert "#40" in prompt_content
    assert "selected appointment detail surface" in prompt_content
    assert "get /v1/appointments/{appointment_id}" in prompt_content


def test_docs_cover_first_alexa_skill_slice() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()
    interaction_model_content = Path(
        "workers/edge-calsync/alexa/interaction-model.json"
    ).read_text(encoding="utf-8").lower()
    skill_manifest = json.loads(
        Path("workers/edge-calsync/alexa/skill-package/skill.json").read_text(
            encoding="utf-8"
        )
    )
    packaged_interaction_model = json.loads(
        Path(
            "workers/edge-calsync/alexa/skill-package/interactionModels/custom/en-US.json"
        ).read_text(encoding="utf-8")
    )
    alexa_readme_content = Path(
        "workers/edge-calsync/alexa/README.md"
    ).read_text(encoding="utf-8").lower()

    assert "#38" in readme_content
    assert "post /alexa" in readme_content
    assert "alexa_allowed_skill_ids" in readme_content
    assert "/privacy" in readme_content
    assert "/terms" in readme_content

    assert "#38" in ops_content
    assert "createappointmentintent" in ops_content
    assert "request-signature flow" in ops_content
    assert "skill-package" in ops_content

    assert "#38" in prompt_content
    assert "post /alexa" in prompt_content
    assert "shared-household alexa adapter" in prompt_content
    assert "request-signature flow" in prompt_content
    assert "get /privacy" in prompt_content

    assert "createappointmentintent" in interaction_model_content
    assert "listappointmentsintent" in interaction_model_content
    assert (
        skill_manifest["manifest"]["apis"]["custom"]["endpoint"]["uri"]
        == "https://edge-calsync.neonbutterfly.net/alexa"
    )
    assert (
        skill_manifest["manifest"]["privacyAndCompliance"]["locales"]["en-US"][
            "privacyPolicyUrl"
        ]
        == "https://calsync.neonbutterfly.net/privacy"
    )
    assert (
        skill_manifest["manifest"]["privacyAndCompliance"]["locales"]["en-US"][
            "termsOfUseUrl"
        ]
        == "https://calsync.neonbutterfly.net/terms"
    )
    assert (
        packaged_interaction_model["interactionModel"]["languageModel"]["invocationName"]
        == "cal sync family"
    )
    assert "create or import the custom skill package" in alexa_readme_content
