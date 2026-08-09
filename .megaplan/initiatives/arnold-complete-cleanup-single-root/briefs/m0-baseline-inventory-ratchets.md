# M0: Baseline, Inventory, And Ratchets

## Outcome

The machine-checkable cleanup baseline and shrink-only guardrails are landed on `main` and the inventory/ratchet portion of this milestone is satisfied. The conformance gate is `arnold/conformance/checks.py` plus `arnold/conformance/legacy_reference_allowlist.json`; it currently has 134 live entries and enforces `stale=[]`. This brief is now a post-hoc verification record, not a prerequisite to moving implementation code.

## Scope

In:

- Verify local `main` contains the native Python completion merge and cleanup commits recorded in `docs/arnold/loose-work-cleanup-disposition-20260625.md`.
- Reconfirm branch/worktree/stash/detached-head disposition for Arnold-local work.
- Record the external old snapshot disposition. The local `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` was removed without an archive ref; M3 carries the required archive-or-explicit-abandonment follow-up.
- Keep the active Reigh engine checkout only while its process still uses it; record the deletion trigger.
- Verify the AST-scanned imports, command strings, docs, skills, scripts, tests, generated assets, discovery rows, public exports, `_pipeline` callers, CLI, chain, worker, and side-effect surfaces.
- Verify the checked-in legacy-reference/shim inventory and its owner, canonical target, kind, removal ticket, expiry milestone, and justification fields.
- Verify the shrink-only tests: new legacy imports fail; unregistered legacy files fail; legacy implementation count cannot increase.

Out:

- Do not treat this milestone as authorization to move Megaplan implementation code; that migration has already landed.
- Do not add compatibility shims before the registry and shim validator exist.
- Do not touch `banodoco/reigh-app` worktrees except to document that they are outside Arnold cleanup.

## Done Criteria

- `[Verified on current main]` The inventory and legacy-reference ratchets are machine-checkable and deterministically regenerable through `arnold/conformance/checks.py` and `arnold/conformance/legacy_reference_allowlist.json`; all 134 entries are live and `stale=[]`.
- `[Verified on current main]` The previous dirty `_pipeline` fake-shim attempt would fail the conformance gates.
- `[Verified on current main]` `_codex_skills` symlink contamination is detectable and is not present in committed changes.
- `[Verified for the inventory; closeout exception recorded]` Arnold-local loose work is inventoried. The unarchived TypeScript snapshot disposition is not silently treated as done and remains an explicit M3 follow-up.
