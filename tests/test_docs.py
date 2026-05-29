from pathlib import Path
import json


def test_docs_cover_first_family_scheduling_console() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "#39" in readme_content
    assert "#40" in readme_content
    assert "#41" in readme_content
    assert "#43" in readme_content
    assert "#44" in readme_content
    assert "#45" in readme_content
    assert "#37" in readme_content
    assert "polished scheduling workspace" in readme_content
    assert "live apple primary-calendar reads" in readme_content
    assert "selected appointment detail" in readme_content
    assert "hide cancelled appointments by default" in readme_content
    assert "readiness surface" in readme_content
    assert "get /api/readiness" in readme_content
    assert "get /alexa/setup" in readme_content
    assert "get /alexa/simulator" in readme_content
    assert "alexa setup page" in readme_content
    assert "alexa simulator page" in readme_content
    assert "downloadable skill package" in readme_content
    assert "https://mcp-calsync.kaymayers9.workers.dev/mcp" in readme_content
    assert "https://mcp-calsync.neonbutterfly.net/mcp" in readme_content
    assert "list_appointments" in readme_content
    assert "edge_internal_token" in readme_content
    assert "mounts that same `.runtime` directory" in readme_content
    assert "http://127.0.0.1:3080/" in readme_content

    assert "#37" in ops_content
    assert "#39" in ops_content
    assert "#40" in ops_content
    assert "#41" in ops_content
    assert "#43" in ops_content
    assert "#45" in ops_content
    assert "mounts it at `/app/.runtime`" in ops_content
    assert "web scheduling workspace" in ops_content
    assert "syncs existing apple calendar events" in ops_content
    assert "post /appointments" in ops_content
    assert "professional web scheduling workspace" in ops_content
    assert "get /api/appointments/{appointment_id}" in ops_content
    assert "include_cancelled=true" in ops_content
    assert "get /api/readiness" in ops_content
    assert "get /alexa/setup" in ops_content
    assert "get /alexa/simulator" in ops_content
    assert "get /alexa/skill-package.zip" in ops_content
    assert "post /alexa/simulator" in ops_content
    assert "post /alexa/simulate" in ops_content
    assert "downloadable alexa custom skill package zip" in ops_content
    assert "post /mcp" in ops_content
    assert "mcp_auth_token" in ops_content
    assert "edge_internal_token" in ops_content
    assert "get /status" in ops_content
    assert "channel-token presence that exists in `/home/kay/apps/calsync/.runtime/channel-tokens.json`" in ops_content

    assert "#37" in prompt_content
    assert "#39" in prompt_content
    assert "#40" in prompt_content
    assert "#41" in prompt_content
    assert "#43" in prompt_content
    assert "#45" in prompt_content
    assert "apple live calendar sync requirement" in prompt_content
    assert "selected appointment detail surface" in prompt_content
    assert "get /v1/appointments/{appointment_id}" in prompt_content
    assert "default active views should hide cancelled appointments" in prompt_content
    assert "full-stack readiness requirement" in prompt_content
    assert "api container must mount that same host `.runtime` directory" in prompt_content
    assert "in-product alexa setup requirement" in prompt_content
    assert "get /alexa/setup" in prompt_content
    assert "get /alexa/skill-package.zip" in prompt_content
    assert "get /alexa/simulator" in prompt_content
    assert "post /alexa/simulate" in prompt_content
    assert "remote mcp worker requirement" in prompt_content
    assert "https://mcp-calsync.neonbutterfly.net/mcp" in prompt_content
    assert "workers.dev" in prompt_content
    assert "forward mcp tool calls into the live edge/origin stack" in prompt_content


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
    assert "post /alexa/simulate" in readme_content
    assert "alexa_allowed_skill_ids" in readme_content
    assert "/privacy" in readme_content
    assert "/terms" in readme_content
    assert "cancelappointmentintent" in readme_content
    assert "rescheduleappointmentintent" in readme_content
    assert "next upcoming appointment" in readme_content

    assert "#38" in ops_content
    assert "createappointmentintent" in ops_content
    assert "cancelappointmentintent" in ops_content
    assert "rescheduleappointmentintent" in ops_content
    assert "nextappointmentintent" in ops_content
    assert "request-signature flow" in ops_content
    assert "skill-package" in ops_content
    assert "alexa simulator page" in ops_content
    assert "spoken response" in ops_content
    assert "token-hash presence flags" in ops_content

    assert "#38" in prompt_content
    assert "post /alexa" in prompt_content
    assert "post /alexa/simulate" in prompt_content
    assert "shared-household alexa adapter" in prompt_content
    assert "request-signature flow" in prompt_content
    assert "get /privacy" in prompt_content
    assert "get /alexa/simulator" in prompt_content
    assert "cancel a matching appointment" in prompt_content
    assert "reschedule a matching appointment" in prompt_content
    assert "read the next upcoming appointment" in prompt_content

    assert "createappointmentintent" in interaction_model_content
    assert "listappointmentsintent" in interaction_model_content
    assert "nextappointmentintent" in interaction_model_content
    assert "cancelappointmentintent" in interaction_model_content
    assert "rescheduleappointmentintent" in interaction_model_content
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
    assert "next upcoming appointment" in alexa_readme_content
