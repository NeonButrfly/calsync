# Backend Prompt Capture

- GitHub issue: `#32`
- Scope: first Apple-first ChatGPT app slice on top of a small CalSync-owned service for conversational calendar write-back

## Interpreted Requirements

- the first conversational scheduling slice should target the shared iCloud family calendar
- ChatGPT should create, edit, and cancel appointments through CalSync instead of talking to Apple directly
- the service should stay small and focused, but it must preserve normalized local appointment records and Apple event mappings
- the shared workspace should act as the operational brain while iCloud remains the family-visible destination
- the initial tool surface should stay narrow and mutation-focused so the experience is reliable before broader search, planning, or reminder automation ships
- the design should leave room for later Google intake, iCloud Reminders sync, structured medical metadata, and Alexa-style voice input

## Behavioral Boundaries

- this slice is Apple/iCloud-first, not a broad multi-provider conversational assistant
- Google inbound event ingestion is future work
- iCloud Reminders sync is future work
- the first conversational app should expose create, edit, cancel, and date-range list flows

## Phase Notes

- issue `#32` builds on the preserved write-capable legacy work from earlier CalSync slices, now archived on `legacy/pre-chatgpt-brain-reset`
- the owned service is the durable contract; ChatGPT should never mutate CalDAV directly
- iCloud remains the family-facing calendar of record for day-to-day visibility
- CalSync should keep audit history and local event mappings so the later family workspace can grow without redesigning this slice

## Implemented In This Slice

- FastAPI runtime with `GET /`, `GET /healthz`, appointment mutation routes, and date-range lookup
- `GET /api/appointments` for date-range appointment lookup
- `GET /api/availability` for open-slot lookup
- `POST /api/appointments` for appointment creation
- `PATCH /api/appointments/{appointment_id}` for appointment edits
- `POST /api/appointments/{appointment_id}/cancel` for appointment cancellation
- local Postgres persistence for:
  - Apple calendar connection metadata
  - normalized appointments
  - appointment external links
  - audit entries
- Alembic bootstrap migration for the Apple-first schema
- Apple CalDAV adapter that writes `.ics` payloads directly to the configured iCloud calendar URL
- dedicated Cloudflare Worker project in `workers/edge-calsync`
- live Worker route on `edge-calsync.neonbutterfly.net/*`
- Cloudflare KV-backed channel hash validation for `chatgpt`, `shortcuts`, `alexa`, and `webhooks`

## Operational Expectations

- the service requires a configured writable Apple calendar target before any mutation route can succeed
- the Apple account should use an app-specific password, not an interactive account password
- the service writes to one selected saved iCloud calendar target at a time, with one default target when the caller does not choose explicitly
- appointment changes should update the same Apple provider event rather than recreating a new one
- cancellations should delete the remote Apple event and mark the local record as `cancelled`

## Known Boundaries In Current Code

- no appointment search yet
- list is limited to explicit date windows, not free-form search
- no Google ingestion yet
- no iCloud Reminders sync yet
- no structured medical metadata API fields yet
- no ChatGPT Apps SDK wrapper yet; the Worker is the live edge, but the dedicated ChatGPT app layer is still future work

## In-Product Google OAuth Setup And Writable Targets Requirement

- GitHub issue: `#3`
- interpreted requirement: the product should support browser-based Google account connection and writable Google scheduling without forcing the operator to hand-edit host secrets or use a separate admin tool

Expected behavior:

- `GET /google/setup` should render an operator-facing Google setup page
- `POST /google/setup` should save the shared Google OAuth client ID and client secret
- those Google OAuth settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- `GET /auth/google/start` should begin a browser-based Google OAuth flow on the live CalSync domain
- `GET /auth/google/callback` should exchange the code, save the Google refresh token, and discover the available calendars
- the product should support more than one connected Google account under that shared OAuth app
- the product should expose a live refresh path so operators can resync one connected Google account and its discovered calendar catalog without reconnecting unnecessarily
- the product should expose a safe disconnect path that clears one linked Google account and its calendar list while preserving the shared deployment-wide OAuth client
- discovered Google calendars should appear as writable targets in the same create and edit flows used by the workspace
- the shared appointment service should be able to create, update, cancel, and date-range sync Google events through those targets

Behavioral boundary:

- this slice adds a shared Google write path inside the product, not a full Google-native standalone experience
- Apple remains the first family-facing target, but the scheduling brain should now treat connected Google calendars as first-class writable options

## In-Product Microsoft OAuth Setup And Writable Targets Requirement

- GitHub issue: `#49`
- interpreted requirement: the product should support browser-based Microsoft account connection and writable Outlook scheduling without forcing the operator to hand-edit host secrets or use a separate admin tool

Expected behavior:

- `GET /microsoft/setup` should render an operator-facing Microsoft setup page
- `POST /microsoft/setup` should save the shared Microsoft OAuth client ID and client secret
- those Microsoft OAuth settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- `GET /auth/microsoft/start` should begin a browser-based Microsoft OAuth flow on the live CalSync domain
- `GET /auth/microsoft/callback` should exchange the code, save the Microsoft refresh token, and discover the available calendars
- the product should support more than one connected Microsoft account under that shared OAuth app
- the product should expose a live refresh path so operators can resync one connected Microsoft account and its discovered calendar catalog without reconnecting unnecessarily
- the product should expose a safe disconnect path that clears one linked Microsoft account and its calendar list while preserving the shared deployment-wide OAuth client
- discovered Microsoft calendars should appear as writable targets in the same create and edit flows used by the workspace
- the shared appointment service should be able to create, update, cancel, and date-range sync Microsoft events through those targets

Behavioral boundary:

- this slice adds a shared Microsoft write path inside the product, not a full Outlook-native standalone experience
- Apple remains the first family-facing target, but the scheduling brain should now treat connected Microsoft calendars as first-class writable options beside Apple and Google

## First Scheduling UX Requirement

- GitHub issue: `#39`
- interpreted requirement: make the rebooted Apple-first backend usable through a clean family scheduling console instead of only API calls and future design notes

Expected UX behavior:

- `GET /` should render a polished scheduling console
- the root experience should let users create appointments directly into the Apple calendar through CalSync
- existing appointments should be visible, editable, and cancellable from the same console
- the UX should feel like a professional product surface, not a raw API debug page
- the web console should reuse the same appointment service and audit-backed write path as the API and Worker layers

## Scheduling Workspace Polish Requirement

- GitHub issue: `#40`
- interpreted requirement: turn the first scheduling console into a more professional scheduling workspace with clearer browsing, stronger appointment detail, and better product-level information architecture

Expected UX behavior:

- `GET /` should support day, week, and month schedule windows
- the workspace should show a selected appointment detail surface instead of only a flat list
- detail should explain where the appointment lives, when it changed, and what CalSync has done with it
- low-level provider metadata may still exist, but it should stay tucked behind a disclosure instead of dominating the primary experience
- the console should still use the same Apple write-back path for create, edit, and cancel

## Unified Connections UX Requirement

- GitHub issue: `#17`
- interpreted requirement: provider onboarding should feel like one professional product flow instead of a set of scattered setup pages

Expected behavior:

- `GET /connections` should summarize the live Apple and Google connection state in one place
- `GET /connections` should summarize the live Apple, Google, and Microsoft connection state in one place
- operators should be able to see which provider paths are already writable and which still need setup
- the shared workspace shell should link to that Connections surface directly
- Apple setup, Google setup, and Microsoft setup can remain separate deeper pages, but the day-to-day operator experience should have one clear entry point for connection state

## Connections Verification Center Requirement

- GitHub issue: `#52`
- interpreted requirement: the shared Connections surface should behave like a setup checklist and live verification center instead of only a read-only provider summary

Expected behavior:

- `GET /connections` should show a checklist-style view of Apple, Google, Microsoft, and Alexa readiness
- `POST /connections/test` should run the same in-product writable calendar smoke flow against a selected target from the Connections page
- the product should persist the last write proof for each writable target so operators can see whether a path was last verified or failed
- the Connections page should show the last write proof message and timestamp per target instead of relying on one-time flash messages only
- provider-specific setup pages may still expose `Run write test`, but `/connections` should become the calm operator surface where setup and verification come together

## Connections Provider Control Center Requirement

- GitHub issue: `#53`
- interpreted requirement: `/connections` should become the primary control surface for routine Google and Microsoft provider management instead of only a status-and-proof page

Expected behavior:

- `/connections` should expose direct connect actions for Google and Microsoft account onboarding
- `/connections` should expose direct refresh actions for one connected Google or Microsoft account at a time
- `/connections` should expose direct disconnect actions for one connected Google or Microsoft account at a time
- those actions should return to the shared Connections page with updated readiness and verification state instead of dropping the operator into a separate setup page
- the provider-specific setup pages can remain for deeper editing of shared OAuth app settings, but routine provider management should feel shared and product-like from `/connections`

## Planner-Style Schedule Board Requirement

- GitHub issue: `#54`
- interpreted requirement: the root schedule workspace should feel like a real planner product, so day, week, and month browsing must materially change the schedule presentation instead of only changing the query range under one agenda layout

Expected behavior:

- `/` should render a day board when `view=day`
- `/` should render a week board when `view=week`
- `/` should render a month board when `view=month`
- the selected-appointment detail pane and write actions should remain intact while the schedule board becomes more calendar-like
- the schedule board should remain useful even when some days are empty, so the planner surface still communicates open space instead of collapsing into a blank page

## Workspace Truthfulness Requirement

- GitHub issue: `#62`
- interpreted requirement: the root scheduling workspace should not show broken helper copy or capability language that overstates the currently connected live state

Expected behavior:

- the planner-board helper text should render the intended human-readable description instead of a Python method string
- the root workspace capability summary should describe the actual connected readiness state for Apple, Google, Microsoft, and Alexa
- when Google or Microsoft are not connected yet, the workspace should say those write paths are waiting for setup instead of reading like live verified capability
- when Alexa is not live yet, the workspace should direct the operator toward setup or a saved turn-on plan instead of implying the live voice route is already active

## Root No-Calendar Create-State Requirement

- GitHub issue: `#67`
- interpreted requirement: when the live runtime has no writable Apple, Google, or Microsoft calendar connected, the root workspace should stay operationally truthful instead of looking like create actions are ready to use

Expected behavior:

- the root workspace capability list should stop claiming Apple read or write capability when no writable calendar path is connected
- the root workspace should clearly explain that a writable calendar must be connected before create, edit, and cancel actions are meaningful
- the create panel should show direct setup guidance instead of only an apparently normal scheduling form
- the target-calendar control should render as unavailable when there are no writable calendars to choose from
- the create submission path should look blocked in the UI until the operator connects at least one writable calendar target

## Root No-Calendar Availability Requirement

- GitHub issue: `#68`
- interpreted requirement: when the live runtime has no writable Apple, Google, or Microsoft calendar connected, the root workspace should not behave like availability search is live or imply that there are simply no openings

Expected behavior:

- the root availability panel should clearly explain that writable calendar setup still blocks meaningful open-time search
- the availability form should look blocked in the UI until the operator connects at least one writable calendar target
- disconnected availability requests should not fall back to `No open windows found`
- the root workspace should point the operator toward setup instead of making the no-calendar state look like a normal empty-schedule result

## Public Booking No-Calendar Availability Requirement

- GitHub issue: `#69`
- interpreted requirement: when the live runtime has no writable Apple, Google, or Microsoft calendar connected, the public booking page should not make invitees or operators think open-time refresh is already live

Expected behavior:

- the public booking page should clearly explain that writable calendar setup still blocks meaningful booking availability search
- the invitee-facing availability refresh controls should look blocked in the UI until at least one writable calendar target is connected
- the page should keep the existing `not ready yet` message, but the blocked availability state should reinforce it instead of contradicting it

## Root No-Calendar Schedule-Sync Requirement

- GitHub issue: `#70`
- interpreted requirement: when the live runtime has no writable Apple, Google, or Microsoft calendar connected, the root schedule board and detail panel should not behave like a normal empty calendar

Expected behavior:

- the root day and week boards should not show `Nothing scheduled yet` for a disconnected runtime
- the root month board should not show `Open` as if it were a normal empty calendar
- the selected-appointment empty state should not say `Select an appointment` when the real blocker is missing calendar setup
- the root workspace should clearly explain that connected calendar setup still blocks meaningful live schedule sync

## Apple Setup No-Account Truthfulness Requirement

- GitHub issue: `#71`
- interpreted requirement: when no Apple account is saved and no deployment-env Apple credentials exist, `/calendar/setup` should behave like a truthful first-time setup flow rather than implying a partially connected Apple state

Expected behavior:

- the Apple setup page should not show `Family` as if it were a real connected account when the runtime source is actually missing
- the connected-account panel should switch to an explicit empty-state instead of rendering placeholder connected-account detail cards
- the writable-target panel should explain that the first Apple account must be saved before additional Apple targets can be managed
- the add-calendar form should stay hidden or blocked until the first Apple account exists

## Booking Setup No-Calendar Truthfulness Requirement

- GitHub issue: `#72`
- interpreted requirement: when the live runtime has no writable Apple, Google, or Microsoft calendar connected, `/booking/setup` should not behave like public-booking configuration is ready or allow disconnected booking-type creation

Expected behavior:

- `GET /booking/setup` should clearly explain that a writable calendar is still required before public booking settings are meaningful
- the booking-settings form should render as blocked in the UI when there are no writable calendar targets
- the setup page should show that no writable calendars are connected yet instead of an empty active target picker
- the booking-type creation flow should look blocked in the UI until at least one writable calendar target is connected
- disconnected `POST /booking/setup` requests should fail clearly instead of saving disconnected public-booking defaults
- disconnected `POST /booking/setup/types` requests should fail clearly instead of creating shareable booking links that cannot schedule anywhere

## Provider Connect Action Truthfulness Requirement

- GitHub issue: `#73`
- interpreted requirement: when the shared Google or Microsoft OAuth app has not been saved yet, the product should not advertise browser account-connect actions that lead straight into known `400` failures

Expected behavior:

- `GET /google/setup` should keep `Connect Google account` blocked until both the shared Google client ID and client secret are saved
- `GET /microsoft/setup` should keep `Connect Microsoft account` blocked until both the shared Microsoft client ID and client secret are saved
- `GET /connections` should reflect the same blocked browser-connect state for Google and Microsoft until their shared OAuth apps exist
- those blocked states should explain that the shared OAuth app must be saved first
- once the shared OAuth app is saved, the browser account-connect actions should become available again without changing the deeper OAuth start routes

## Public Booking Page Requirement

- GitHub issue: `#55`
- interpreted requirement: CalSync should expose a first invitee-facing booking page so the shared write-capable scheduling brain is useful outside the internal operator workspace

Expected behavior:

- `GET /book` should render a public booking page
- the booking page should show open time from the same shared availability service used by the internal workspace
- an invitee should be able to choose one available time and submit a booking request
- the booking request should create a real appointment on the default writable connected calendar target
- the booking page should confirm the saved appointment details after success instead of bouncing the user into the internal operator workspace

## In-Product Booking Setup Requirement

- GitHub issue: `#56`
- interpreted requirement: operators should be able to control the invitee-facing booking experience from inside CalSync instead of leaving the public booking page hard-coded

Expected behavior:

- `GET /booking/setup` should render an operator-facing booking setup page
- the setup page should let operators save the public booking title, description, default duration, search window, success message, and writable target
- those booking settings should be stored securely in the product vault
- `GET /book` should render from those saved booking settings
- the public booking flow should use the configured writable target when it is still available

## Public Booking Availability Rules Requirement

- GitHub issue: `#57`
- interpreted requirement: the public booking page should behave like a real scheduling surface, so operators should be able to define which weekdays and hours are actually bookable

Expected behavior:

- `/booking/setup` should let operators choose the public booking weekdays
- `/booking/setup` should let operators choose the public booking day start and end times
- those public booking availability rules should be stored securely in the product vault
- `/book` should only show open slots that fall inside the saved public booking weekdays and daily time window
- the internal root workspace availability finder can keep its broader shared defaults; this slice only tightens the invitee-facing booking surface

## Multiple Public Booking Types Requirement

- GitHub issue: `#58`
- interpreted requirement: operators should be able to publish more than one public booking flow, each with its own shareable link and invitee-facing defaults, so CalSync feels like a real scheduling product instead of one global booking form

Expected behavior:

- `/booking/setup` should show the currently configured booking types
- operators should be able to create a named booking type with a stable slug
- each booking type should have a shareable public URL like `/book/school-intake`
- each booking type should carry its own public title, description, duration, search window, success message, writable target, and booking weekday/hour rules
- `/book` can continue to render the default booking type, but `/book/{slug}` should render the selected booking type directly

Expected API/edge support:

- `GET /api/appointments/{appointment_id}` should return the richer appointment detail payload
- `GET /v1/appointments/{appointment_id}` should expose the same detail through the Worker for future channel use

## Public Booking Catalog Requirement

- GitHub issue: `#59`
- interpreted requirement: once CalSync supports multiple public booking types, the root `/book` experience should feel like a professional scheduling catalog instead of silently dumping invitees into one default form

Expected behavior:

- when more than one public booking type exists, `GET /book` should render a chooser instead of a single booking form
- the chooser should explain that the invitee must pick the appointment flow that fits their need before choosing time
- each booking-type card should show the public title, description, duration, weekday summary, and time-window summary
- each booking-type card should link directly into its focused booking URL such as `/book/school-intake`
- when only one public booking type exists, `GET /book` may still render that focused booking form directly

## Public Booking Type Management Requirement

- GitHub issue: `#60`
- interpreted requirement: once CalSync supports multiple public booking types, operators should be able to manage those links directly from the product instead of needing backend-only cleanup or default switching

Expected behavior:

- `/booking/setup` should expose a direct action to make an existing booking type the default public `/book` flow
- `/booking/setup` should expose a direct action to delete an existing booking type
- when the current default booking type is deleted and another type remains, the product should promote a remaining type to default automatically
- deleting a booking type should remove its shareable `/book/{slug}` link cleanly
- the management actions should return the operator to `/booking/setup` with clear success or error feedback

## Public Booking Invitee Contact Requirement

- GitHub issue: `#63`
- interpreted requirement: the public booking flow should capture who is requesting the appointment and how to reach them, so operators are not left with a booked slot but no follow-up context

Expected behavior:

- `/book` and `/book/{slug}` should require the requester name
- `/book` and `/book/{slug}` should require requester contact details such as an email address or phone number
- the booking confirmation should show the captured requester name and contact details back to the invitee
- the resulting appointment context should preserve the requester name and contact details for operators, even if the appointment schema stays lightweight
- this slice may reuse the existing appointment notes field for that preserved contact context instead of requiring a brand new database model

## Operator Settings Backup And Restore Requirement

- GitHub issue: `#64`
- interpreted requirement: the product-managed Apple, Google, Microsoft, Alexa, and booking setup should be recoverable after database loss or environment drift instead of forcing the operator to rebuild everything manually

Expected behavior:

- `GET /connections/settings-backup` should download an encrypted export of the current operator settings
- `POST /connections/settings-restore` should accept that encrypted backup and restore the saved operator settings into the product vault
- the product should provide an encrypted export and restore path for operator settings from the shared `/connections` surface
- the exported backup should not expose plaintext Apple credentials, OAuth client secrets, refresh tokens, or Alexa linking secrets
- the restore flow should validate the backup shape and fail with a clear operator-facing message when the file is malformed or uses the wrong encryption context
- the backup and restore flow should cover the product-managed provider, booking, and Alexa configuration that CalSync stores in operator settings

Behavioral boundary:

- this slice is about resilient export and restore of encrypted operator settings, not a generic full-database backup system
- restore is expected to work with the same CalSync deployment encryption key that created the backup

## Alexa Contextual Next Guidance Requirement

- GitHub issue: `#65`
- interpreted requirement: Alexa-focused surfaces should show voice-specific next steps instead of reusing the broad provider-readiness guidance that is useful on the general workspace

Expected behavior:

- `/alexa/setup` should show voice-specific next guidance in the status card and turn-on summary
- the Alexa voice panel on `/connections` should show that same voice-specific guidance
- the guidance should explain the real next Alexa work, such as connecting a writable calendar, saving Cloudflare Worker access, saving account linking, or applying the saved edge plan
- generic workspace and provider-readiness copy may still exist elsewhere in the product, but Alexa-focused surfaces should not fall back to the broad `Add an Apple calendar or finish Google or Microsoft setup...` message as their primary next step

## Alexa Simulator Readiness Guidance Requirement

- GitHub issue: `#66`
- interpreted requirement: the Alexa simulator should show clear readiness and blocker guidance when no connected calendars are available instead of only rendering empty calendar selectors and a generic form

Expected behavior:

- `/alexa/simulator` should show a simulator-readiness summary before the request form
- when no connected writable calendar exists, the simulator should say that scheduling-intent tests are still blocked by missing calendar setup
- that no-calendar state should still explain that `LaunchRequest` and general voice-copy previews remain useful
- empty named-calendar selectors should get helper text that explains why there are no choices yet and what setup will populate them

## Alexa Account-Linking Readiness Requirement

- GitHub issue: `#84`
- interpreted requirement: the shared Alexa setup guidance should surface account-linking readiness directly instead of treating Cloudflare access and skill allowlisting as the only remaining Alexa setup state

Expected behavior:

- the Alexa voice panel on `/connections` should show whether account linking is ready or still needs setup
- the shared Alexa next-action guidance should mention saving a household link code whenever account linking is still missing and that is part of the real remaining turn-on work
- when account linking is already configured, `/connections` should say so plainly instead of leaving that state hidden on `/alexa/setup` alone

## Alexa Step 4 Prerequisite Visibility Requirement

- GitHub issue: `#85`
- interpreted requirement: the final Alexa turn-on summary should show account-linking readiness as one of the visible live prerequisites instead of forcing operators to infer it from an earlier setup step

Expected behavior:

- `GET /alexa/setup` Step 4 should include an explicit account-linking readiness row
- that row should show whether account linking is configured right now
- the final Step 4 checklist and next-action guidance should stay aligned, so the page does not hide one of the real live turn-on prerequisites

## Alexa Step 4 Writable Calendar Requirement

- GitHub issue: `#86`
- interpreted requirement: the final Alexa turn-on summary should show whether a writable calendar is connected, because that is the first real scheduling prerequisite in the current live turn-on flow

Expected behavior:

- `GET /alexa/setup` Step 4 should include an explicit writable-calendar readiness row
- that row should show whether CalSync currently has any writable connected calendar path
- the Step 4 checklist should agree with the next-action guidance instead of hiding the current first blocker in voice turn-on

## Alexa Step 4 Cloudflare Access Requirement

- GitHub issue: `#87`
- interpreted requirement: the final Alexa turn-on summary should show whether Cloudflare Worker access is configured, because the live next-action guidance already treats product-managed Worker access as a prerequisite for live edge turn-on

Expected behavior:

- `GET /alexa/setup` Step 4 should include an explicit Cloudflare-access readiness row
- that row should show whether CalSync currently has saved Cloudflare Worker-management credentials
- the Step 4 checklist should agree with the live helper and next-action guidance instead of hiding the Worker-access blocker outside the final summary

## Alexa Step 4 Desired State Requirement

- GitHub issue: `#88`
- interpreted requirement: the final Alexa turn-on summary should show whether a desired Alexa plan has already been saved in CalSync, because the product supports a save-now/apply-later flow and the live turn-on path depends on that saved desired state

Expected behavior:

- `GET /alexa/setup` Step 4 should include an explicit desired-state readiness row
- that row should show whether CalSync currently has saved desired Alexa edge settings
- the Step 4 checklist should agree with the save-now/apply-later flow instead of hiding the desired-state prerequisite in a separate status card

## Connections Alexa Desired State Requirement

- GitHub issue: `#89`
- interpreted requirement: the shared Alexa panel on `/connections` should tell operators when no desired Alexa plan has been saved yet, instead of presenting the unsaved default state like a real saved live plan

Expected behavior:

- `GET /connections` should show a truthful desired-settings status inside the Alexa panel
- when no desired Alexa edge state has been saved yet, the panel should say that clearly instead of showing `Keep Alexa off` as if that were a deliberate saved plan
- when a desired Alexa plan has been saved, the panel should acknowledge that it is saved and describe the saved mode

## Connections Alexa Writable Calendar Requirement

- GitHub issue: `#90`
- interpreted requirement: the shared Alexa panel on `/connections` should show whether a writable calendar is connected, because that is the first real scheduling prerequisite in the live Alexa turn-on flow

Expected behavior:

- `GET /connections` should include a writable-calendar readiness card inside the Alexa panel
- that card should show `Ready` when CalSync has a writable connected calendar path and `Needs setup` when it does not
- the shared Alexa panel should agree with its own next-action guidance instead of hiding the writable-calendar blocker only in summary text

## Connections Provider Next Actions Requirement

- GitHub issue: `#91`
- interpreted requirement: the shared `/connections` finish-line summary should tell operators to save the shared Google or Microsoft OAuth app first when browser account connect is not yet available

Expected behavior:

- `GET /connections` should keep the Google and Microsoft `Next actions` summary aligned with the provider cards on the same page
- when the shared OAuth app is missing, the summary should say to save the shared OAuth app before browser account connect is available
- only once the shared OAuth app is saved should the summary advance to telling operators to connect the account through the browser

## Alexa Setup Unsaved Desired-State Truthfulness Requirement

- GitHub issue: `#121`
- interpreted requirement: `/alexa/setup` should not present fallback default Alexa settings as if they were a real saved operator plan when no desired Alexa edge state has actually been saved yet

Expected behavior:

- when `desired_alexa.saved` is false, the `Desired Alexa settings` card should render an explicit unsaved state instead of `Alexa should stay disabled`
- in that same unsaved state, the `Pending edge changes` card should not say `Live Worker already matches`
- the page should instead explain that no desired Alexa plan has been saved yet and that CalSync cannot compare the live Worker to a saved plan until one exists
- once a desired Alexa plan is actually saved, the setup page can resume the existing enabled/disabled and drift-vs-match wording

## Alexa Blank-Save Truthfulness Requirement

- GitHub issue: `#122`
- interpreted requirement: saving blank Alexa defaults, or saving Alexa enabled without any real skill ID, should not count as a real desired Alexa live plan

Expected behavior:

- `GET /api/readiness` should keep telling operators to save the Alexa plan and real skill ID until at least one real skill ID is saved
- `GET /alexa/setup` should keep the desired-settings and pending-edge cards in a not-saved state when no real skill ID exists yet
- `GET /connections` should keep the shared Alexa desired-settings card in a not-saved state when no real skill ID exists yet
- blank/default Alexa saves may preserve the safe disabled runtime state, but they should not suppress the real missing-skill-ID guidance
- simply checking `enable_alexa` without a real skill ID should still leave the setup flow blocked on the skill-ID step

## Alexa Save-Response Truthfulness Requirement

- GitHub issue: `#123`
- interpreted requirement: when an Alexa submit still does not create a real desired live plan, the response itself should not claim success as if a live plan was saved

Expected behavior:

- blank `POST /alexa/setup` and blank `POST /connections/alexa` should not flash `Desired Alexa settings saved securely.`
- instead, those blank saves should say that no desired Alexa plan was saved yet
- `POST /alexa/setup` and `POST /connections/alexa` with `enable_alexa=true` but no real skill ID should say that the real Alexa skill ID is still required before a live plan can be saved
- these incomplete submits should skip edge-apply attempts and should not surface Cloudflare apply errors as if the only blocker were Worker access
- the rendered response should stay aligned with `desired_alexa.saved=false`, the `Not saved yet` cards, and the shared readiness next action

## Alexa Draft Helper-Copy Truthfulness Requirement

- GitHub issue: `#124`
- interpreted requirement: when the operator has only an Alexa draft with `enable_alexa=true` but no real skill ID, the helper copy under the Alexa forms should not talk like a real desired plan can already be saved

Expected behavior:

- on both `GET /alexa/setup` and `GET /connections`, when the current Alexa draft is enabled but still has no real skill ID, the helper copy below the form should say that the real Alexa skill ID is still required
- that helper should not keep saying `this will save the desired Alexa plan in CalSync until live edge updates are available`
- the helper should stay aligned with the truthful incomplete-submit response copy, the `Not saved yet` cards, and the shared readiness next action

## Alexa Draft-State Distinction Requirement

- GitHub issue: `#125`
- interpreted requirement: when the operator has turned Alexa on in the form but still has no real skill ID, CalSync should describe that as a draft state, not as untouched defaults

Expected behavior:

- `GET /api/readiness` should expose the skill-ID-missing state as a draft, not `source=defaults`
- `GET /alexa/setup` and `GET /connections` should show an explicit draft-only desired-settings state when `enable_alexa=true` but no real skill ID exists yet
- that draft-only state should stay distinct from untouched defaults and from a real saved live plan
- the draft-only state should still keep the real skill-ID step visible and should not imply that Cloudflare access is already the next blocker

## Alexa Simulator Draft-State Requirement

- GitHub issue: `#126`
- interpreted requirement: when the operator has only a skill-ID-missing Alexa draft, `/alexa/simulator` should stop reading like route enablement is the only remaining Alexa gap

Expected behavior:

- when `desired_alexa.enable_alexa=true`, `desired_alexa.saved=false`, and no real skill ID exists yet, `GET /alexa/simulator` should explicitly describe that the live Alexa plan is still only a draft
- in that same state, the simulator readiness detail should keep the shared skill-ID-first next action visible instead of only saying the real route is disabled
- the simulator should still say scheduling rehearsal is useful now because the writable calendar path is connected; this is a truthfulness requirement about the remaining live blocker, not a rollback of simulator usefulness

## Connections Alexa Live Route Truthfulness Requirement

- GitHub issue: `#127`
- interpreted requirement: when the operator only has an Alexa draft and no real skill ID has been saved yet, the `Live route` detail card on `GET /connections` should stay aligned with the same blocker ordering already used by readiness and the other Alexa cards on that page

Expected behavior:

- in the skill-ID-missing draft state, the `Live route` card on `GET /connections` should not say route enablement is the only missing step
- that card should instead describe the current blocker ordering with the same desired-state-first guidance as the rest of the Alexa panel
- the Connections Alexa panel should not mix newer draft-state guidance with older route-enable-only detail copy in the same live state

## Blocked Operator Apple Reconnect Requirement

- GitHub issue: `#92`
- interpreted requirement: when the current live deployment is blocked on reconnecting the recovered Apple household calendar, the main operator-facing blocked surfaces should point directly at that Apple reconnect path instead of only saying that a writable calendar is missing

Expected behavior:

- when shared readiness already says Apple reconnect is the next step, the root workspace action stack on `/` should include a direct Apple setup action alongside the other operator links
- when `/booking/setup` is blocked only because no writable calendar is connected and recovered Apple hints already exist, the blocker copy should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before configuring public booking
- `/booking/setup` should also expose direct operator actions into Apple setup and Connections in that recovery-shaped blocked state
- invitee-facing `/book` copy can remain generic, because it should not expose operator-only Apple recovery details to the public booking surface

## Blocked Root Recovery Guidance Requirement

- GitHub issue: `#93`
- interpreted requirement: once the live deployment is clearly in Apple recovery mode, the blocked root workspace panels should stop mixing generic no-calendar copy with recovery-aware guidance on the same page

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /` should use Apple reconnect guidance in the blocked schedule, detail, create, and availability panels
- those blocked panel messages should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before expecting live schedule data, appointment detail, writes, or availability search
- the blocked detail panel should expose the same direct operator actions into Connections and Apple setup that the other blocked root panels already provide
- when no recovery hint exists, the root workspace can keep the more generic writable-calendar wording used for a blank-install disconnected state

## Alexa Recovery Guidance Requirement

- GitHub issue: `#94`
- interpreted requirement: when the live deployment is in Apple recovery mode, Alexa setup and Connections should stop describing the voice prerequisite as a generic writable-calendar setup problem and instead point at the specific recovered Apple reconnect path

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /alexa/setup` should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before the remaining Alexa account-linking and edge steps
- in that same state, `GET /connections` should make the Alexa writable-calendar card recovery-aware instead of only saying to connect a writable calendar
- the `Alexa:` line in the Connections `Finish the live stack` summary should also reflect that Apple reconnect comes before the remaining household link-code or Cloudflare steps
- when no recovery hint exists, the Alexa surfaces can keep the more generic writable-calendar wording used for a blank-install disconnected state

## Booking Setup Recovery Guidance Requirement

- GitHub issue: `#95`
- interpreted requirement: when the live deployment is in Apple recovery mode, the full booking-setup operator path should stop mixing recovery-aware blockers with generic writable-calendar copy

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /booking/setup` should use Apple reconnect guidance in the target-behavior card as well as the top-level blocked state
- in that same state, disconnected `POST /booking/setup` requests should fail with Apple reconnect guidance instead of the generic writable-calendar save error
- disconnected `POST /booking/setup/types` requests should fail with Apple reconnect guidance instead of the generic writable-calendar booking-type error
- when no recovery hint exists, the booking setup page and disconnected booking setup actions can keep the more generic writable-calendar wording used for a blank-install disconnected state

## Workspace Capability Recovery Guidance Requirement

- GitHub issue: `#96`
- interpreted requirement: when the live deployment is in Apple recovery mode, the root `What works today` capability summary should stop using blank-install writable-calendar wording

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, the root workspace capability summary should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password to unlock create, edit, and cancel appointments
- when no recovery hint exists, the root workspace capability summary can keep the more generic writable-calendar wording used for a blank-install disconnected state

## Alexa Simulator Recovery Guidance Requirement

- GitHub issue: `#97`
- interpreted requirement: when the live deployment is in Apple recovery mode, the Alexa simulator readiness panel should stop using blank-install missing-calendar wording

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /alexa/simulator` should say Apple reconnect still blocks meaningful scheduling tests
- in that same state, the simulator readiness copy should tell operators that recovered Apple hints are already loaded into Apple setup and that scheduling intents become useful after saving a fresh app-specific password on the recovered Apple calendar
- the simulator readiness panel should expose direct operator actions into Apple setup and Connections in that recovery-shaped state
- when no recovery hint exists, the simulator can keep the more generic missing-calendar wording used for a blank-install disconnected state

## Alexa Simulator Selector Guidance Requirement

- GitHub issue: `#98`
- interpreted requirement: when the live deployment is in Apple recovery mode, the empty named-calendar helper text on the Alexa simulator should stop using blank-install setup wording

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, the empty `Target calendar` helper copy on `GET /alexa/simulator` should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before named calendar targeting appears
- in that same state, the empty `New calendar` helper copy on `GET /alexa/simulator` should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password before reschedule moves can target a named calendar there
- when no recovery hint exists, those empty selector helper lines can keep the more generic blank-install wording about named calendar targeting appearing after provider setup is connected

## Public Booking Recovery Guidance Requirement

- GitHub issue: `#99`
- interpreted requirement: when the live deployment is in Apple recovery mode, the blocked public booking page should stop using blank-install no-calendar wording

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /book` should point blocked availability search at Apple reconnect rather than generic writable-calendar setup
- in that same state, the public booking target card should acknowledge that recovered Apple hints are ready and point operators to Apple setup plus the loaded recovered calendar
- in that same state, the blocked request-time panel on `GET /book` should say Apple reconnect still blocks invitees from requesting time
- when no recovery hint exists, the public booking page can keep the more generic no-calendar wording used for a blank-install disconnected state

## Public Booking Submit Error Requirement

- GitHub issue: `#100`
- interpreted requirement: when the live deployment is in Apple recovery mode, blocked direct public booking submit responses should stop using the stale generic no-target error

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, blocked `POST /book` responses should say Apple reconnect still blocks public booking requests
- in that same state, blocked `POST /book/{slug}` responses should use that same Apple reconnect submit guidance
- when no recovery hint exists, blocked public booking submit responses can keep the more generic `No writable calendar target is ready for public booking yet.` wording

## Root Appointment Submit Error Requirement

- GitHub issue: `#101`
- interpreted requirement: when the live deployment is in Apple recovery mode, blocked direct schedule-workspace appointment-create responses should stop using the raw Apple config error

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, blocked `POST /appointments` responses should say Apple reconnect still blocks write actions
- in that same state, the blocked response should not fall back to `Primary Apple/iCloud calendar is not configured.`
- when no recovery hint exists, blocked direct appointment-create responses can keep the more generic `Connect a writable calendar before creating appointments from the schedule workspace.` wording

## Appointment Edit And Cancel Recovery Requirement

- GitHub issue: `#105`
- interpreted requirement: when the live deployment is in Apple recovery mode, stale deep-link appointment edit and cancel routes should stop exposing a working editor or a raw missing-target error

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /appointments/{appointment_id}/edit` should stop at an Apple reconnect blocker instead of rendering a real edit form
- in that same state, direct `POST /appointments/{appointment_id}/edit` should point operators to Apple reconnect instead of falling through to `Apple calendar target URL was not found.`
- in that same state, direct `POST /appointments/{appointment_id}/cancel` should point operators to Apple reconnect instead of falling through to `Apple calendar target URL was not found.`
- the blocked deep-link state should expose direct operator actions into Apple setup and Connections
- blank-install disconnected states can keep their current more generic missing-calendar behavior when no recovery hint exists

## Appointment Update And Cancel API Recovery Requirement

- GitHub issue: `#106`
- interpreted requirement: when the live deployment is in Apple recovery mode, direct appointment update and cancel API routes should stop exposing the raw missing-target error that the rest of the product already normalizes

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `PATCH /api/appointments/{appointment_id}` should point callers to Apple reconnect instead of falling through to `Apple calendar target URL was not found.`
- in that same state, `POST /api/appointments/{appointment_id}/cancel` should point callers to Apple reconnect instead of falling through to `Apple calendar target URL was not found.`
- create, list, get, availability, root submit, public booking submit, and stale deep-link edit routes should continue using that same recovery-mode Apple reconnect guidance after the API write paths are aligned
- blank-install disconnected states can keep their current more generic missing-calendar behavior when no recovery hint exists

## Alexa Worker Recovery Normalization Requirement

- GitHub issue: `#107`
- interpreted requirement: the Alexa Worker should follow the current origin Apple reconnect guidance instead of hardcoding older fresh-password-only recovery copy, so the live edge path cannot drift behind the original-key recovery flow

Expected behavior:

- when the Worker is in Apple recovery mode, launch, help, and fallback guidance should follow the current readiness-driven Apple reconnect message instead of older hardcoded fresh-password-only wording
- when the Worker receives `Apple calendar target URL was not found.` or the other recovery-mode Apple backend errors, it should speak that same current Apple reconnect guidance instead of falling back to stale Worker-owned copy
- create, availability, cancel, reschedule, and any other scheduling intents that rely on the shared normalization helper should all inherit that same recovery behavior after the Worker update
- the Worker tests should cover the stale Apple target error explicitly so the edge layer cannot silently drift behind origin normalization again
- live Cloudflare deployments should keep the `loadAppleRecoveryGuidance`, `normalizeSchedulingErrorSpeech`, and `Apple reconnect still needs one more step.` markers present so the edge proof cannot silently drift behind the repo code

## Alexa Operator Docs Truthfulness Requirement

- GitHub issue: `#128`
- interpreted requirement: once the live Alexa Worker code gap is cleared, operator docs and the imported skill-package instructions should stop reading like direct Worker env edits and manual redeploys are still the primary setup flow

Expected behavior:

- README and ops tracking should reflect that issue `#107` is the closed live Worker deployment slice, not an still-blocked redeploy path
- the Alexa docs should tell operators to copy the generated real Alexa skill ID into the CalSync Alexa setup flow first
- the Alexa package `testingInstructions` should point to CalSync-managed desired settings and allowlist save steps before mentioning any lower-level Worker fallback

## Alexa Worker Allowlist Safety Requirement

- GitHub issue: `#129`
- interpreted requirement: the live Alexa Worker should default to deny when no real allowed skill IDs have been configured yet, instead of treating an empty allowlist as permissive

Expected behavior:

- `POST /alexa` should reject requests when `ALEXA_ALLOWED_SKILL_IDS` is empty, even if the incoming request contains a non-empty Alexa `applicationId`
- the Worker should only accept live Alexa requests after at least one configured allowed skill ID is present and the incoming skill ID matches it
- Worker tests should keep explicit coverage for the empty-allowlist `403` path so this edge safety contract cannot silently drift

## Alexa Follow-up Docs Truthfulness Requirement

- GitHub issue: `#130`
- interpreted requirement: once product-managed Cloudflare Worker access is already configured, the repo docs should stop presenting the old Pi-side `sync-cloudflare` token nicety as the main current follow-up item

Expected behavior:

- the docs follow-up section should say the real current blocker is recovering the real Alexa skill ID, saving the final desired Alexa plan, and enabling the live route safely
- the Pi-side `CLOUDFLARE_API_TOKEN` / `sync-cloudflare` path can stay documented as a lower-priority operational nicety instead of the main Alexa blocker
- docs-test coverage should assert that the follow-up section names the real Alexa skill ID and no longer treats `sync-cloudflare` as the current blocker

## Alexa Recovery Scheduling Error Requirement

- GitHub issue: `#102`
- interpreted requirement: when the live deployment is in Apple recovery mode, blocked Alexa scheduling intents should stop speaking the raw Apple config error

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, blocked Alexa scheduling intents should point to Apple reconnect and the need for a fresh app-specific password
- in that same state, simulator and live voice scheduling responses should not fall back to `Primary Apple/iCloud calendar is not configured.`
- blank-install disconnected states can keep more generic calendar-not-ready voice guidance when no recovery hint exists

## Alexa Recovery Read-Intent Requirement

- GitHub issue: `#103`
- interpreted requirement: when the live deployment is in Apple recovery mode, Alexa read and lookup intents should stop surfacing stale local appointment state or generic empty-search fallbacks as if the household calendar were still live

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, `GET /api/appointments` should not surface stale local appointment rows as live calendar truth
- in that same state, `GET /api/appointments/{appointment_id}` should not expose stale local appointment detail
- in that same state, `GET /api/availability` should not fall back to generic no-opening results
- blocked Alexa list, next, availability, cancel, and reschedule flows should all point to Apple reconnect and the need for a fresh app-specific password
- simulator and live voice read intents should not fall back to stale local appointments, `I could not find...`, or `I could not find an opening...` when Apple reconnect is still the real blocker
- blank-install disconnected states can keep more generic calendar-not-ready behavior when no recovery hint exists

## Alexa Recovery Guidance-Intent Requirement

- GitHub issue: `#104`
- interpreted requirement: when the live deployment is in Apple recovery mode, Alexa launch, help, and fallback guidance should stop coaching blocked calendar reads or writes as if the household calendar were already usable

Expected behavior:

- when legacy Apple recovery hints exist and no writable calendar is connected, LaunchRequest, `AMAZON.HelpIntent`, and `AMAZON.FallbackIntent` should all point to Apple reconnect and the need for a fresh app-specific password
- the public simulator guidance intents should not keep coaching blocked create or read flows when Apple reconnect is still the real blocker
- the Worker should rely on a safe recovery-mode readiness signal instead of guessing from raw provider error text
- blank-install disconnected states can keep more generic calendar-not-ready guidance when no recovery hint exists

## Apple Live Calendar Sync Requirement

- GitHub issue: `#41`
- interpreted requirement: the Apple-first workspace and Alexa flows must read the actual household Apple calendar, not only CalSync-created rows

Expected behavior:

- date-range schedule views should sync existing Apple calendar events into the shared appointment store before rendering
- `GET /api/appointments` should surface Apple events that already existed before CalSync created anything
- default active views should hide cancelled appointments so stale noise does not dominate the schedule or voice responses
- cancelled items should still remain available for explicit reference when the operator intentionally asks for them
- edit and cancel flows should work for provider-synced Apple events, not just locally originated writes
- Alexa day-list, cancel, and reschedule flows should benefit from the same synced Apple event inventory because they already call the shared origin APIs

Operational boundary:

- this first live-read slice only needs range-based Apple sync for the requested window
- it does not yet need a full long-running background mirror of the entire calendar history

## In-Product Apple Calendar Setup Requirement

- GitHub issue: `#46`
- interpreted requirement: the Apple-first product should manage its own Apple calendar connection from the UI instead of depending only on host `.env` edits

Expected behavior:

- `GET /calendar/setup` should render an operator-facing Apple calendar setup page
- `POST /calendar/setup` should save the Apple account label, Apple username, Apple app-specific password, primary calendar URL, and primary calendar name
- the product should support more than one connected Apple account under that setup surface
- those product-managed Apple settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- the appointment service and readiness surface should fall back to product-vault Apple settings when deployment env values are absent
- the main workspace and Alexa setup flow should link back to the Apple calendar setup page

## Multi-Calendar Apple Target Requirement

- GitHub issue: `#31`
- interpreted requirement: the Apple-first product should support more than one saved writable Apple calendar target, not only one hard-wired family destination

Expected behavior:

- `POST /calendar/setup/calendars` should let the operator add another Apple calendar target for a selected Apple account without losing the current default target
- create and edit flows should expose a target calendar picker when more than one Apple calendar is saved
- `POST /api/appointments` should accept `target_calendar_url` so callers can choose a non-default Apple destination
- `PATCH /api/appointments/{appointment_id}` should accept `target_calendar_url` so the appointment can move between saved Apple calendars
- date-range sync should read across the saved Apple calendar targets instead of only one primary calendar

## Named Apple Calendar Voice Target Requirement

- GitHub issue: `#47`
- interpreted requirement: Alexa and the in-product simulator should be able to target a saved Apple calendar by human-friendly name instead of always assuming the default destination

Expected behavior:

- the shared scheduling contract should accept `target_calendar_name` in create and update flows
- Alexa create flows should support a calendar-name slot for choosing a saved Apple target
- Alexa reschedule flows should support a new calendar-name slot for moving an appointment to another saved Apple target
- the in-product simulator should expose those calendar-name fields so voice routing can be tested without guessing raw payloads

## Provider-Aware Alexa Calendar Target Requirement

- GitHub issue: `#50`
- interpreted requirement: Alexa and the in-product simulator should treat Apple, Google, and Microsoft calendar targets as one provider-aware scheduling surface instead of staying Apple-shaped after the shared scheduling brain became multi-provider

Expected behavior:

- the simulator should populate calendar-name options from the shared scheduling brain, not from Apple-only runtime state
- `target_calendar_name` should resolve against a unified provider-aware calendar target catalog
- provider-aware names such as `Family on Google` or `Calendar on Microsoft` should route correctly
- ambiguous bare names should fail clearly with actionable options instead of silently falling through between providers
- voice-facing docs and setup guidance should describe provider-aware targeting across Apple, Google, and Microsoft

## In-Product Writable Calendar Smoke Test Requirement

- GitHub issue: `#51`
- interpreted requirement: the product should let operators prove a writable Apple, Google, or Microsoft calendar target actually supports create, update, and cancel from inside CalSync

Expected behavior:

- Apple, Google, and Microsoft writable target cards should expose a `Run write test` action
- the shared scheduling brain should run a safe create -> update -> cancel verification cycle against the selected target
- if a step fails after create, CalSync should attempt cleanup and surface the real error
- the product should show a clear success message naming the calendar and provider that passed

## Availability Requirement

- GitHub issue: `#48`
- interpreted requirement: the Apple-first product should suggest open windows from the shared schedule through the workspace, edge API, and Alexa instead of only listing appointments

Expected behavior:

- `GET /api/availability` should return open windows for a requested date range and duration
- `GET /v1/availability` should expose the same behavior through the edge Worker
- the root workspace should expose a simple availability finder
- Alexa should support a `FindAvailabilityIntent`
- the simulator should expose the same intent so the running product can preview availability speech

## Cloudflare Deployment Requirement

- GitHub issue: `#35`
- interpreted requirement: evaluate Cloudflare against the rebooted Apple-first service and choose the path that matches the current FastAPI plus Postgres plus Apple CalDAV architecture

Expected deployment behavior:

- publish through Cloudflare Tunnel first if we want Cloudflare in front of the current service
- keep `kayraspi` or another Linux host as the origin until the database is externalized
- do not force this repo into Pages
- do not treat the current codebase as a drop-in Workers deployment
- revisit Cloudflare Containers only after the database/runtime boundary is redesigned

## Cloudflare Edge Worker Requirement

- GitHub issue: `#36`
- interpreted requirement: add a dedicated ChatGPT-first Cloudflare Worker as a thin authenticated edge proxy in front of the Pi-hosted Apple-first origin service

Expected edge behavior:

- deploy a dedicated Worker on its own subdomain such as `edge-calsync.neonbutterfly.net`
- keep the actual scheduling brain on `https://calsync.neonbutterfly.net`
- expose create, update, cancel, and list appointment routes through the Worker
- treat ChatGPT as the first enabled channel
- keep the Worker non-human-facing and machine-only
- keep token source-of-truth on the Pi and sync token hashes into Cloudflare automatically

Current reality:

- the Worker is live on `edge-calsync.neonbutterfly.net`
- the Pi origin now supports the Worker-facing list contract
- the Pi stores channel tokens in `/home/kay/apps/calsync/.runtime/channel-tokens.json`
- Cloudflare KV currently holds the active channel hashes used by the Worker
- the API container must mount that same host `.runtime` directory so readiness and origin-side channel tooling reflect the real source-of-truth

## Remote MCP Worker Requirement

- GitHub issue: `#37`
- interpreted requirement: expose the Apple-first scheduling brain as a real authenticated remote MCP server instead of only a raw edge HTTP API

Expected behavior:

- deploy a dedicated MCP Worker on `https://mcp-calsync.neonbutterfly.net/mcp`
- keep a `workers.dev` endpoint available as a fallback alongside the custom hostname
- expose:
  - `list_appointments`
  - `create_appointment`
  - `update_appointment`
  - `cancel_appointment`
- require authenticated client access from day one
- keep the edge Worker and origin as the only places that know the lower-level scheduling API and Apple write path
- forward MCP tool calls into the live edge/origin stack instead of duplicating calendar logic

## Alexa Skill Requirement

- GitHub issue: `#38`
- interpreted requirement: add a first Alexa custom-skill layer on top of the same shared scheduling brain instead of creating a separate voice-only backend

Expected voice behavior:

- Alexa should use the same appointment create, list, cancel, and reschedule flows as other channels
- the first voice slice should support:
  - launch and help
  - create appointment
  - list appointments for a requested day
  - read the next upcoming appointment
  - cancel a matching appointment
  - reschedule a matching appointment
- all actual calendar mutation must still happen in the origin service
- the shared `/connections` surface should show the current Alexa launch state and allow operators to save or apply desired edge settings without leaving the primary control center

Expected auth shape:

- the Alexa route should verify signed Alexa web-service requests using Amazon's certificate and request-signature flow
- the Worker should only accept configured Alexa skill IDs from `ALEXA_ALLOWED_SKILL_IDS`
- the route should remain disabled until `ENABLE_ALEXA=true`
- the first household account-linking flow may use an implicit grant, but the live Worker should still require the linked Alexa access token whenever account linking has been configured in CalSync

Current repo artifacts:

- Worker route: `POST /alexa`
- Worker simulator route: `POST /alexa/simulate`
- interaction model: `workers/edge-calsync/alexa/interaction-model.json`
- importable skill package: `workers/edge-calsync/alexa/skill-package`
- voice adapter implementation: `workers/edge-calsync/src/alexa.ts`
- origin-side simulator page:
  - `GET /alexa/simulator`
  - `POST /alexa/simulator`
- public policy pages on the origin:
  - `GET /privacy`
  - `GET /terms`

Known boundary in this slice:

- this is a first shared-household Alexa adapter, not a full multi-user account-linking platform
- before the skill is fully live, the product should still preview the real voice logic through an authenticated simulator path instead of repo-only tests or blind guesswork

## Full-Stack Readiness Requirement

- GitHub issue: `#43`
- interpreted requirement: the product itself should explain whether the Apple-first origin, channel tokens, edge Worker, and Alexa setup are actually ready, instead of forcing operators to infer readiness from docs or deployment memory

Expected behavior:

- `GET /api/readiness` should return a safe merged readiness snapshot
- the root scheduling workspace should surface that snapshot in plain language
- `GET /status` on the edge Worker should return public-safe channel and Alexa readiness without requiring auth
- the readiness surface should never expose raw tokens, secrets, or skill IDs
- the app should point to the next meaningful operator action when Alexa or channel setup is incomplete

## In-Product Alexa Setup Requirement

- GitHub issue: `#45`
- interpreted requirement: the running product should help operators finish Alexa setup directly, including a downloadable skill package and the live endpoint/policy links

Expected behavior:

- `GET /alexa/setup` should render a voice setup page inside the product
- `GET /alexa/skill-package.zip` should return the Alexa custom skill package from the running app
- the setup page should show the live edge endpoint, privacy URL, terms URL, and current readiness state
- the setup page should let the operator save Cloudflare Worker-management credentials inside the product instead of relying only on host `.env` edits
- those product-managed Worker credentials should be stored encrypted at rest with `ENCRYPTION_KEY`
- the setup page should read the current edge Worker Alexa flags when Cloudflare worker-management settings are available
- the setup page should let the operator update `ENABLE_ALEXA` and `ALEXA_ALLOWED_SKILL_IDS` from the product when the Cloudflare token has `Workers Scripts Write`
- the setup page should let the operator save a household Alexa link code and should surface the CalSync-hosted authorization URL for Alexa account linking
- the root scheduling workspace should link operators into the Alexa setup flow

## Desired Alexa Edge Settings Requirement

- GitHub issue: `#61`
- interpreted requirement: the product should preserve the intended Alexa edge state even before live Worker management is available, and it should show whether that saved plan still differs from the current Worker

Expected behavior:

- `POST /alexa/setup` should always save the desired `ENABLE_ALEXA` and `ALEXA_ALLOWED_SKILL_IDS` values in the product vault
- those desired Alexa settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- if Cloudflare Worker management is configured, the same action should also apply the desired state to the live Worker
- if Cloudflare Worker management is not configured, the operator should still get a success path for saving the desired state plus a clear explanation of what still blocks the live apply
- `GET /alexa/setup` should show the saved desired Alexa state beside the live Worker state
- the product should call out drift clearly when the saved desired Alexa state and live Worker do not match yet
- `GET /api/readiness` should surface that saved desired Alexa state so the next-action guidance can reflect a saved-but-not-yet-applied Alexa turn-on plan

## Restore-Aware Readiness Requirement

- GitHub issue: `#75`
- interpreted requirement: when CalSync has non-provider operator settings saved but no connected Apple, Google, or Microsoft provider setup left, the shared readiness guidance should treat that state as a likely recovery case and point operators toward encrypted restore from Connections

Expected behavior:

- `GET /api/readiness` should no longer act like fresh provider onboarding is the only next move when the deployment still has non-provider product-vault state such as booking setup, Alexa state, Cloudflare worker credentials, or persisted write-verification history
- in that recovery-shaped state, the shared next-action guidance on `/` and `/connections` should mention restoring an encrypted backup from Connections before or alongside re-entering provider setup
- if saved provider setup still exists, the product does not need to force restore-first guidance; this requirement is specifically about likely settings-loss recovery cases

## Legacy Apple Backup Recovery Requirement

- GitHub issue: `#76`
- interpreted requirement: the preserved old Pi SQL backup should help recover the Apple path inside the current product instead of forcing operators to inspect a legacy dump by hand

Expected behavior:

- `/connections` should accept a legacy SQL dump or zip from the old Pi backup path and extract Apple recovery hints from it
- those hints should include the recovered Apple account identity plus the old calendar URLs and a recommended writable calendar hint when the dump contains one
- `/calendar/setup` should surface those recovered hints clearly when no Apple account is connected yet
- the recovered hints should help the operator finish Apple setup with a fresh app-specific password, but they must not falsely mark Apple as connected or ready on their own
- this feature may stay focused on Apple legacy recovery; it does not need to complete Google or Microsoft legacy import in this slice

## Legacy Apple Recovery Form Prefill Requirement

- GitHub issue: `#77`
- interpreted requirement: once legacy Apple hints have been imported, the operator should be able to load those recovered values directly into the Apple setup form instead of retyping the account and calendar details by hand

Expected behavior:

- when no Apple account is connected yet, `/calendar/setup` should offer a one-step way to load a recovered Apple calendar hint into the setup form
- loading a recovered hint should prefill the Apple account label, Apple username, calendar URL, and calendar name while still requiring a fresh app-specific password before save
- operators should be able to load either the recommended writable hint or another recovered calendar hint from the imported legacy data
- loading recovered values into the form must not falsely mark Apple connected or ready before a real save succeeds

## Apple Recovery Guidance Requirement

- GitHub issue: `#78`
- interpreted requirement: once legacy Apple hints exist, the shared readiness and Apple provider surfaces should point to the concrete reconnect step instead of still reading like a generic missing-provider state

Expected behavior:

- when legacy Apple recovery hints exist and no Apple account is connected yet, GET /api/readiness should tell operators to open Apple setup, load a recovered Apple hint, and save a fresh app-specific password
- `/` and `/connections` should reflect that more specific Apple reconnect guidance through their existing readiness surfaces
- `/connections` should acknowledge that a recovered Apple hint is available inside the Apple provider summary
- `/calendar/setup` should show a source-card state like recovered-hint availability instead of generic `Missing`
- these guidance improvements must not falsely mark Apple connected or ready before a real save succeeds

## Apple Setup Validation Requirement

- GitHub issue: `#79`
- interpreted requirement: before the operator saves recovered or newly entered Apple credentials into the live product vault, CalSync should let them validate the Apple username, app-specific password, and calendar URL safely from the setup form

Expected behavior:

- `POST /calendar/setup/validate` should test the entered Apple username, app-specific password, and primary calendar URL without persisting those values first
- the validation action should return a clear success path when the Apple calendar can be read safely
- the validation action should return a clear failure path when Apple authentication or calendar access fails
- validation must not mutate the saved Apple account state, writable target state, or readiness state on its own
- `/calendar/setup` should expose a visible `Validate Apple connection` action alongside save so the reconnect flow is not blind

## Legacy Apple Recommended Target Requirement

- GitHub issue: `#80`
- interpreted requirement: when CalSync imports legacy Apple backup hints, the default reconnect target should prefer the actual recovered writable booking target instead of a merely enabled personal-reference calendar

Expected behavior:

- legacy Apple recovery extraction should rank explicit `writable_booking_target` calendars ahead of generic enabled calendars when choosing the recommended reconnect hint
- `/calendar/setup` and `/connections` should therefore point operators at the real recovered writable booking target by default after import
- generic enabled personal-reference calendars may still be listed as recovered hints, but they should not outrank an explicit recovered write target

## Automatic Apple Recovery Prefill Requirement

- GitHub issue: `#81`
- interpreted requirement: once CalSync knows the recommended recovered Apple reconnect target, the default Apple setup page should open directly in that recovered reconnect state instead of waiting for the operator to click a second load-hint action first

Expected behavior:

- when no Apple account is connected yet and legacy Apple recovery hints exist, `GET /calendar/setup` should auto-load the recommended recovered Apple hint into the setup form
- the auto-loaded state should prefill the Apple account label, username, primary calendar URL, and calendar name for the recommended reconnect target
- the product should still require a fresh app-specific password before validation or save can complete the reconnect
- operators should still be able to switch to a different recovered calendar hint explicitly if the recommended reconnect target is not the one they want
- this default-prefill behavior must not falsely mark Apple connected or ready before a real save succeeds

## Apple Recovery Guidance Alignment Requirement

- GitHub issue: `#82`
- interpreted requirement: once the recommended recovered Apple hint auto-loads by default, shared readiness and Connections guidance should stop describing the older manual hint-loading workflow

Expected behavior:

- when legacy Apple recovery hints exist and no Apple account is connected yet, shared readiness guidance should tell operators to open Apple setup, confirm the loaded recovered calendar, and save a fresh app-specific password
- `/connections` should use the same already-loaded recovery framing in the Apple setup checklist, provider summary, and finish-the-stack guidance
- `/connections` should no longer expose a primary action that suggests the default recovered Apple hint still needs to be manually loaded first
- operators should still be able to switch to another recovered calendar from inside `/calendar/setup` if the recommended reconnect target is not the one they want

## Legacy Apple Encrypted Secret Recovery Requirement

- GitHub issue: `#108`
- interpreted requirement: when a preserved legacy Apple backup contains an encrypted app-specific password, CalSync should preserve that secret safely, detect whether the current encryption key can reuse it, and surface the truthful recovery state instead of silently dropping it

Expected behavior:

- importing a legacy Apple backup should retain the presence of `credential_secret_encrypted` alongside the existing calendar hints
- when the current CalSync `encryption_key` can decrypt that preserved Apple secret, `/calendar/setup` should allow validate/save without forcing the operator to retype the password
- when the current CalSync `encryption_key` cannot decrypt that preserved Apple secret, `/calendar/setup`, `/connections`, and shared readiness guidance should say the original key is needed or a fresh manual app-specific password must be entered
- these encrypted-secret diagnostics must not falsely mark Apple connected or ready before a real save succeeds

## Legacy Apple Original-Key Recovery Requirement

- GitHub issue: `#113`
- interpreted requirement: when a preserved legacy Apple app-specific password still needs the original CalSync encryption key, Apple setup should let operators enter that original key once so CalSync can recover the secret and re-save it under the current deployment key

Expected behavior:

- when the preserved Apple password still needs the original key, `GET /calendar/setup` should expose a one-time `Original CalSync encryption key` field alongside the existing Apple reconnect form
- `POST /calendar/setup/validate` should accept that original key, decrypt the preserved Apple secret if the key is correct, and validate the loaded recovered calendar without persisting the key itself
- `POST /calendar/setup` should accept that original key, decrypt the preserved Apple secret if the key is correct, and save the Apple account by re-encrypting the recovered password under the current deployment key
- if the supplied original key is wrong, Apple setup should return a clear recovery-specific error instead of falling back to the generic missing-password error

## Original-Key Recovery Guidance Requirement

- GitHub issue: `#114`
- interpreted requirement: once Apple setup supports one-time original-key recovery, recovery-mode guidance should stop implying that operators must globally restore the deployment encryption key

Expected behavior:

- original-key-needed recovery guidance should tell operators to open Apple setup and enter the original CalSync encryption key there, or save a fresh app-specific password
- that wording should flow consistently through shared readiness, blocked root and booking messaging, recovery-mode appointment API responses, Alexa setup, Connections, and the Alexa simulator
- Apple setup can still use more specific local wording like `Enter that key below` because the form field lives on that page

## Connected Apple Truthfulness Requirement

- GitHub issue: `#115`
- interpreted requirement: once Apple has been reconnected successfully and live readiness is green again, `/connections` must stop showing stale legacy recovery-secret blockers that imply Apple still needs the original key

Expected behavior:

- when Apple read/write is live again, the Apple card on `GET /connections` should prioritize the connected-state summary and connected accounts/targets
- the stale `Recovered password` card should not render while Apple is already connected and writable, even if preserved legacy recovery metadata still exists in operator settings
- legacy encrypted-secret diagnostics can still render in recovery mode before the reconnect is complete

## Shared Alexa Readiness Requirement

- GitHub issue: `#116`
- interpreted requirement: once Apple is already connected and writable again, shared readiness should name the earliest real Alexa blockers instead of skipping straight to generic edge enablement

Expected behavior:

- when a writable calendar is ready but Alexa account linking and Cloudflare Worker access are still missing, `GET /api/readiness` should tell operators to save a household link code and Cloudflare Worker access
- when account linking is ready but Cloudflare Worker access is still missing, shared readiness should say to save Cloudflare Worker access
- when Cloudflare Worker access is ready but account linking is still missing, shared readiness should say to save a household link code
- shared surfaces like `GET /connections` that print `readiness.next_action` should stay aligned automatically once the readiness API is corrected

## Alexa Setup Account-Linking Intro Truthfulness Requirement

- GitHub issue: `#117`
- interpreted requirement: once Alexa account linking is already configured, the Step 2.5 intro on `GET /alexa/setup` should stop reading like first-time setup is still incomplete

Expected behavior:

- when a household link code and bearer token are already saved, the Step 2.5 intro should say those account-linking details are already ready and point operators toward using the authorization URL in Alexa settings
- that same configured-state intro should still mention that the operator can save a new household link code from the page if they want to rotate it
- the older `Save a household link code, then use the authorization URL below...` wording should only render before account linking has been configured
- the configured Step 2.5 intro should stay aligned with the existing `Link code saved` and `Access token ready` status cards on the same page

## Alexa Desired-State Next-Step Requirement

- GitHub issue: `#118`
- interpreted requirement: once Apple is already connected and Alexa account linking is already configured, shared readiness and Alexa-specific next-step guidance should stop skipping over the unsaved desired Alexa plan

Expected behavior:

- when the desired Alexa plan is still unsaved after account linking is ready, `GET /api/readiness` should tell operators to save the Alexa plan and real skill ID before Cloudflare apply-only guidance takes over
- `GET /alexa/setup` and `GET /connections` should keep their Alexa `Next action` copy aligned with that same desired-state-first branch
- once the desired Alexa plan has been saved, the next-step guidance can advance to Cloudflare Worker access or live edge apply work
- this branch should only override the older Cloudflare-only guidance after the account-linking prerequisite has already been satisfied

## Alexa Skill-ID Form Guidance Requirement

- GitHub issue: `#119`
- interpreted requirement: when the live product asks operators to save the Alexa plan and real skill ID, the save forms themselves should explain where that real skill ID comes from

Expected behavior:

- `GET /alexa/setup` should tell operators to import the skill package in the Alexa developer console, copy the generated real Alexa skill ID, and paste it into `Allowed skill IDs`
- `GET /connections` should surface the same guidance or point operators back to Alexa setup for the fuller turn-on flow
- the `Allowed skill IDs` field should not read like unexplained low-level config when no skill ID has been saved yet
- this guidance should stay aligned with the repo Alexa README and skill-package instructions that already describe copying the generated skill ID after import

## Connections Alexa Summary Truthfulness Requirement

- GitHub issue: `#120`
- interpreted requirement: once `/api/readiness` and the main Alexa forms point to the desired-state-first next step, the remaining Alexa summaries on `/connections` should stop using older generic edge-enable wording

Expected behavior:

- the `Alexa edge route` status card on `GET /connections` should describe the current post-account-linking state with the same desired-state-first ordering
- the `Finish the live stack` Alexa summary on `GET /connections` should mirror that same current guidance instead of older `finish edge enablement and skill-ID allowlisting` copy
- these summaries should stay aligned with `readiness.next_action` and the shared Alexa form guidance on the same page
- the page should not mix desired-state-first messaging and older generic edge-enable messaging in the same live state

## Alexa Encrypted Secret Recovery Guidance Requirement

- GitHub issue: `#109`
- interpreted requirement: when legacy Apple recovery hints exist and no writable calendar is connected, Alexa-facing recovery surfaces should mirror the preserved encrypted-secret state instead of always acting like a fresh password is the only path forward

Expected behavior:

- when the preserved Apple password is reusable with the current key, `GET /alexa/setup`, the Alexa panel on `GET /connections`, and `GET /alexa/simulator` should point operators to validate or save the already-loaded recovered calendar
- when the preserved Apple password still needs the original key, those same Alexa surfaces should tell operators to enter the original CalSync encryption key on Apple setup or save a fresh manual app-specific password before the remaining Alexa steps
- when no preserved encrypted password exists, those Alexa surfaces can keep the older recovery wording about confirming the loaded recovered calendar and saving a fresh app-specific password
- the Alexa simulator readiness copy and empty selector helper text should follow the same reusable-versus-original-key distinction so voice rehearsal guidance does not drift behind Apple setup and Connections

## Non-Alexa Encrypted Secret Recovery Guidance Requirement

- GitHub issue: `#110`
- interpreted requirement: when legacy Apple recovery hints exist and no writable calendar is connected, the rest of the recovery-mode app should mirror the preserved encrypted-secret state instead of always acting like a fresh password is the only next step

Expected behavior:

- blocked root workspace messaging, blocked booking flows, and stale appointment edit/cancel blockers should all distinguish between reusable preserved Apple secrets, original-key-needed recovery, and the older fresh-password-only recovery case
- recovery-mode public booking and booking-setup messages should point to the original CalSync encryption key when that is the real current blocker
- recovery-mode appointment API responses should use the same reusable-versus-original-key distinction instead of only saying to confirm the recovered calendar and save a fresh password

## Root Default Target Recovery Requirement

- GitHub issue: `#111`
- interpreted requirement: when legacy Apple recovery hints exist and the recommended recovered calendar is already loaded into Apple setup, the root workspace should stop reading like an empty target state

Expected behavior:

- if a writable calendar is truly connected, the root target card should keep showing the live connected target
- if no writable calendar is connected and no legacy Apple recovery hints exist, the root target card may continue to say `No calendar selected`
- if no writable calendar is connected and legacy Apple recovery hints exist, the root target card should show the recommended recovered Apple calendar name instead of `No calendar selected`
- in the original-key-needed recovery branch, that same target card should explain that the recovered Apple target is already loaded in setup and still needs the original CalSync encryption key or a fresh app-specific password

## Blocked Target Selector Recovery Requirement

- GitHub issue: `#112`
- interpreted requirement: when a disabled calendar target selector is blocked only because Apple reconnect is still incomplete, it should not read like a blank install if the recovered target is already known

Expected behavior:

- if no writable calendar is connected and no legacy Apple recovery hints exist, disabled target selectors may continue to say `No writable calendars connected yet`
- if no writable calendar is connected and legacy Apple recovery hints exist, the disabled target selectors on the root workspace create form and `/booking/setup` should name the recommended recovered Apple target instead of the generic empty text
- in the original-key-needed branch, those selector labels should mention that Apple setup still needs the original CalSync encryption key or a fresh app-specific password

## Root Workspace Stale Detail Blocking Requirement

- GitHub issue: `#83`
- interpreted requirement: when no writable calendar is connected, the root workspace should not keep showing stale hero stats, next-up text, or selected appointment detail from old local appointment rows

Expected behavior:

- when `any_calendar_ready` is false, the root workspace should keep the hero summary in a clearly blocked state instead of showing stale appointment counts or a stale next-up appointment
- when `any_calendar_ready` is false, the root workspace should not render selected appointment detail, audit trail, or edit/cancel actions from stale local appointment rows
- the blocked board, blocked detail panel, blocked create form, and blocked availability state should all agree with each other about the disconnected state
- the disconnected root workspace should not keep offering stale schedule-reference links that imply a still-live selected appointment context

## Alexa Save-Only Action Truthfulness Requirement

- GitHub issue: `#74`
- interpreted requirement: Alexa setup surfaces should distinguish saving the desired voice plan from applying it live, so operators are not told they can update the edge Worker when Cloudflare Worker management is still unavailable

Expected behavior:

- when Cloudflare Worker management is available, `/alexa/setup` may continue to use live-apply language like `Apply edge settings`
- when Cloudflare Worker management is available, the Alexa form on `/connections` may continue to use live-apply language like `Apply Alexa settings`
- when Cloudflare Worker management is unavailable, both surfaces should switch to truthful save-only labels instead of promising a live apply
- the save-only state should explain that CalSync will store the desired Alexa enablement and skill allowlist until live Worker updates are available
- the existing save-now/apply-later behavior from `#61` should stay intact; this is a truthfulness requirement for wording and operator guidance, not a behavior rollback
