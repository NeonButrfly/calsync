# Backend Prompt Capture

- GitHub issue: `#1`
- Scope: Phase 1 foundation for a read-only calendar aggregation service

## Interpreted Requirements

- provide a Linux and Docker Compose friendly deployment with `APP_HOST=0.0.0.0` and `APP_PORT=3080`
- require first-run admin setup instead of shipping a default account
- require mandatory MFA with TOTP, QR enrollment, and recovery codes
- provide local break-glass recovery commands
- keep all provider behavior read-only
- publish read-only ICS feeds with stable unguessable tokens
- support a mock provider mode so the app can be validated before Google or Apple credentials exist

## Behavioral Boundaries

- mandatory MFA stays enabled for admin access
- provider access is read-only
- no Google write-back
- no Apple write-back
- no destructive provider actions

## Phase Notes

- Phase 1 uses the mock provider and the normalized local event model
- Google OAuth setup is documented for Phase 2
- Apple app-specific password and CalDAV integration are documented for Phase 3
