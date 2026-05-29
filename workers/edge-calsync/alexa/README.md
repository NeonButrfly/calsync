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
4. After the skill is created, copy the real Alexa skill ID.
5. Set the Worker environment:
   - `ALEXA_ALLOWED_SKILL_IDS=<real skill id>`
   - `ENABLE_ALEXA=true`
6. Redeploy the Worker.
7. Test the launch, next-up, list, availability, create, cancel, and reschedule flows in the developer console.
8. If more than one connected calendar target is saved in CalSync, test provider-aware named calendar routing as part of the create and reschedule flows.

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

- no public store publishing workflow yet
- no multi-user household identity model yet
- no fully natural follow-up dialog for ambiguous matches yet
