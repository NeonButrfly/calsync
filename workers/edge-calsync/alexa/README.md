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
7. Test the launch, list, and create flows in the developer console.

## Current scope

- launch/help
- create appointment
- list appointments for a requested day

## Current limits

- no public store publishing workflow yet
- no multi-user household identity model yet
- no update or cancel voice intent yet
