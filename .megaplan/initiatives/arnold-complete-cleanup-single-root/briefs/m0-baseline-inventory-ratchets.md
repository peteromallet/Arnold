# M0: Baseline, Inventory, And Ratchets

## Outcome

The repo has a machine-checkable cleanup baseline and guardrails before any single-root implementation migration begins. Every known loose-work item is decided, every legacy Megaplan surface is inventoried, and tests prevent new untracked legacy coupling.

## Scope

In:

- Verify local `main` contains the native Python completion merge and cleanup commits recorded in `docs/arnold/loose-work-cleanup-disposition-20260625.md`.
- Reconfirm branch/worktree/stash/detached-head disposition for Arnold-local work.
- Decide the external old snapshot: push `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` to `archive/typescript-bot-era`, verify, then delete locally unless the push fails.
- Keep the active Reigh engine checkout only while its process still uses it; record the deletion trigger.
- AST-scan imports, command strings, docs, skills, scripts, tests, generated assets, discovery rows, public exports, `_pipeline` callers, CLI, chain, worker, and side-effect surfaces.
- Create a checked-in legacy-file/shim registry with owner, canonical target, kind, removal ticket, expiry milestone, and justification.
- Add shrink-only tests: new legacy imports fail; unregistered legacy files fail; legacy implementation count cannot increase.

Out:

- Do not move Megaplan implementation code yet except test/support code needed for the ratchets.
- Do not add compatibility shims before the registry and shim validator exist.
- Do not touch `banodoco/reigh-app` worktrees except to document that they are outside Arnold cleanup.

## Done Criteria

- Inventory and legacy registry can be regenerated deterministically.
- The previous dirty `_pipeline` fake-shim attempt would fail the new gates.
- `_codex_skills` symlink contamination is detectable and not present in committed changes.
- No Arnold-local loose work remains undecided.
