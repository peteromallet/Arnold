# M3: Human Interaction — Decision Record

**Decision**: DEFER — do not implement a neutral human-interaction step at this time.

**Date**: 2026-06-13

## Rationale

Two consumers exist but diverge on suspend/resume mechanics:

| Consumer | Step | Suspension Mechanism | Resume Payload Key |
|----------|------|---------------------|-------------------|
| `evidence_pack` | `HumanReviewStep` (`steps.py:496`) | Returns `ContractResult(SUSPENDED)` with `next="suspended"` — routed via edge-resolution failure (no edge named `"suspended"`) | `ctx.inputs["human_input"]` |
| `megaplan` | `HumanDecisionStep` (`human_gate.py`) | Writes `awaiting_user.json` to `plan_dir`, returns `next="halt"` with `state_patch` (`_pipeline_paused=True`) | Reads `awaiting_user.json` from `plan_dir` |

The shared envelope primitives — `Suspension` (`types.py:583`) and `ContractResult(status=SUSPENDED)` (`types.py:697`) — are already neutral and adequate. The divergence is in *how* consumers trigger and resolve suspension, not in the data shape.

### Both Suspension Mechanisms

1. **Edge-routing failure** (`executor.py:239-266`): `resolve_edge()` fails to find a matching edge for the step's `next` label. For simple stages (no `decision_vocabulary`/`override_vocabulary`), the executor breaks gracefully. This is how `evidence_pack` suspends — `HumanReviewStep` returns `next="suspended"` and no edge matches.

2. **Hooks-override** (`executor.py:211`): The executor calls `resolved_hooks.should_suspend(stage, state, result)`. The default `NullExecutorHooks.should_suspend` (`hooks.py:320-326`) returns `(False, None)`. `EvidencePackHooks` does **not** override `should_suspend` — its suspension is purely edge-routing-driven. A package *could* override this to implement custom suspension logic.

### Resume Cursor

The neutral suspend/resume contract uses `RESUME_CURSOR_FILENAME = "resume_cursor.json"` (`resume.py:17`). `EvidencePackHooks.on_step_end` (`hooks.py:76-84`) persists the cursor when a `ContractResult` has `status == SUSPENDED`.

## Objective Revisit Trigger

Revisit when **both** conditions are met:
1. Megaplan migrates off `human_gate.py`'s `awaiting_user.json` / `plan_dir` pattern to the current `Suspension` + `ContractResult(SUSPENDED)` + `resume_cursor.json` shape; **AND**
2. A third pipeline package needs the same human-interaction semantics, proving the abstraction is genuinely shared rather than premature.

Until then, the `Suspension` dataclass and `ContractResult` remain the neutral shared envelope — each package wires its own step implementation.

## Anchors

| Anchor | File:Line | What |
|--------|-----------|------|
| `Suspension` | `arnold/pipeline/types.py:583` | Frozen dataclass: `kind`, `awaitable`, `prompt`, `display_refs`, `resume_input_schema`, `resume_cursor`, `thread_ref`, `actor`, `deadline`, `on_timeout`, `default_action` |
| `ContractResult` | `arnold/pipeline/types.py:697` | Frozen dataclass: `status` (ContractStatus enum), `payload`, `suspension`, `evidence_refs`, etc. |
| `RESUME_CURSOR_FILENAME` | `arnold/pipeline/resume.py:17` | `"resume_cursor.json"` — the neutral cursor filename |
| Suspension delegation | `arnold/pipeline/executor.py:211` | `suspend, halt_reason = resolved_hooks.should_suspend(stage, state, result)` |
| Default no-op | `arnold/pipeline/hooks.py:320-326` | `NullExecutorHooks.should_suspend` returns `(False, None)` |
| `HumanReviewStep` (evidence_pack) | `arnold/pipelines/evidence_pack/steps.py:496` | Reads `ctx.inputs["human_input"]`; returns SUSPENDED/COMPLETED/FAILED |
| `HumanDecisionStep` (megaplan) | `arnold/pipelines/megaplan/_pipeline/steps/human_gate.py` | Writes/reads `awaiting_user.json`; returns `next="halt"` |
| Edge-routing fallback | `arnold/pipeline/executor.py:239-266` | Route-resolution failure gracefully halts for simple stages |

## Consumers Acknowledged

1. **evidence_pack** — `HumanReviewStep` at `steps.py:496`: full `Suspension` + `ContractResult(SUSPENDED)` consumer; resume via `ctx.inputs["human_input"]`.
2. **megaplan** — `HumanDecisionStep` at `human_gate.py`: pre-Suspension consumer using file-based `awaiting_user.json`; `state_patch` with `_pipeline_paused=True`.

## Design Decision: Reuse evidence_pack.HumanReviewStep

Package-local steps (in `_deliberation_example`) should reuse `evidence_pack.HumanReviewStep` rather than reimplementing suspension logic. This step:
- Already returns the correct `ContractResult(SUSPENDED)` shape
- Reads resume payload from `ctx.inputs["human_input"]`
- Writes checkpoint artifacts via `_artifact_path(ctx, ...)`
- Proves the existing step is genuinely reusable across packages, strengthening the deferral rationale
