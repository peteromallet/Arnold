# M5c — Evaluation / execute-core decomposition

**Rubric:** `directed//high`, robustness `full`
**Position in epic:** milestone 9 of 12. Depends on M4 (names) + M5b (cli/chain already split, shared git util exists). Pure behavior-preserving refactor of the two **coupled** god files. (Trimmed by Codex sense-check: the original M5c also held `patterns.py`/`phase_result.py` — those moved to **M5d** as independent fronts; `prep_research.py` is **deferred out of this epic** as its own follow-up.)

## Outcome
Split `orchestration/evaluation.py` and `execute/core.py` along their natural seams with public import paths preserved and zero behavior change. They're done together because `execute/core.py` is the primary consumer of `evaluation.py` — splitting one while leaving the other is structurally incoherent.

## Scope (IN)
- **`orchestration/evaluation.py` (~914 loc)** → split the blob by concern: gate-signal logic, plan-structure validation, plan-delta computation, recurring-critique detection, orchestrator guidance, flag weighting, rubber-stamp detection, execution-evidence validation. Imported by `handlers/{shared,critique,gate,review}.py` and `execute/{core,quality,step_edit,timeout}.py` — preserve those paths. Relocate the ~80 loc of pure git helpers (`_normalize_repo_path`, `_parse_git_status_paths`, `_run_git_status_paths`, `_discover_nested_git_repos`, `_collect_git_status_paths_with_nested_repos`, `:73-151`) into the shared git module M5b created.
- **`execute/core.py` (~1863 loc — the standout gap-hunt finding)** → split at the clear seams: `handle_execute_auto_loop` (`:1198-1863`, ~665 loc) and `handle_execute_one_batch` → `execute/batch.py`; `_build_aggregate_execution_payload` + `_compute_execute_scope_drift` + receipts → `execute/aggregation.py`; `_run_and_merge_batch` (`:577-731`) + `_merge_batch_results` (`:387-504`) → reconcile with the existing `execute/merge.py`.

## Locked decisions
- **Behavior-preserving only** — no logic/signature changes beyond import location. (The `execute/core.py` swallows at `:761`/`:828` are M3b's job; if M3b already ran, do not re-touch them — just relocate their enclosing functions intact.)
- Preserve public import paths via `__init__.py` re-exports; collapse-don't-fork.
- **One commit per file** (evaluation, then core), full-suite + M0 baselines green after each.

## Open questions (for plan to resolve)
- Dependency direction among the `evaluation.py` concern modules (`build_gate_signals` calls `flag_weight`/`compute_plan_delta_percent`/`compute_recurring_critiques`) — order to avoid cycles.
- Does `_run_and_merge_batch`/`_merge_batch_results` belong in the existing `execute/merge.py`, or a new module? (avoid a circular import with `core`)

## Constraints
- Full suite + M0 baselines (import-smoke especially) green; no circular imports.
- `evaluation.py`'s broad importer set (8+ call sites across handlers + execute) must keep resolving.
- **Add behavior tests** for the split surfaces (Codex: M0 is blind to subtle orchestration changes from the eval/core split) — e.g. a focused test that `build_gate_signals` and `handle_execute_auto_loop` produce identical output pre/post-split on a fixture.

## Done criteria
- `evaluation.py` and `execute/core.py` each decomposed; no new module > ~800 loc, single-responsibility.
- All prior public import paths resolve (M0 import-smoke green).
- Zero behavior diff — goldens + the new split-surface behavior tests pass.

## Touchpoints
`megaplan/orchestration/evaluation.py`, `megaplan/execute/{core,merge,quality,timeout,step_edit}.py`, the shared git module from M5b, `tests/` (import paths + new behavior tests).

## Step order
evaluation.py (+ git-helper relocation) → execute/core.py (its consumer). Each a separate commit.

## Anti-scope
- Do NOT change behavior, fix bugs, or alter error handling (M3*) — only move code.
- Do NOT rename concepts (M4) or touch store/cli/chain/workers (M2/M5a/M5b) or the M5d files.
- Do NOT decompose `prep_research.py` — deferred out of this epic.
- **Enforceable guardrail:** `execute/core.py` holds `handle_execute_auto_loop` (dispatch-adjacent). NO edits to `_phase_command`, `drive()` next-step selection, `workflow_next`/`infer_next_steps`, loop dispatch, or chain↔auto coupling — relocate intact only; a reviewer greps these symbols.
