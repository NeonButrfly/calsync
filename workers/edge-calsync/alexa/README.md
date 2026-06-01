# CalSync Alexa Skill Setup

This folder now contains the first real Alexa developer-console package for issue `#38`.

## Files

- `interaction-model.json`
  - standalone interaction model reference
- `skill-package/skill.json`
  - custom skill manifest for the web-service endpoint
- `skill-package/interactionModels/custom/en-US.json`
  - importable locale interaction model

## Intended endpoint

- `https://edge-calsync.neonbutterfly.net/alexa`

## Setup flow

1. In the Alexa developer console, create or import the custom skill package.
2. Import the files under `skill-package`.
3. Keep the endpoint as a `HTTPS` web-service endpoint with a trusted certificate.
4. Configure account linking:
   - authorization URL: `https://calsync.neonbutterfly.net/alexa/account-linking/authorize`
   - client ID: `calsync-alexa-household`
   - scopes: `calendar:read`, `calendar:write`
   - grant type: implicit
5. Save a household link code on `GET /alexa/setup` before you try the Alexa link flow.
6. After the skill is created, copy the real Alexa skill ID.
7. Paste that skill ID into `Allowed skill IDs` on `GET /alexa/setup`.
8. Save the desired Alexa plan in CalSync.
9. If Cloudflare Worker access is configured in CalSync, use `GET /alexa/setup` to turn Alexa on for the live Worker.
10. Test the launch, next-up, list, availability, create, cancel, and reschedule flows in the developer console.
11. If more than one connected calendar target is saved in CalSync, test provider-aware named calendar routing as part of the create and reschedule flows.

## Low-level fallback

If you intentionally need the manual Worker path instead of the CalSync setup flow:

- set `ALEXA_ALLOWED_SKILL_IDS=<real skill id>`
- set `ENABLE_ALEXA=true`
- redeploy the Worker

## Current scope

- launch/help
- create appointment
- create appointment on a provider-aware named calendar target across Apple, Google, and Microsoft
- next upcoming appointment
- find open time for a requested date or date range
- list appointments for a requested day
- cancel a matching appointment
- reschedule a matching appointment, including moving it to another provider-aware named calendar target across Apple, Google, and Microsoft

## Current limits

- the first account-linking path is a shared-household implicit grant, not a multi-user identity system
- no public store publishing workflow yet
- no multi-user household identity model yet
- no fully natural follow-up dialog for ambiguous matches yet
