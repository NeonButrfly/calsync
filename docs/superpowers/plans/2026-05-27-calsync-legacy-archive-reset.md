# CalSync Legacy Archive Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the current full CalSync app on a dedicated legacy branch, then reset `main` to a clean Apple-first ChatGPT foundation with only the new direction docs and minimal repo scaffolding.

**Architecture:** Treat the existing app as archived reference material instead of deleting its history. Keep the reboot branch intentionally tiny so future implementation work starts from a deliberate product core rather than the previous multi-surface UI and scheduling stack.

**Tech Stack:** Git, GitHub issues, Markdown docs, existing CalSync repo

---

### Task 1: Lock the pre-reset checkpoint

**Files:**
- Modify: none
- Test: git history and issue tracker state

- [ ] **Step 1: Create the required snapshot commit**

Run:

```powershell
git commit --allow-empty -m "chore: snapshot before legacy archive reset"
```

Expected: a new snapshot commit exists at the current `main` head before any branch/archive changes.

- [ ] **Step 2: Verify current tracker coverage**

Run:

```powershell
gh issue list --limit 100 --search "archive reset legacy ChatGPT app"
```

Expected: no duplicate issue already covers the requested archive/reset slice.

- [ ] **Step 3: Verify the dedicated archive/reset issue**

Run:

```powershell
gh issue view 33
```

Expected: issue `#33` is the canonical tracker for the reset work and can be referenced by follow-up docs or commits.

### Task 2: Preserve the full old app on a legacy branch

**Files:**
- Modify: git refs only
- Test: local and remote branch presence

- [ ] **Step 1: Create the legacy branch from the current preserved app state**

Run:

```powershell
git branch legacy/pre-chatgpt-brain-reset
```

Expected: the current full-app tree is reachable from `legacy/pre-chatgpt-brain-reset`.

- [ ] **Step 2: Push the legacy branch to origin**

Run:

```powershell
git push origin legacy/pre-chatgpt-brain-reset
```

Expected: the archived branch is available remotely for later reference.

- [ ] **Step 3: Verify the remote branch exists**

Run:

```powershell
git ls-remote origin refs/heads/legacy/pre-chatgpt-brain-reset
```

Expected: one SHA is returned for the remote legacy branch.

### Task 3: Replace the current app tree with a minimal reboot scaffold on `main`

**Files:**
- Keep: `C:\Code\calsync\.gitignore`
- Keep: `C:\Code\calsync\docs\superpowers\specs\2026-05-27-calsync-apple-calendar-chatgpt-app-design.md`
- Keep: `C:\Code\calsync\docs\superpowers\plans\2026-05-27-calsync-legacy-archive-reset.md`
- Modify: `C:\Code\calsync\README.md`
- Modify: `C:\Code\calsync\docs\prompts\backend.md`
- Delete: legacy app/runtime files and old planning/docs that no longer belong on the clean reboot branch

- [ ] **Step 1: Remove the legacy application directories and files from `main`**

Run:

```powershell
git rm -r alembic src tests
git rm .env.example alembic.ini docker-compose.yml Dockerfile pyproject.toml
```

Expected: the old backend, tests, and runtime scaffolding are removed from `main` but remain preserved on the legacy branch.

- [ ] **Step 2: Remove old roadmap/spec docs that describe the previous product**

Run:

```powershell
git rm docs/ops.md
git rm docs/prompts/backend.md
git rm docs/superpowers/specs/2026-05-12-calsync-phase-1-foundation-design.md
git rm docs/superpowers/specs/2026-05-13-calsync-phase-2-google-oauth-design.md
git rm docs/superpowers/specs/2026-05-13-calsync-provider-onboarding-ui-design.md
git rm docs/superpowers/specs/2026-05-14-calsync-public-url-google-flightboard-design.md
git rm docs/superpowers/specs/2026-05-22-calsync-utility-expansion-design.md
git rm docs/superpowers/specs/2026-05-23-calsync-problem-actions-event-explain-design.md
git rm docs/superpowers/specs/2026-05-24-calsync-best-in-class-roadmap-design.md
git rm docs/superpowers/specs/2026-05-24-calsync-microsoft-connect-discovery-design.md
git rm docs/superpowers/specs/2026-05-24-calsync-write-capable-scheduling-redesign-design.md
git rm docs/superpowers/plans/2026-05-12-calsync-phase-1-foundation.md
git rm docs/superpowers/plans/2026-05-13-calsync-phase-2-google-oauth.md
git rm docs/superpowers/plans/2026-05-13-calsync-provider-onboarding-ui.md
git rm docs/superpowers/plans/2026-05-14-calsync-public-url-google-flightboard.md
git rm docs/superpowers/plans/2026-05-22-calsync-utility-expansion-phase-a.md
git rm docs/superpowers/plans/2026-05-23-calsync-problem-actions-event-explain.md
git rm docs/superpowers/plans/2026-05-24-calsync-microsoft-connect-discovery.md
git rm docs/superpowers/plans/2026-05-24-calsync-source-confidence-and-lineage.md
git rm docs/superpowers/plans/2026-05-24-calsync-write-capable-foundation-phase-a-b1.md
```

Expected: `main` keeps only reboot-relevant docs instead of the previous app history.

- [ ] **Step 3: Rewrite the README for the clean reboot**

README should state:

```markdown
# CalSync

CalSync is being rebooted as an Apple-first conversational scheduling system.

## Current focus

- ChatGPT app for Apple Calendar
- small owned service as the scheduling brain
- iCloud as the family-facing calendar target

## Legacy app archive

The previous full CalSync application has been preserved on the `legacy/pre-chatgpt-brain-reset` branch for reference.
```

Expected: the root README matches the new starting point immediately.

### Task 4: Recreate the minimal reboot docs

**Files:**
- Create: `C:\Code\calsync\docs\prompts\backend.md`
- Create: `C:\Code\calsync\docs\superpowers\specs\2026-05-27-calsync-apple-calendar-chatgpt-app-design.md`
- Create: `C:\Code\calsync\docs\superpowers\plans\2026-05-27-calsync-legacy-archive-reset.md`
- Test: content review and placeholder scan

- [ ] **Step 1: Restore the approved Apple-first design spec**

File content must preserve the approved design for:

- Apple/iCloud-first ChatGPT appointment create, edit, cancel
- owned service boundary
- local normalized appointment records and audit history
- future path to Google intake, iCloud Reminders sync, and family brain expansion

- [ ] **Step 2: Restore the matching prompt capture**

`docs/prompts/backend.md` should contain only the reboot-relevant entry for issue `#32`, including:

- Apple/iCloud-first conversational write-back scope
- owned-service requirement
- iCloud as the family-visible destination
- future work boundaries for Google intake and iCloud Reminders sync

- [ ] **Step 3: Keep the reset plan itself in the repo**

Expected: the clean `main` branch still documents how and why the reset happened.

### Task 5: Validate, commit, and publish the clean reset

**Files:**
- Modify: git index/history
- Test: git status, branch, remote, log, push parity

- [ ] **Step 1: Review the new top-level tree**

Run:

```powershell
Get-ChildItem -Force
```

Expected: the repo root is minimal and no longer contains the old app directories.

- [ ] **Step 2: Commit the reset**

Run:

```powershell
git add -A
git commit -m "chore: reset main to Apple-first ChatGPT foundation"
```

Expected: one commit captures the clean reset.

- [ ] **Step 3: Push `main` and verify parity**

Run:

```powershell
git push origin HEAD:main
git fetch --prune origin "+refs/heads/main:refs/remotes/origin/main"
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected: `LOCAL_HEAD == REMOTE_MAIN`.

## Self-Review Notes

- Spec coverage: this plan covers issue tracking, legacy branch preservation, root cleanup, doc recreation, commit/push verification, and remote parity checks.
- Placeholder scan: all operational steps use exact branch names, commit messages, file paths, and validation commands.
- Type consistency: the branch name, issue title, kept file paths, and reset commit message are consistent across tasks.
