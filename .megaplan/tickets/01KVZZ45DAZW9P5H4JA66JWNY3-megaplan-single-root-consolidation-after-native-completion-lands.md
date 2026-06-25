---
id: 01KVZZ45DAZW9P5H4JA66JWNY3
title: Megaplan single-root consolidation after native completion lands
status: open
source: human
tags:
- megaplan
- refactor
- native-pipelines
- compatibility
- reliability
codebase_id: null
created_at: '2026-06-25T18:01:55.882992+00:00'
last_edited_at: '2026-06-25T18:01:55.882992+00:00'
epics: []
---

Problem
Megaplan still has two live source roots with overlapping behavior:

- `arnold_pipelines/megaplan`
- `arnold/pipelines/megaplan`

The correct direction is to make `arnold_pipelines.megaplan` the single implementation authority and delete the legacy `arnold.pipelines.megaplan` implementation tree. The current dirty `megaplan-single` edits prove the right concern, but they are premature as an implementation: they remove compatibility exports, registration side effects, and `_pipeline` implementation files before the canonical replacement surface and caller migration are proven. In particular, the attempted `_pipeline` shims point at `arnold_pipelines.megaplan._pipeline`, which does not currently exist.

Recommended direction
Do this as a dedicated follow-up cleanup from the post-`native-python-pipelines-completion-thread2` base, not mixed into the completion epic merge. Keep the planning document `docs/arnold/megaplan-single-implementation-root-fix.md`, but do not land the current dirty root-consolidation implementation as-is.

Sequencing
1. Land the completed `native-python-pipelines-completion-thread2` branch first.
2. Preserve/commit the follow-up planning docs separately.
3. Start this cleanup from that merged base.
4. Build a shrinking allowlist of all remaining `arnold.pipelines.megaplan` import callers and compatibility exports.
5. Move or recreate any required implementation surfaces in `arnold_pipelines.megaplan` before changing legacy imports to shims.
6. Convert legacy modules to narrow temporary shims only where tests prove callers still need them.
7. Delete the legacy tree only after all import, CLI, resume, chain/PR, and package compatibility gates are green.

Acceptance criteria
- `arnold_pipelines.megaplan` is documented and enforced as the single implementation authority.
- No module under `arnold_pipelines/megaplan` imports from `arnold.pipelines.megaplan`.
- Every remaining `arnold.pipelines.megaplan` import is either migrated or covered by a named temporary shim with an owner/removal phase.
- Legacy compatibility exports are either migrated to canonical public surfaces or explicitly removed with tests/docs updated.
- Import side effects such as content-type registration and model-step adapter installation are deterministic regardless of import order during the transition.
- `_pipeline` compatibility is handled deliberately: either moved into canonical form before shimming, or callers are migrated before deletion. No shim points at a missing canonical module.
- `tests/test_pipeline_run_cli.py`, `tests/characterization/test_import_surface.py`, Megaplan resume/import characterization, chain/PR helper tests, and package/wheel smoke tests remain green throughout.
- The final state has no business logic under `arnold/pipelines/megaplan`; ideally no `arnold/pipelines/megaplan` package remains at all.

Non-goals
- Do not use this ticket to reopen the completed native pipeline epic.
- Do not land a big-bang root deletion without compatibility gates.
- Do not keep permanent shims as the final architecture.

Suggested source artifacts
- `docs/arnold/megaplan-single-implementation-root-fix.md`
- `briefs/native-completion-merge-decision-plan.md`
- `briefs/megaplan-functionality-regression-review.md`
- Current dirty-tree review outputs under `/tmp/arnold_cleanup_review/outputs` while available.
