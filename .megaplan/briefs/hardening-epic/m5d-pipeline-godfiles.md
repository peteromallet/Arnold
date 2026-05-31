# M5d — Pipeline god-file decomposition

**Rubric:** `directed//high`, robustness `full`
**Position in epic:** milestone 10 of 12. **New milestone** (Codex A split M5c — these are independent cleanup fronts, not coupled to evaluation/core). Depends on M4 (names). Pure behavior-preserving refactor.

## Outcome
Split the two remaining independent god files along their natural seams, public import paths preserved, zero behavior change.

## Scope (IN)
- **`_pipeline/patterns.py` (~870 loc)** → god file with 5+ separable concerns: static topology patterns (critique loop, alternating turns), dynamic subloop primitives (`panel_from_artifact`, `dynamic_fanout`, `iterate_until_consensus`, `paired_round`), join functions (`majority_vote`, `weighted_vote`), overlay builders (`mode_prompts`), internal helpers (`_specialize_step`, `_read_specs_from_path`). Split by concern.
- **`orchestration/phase_result.py` (~720 loc)** → the regex-based provider-error classification (`:220-352`, ~130 loc) is independent of the `PhaseResult` data-model + atomic-I/O + context-manager guard. Split the classifier out (`phase_result_classify.py` or similar), leaving the model + I/O.

## Locked decisions
- **Behavior-preserving only** — no logic/signature changes beyond import location.
- Preserve public import paths via `__init__.py` re-exports; collapse-don't-fork.
- **One commit per file**, full-suite + M0 baselines green after each.

## Open questions (for plan to resolve)
- For `patterns.py`: which concern modules need to import which? Order to avoid cycles (the dynamic primitives may reference the join functions).
- For `phase_result.py`: do any external callers import the regex classifier directly, or only via `PhaseResult`? (preserve whatever they import)

## Constraints
- Full suite + M0 baselines (import-smoke) green; no circular imports.

## Done criteria
- `patterns.py` and `phase_result.py` each decomposed; no new module > ~800 loc, single-responsibility.
- All prior public import paths resolve (M0 import-smoke green).
- Zero behavior diff — goldens + suite pass unchanged.

## Touchpoints
`megaplan/_pipeline/patterns.py`, `megaplan/orchestration/phase_result.py`, `tests/` (import paths only).

## Step order
patterns.py → phase_result.py. Each a separate commit.

## Anti-scope
- Do NOT change behavior, fix bugs, or alter error handling (M3*) — only move code.
- Do NOT rename concepts (M4) or touch the M5a/M5b/M5c files.
- Do NOT decompose `prep_research.py` — deferred out of this epic.
- **Enforceable guardrail:** NO edits to next-step resolution / engine dispatch symbols (`_phase_command`, `drive()` selection, `workflow_next`/`infer_next_steps`, loop dispatch) — these files shouldn't touch them anyway; confirm by grep.
