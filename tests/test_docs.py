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
    assert "#83" in readme_content
    assert "#84" in readme_content
    assert "#85" in readme_content
    assert "#86" in readme_content
    assert "#87" in readme_content
    assert "#88" in readme_content
    assert "#89" in readme_content
    assert "#90" in readme_content
    assert "#91" in readme_content
    assert "#92" in readme_content
    assert "#93" in readme_content
    assert "#94" in readme_content
    assert "#95" in readme_content
    assert "#96" in readme_content
    assert "#97" in readme_content
    assert "#98" in readme_content
    assert "#99" in readme_content
    assert "#100" in readme_content
    assert "#101" in readme_content
    assert "#102" in readme_content
    assert "#103" in readme_content
    assert "#104" in readme_content
    assert "#105" in readme_content
    assert "#106" in readme_content
    assert "#115" in readme_content
    assert "#116" in readme_content
    assert "#117" in readme_content
    assert "#118" in readme_content
    assert "#119" in readme_content
    assert "#120" in readme_content
    assert "#121" in readme_content
    assert "#122" in readme_content
    assert "#123" in readme_content
    assert "#124" in readme_content
    assert "#125" in readme_content
    assert "#126" in readme_content
    assert "#127" in readme_content
    assert "#129" in readme_content
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
    assert "a fully blocked disconnected root workspace" in readme_content
    assert "make apple recovery messaging point to the reconnect step" in readme_content
    assert "recovery-aware apple messaging across readiness, connections, and apple setup" in readme_content
    assert "safe apple setup validation before reconnect save" in readme_content
    assert "legacy apple recovery hint ranking that now prefers the real recovered writable booking target over a merely enabled personal-reference calendar" in readme_content
    assert "legacy apple encrypted-secret recovery state now tells operators whether the preserved apple password is reusable with the current key or still needs the original key" in readme_content
    assert "one-time legacy-secret recovery with the original calsync encryption key" in readme_content
    assert "recovery-aware product guidance now also points operators to enter that original key on apple setup" in readme_content
    assert "recovery-aware apple reconnect actions on `/` and `/booking/setup`" in readme_content
    assert "recovery-aware apple reconnect messaging across the blocked root workspace panels" in readme_content
    assert "recovery-aware apple reconnect guidance on alexa setup and connections" in readme_content
    assert "recovery-aware apple reconnect guidance through the full booking-setup operator flow" in readme_content
    assert "recovery-aware apple reconnect guidance in the root workspace capability summary" in readme_content
    assert "recovery-aware simulator readiness guidance on `/alexa/simulator`" in readme_content
    assert "recovery-aware alexa simulator selector guidance on `/alexa/simulator`" in readme_content
    assert "recovery-aware public booking guidance on `/book`" in readme_content
    assert "recovery-aware public booking submit errors" in readme_content
    assert "recovery-aware root appointment submit errors" in readme_content
    assert "recovery-aware alexa scheduling errors" in readme_content
    assert "recovery-aware alexa read intents" in readme_content
    assert "non-alexa recovery guidance now mirrors the legacy apple encrypted-secret state across blocked root, booking, stale edit/cancel, and appointment api responses" in readme_content
    assert "alexa recovery guidance now mirrors the legacy apple encrypted-secret state across alexa setup, connections, and the simulator" in readme_content
    assert "voice-specific next guidance on alexa-focused setup surfaces" in readme_content
    assert "shared alexa account-linking readiness on `/connections`" in readme_content
    assert "an account-linking row in alexa step 4" in readme_content
    assert "align alexa setup account-linking intro copy with the already-saved state" in readme_content
    assert "align alexa next-step guidance with the unsaved desired-state flow after account linking" in readme_content
    assert "expose real alexa skill-id guidance directly on the setup forms" in readme_content
    assert "align the remaining connections alexa summaries with the desired-state-first guidance" in readme_content
    assert "keep `/alexa/setup` truthful when no desired alexa plan has been saved yet" in readme_content
    assert "keep blank alexa saves from counting as a real desired plan" in readme_content
    assert "keep alexa save responses truthful when no real plan exists" in readme_content
    assert "keep alexa helper copy truthful when the skill id is still missing" in readme_content
    assert "keep alexa draft state distinct from untouched defaults" in readme_content
    assert "keep the connections alexa live-route card aligned with the real blocker order" in readme_content
    assert "sync alexa docs and skill-package instructions with the live worker deployment state" in readme_content
    assert "a writable-calendar row in alexa step 4" in readme_content
    assert "a cloudflare-access row in alexa step 4" in readme_content
    assert "a desired-settings row in alexa step 4" in readme_content
    assert "a truthful desired-settings card on `/connections`" in readme_content
    assert "a writable-calendar card on `/connections` for alexa" in readme_content
    assert "a truthful live-route card on `/connections` for alexa" in readme_content
    assert "truthful google and microsoft next-action summaries on `/connections`" in readme_content
    assert "simulator readiness summary for no-calendar voice testing states" in readme_content
    assert "live-vs-desired drift visibility" in readme_content
    assert "workspace capability summary now reflects the actual connected readiness state" in readme_content
    assert "root workspace now also blocks the create flow clearly when no writable calendar is connected" in readme_content
    assert "root workspace now also blocks availability search clearly when no writable calendar is connected" in readme_content
    assert "public booking flow now also blocks the invitee-facing availability refresh controls clearly when no writable calendar is connected" in readme_content
    assert "public booking flow now also aligns its blocked availability, request, and target-card copy with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "public booking flow now also aligns blocked direct submit errors with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "root schedule workspace now also aligns blocked direct appointment-create submit errors with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "stale deep-link appointment edit and cancel routes now also align with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "recovery-mode appointment update and cancel api routes now also align with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "alexa scheduling intents now also align blocked recovery-mode voice errors with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "alexa launch, help, and fallback guidance now also align with apple reconnect when legacy recovery hints already exist" in readme_content
    assert "root workspace default-target card now also shows the loaded recovered apple target instead of `no calendar selected` when legacy recovery hints already exist but reconnect is still blocked" in readme_content
    assert "blocked root and booking-setup target selectors now also name the loaded recovered apple target instead of falling back to `no writable calendars connected yet` while reconnect is still blocked" in readme_content
    assert "root workspace now also blocks the empty schedule board and detail panel clearly when no writable calendar is connected" in readme_content
    assert "disconnected root workspace now also blocks stale hero stats, next-up copy, and selected appointment detail" in readme_content
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
    assert "#83" in ops_content
    assert "#84" in ops_content
    assert "#85" in ops_content
    assert "#86" in ops_content
    assert "#87" in ops_content
    assert "#88" in ops_content
    assert "#89" in ops_content
    assert "#90" in ops_content
    assert "#91" in ops_content
    assert "#92" in ops_content
    assert "#93" in ops_content
    assert "#94" in ops_content
    assert "#95" in ops_content
    assert "#96" in ops_content
    assert "#97" in ops_content
    assert "#98" in ops_content
    assert "#99" in ops_content
    assert "#100" in ops_content
    assert "#101" in ops_content
    assert "#102" in ops_content
    assert "#103" in ops_content
    assert "#104" in ops_content
    assert "#105" in ops_content
    assert "#106" in ops_content
    assert "#110" in ops_content
    assert "#109" in ops_content
    assert "#108" in ops_content
    assert "#113" in ops_content
    assert "#114" in ops_content
    assert "#115" in ops_content
    assert "#116" in ops_content
    assert "#117" in ops_content
    assert "#118" in ops_content
    assert "#119" in ops_content
    assert "#120" in ops_content
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
    assert "blocked root hero/detail truthfulness for stale local appointment rows" in ops_content
    assert "recovery-aware apple reconnect messaging" in ops_content
    assert "encrypted operator-settings backup and restore from `/connections`" in ops_content
    assert "surfaces recovered legacy apple hints on `/calendar/setup`" in ops_content
    assert "load a recovered apple calendar hint directly into the `/calendar/setup` form" in ops_content
    assert "safe apple setup validation before reconnect save" in ops_content
    assert "legacy apple encrypted-secret recovery diagnostics now show on `/calendar/setup`, `/connections`, and shared readiness guidance whether the preserved apple password is reusable with the current key or still needs the original key" in ops_content
    assert "`/calendar/setup` now also accepts a one-time original calsync encryption key so operators can recover a preserved apple app-specific password from a legacy backup and re-save it under the current deployment key" in ops_content
    assert "recovery-aware product messaging now points operators to enter that original key on apple setup instead of implying the deployment key itself must be restored globally first" in ops_content
    assert "blocked root workspace copy, booking blockers, stale appointment edit/cancel blockers, and appointment api recovery guidance now mirror that same legacy apple encrypted-secret recovery state instead of falling back to fresh-password-only guidance" in ops_content
    assert "alexa setup, the connections alexa panel, and the alexa simulator now mirror that same legacy apple encrypted-secret recovery state instead of falling back to fresh-password-only guidance" in ops_content
    assert "recovery-aware apple hint ranking that prefers true writable booking targets" in ops_content
    assert "keeps blocked operator surfaces on `/` and `/booking/setup` aligned with that apple recovery flow" in ops_content
    assert "keeps the blocked root schedule, detail, create, and availability panels aligned with that same apple recovery flow" in ops_content
    assert "keeps alexa setup and the connections voice panel aligned with that same apple recovery flow" in ops_content
    assert "keeps the booking setup target-behavior card plus blocked save and booking-type creation responses aligned with that same apple recovery flow" in ops_content
    assert "keeps the root `what works today` capability summary aligned with that same apple recovery flow" in ops_content
    assert "keeps the alexa simulator readiness panel aligned with that same apple recovery flow" in ops_content
    assert "keeps the alexa simulator empty selector helper text aligned with that same apple recovery flow" in ops_content
    assert "keeps the public booking page aligned with that same apple recovery flow" in ops_content
    assert "keeps blocked public booking submit responses aligned with that same apple recovery flow" in ops_content
    assert "keeps blocked root appointment-create submit responses aligned with that same apple recovery flow" in ops_content
    assert "keeps stale deep-link appointment edit and cancel routes aligned with that same apple recovery flow" in ops_content
    assert "keeps recovery-mode appointment update and cancel api routes aligned with that same apple recovery flow" in ops_content
    assert "keeps blocked alexa scheduling responses aligned with that same apple recovery flow" in ops_content
    assert "keeps blocked alexa read intents aligned with that same apple recovery flow" in ops_content
    assert "keeps alexa launch, help, and fallback guidance aligned with that same apple recovery flow" in ops_content
    assert "keeps the root workspace default-target card aligned with that same apple recovery flow" in ops_content
    assert "keeps blocked root and booking-setup target selectors aligned with that same apple recovery flow" in ops_content
    assert "voice-specific next guidance for alexa setup and connections voice panels" in ops_content
    assert "exposes alexa account-linking readiness on `/connections`" in ops_content
    assert "step 2.5 intro copy from first-time save guidance to configured-state guidance" in ops_content
    assert "save the alexa plan and real skill id before cloudflare worker apply-only guidance takes over" in ops_content
    assert "saving blank alexa defaults or an enabled-without-skill-id state should not count as a real desired alexa plan" in ops_content
    assert "alexa save responses should stop flashing `desired alexa settings saved securely.` when no real plan exists yet" in ops_content
    assert "once the operator has only a skill-id-missing alexa draft, the helper copy under the alexa forms should stop saying it will save a desired alexa plan" in ops_content
    assert "once the operator has only an alexa draft with `enable_alexa=true` and no real skill id, the app should stop calling that state `defaults`" in ops_content
    assert "once the operator has only an alexa draft with `enable_alexa=true` and no real skill id, `/alexa/simulator` should stop reading like route enablement is the only missing step" in ops_content
    assert "copy the generated real alexa skill id from the alexa developer console after importing the package" in ops_content
    assert "the alexa worker code is now deployed live on cloudflare with the recovery-guidance normalization" in ops_content
    assert "the alexa docs and skill-package instructions now point operators to the current calsync alexa setup flow first" in ops_content
    assert "remaining alexa summaries on `/connections`, including the edge-route status card and the `finish the live stack` alexa line" in ops_content
    assert "keeps the shared alexa desired-settings card on `/connections` truthful" in ops_content
    assert "exposes writable-calendar readiness on `/connections` for the alexa panel" in ops_content
    assert "keeps the shared alexa live-route card on `/connections` truthful" in ops_content
    assert "keeps the shared google and microsoft next-action summary on `/connections` truthful" in ops_content
    assert "exposes account-linking readiness directly in alexa step 4" in ops_content
    assert "exposes writable-calendar readiness directly in alexa step 4" in ops_content
    assert "exposes cloudflare worker access readiness directly in alexa step 4" in ops_content
    assert "exposes desired alexa-state readiness directly in alexa step 4" in ops_content
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
    assert "keeps the disconnected root hero and selected-detail surfaces blocked too" in ops_content
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
    assert "#113" in prompt_content
    assert "#114" in prompt_content
    assert "#115" in prompt_content
    assert "#116" in prompt_content
    assert "#117" in prompt_content
    assert "#118" in prompt_content
    assert "#119" in prompt_content
    assert "#120" in prompt_content
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
    assert "alexa account-linking readiness requirement" in prompt_content
    assert "alexa setup account-linking intro truthfulness requirement" in prompt_content
    assert "alexa desired-state next-step requirement" in prompt_content
    assert "alexa skill-id form guidance requirement" in prompt_content
    assert "connections alexa summary truthfulness requirement" in prompt_content
    assert "alexa step 4 prerequisite visibility requirement" in prompt_content
    assert "alexa step 4 writable calendar requirement" in prompt_content
    assert "alexa step 4 cloudflare access requirement" in prompt_content
    assert "alexa step 4 desired state requirement" in prompt_content
    assert "connections alexa desired state requirement" in prompt_content
    assert "connections alexa writable calendar requirement" in prompt_content
    assert "connections provider next actions requirement" in prompt_content
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
    assert "legacy apple encrypted secret recovery requirement" in prompt_content
    assert "root default target recovery requirement" in prompt_content
    assert "blocked target selector recovery requirement" in prompt_content
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
    assert "blocked operator apple reconnect requirement" in prompt_content
    assert "blocked root recovery guidance requirement" in prompt_content
    assert "alexa recovery guidance requirement" in prompt_content
    assert "booking setup recovery guidance requirement" in prompt_content
    assert "workspace capability recovery guidance requirement" in prompt_content
    assert "alexa simulator recovery guidance requirement" in prompt_content
    assert "alexa simulator draft-state requirement" in prompt_content
    assert "alexa simulator selector guidance requirement" in prompt_content
    assert "public booking recovery guidance requirement" in prompt_content
    assert "public booking submit error requirement" in prompt_content
    assert "root appointment submit error requirement" in prompt_content
    assert "alexa recovery scheduling error requirement" in prompt_content
    assert "alexa recovery read-intent requirement" in prompt_content
    assert "alexa recovery guidance-intent requirement" in prompt_content
    assert "appointment edit and cancel recovery requirement" in prompt_content
    assert "appointment update and cancel api recovery requirement" in prompt_content
    assert "alexa worker recovery normalization requirement" in prompt_content
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
    assert "when the current calsync `encryption_key` can decrypt that preserved apple secret, `/calendar/setup` should allow validate/save without forcing the operator to retype the password" in prompt_content
    assert "when the current calsync `encryption_key` cannot decrypt that preserved apple secret, `/calendar/setup`, `/connections`, and shared readiness guidance should say the original key is needed or a fresh manual app-specific password must be entered" in prompt_content
    assert "when the preserved apple password still needs the original key, `get /calendar/setup` should expose a one-time `original calsync encryption key` field" in prompt_content
    assert "`post /calendar/setup/validate` should accept that original key, decrypt the preserved apple secret if the key is correct, and validate the loaded recovered calendar without persisting the key itself" in prompt_content
    assert "`post /calendar/setup` should accept that original key, decrypt the preserved apple secret if the key is correct, and save the apple account by re-encrypting the recovered password under the current deployment key" in prompt_content
    assert "original-key-needed recovery guidance should tell operators to open apple setup and enter the original calsync encryption key there" in prompt_content
    assert "when the preserved apple password is reusable with the current key, `get /alexa/setup`, the alexa panel on `get /connections`, and `get /alexa/simulator` should point operators to validate or save the already-loaded recovered calendar" in prompt_content
    assert "when `desired_alexa.enable_alexa=true`, `desired_alexa.saved=false`, and no real skill id exists yet, `get /alexa/simulator` should explicitly describe that the live alexa plan is still only a draft" in prompt_content
    assert "when the preserved apple password still needs the original key, those same alexa surfaces should tell operators to enter the original calsync encryption key on apple setup or save a fresh manual app-specific password before the remaining alexa steps" in prompt_content
    assert "the alexa simulator readiness copy and empty selector helper text should follow the same reusable-versus-original-key distinction so voice rehearsal guidance does not drift behind apple setup and connections" in prompt_content
    assert "blocked root workspace messaging, blocked booking flows, and stale appointment edit/cancel blockers should all distinguish between reusable preserved apple secrets, original-key-needed recovery, and the older fresh-password-only recovery case" in prompt_content
    assert "recovery-mode public booking and booking-setup messages should point to the original calsync encryption key when that is the real current blocker" in prompt_content
    assert "recovery-mode appointment api responses should use the same reusable-versus-original-key distinction instead of only saying to confirm the recovered calendar and save a fresh password" in prompt_content
    assert "shared readiness guidance should tell operators to open apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password" in prompt_content
    assert "the root workspace action stack on `/` should include a direct apple setup action alongside the other operator links" in prompt_content
    assert "`/booking/setup` should also expose direct operator actions into apple setup and connections in that recovery-shaped blocked state" in prompt_content
    assert "the blocked detail panel should expose the same direct operator actions into connections and apple setup that the other blocked root panels already provide" in prompt_content
    assert "the `alexa:` line in the connections `finish the live stack` summary should also reflect that apple reconnect comes before the remaining household link-code or cloudflare steps" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, `get /booking/setup` should use apple reconnect guidance in the target-behavior card as well as the top-level blocked state" in prompt_content
    assert "disconnected `post /booking/setup` requests should fail with apple reconnect guidance instead of the generic writable-calendar save error" in prompt_content
    assert "disconnected `post /booking/setup/types` requests should fail with apple reconnect guidance instead of the generic writable-calendar booking-type error" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, the root workspace capability summary should tell operators to open apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password to unlock create, edit, and cancel appointments" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, `get /alexa/simulator` should say apple reconnect still blocks meaningful scheduling tests" in prompt_content
    assert "the simulator readiness panel should expose direct operator actions into apple setup and connections in that recovery-shaped state" in prompt_content
    assert "the empty `target calendar` helper copy on `get /alexa/simulator` should tell operators to open apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before named calendar targeting appears" in prompt_content
    assert "the empty `new calendar` helper copy on `get /alexa/simulator` should tell operators to open apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before reschedule moves can target a named calendar there" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, `get /book` should point blocked availability search at apple reconnect rather than generic writable-calendar setup" in prompt_content
    assert "the public booking target card should acknowledge that recovered apple hints are ready and point operators to apple setup plus the loaded recovered calendar" in prompt_content
    assert "the blocked request-time panel on `get /book` should say apple reconnect still blocks invitees from requesting time" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, blocked `post /book` responses should say apple reconnect still blocks public booking requests" in prompt_content
    assert "blocked `post /book/{slug}` responses should use that same apple reconnect submit guidance" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, blocked `post /appointments` responses should say apple reconnect still blocks write actions" in prompt_content
    assert "the blocked response should not fall back to `primary apple/icloud calendar is not configured.`" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, `get /appointments/{appointment_id}/edit` should stop at an apple reconnect blocker instead of rendering a real edit form" in prompt_content
    assert "direct `post /appointments/{appointment_id}/edit` should point operators to apple reconnect instead of falling through to `apple calendar target url was not found.`" in prompt_content
    assert "direct `post /appointments/{appointment_id}/cancel` should point operators to apple reconnect instead of falling through to `apple calendar target url was not found.`" in prompt_content
    assert "the blocked deep-link state should expose direct operator actions into apple setup and connections" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, `patch /api/appointments/{appointment_id}` should point callers to apple reconnect instead of falling through to `apple calendar target url was not found.`" in prompt_content
    assert "in that same state, `post /api/appointments/{appointment_id}/cancel` should point callers to apple reconnect instead of falling through to `apple calendar target url was not found.`" in prompt_content
    assert "when the worker receives `apple calendar target url was not found.` or the other recovery-mode apple backend errors, it should speak that same current apple reconnect guidance instead of falling back to stale worker-owned copy" in prompt_content
    assert "when the worker is in apple recovery mode, launch, help, and fallback guidance should follow the current readiness-driven apple reconnect message instead of older hardcoded fresh-password-only wording" in prompt_content
    assert "the worker tests should cover the stale apple target error explicitly so the edge layer cannot silently drift behind origin normalization again" in prompt_content
    assert "live cloudflare deployments should keep the `loadapplerecoveryguidance`, `normalizeschedulingerrorspeech`, and `apple reconnect still needs one more step.` markers present" in prompt_content
    assert "once the live alexa worker code gap is cleared, operator docs and the imported skill-package instructions should stop reading like direct worker env edits and manual redeploys are still the primary setup flow" in prompt_content
    assert "the alexa package `testinginstructions` should point to calsync-managed desired settings and allowlist save steps before mentioning any lower-level worker fallback" in prompt_content
    assert "the live alexa worker should default to deny when no real allowed skill ids have been configured yet" in prompt_content
    assert "`post /alexa` should reject requests when `alexa_allowed_skill_ids` is empty" in prompt_content
    assert "empty-allowlist `403` path" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, blocked alexa scheduling intents should point to apple reconnect and the need for a fresh app-specific password" in prompt_content
    assert "simulator and live voice scheduling responses should not fall back to `primary apple/icloud calendar is not configured.`" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, `get /api/appointments` should not surface stale local appointment rows as live calendar truth" in prompt_content
    assert "blocked alexa list, next, availability, cancel, and reschedule flows should all point to apple reconnect and the need for a fresh app-specific password" in prompt_content
    assert "simulator and live voice read intents should not fall back to stale local appointments, `i could not find...`, or `i could not find an opening...` when apple reconnect is still the real blocker" in prompt_content
    assert "when legacy apple recovery hints exist and no writable calendar is connected, launchrequest, `amazon.helpintent`, and `amazon.fallbackintent` should all point to apple reconnect and the need for a fresh app-specific password" in prompt_content
    assert "the public simulator guidance intents should not keep coaching blocked create or read flows when apple reconnect is still the real blocker" in prompt_content
    assert "the worker should rely on a safe recovery-mode readiness signal instead of guessing from raw provider error text" in prompt_content
    assert "when legacy apple recovery hints exist and the recommended recovered calendar is already loaded into apple setup, the root workspace should stop reading like an empty target state" in prompt_content
    assert "if no writable calendar is connected and legacy apple recovery hints exist, the root target card should show the recommended recovered apple calendar name instead of `no calendar selected`" in prompt_content
    assert "if no writable calendar is connected and legacy apple recovery hints exist, the disabled target selectors on the root workspace create form and `/booking/setup` should name the recommended recovered apple target instead of the generic empty text" in prompt_content
    assert "when `any_calendar_ready` is false, the root workspace should keep the hero summary in a clearly blocked state instead of showing stale appointment counts or a stale next-up appointment" in prompt_content
    assert "the alexa voice panel on `/connections` should show whether account linking is ready or still needs setup" in prompt_content
    assert "`get /alexa/setup` step 4 should include an explicit account-linking readiness row" in prompt_content
    assert "the older `save a household link code, then use the authorization url below...` wording should only render before account linking has been configured" in prompt_content
    assert "when the desired alexa plan is still unsaved after account linking is ready, `get /api/readiness` should tell operators to save the alexa plan and real skill id before cloudflare apply-only guidance takes over" in prompt_content
    assert "saving blank alexa defaults, or saving alexa enabled without any real skill id, should not count as a real desired alexa live plan" in prompt_content
    assert "simply checking `enable_alexa` without a real skill id should still leave the setup flow blocked on the skill-id step" in prompt_content
    assert "blank `post /alexa/setup` and blank `post /connections/alexa` should not flash `desired alexa settings saved securely.`" in prompt_content
    assert "with `enable_alexa=true` but no real skill id should say that the real alexa skill id is still required before a live plan can be saved" in prompt_content
    assert "when the current alexa draft is enabled but still has no real skill id, the helper copy below the form should say that the real alexa skill id is still required" in prompt_content
    assert "should not keep saying `this will save the desired alexa plan in calsync until live edge updates are available`" in prompt_content
    assert "`get /api/readiness` should expose the skill-id-missing state as a draft, not `source=defaults`" in prompt_content
    assert "`get /alexa/setup` and `get /connections` should show an explicit draft-only desired-settings state when `enable_alexa=true` but no real skill id exists yet" in prompt_content
    assert "`get /alexa/setup` should tell operators to import the skill package in the alexa developer console, copy the generated real alexa skill id, and paste it into `allowed skill ids`" in prompt_content
    assert "the `finish the live stack` alexa summary on `get /connections` should mirror that same current guidance instead of older `finish edge enablement and skill-id allowlisting` copy" in prompt_content
    assert "the `live route` detail card on `get /connections` should stay aligned with the same blocker ordering already used by readiness and the other alexa cards on that page" in prompt_content
    assert "`get /alexa/setup` step 4 should include an explicit writable-calendar readiness row" in prompt_content
    assert "`get /alexa/setup` step 4 should include an explicit cloudflare-access readiness row" in prompt_content
    assert "`get /alexa/setup` step 4 should include an explicit desired-state readiness row" in prompt_content
    assert "`get /connections` should show a truthful desired-settings status inside the alexa panel" in prompt_content
    assert "`get /connections` should include a writable-calendar readiness card inside the alexa panel" in prompt_content
    assert "`get /connections` should keep the google and microsoft `next actions` summary aligned with the provider cards on the same page" in prompt_content
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
    assert "paste that skill id into `allowed skill ids` on `get /alexa/setup`" in alexa_readme_content
    assert "save the desired alexa plan in calsync" in alexa_readme_content
    assert "low-level fallback" in alexa_readme_content
    assert (
        "copy the generated real alexa skill id into allowed skill ids on the calsync alexa setup page"
        in skill_manifest["manifest"]["publishingInformation"][
            "testingInstructions"
        ].lower()
    )
    assert "save the desired alexa plan there" in skill_manifest["manifest"][
        "publishingInformation"
    ]["testingInstructions"].lower()
