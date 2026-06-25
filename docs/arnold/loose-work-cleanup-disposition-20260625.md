# Loose Work Cleanup Disposition - 2026-06-25

This records the cleanup decision for the dirty `native-python-working-tree`
state that existed before `native-python-pipelines-completion-thread2` was
merged to `main`.

The source checkpoint was commit `3c7f9b0b`:
`checkpoint: loose work before cleanup migration`.

## Final Decision

Land the completed native-python completion epic and the safe follow-up
planning/runtime fixes. Reject the half-applied `megaplan-single` root
consolidation implementation. Preserve the single-root direction as an explicit
future ticket, not as dirty branch code.

Current local `main` now contains:

- completed `native-python-pipelines-completion-thread2`;
- follow-up composition and platform epic briefs;
- a ticket for proper single-root Megaplan consolidation;
- selected small Megaplan/Hermes/tool hardening fixes.

## Landed

| Area | Decision | Reason |
| --- | --- | --- |
| `native-python-pipelines-completion-thread2` | Landed to `main` | Completed M1-M7 native completion epic. This was the canonical completed branch. |
| Follow-up composition epic briefs | Landed | Required next direction; includes Megaplan compositional migration first. |
| Follow-up platform epic briefs | Landed | Required platform/security/durability follow-up after composition. |
| End-state validation review | Landed | Captures Codex/DeepSeek validation and acceptance-criteria changes. |
| Megaplan regression review | Landed | Captures compatibility risks around CLI, hooks, resume files, import surfaces, chain/PR behavior. |
| Merge decision plan | Landed | Records why `thread2` was merged and `megaplan-single` was not. |
| Completion M6/M7 criteria tightening | Landed | Keeps the current epic docs aligned with the reviewed compatibility gates. |
| Single-root direction doc | Landed | Keeps the architectural diagnosis and phased plan without landing unsafe code. |
| Single-root Megaplan ticket `01KVZZ45DAZW9P5H4JA66JWNY3` | Landed | Tracks the proper future cleanup with gates and non-goals. |
| `arnold_pipelines/megaplan/workers/hermes.py` tool-arg validation and severity normalization | Landed | Small, self-contained hardening with tests; avoids malformed content tool calls and common severity enum drift. |
| Prompt exact-path instructions and `tests/prompts/test_template_read_instruction.py` | Landed | Pairs with tool-call validation so models do not emit empty `read_file` calls. |
| `arnold/agent/tools/file_tools.py` empty-path guard | Landed | Defensive, scoped, and covered by targeted tests. |
| `arnold_pipelines/megaplan/handlers/critique.py` raw evaluator recovery | Landed | Recovers valid Codex JSON verdicts when structured-output payload is empty. |
| `arnold_pipelines/megaplan/orchestration/authority_readers.py` terminal-status evidence gating | Landed | Prevents speculative pending-task evidence from counting as completed work. |
| `arnold_pipelines/megaplan/execute/batch.py` skipped-with-note scheduling fix | Landed | Prevents intentionally skipped baseline-unavailable checkpoints from blocking dependents. |
| `arnold_pipelines/megaplan/observability/events.py` missing-envelope debug log | Landed | Avoids spurious warning stderr being interpreted as phase failure. |

## Rejected / Deleted From The Migration

| Area | Decision | Reason |
| --- | --- | --- |
| Dirty `arnold/pipelines/megaplan/__init__.py` forwarding shim | Rejected | Removed broad lazy exports and import side effects before callers were migrated. Would break existing imports and make behavior import-order dependent. |
| Dirty `arnold/pipelines/megaplan/_pipeline/{__init__,registry,types}.py` shims | Rejected | Pointed at `arnold_pipelines.megaplan._pipeline`, which does not exist. This would make `_pipeline.registry` and `_pipeline.types` imports fail immediately. |
| Dirty `arnold_pipelines/megaplan/__init__.py` side-effect move | Rejected | Moved registration/model-adapter side effects without proving deterministic behavior for legacy import callers. This belongs in the single-root ticket. |
| Dirty `tests/arnold_pipelines/megaplan/test_package.py` migration-state changes | Rejected | Encoded a not-yet-real future state and would mask the broken `_pipeline` shim problem. |
| Dirty `tests/runtime/test_megaplan_import_path_parity.py` | Rejected for now | Valuable idea, wrong time. It tests a transitional single-root state that is not implemented safely yet. Fold into the single-root ticket. |
| Dirty `arnold_pipelines/megaplan/runtime/process.py` VCS-root walk | Rejected | Competes with the completed epic's engine-root behavior. Not needed for the landed path. |
| Dirty `arnold_pipelines/megaplan/chain/{hinge_gate,m3_dual_green,m5_eval_gates}.py` root changes | Rejected | Depended on the rejected `runtime/process.py` root change. |
| Dirty `arnold/agent/tools/terminal_tool.py` loader | Rejected | Contained a hardcoded absolute path into this local checkout. Not acceptable to land. |
| Dirty `arnold/pipelines/megaplan/workers/turn_cap.py`, `arnold_pipelines/megaplan/workers/turn_cap.py`, and `tests/test_workers_turn_cap.py` | Rejected from this migration | The completed epic removed the host-wide local turn cap. Reintroducing it conflicts with the current Shannon/channel posture. Future admission control needs a separate design if required. |
| Dirty Shannon docs changing "no local throttle" back toward an opt-in host cap | Rejected | Conflicted with the completed epic's decision to avoid local admission throttles and rely on provider/API signals. |
| Dirty `sync-skills.sh` Kimi/agents changes | Rejected | Unrelated to the native completion merge and root cleanup. Needs a separate skill-sync decision if still desired. |
| `_codex_skills/*/SKILL.md` symlink/type changes | Rejected | Local symlink contamination. The repo should keep regular checked-in skill files. |
| `briefs/native-python-pipelines-completion/.megaplan/plans/.chains/chain-ebce1153efc0.json` | Deleted | Runtime chain state, not source. The completed branch history and docs are the durable record. |
| `native-python-pipelines-completion-goal.md` | Deleted | One-off execution prompt duplicated by `chain.yaml` and `NORTHSTAR.md`. |

## Branch And Worktree Decisions

| Item | Decision | Reason |
| --- | --- | --- |
| `native-python-pipelines-completion-thread2` branch | Merged, then deleted | Its commits are now on `main`. |
| `native-python-pipelines-completion` branch | Deleted | Strict ancestor of `thread2`; no unique work remained. |
| `megaplan-single-impl-fix` branch | Deleted | Same commit as the old working-tree tip; the valuable direction was moved to docs/ticket, unsafe implementation rejected. |
| `editable-install` branch | Deleted | Already merged into the lineage; no unique patches remained. |
| `reigh-pristine-sdk-boundary` branch in this Arnold repo | Deleted | Same commit as old `main`; no unique Arnold work. |
| `native-python-working-tree` branch | Merged to `main`, then deleted | Its work is now on local `main`. |
| `/Users/peteromalley/Documents/.megaplan-worktrees/native-python-pipelines-completion-thread2` | Temporary keep until live process exits | A separate active Reigh megaplan process still has this path as its engine checkout. It is detached at `b3156f20`; remove it after that process exits. This is not preserved product work. |
| `/Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run` | Preserve outside Arnold cleanup | Different repository (`banodoco/reigh-app`) with active dirty SDK work and a live megaplan process. Do not delete from Arnold cleanup. |
| `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` | Not resolved by Arnold merge; must be separately dispositioned | Different root commit despite Arnold remote name. Contains old TypeScript bot-era dirty work. It should be reviewed as a separate repo snapshot, not silently deleted as part of this Python Arnold cleanup. |

## Why The Root Consolidation Was Not Landed

The single-root goal is correct: `arnold_pipelines.megaplan` should become the
single implementation authority and `arnold.pipelines.megaplan` should stop
carrying business logic. The dirty implementation was rejected because it tried
to cut over before the canonical replacement surface and caller migration
existed.

Load-bearing breakages in the rejected patch:

- `_pipeline` shims forwarded to a missing `arnold_pipelines.megaplan._pipeline`;
- broad lazy exports disappeared from the legacy package without replacement;
- content-type registration and model-step adapter installation became
  import-order dependent;
- tests were changed to accept a future migration state while real callers
  would still fail.

The proper path is captured in ticket
`01KVZZ45DAZW9P5H4JA66JWNY3`: build a shrink-only allowlist, migrate callers
and compatibility exports deliberately, prove import/CLI/resume/chain/PR/wheel
gates, and then delete the legacy tree.
