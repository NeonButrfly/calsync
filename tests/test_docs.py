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
    assert "#46" in readme_content
    assert "#47" in readme_content
    assert "#48" in readme_content
    assert "#49" in readme_content
    assert "#50" in readme_content
    assert "#51" in readme_content
    assert "#52" in readme_content
    assert "#53" in readme_content
    assert "#54" in readme_content
    assert "#55" in readme_content
    assert "#56" in readme_content
    assert "#57" in readme_content
    assert "#58" in readme_content
    assert "#59" in readme_content
    assert "#60" in readme_content
    assert "#61" in readme_content
    assert "#62" in readme_content
    assert "#63" in readme_content
    assert "#65" in readme_content
    assert "#66" in readme_content
    assert "#67" in readme_content
    assert "#68" in readme_content
    assert "#69" in readme_content
    assert "#70" in readme_content
    assert "#71" in readme_content
    assert "#72" in readme_content
    assert "#73" in readme_content
    assert "#74" in readme_content
    assert "#75" in readme_content
    assert "#76" in readme_content
    assert "#77" in readme_content
    assert "#78" in readme_content
    assert "#79" in readme_content
    assert "#80" in readme_content
    assert "#81" in readme_content
    assert "#82" in readme_content
    assert "#31" in readme_content
    assert "#3" in readme_content
    assert "#37" in readme_content
    assert "polished scheduling workspace" in readme_content
    assert "live apple primary-calendar reads" in readme_content
    assert "selected appointment detail" in readme_content
    assert "hide cancelled appointments by default" in readme_content
    assert "readiness surface" in readme_content
    assert "get /api/readiness" in readme_content
    assert "get /api/availability" in readme_content
    assert "get /connections" in readme_content
    assert "post /connections/test" in readme_content
    assert "post /connections/alexa" in readme_content
    assert "get /connections/settings-backup" in readme_content
    assert "post /connections/legacy-backup/import" in readme_content
    assert "post /connections/settings-restore" in readme_content
    assert "post /connections/google/refresh" in readme_content
    assert "post /connections/google/disconnect" in readme_content
    assert "post /connections/microsoft/refresh" in readme_content
    assert "post /connections/microsoft/disconnect" in readme_content
    assert "get /alexa/setup" in readme_content
    assert "post /alexa/setup" in readme_content
    assert "get /calendar/setup" in readme_content
    assert "post /calendar/setup" in readme_content
    assert "post /calendar/setup/validate" in readme_content
    assert "post /calendar/setup/calendars" in readme_content
    assert "get /google/setup" in readme_content
    assert "post /google/setup" in readme_content
    assert "get /auth/google/start" in readme_content
    assert "get /auth/google/callback" in readme_content
    assert "get /microsoft/setup" in readme_content
    assert "post /microsoft/setup" in readme_content
    assert "post /microsoft/setup/refresh" in readme_content
    assert "post /microsoft/setup/disconnect" in readme_content
    assert "get /auth/microsoft/start" in readme_content
    assert "get /auth/microsoft/callback" in readme_content
    assert "get /alexa/simulator" in readme_content
    assert "alexa setup page" in readme_content
    assert "apple calendar setup page" in readme_content
    assert "apple account management flow" in readme_content
    assert "multiple connected apple accounts under the same product-managed scheduling surface" in readme_content
    assert "browser-based google oauth connect on the live calsync domain" in readme_content
    assert "google calendar refresh and disconnect controls" in readme_content
    assert "multiple connected google accounts under one shared oauth app" in readme_content
    assert "writable google calendar targets" in readme_content
    assert "browser-based microsoft oauth connect on the live calsync domain" in readme_content
    assert "microsoft calendar refresh and disconnect controls" in readme_content
    assert "multiple connected microsoft accounts under one shared oauth app" in readme_content
    assert "writable microsoft calendar targets" in readme_content
    assert "google and microsoft setup surfaces that now block browser connect actions until the shared oauth app is actually saved" in readme_content
    assert "writable calendar smoke tests" in readme_content
    assert "connections workspace at `/connections`" in readme_content
    assert "checklist-style connections workspace" in readme_content
    assert "persisted connection verification summaries" in readme_content
    assert "stronger connections control center" in readme_content
    assert "alexa turn-on controls in `/connections`" in readme_content
    assert "encrypted operator-settings backup and restore" in readme_content
    assert "planner-style scheduling board" in readme_content
    assert "public booking page at `/book`" in readme_content
    assert "invitee contact capture in the public booking flow" in readme_content
    assert "booking setup page at `/booking/setup`" in readme_content
    assert "get /booking/setup" in readme_content
    assert "public booking flow is now configurable" in readme_content
    assert "public booking availability rules" in readme_content
    assert "multiple public booking types with shareable links" in readme_content
    assert "public booking catalog at `/book`" in readme_content
    assert "default `/book` route now becomes a booking-type chooser" in readme_content
    assert "booking type management actions" in readme_content
    assert "public booking flow now captures the requester name and contact details" in readme_content
    assert "booking setup now also blocks its save and create actions clearly when no writable calendar is connected" in readme_content
    assert "bookable weekdays and daily booking hours" in readme_content
    assert "/book/school-intake" in readme_content
    assert "get /book" in readme_content
    assert "invitee claim an open time" in readme_content
    assert "day, week, and month planning states" in readme_content
    assert "target-calendar picker" in readme_content
    assert "open-time finder" in readme_content
    assert "multiple saved apple calendar targets" in readme_content
    assert "edge-settings form" in readme_content
    assert "cloudflare access form" in readme_content
    assert "product vault" in readme_content
    assert "alexa simulator page" in readme_content
    assert "downloadable skill package" in readme_content
    assert "persisted desired alexa edge settings" in readme_content
    assert "truthful save-only alexa action labels on `/alexa/setup` and `/connections`" in readme_content
    assert "restore-aware readiness guidance" in readme_content
    assert "legacy pi-backup import path for apple recovery hints" in readme_content
    assert "load recovered apple backup hints into the setup form" in readme_content
    assert "automatic loading of the recommended recovered apple hint on the default setup page" in readme_content
    assert "shared apple recovery guidance that now reflects the already-loaded reconnect state" in readme_content
    assert "make apple recovery messaging point to the reconnect step" in readme_content
    assert "recovery-aware apple messaging across readiness, connections, and apple setup" in readme_content
    assert "safe apple setup validation before reconnect save" in readme_content
    assert "legacy apple recovery hint ranking that now prefers the real recovered writable booking target over a merely enabled personal-reference calendar" in readme_content
    assert "voice-specific next guidance on alexa-focused setup surfaces" in readme_content
    assert "simulator readiness summary for no-calendar voice testing states" in readme_content
    assert "live-vs-desired drift visibility" in readme_content
    assert "workspace capability summary now reflects the actual connected readiness state" in readme_content
    assert "root workspace now also blocks the create flow clearly when no writable calendar is connected" in readme_content
    assert "root workspace now also blocks availability search clearly when no writable calendar is connected" in readme_content
    assert "public booking flow now also blocks the invitee-facing availability refresh controls clearly when no writable calendar is connected" in readme_content
    assert "root workspace now also blocks the empty schedule board and detail panel clearly when no writable calendar is connected" in readme_content
    assert "apple setup page now also stays truthful when no apple account exists" in readme_content
    assert "that apple setup page now also exposes a safe validation action before save, so operators can test a fresh app-specific password and calendar url without mutating the live vault state" in readme_content
    assert "named apple calendar targeting through alexa and the simulator" in readme_content
    assert "provider-aware alexa calendar targeting across apple, google, and microsoft" in readme_content
    assert "https://mcp-calsync.kaymayers9.workers.dev/mcp" in readme_content
    assert "https://mcp-calsync.neonbutterfly.net/mcp" in readme_content
    assert "workers.dev mcp fallback" in readme_content
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
    assert "#46" in ops_content
    assert "#47" in ops_content
    assert "#48" in ops_content
    assert "#49" in ops_content
    assert "#50" in ops_content
    assert "#51" in ops_content
    assert "#52" in ops_content
    assert "#53" in ops_content
    assert "#54" in ops_content
    assert "#55" in ops_content
    assert "#56" in ops_content
    assert "#57" in ops_content
    assert "#58" in ops_content
    assert "#59" in ops_content
    assert "#60" in ops_content
    assert "#61" in ops_content
    assert "#62" in ops_content
    assert "#63" in ops_content
    assert "#65" in ops_content
    assert "#66" in ops_content
    assert "#67" in ops_content
    assert "#68" in ops_content
    assert "#69" in ops_content
    assert "#70" in ops_content
    assert "#71" in ops_content
    assert "#72" in ops_content
    assert "#73" in ops_content
    assert "#74" in ops_content
    assert "#75" in ops_content
    assert "#76" in ops_content
    assert "#77" in ops_content
    assert "#78" in ops_content
    assert "#79" in ops_content
    assert "#80" in ops_content
    assert "#81" in ops_content
    assert "#82" in ops_content
    assert "#31" in ops_content
    assert "#3" in ops_content
    assert "mounts it at `/app/.runtime`" in ops_content
    assert "web scheduling workspace" in ops_content
    assert "syncs existing apple calendar events" in ops_content
    assert "post /appointments" in ops_content
    assert "professional web scheduling workspace" in ops_content
    assert "connections workspace at `/connections`" in ops_content
    assert "get /api/appointments/{appointment_id}" in ops_content
    assert "get /api/availability" in ops_content
    assert "include_cancelled=true" in ops_content
    assert "get /api/readiness" in ops_content
    assert "get /calendar/setup" in ops_content
    assert "post /calendar/setup" in ops_content
    assert "post /calendar/setup/validate" in ops_content
    assert "post /calendar/setup/calendars" in ops_content
    assert "get /connections" in ops_content
    assert "post /connections/test" in ops_content
    assert "post /connections/alexa" in ops_content
    assert "get /connections/settings-backup" in ops_content
    assert "post /connections/legacy-backup/import" in ops_content
    assert "post /connections/settings-restore" in ops_content
    assert "post /connections/google/refresh" in ops_content
    assert "post /connections/google/disconnect" in ops_content
    assert "post /connections/microsoft/refresh" in ops_content
    assert "post /connections/microsoft/disconnect" in ops_content
    assert "get /google/setup" in ops_content
    assert "post /google/setup" in ops_content
    assert "get /auth/google/start" in ops_content
    assert "get /auth/google/callback" in ops_content
    assert "get /microsoft/setup" in ops_content
    assert "post /microsoft/setup" in ops_content
    assert "post /microsoft/setup/refresh" in ops_content
    assert "post /microsoft/setup/disconnect" in ops_content
    assert "get /auth/microsoft/start" in ops_content
    assert "get /auth/microsoft/callback" in ops_content
    assert "get /alexa/setup" in ops_content
    assert "post /alexa/setup" in ops_content
    assert "get /alexa/simulator" in ops_content
    assert "get /alexa/skill-package.zip" in ops_content
    assert "post /alexa/simulator" in ops_content
    assert "post /alexa/simulate" in ops_content
    assert "provider-aware calendar targets drawn from the shared scheduling brain" in ops_content
    assert "get /v1/availability" in ops_content
    assert "cloudflare worker access form" in ops_content
    assert "apple calendar setup page" in ops_content
    assert "more than one connected apple account" in ops_content
    assert "a safe validation action that tests fresh apple credentials and calendar access before save" in ops_content
    assert "google setup page" in ops_content
    assert "browser-based account connect on the live calsync domain" in ops_content
    assert "multiple connected google accounts under the same shared oauth app" in ops_content
    assert "writable google targets appear in the same picker" in ops_content
    assert "refresh action that resyncs one connected google account email and discovered calendars" in ops_content
    assert "disconnect action that clears one linked google account" in ops_content
    assert "run an in-product write smoke test" in ops_content
    assert "checklist-style verification center at `/connections`" in ops_content
    assert "direct google and microsoft refresh/disconnect actions from `/connections`" in ops_content
    assert "alexa launch state and quick edge-setting controls from `/connections`" in ops_content
    assert "uses restore-aware readiness guidance when only non-provider settings remain" in ops_content
    assert "legacy pi-backup import path on `/connections`" in ops_content
    assert "one-step loading of recovered apple hints into the setup form" in ops_content
    assert "automatic default loading of the recommended apple recovery hint" in ops_content
    assert "shared apple recovery guidance aligned with the already-loaded reconnect state" in ops_content
    assert "recovery-aware apple reconnect messaging" in ops_content
    assert "encrypted operator-settings backup and restore from `/connections`" in ops_content
    assert "surfaces recovered legacy apple hints on `/calendar/setup`" in ops_content
    assert "load a recovered apple calendar hint directly into the `/calendar/setup` form" in ops_content
    assert "safe apple setup validation before reconnect save" in ops_content
    assert "recovery-aware apple hint ranking that prefers true writable booking targets" in ops_content
    assert "voice-specific next guidance for alexa setup and connections voice panels" in ops_content
    assert "simulator readiness guidance for missing connected calendar states" in ops_content
    assert "planner-style day/week/month board at `/`" in ops_content
    assert "first public booking page at `/book`" in ops_content
    assert "public booking requester contact capture" in ops_content
    assert "in-product booking setup page at `/booking/setup`" in ops_content
    assert "get /booking/setup" in ops_content
    assert "public booking weekday and hour rules" in ops_content
    assert "multiple public booking types" in ops_content
    assert "public booking catalog so `/book` becomes a chooser" in ops_content
    assert "in-product booking type management" in ops_content
    assert "booking-type chooser at `/book`" in ops_content
    assert "post /booking/setup/types/default" in ops_content
    assert "post /booking/setup/types/delete" in ops_content
    assert "get /book/{slug}" in ops_content
    assert "invitee-facing copy, default duration, search horizon, success message, and chosen writable target" in ops_content
    assert "get /book" in ops_content
    assert "searches open time and creates a real appointment" in ops_content
    assert "public booking requester contact fields" in ops_content
    assert "distinct day, week, and month planning states" in ops_content
    assert "microsoft setup page" in ops_content
    assert "browser-based account connect on the live calsync domain" in ops_content
    assert "multiple connected microsoft accounts under the same shared oauth app" in ops_content
    assert "writable microsoft targets appear in the same picker" in ops_content
    assert "refresh action that resyncs one connected microsoft account email and discovered calendars" in ops_content
    assert "disconnect action that clears one linked microsoft account" in ops_content
    assert "target apple calendar" in ops_content
    assert "additional tracked apple calendar targets" in ops_content
    assert "move an appointment from one saved apple calendar target to another" in ops_content
    assert "encrypted with `encryption_key`" in ops_content
    assert "workers scripts write" in ops_content
    assert "enable_alexa" in ops_content
    assert "alexa_allowed_skill_ids" in ops_content
    assert "downloadable alexa custom skill package zip" in ops_content
    assert "desired alexa edge-state summary" in ops_content
    assert "save-now/apply-later path" in ops_content
    assert "truthful save-only action labels instead of implying a live apply path that cannot run yet" in ops_content
    assert "actual connected readiness state instead of static broad capability copy" in ops_content
    assert "blocked root create state when no writable calendar is connected" in ops_content
    assert "blocked root availability state when no writable calendar is connected" in ops_content
    assert "blocked root schedule-sync state when no writable calendar is connected" in ops_content
    assert "blocked public-booking availability state when no writable calendar is connected" in ops_content
    assert "blocked booking-setup state when no writable calendar is connected" in ops_content
    assert "blocked google and microsoft browser-connect actions until the shared oauth app has been saved" in ops_content
    assert "truthful apple setup empty state when no apple account is connected" in ops_content
    assert "post /mcp" in ops_content
    assert "mcp_auth_token" in ops_content
    assert "edge_internal_token" in ops_content
    assert "workers.dev mcp fallback" in ops_content
    assert "get /status" in ops_content
    assert "channel-token presence that exists in `/home/kay/apps/calsync/.runtime/channel-tokens.json`" in ops_content

    assert "#37" in prompt_content
    assert "#39" in prompt_content
    assert "#40" in prompt_content
    assert "#41" in prompt_content
    assert "#43" in prompt_content
    assert "#45" in prompt_content
    assert "#46" in prompt_content
    assert "#47" in prompt_content
    assert "#48" in prompt_content
    assert "#49" in prompt_content
    assert "#50" in prompt_content
    assert "#51" in prompt_content
    assert "#52" in prompt_content
    assert "#53" in prompt_content
    assert "#54" in prompt_content
    assert "#55" in prompt_content
    assert "#56" in prompt_content
    assert "#57" in prompt_content
    assert "#58" in prompt_content
    assert "#59" in prompt_content
    assert "#60" in prompt_content
    assert "#61" in prompt_content
    assert "#62" in prompt_content
    assert "#63" in prompt_content
    assert "#65" in prompt_content
    assert "#66" in prompt_content
    assert "#67" in prompt_content
    assert "#68" in prompt_content
    assert "#69" in prompt_content
    assert "#70" in prompt_content
    assert "#71" in prompt_content
    assert "#72" in prompt_content
    assert "#73" in prompt_content
    assert "#74" in prompt_content
    assert "#75" in prompt_content
    assert "#76" in prompt_content
    assert "#77" in prompt_content
    assert "#78" in prompt_content
    assert "#79" in prompt_content
    assert "#31" in prompt_content
    assert "#3" in prompt_content
    assert "#17" in prompt_content
    assert "apple live calendar sync requirement" in prompt_content
    assert "in-product apple calendar setup requirement" in prompt_content
    assert "selected appointment detail surface" in prompt_content
    assert "get /v1/appointments/{appointment_id}" in prompt_content
    assert "get /api/availability" in prompt_content
    assert "default active views should hide cancelled appointments" in prompt_content
    assert "full-stack readiness requirement" in prompt_content
    assert "api container must mount that same host `.runtime` directory" in prompt_content
    assert "in-product alexa setup requirement" in prompt_content
    assert "shared `/connections` surface should show the current alexa launch state" in prompt_content
    assert "encrypted export and restore path for operator settings" in prompt_content
    assert "alexa-focused surfaces should show voice-specific next steps" in prompt_content
    assert "simulator should show clear readiness and blocker guidance when no connected calendars are available" in prompt_content
    assert "get /alexa/setup" in prompt_content
    assert "get /alexa/skill-package.zip" in prompt_content
    assert "get /alexa/simulator" in prompt_content
    assert "get /calendar/setup" in prompt_content
    assert "post /calendar/setup" in prompt_content
    assert "post /calendar/setup/validate" in prompt_content
    assert "post /calendar/setup/calendars" in prompt_content
    assert "get /google/setup" in prompt_content
    assert "post /google/setup" in prompt_content
    assert "get /auth/google/start" in prompt_content
    assert "get /auth/google/callback" in prompt_content
    assert "get /microsoft/setup" in prompt_content
    assert "post /microsoft/setup" in prompt_content
    assert "get /auth/microsoft/start" in prompt_content
    assert "get /auth/microsoft/callback" in prompt_content
    assert "save the apple account label" in prompt_content
    assert "support more than one connected apple account under that setup surface" in prompt_content
    assert "in-product google oauth setup and writable targets requirement" in prompt_content
    assert "unified connections ux requirement" in prompt_content
    assert "connections verification center requirement" in prompt_content
    assert "connections provider control center requirement" in prompt_content
    assert "planner-style schedule board requirement" in prompt_content
    assert "public booking page requirement" in prompt_content
    assert "in-product booking setup requirement" in prompt_content
    assert "`get /booking/setup` should render an operator-facing booking setup page" in prompt_content
    assert "booking settings should be stored securely in the product vault" in prompt_content
    assert "public booking availability rules requirement" in prompt_content
    assert "operators should be able to define which weekdays and hours are actually bookable" in prompt_content
    assert "multiple public booking types requirement" in prompt_content
    assert "shareable public url like `/book/school-intake`" in prompt_content
    assert "public booking catalog requirement" in prompt_content
    assert "when more than one public booking type exists, `get /book` should render a chooser" in prompt_content
    assert "weekday summary, and time-window summary" in prompt_content
    assert "public booking type management requirement" in prompt_content
    assert "make an existing booking type the default public `/book` flow" in prompt_content
    assert "delete an existing booking type" in prompt_content
    assert "public booking invitee contact requirement" in prompt_content
    assert "should require the requester name" in prompt_content
    assert "should require requester contact details" in prompt_content
    assert "`get /book` should render a public booking page" in prompt_content
    assert "create a real appointment on the default writable connected calendar target" in prompt_content
    assert "get /connections" in prompt_content
    assert "post /connections/test" in prompt_content
    assert "`/` should render a day board" in prompt_content
    assert "`/` should render a week board" in prompt_content
    assert "`/` should render a month board" in prompt_content
    assert "save the shared google oauth client id and client secret" in prompt_content
    assert "save the google refresh token" in prompt_content
    assert "support more than one connected google account under that shared oauth app" in prompt_content
    assert "expose a live refresh path" in prompt_content
    assert "safe disconnect path" in prompt_content
    assert "create, update, cancel, and date-range sync google events" in prompt_content
    assert "in-product microsoft oauth setup and writable targets requirement" in prompt_content
    assert "save the shared microsoft oauth client id and client secret" in prompt_content
    assert "save the microsoft refresh token" in prompt_content
    assert "support more than one connected microsoft account under that shared oauth app" in prompt_content
    assert "create, update, cancel, and date-range sync microsoft events" in prompt_content
    assert "multi-calendar apple target requirement" in prompt_content
    assert "target_calendar_url" in prompt_content
    assert "create and edit flows should expose a target calendar picker" in prompt_content
    assert "named apple calendar voice target requirement" in prompt_content
    assert "provider-aware alexa calendar target requirement" in prompt_content
    assert "family on google" in prompt_content
    assert "calendar on microsoft" in prompt_content
    assert "in-product writable calendar smoke test requirement" in prompt_content
    assert "run write test" in prompt_content
    assert "target_calendar_name" in prompt_content
    assert "availability requirement" in prompt_content
    assert "findavailabilityintent" in prompt_content
    assert "save cloudflare worker-management credentials inside the product" in prompt_content
    assert "stored encrypted at rest with `encryption_key`" in prompt_content
    assert "desired alexa edge settings requirement" in prompt_content
    assert "restore-aware readiness requirement" in prompt_content
    assert "legacy apple backup recovery requirement" in prompt_content
    assert "legacy apple recovery form prefill requirement" in prompt_content
    assert "apple recovery guidance requirement" in prompt_content
    assert "apple setup validation requirement" in prompt_content
    assert "legacy apple recommended target requirement" in prompt_content
    assert "alexa save-only action truthfulness requirement" in prompt_content
    assert "should always save the desired `enable_alexa` and `alexa_allowed_skill_ids` values" in prompt_content
    assert "workspace truthfulness requirement" in prompt_content
    assert "root no-calendar create-state requirement" in prompt_content
    assert "root no-calendar availability requirement" in prompt_content
    assert "public booking no-calendar availability requirement" in prompt_content
    assert "booking setup no-calendar truthfulness requirement" in prompt_content
    assert "provider connect action truthfulness requirement" in prompt_content
    assert "root no-calendar schedule-sync requirement" in prompt_content
    assert "apple setup no-account truthfulness requirement" in prompt_content
    assert "should not show broken helper copy or capability language that overstates the currently connected live state" in prompt_content
    assert "target-calendar control should render as unavailable when there are no writable calendars to choose from" in prompt_content
    assert "disconnected availability requests should not fall back to `no open windows found`" in prompt_content
    assert "invitee-facing availability refresh controls should look blocked in the ui until at least one writable calendar target is connected" in prompt_content
    assert "the root month board should not show `open` as if it were a normal empty calendar" in prompt_content
    assert "the add-calendar form should stay hidden or blocked until the first apple account exists" in prompt_content
    assert "disconnected `post /booking/setup` requests should fail clearly instead of saving disconnected public-booking defaults" in prompt_content
    assert "disconnected `post /booking/setup/types` requests should fail clearly instead of creating shareable booking links that cannot schedule anywhere" in prompt_content
    assert "`get /google/setup` should keep `connect google account` blocked until both the shared google client id and client secret are saved" in prompt_content
    assert "`get /connections` should reflect the same blocked browser-connect state for google and microsoft until their shared oauth apps exist" in prompt_content
    assert "shared next-action guidance on `/` and `/connections` should mention restoring an encrypted backup from connections" in prompt_content
    assert "`/connections` should accept a legacy sql dump or zip from the old pi backup path and extract apple recovery hints from it" in prompt_content
    assert "should offer a one-step way to load a recovered apple calendar hint into the setup form" in prompt_content
    assert "loading a recovered hint should prefill the apple account label, apple username, calendar url, and calendar name" in prompt_content
    assert "get /api/readiness should tell operators to open apple setup, load a recovered apple hint, and save a fresh app-specific password" in prompt_content
    assert "`post /calendar/setup/validate` should test the entered apple username, app-specific password, and primary calendar url without persisting those values first" in prompt_content
    assert "`/calendar/setup` should expose a visible `validate apple connection` action alongside save so the reconnect flow is not blind" in prompt_content
    assert "legacy apple recovery extraction should rank explicit `writable_booking_target` calendars ahead of generic enabled calendars when choosing the recommended reconnect hint" in prompt_content
    assert "when no apple account is connected yet and legacy apple recovery hints exist, `get /calendar/setup` should auto-load the recommended recovered apple hint into the setup form" in prompt_content
    assert "shared readiness guidance should tell operators to open apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password" in prompt_content
    assert "both surfaces should switch to truthful save-only labels instead of promising a live apply" in prompt_content
    assert "enable_alexa" in prompt_content
    assert "alexa_allowed_skill_ids" in prompt_content
    assert "post /alexa/simulate" in prompt_content
    assert "remote mcp worker requirement" in prompt_content
    assert "https://mcp-calsync.neonbutterfly.net/mcp" in prompt_content
    assert "workers.dev" in prompt_content
    assert "available as a fallback alongside the custom hostname" in prompt_content
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
    account_linking_manifest = json.loads(
        Path("workers/edge-calsync/alexa/skill-package/accountLinking.json").read_text(
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
    assert "get /alexa/account-linking/authorize" in readme_content
    assert "post /api/alexa/account-linking/validate" in readme_content
    assert "alexa_allowed_skill_ids" in readme_content
    assert "/privacy" in readme_content
    assert "/terms" in readme_content
    assert "cancelappointmentintent" in readme_content
    assert "rescheduleappointmentintent" in readme_content
    assert "findavailabilityintent" in readme_content
    assert "next upcoming appointment" in readme_content
    assert "provider-aware named calendar target across apple, google, and microsoft" in readme_content
    assert "household alexa account linking" in readme_content

    assert "#38" in ops_content
    assert "createappointmentintent" in ops_content
    assert "cancelappointmentintent" in ops_content
    assert "rescheduleappointmentintent" in ops_content
    assert "nextappointmentintent" in ops_content
    assert "findavailabilityintent" in ops_content
    assert "request-signature flow" in ops_content
    assert "skill-package" in ops_content
    assert "alexa simulator page" in ops_content
    assert "edge worker controls" in ops_content
    assert "spoken response" in ops_content
    assert "token-hash presence flags" in ops_content
    assert "provider-aware named calendar target across apple, google, and microsoft" in ops_content
    assert "authorization url: `https://calsync.neonbutterfly.net/alexa/account-linking/authorize`" in ops_content
    assert "grant type: implicit" in ops_content

    assert "#38" in prompt_content
    assert "post /alexa" in prompt_content
    assert "post /alexa/simulate" in prompt_content
    assert "shared-household alexa adapter" in prompt_content
    assert "request-signature flow" in prompt_content
    assert "get /privacy" in prompt_content
    assert "get /alexa/simulator" in prompt_content
    assert "implicit grant" in prompt_content
    assert "cancel a matching appointment" in prompt_content
    assert "reschedule a matching appointment" in prompt_content
    assert "read the next upcoming appointment" in prompt_content
    assert "new calendar-name slot" in prompt_content
    assert "findavailabilityintent" in prompt_content

    assert "createappointmentintent" in interaction_model_content
    assert "listappointmentsintent" in interaction_model_content
    assert "nextappointmentintent" in interaction_model_content
    assert "findavailabilityintent" in interaction_model_content
    assert "cancelappointmentintent" in interaction_model_content
    assert "rescheduleappointmentintent" in interaction_model_content
    assert "calendar_name" in interaction_model_content
    assert "new_calendar_name" in interaction_model_content
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
    assert (
        account_linking_manifest["accountLinkingRequest"]["authorizationUrl"]
        == "https://calsync.neonbutterfly.net/alexa/account-linking/authorize"
    )
    assert account_linking_manifest["accountLinkingRequest"]["type"] == "IMPLICIT"
    assert (
        account_linking_manifest["accountLinkingRequest"]["clientId"]
        == "calsync-alexa-household"
    )
    assert "create or import the custom skill package" in alexa_readme_content
    assert "next upcoming appointment" in alexa_readme_content
    assert "find open time" in alexa_readme_content
    assert "named calendar routing" in alexa_readme_content
    assert "provider-aware named calendar target across apple, google, and microsoft" in alexa_readme_content
    assert "household link code" in alexa_readme_content
