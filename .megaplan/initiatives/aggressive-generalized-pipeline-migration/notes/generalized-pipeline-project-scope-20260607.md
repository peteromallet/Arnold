# Generalized Pipeline Project Scope

Date: 2026-06-07

## Purpose

This project turns Megaplan from a mostly bespoke planning harness into one pipeline package built on a reusable Arnold pipeline substrate.

The target world is:

- simple Python scripts can compose reusable steps
- Megaplan's existing plan / critique / revise / gate / execute / review phases are exposed as reusable step contracts
- Megaplan itself is implemented as a pipeline over those contracts
- chain and epic orchestration remain a higher-level policy layer, not the base runtime
- evidence, receipts, state, artifacts, model capture, and runner behavior are reusable by other pipelines

This project should not take precedence over the active Evidence-First Pipeline Semantics epic. It should build on that work once the evidence and engine-isolation foundations are trustworthy.

## Current Shape

Today Megaplan already contains most of the machinery:

- phase handlers for `plan`, `critique`, `revise`, `gate`, `finalize`, `execute`, `review`
- worker dispatch through Codex, Shannon, Hermes, and model routing profiles
- schemas and capture validation in `model_seam.py`
- plan state and artifacts under `.megaplan/plans/<plan>`
- receipts, event logs, cost records, active-step heartbeat, and status rendering
- auto-driver logic in `auto.py`
- chain / epic orchestration in `chain/`
- partial Python pipeline infrastructure under `_pipeline/`

The problem is that step behavior is still spread across multiple places:

- worker schema maps in `workers/_impl.py`
- capture schema maps and normalizers in `model_seam.py`
- JSON schemas in `schemas/runtime.py`
- schema projections in `schema_seeds.py`
- state transitions in `_core/workflow.py` and `_core/topology.py`
- orchestration policy in `auto.py` and `chain/`

The project is mostly extraction and stabilization, not invention.

## Project Scope

### In Scope

1. Define a reusable `StepContract` registry.
2. Expose a small synchronous runner API for existing Megaplan steps.
3. Extract generic runtime pieces into neutral `arnold.pipeline` modules.
4. Keep Megaplan's domain policy in Megaplan, not in the generic runtime.
5. Make Megaplan's own pipeline read as composition over generic primitives.
6. Keep chain / epic behavior as a policy layer above pipelines.
7. Prove the abstraction with at least one non-Megaplan pipeline.
8. Add characterization tests so the extraction cannot silently alter current Megaplan behavior.

### Out of Scope

- Building a YAML DSL first.
- Rewriting all of Megaplan in one pass.
- Changing `ContractResult` or the active model-seam capture behavior during the Evidence-First epic.
- Removing compatibility paths before replay/dual-run tests are green.
- Moving Git/PR/merge policy into the generic runner.
- Moving Megaplan-specific gate recommendations into `arnold.pipeline`.

## Likely Milestones

### M0: Characterize Current Behavior

Outcome: freeze the current observable behavior before extraction.

Deliverables:

- workflow transition matrix fixture
- recovery-map characterization tests
- trace replay fixtures for happy path, iterate, blocked, retry, escalate
- import-surface grep gates proving generic modules do not depend on Megaplan

Done when: the current Megaplan runner can be refactored behind these tests without behavior drift.

### M1: Step Contract Registry

Outcome: make step metadata one source of truth.

Deliverables:

- `arnold/pipelines/megaplan/step_contracts.py`
- `StepContract` dataclass
- registry entries for `prep`, `plan`, `critique`, `critique_evaluator`, `revise`, `gate`, `finalize`, `execute`, `review`, and loop steps
- derived schema/capture/normalizer views
- consistency tests proving old dicts and new registry match

Done when: new steps no longer require manual edits across four unrelated registries.

### M2: Synchronous Runner API

Outcome: simple Python scripts can run existing Megaplan steps.

Deliverables:

- `arnold/pipelines/megaplan/runner.py`
- `StepOutcome`
- `next_steps(plan, root=...)`
- `run_step(plan, step, root=...)`
- `run_pipeline(plan, steps, root=...)`
- tests for plan -> critique -> gate and critique -> revise -> critique loops

Done when: a Python script can compose existing Megaplan phases without invoking the full auto-driver.

### M3: Generic Runtime Extraction

Outcome: non-Megaplan pipelines can reuse state, artifact, event, and receipt infrastructure.

Deliverables under `arnold/pipeline/_runtime/`:

- `atomic_io.py`
- `event_log.py`
- `state_cache.py`
- `locking.py`
- `artifact_repo.py`
- `receipt.py`
- `budget.py`
- `sandbox.py`
- re-export shims from old Megaplan paths

Done when: Megaplan still imports through compatibility shims, while a new pipeline can import the generic runtime directly.

### M4: Pipeline Package Surface

Outcome: Python-first pipeline packages become the normal user surface.

Deliverables:

- stable `Pipeline.builder(...)` API in the neutral namespace
- documented pipeline package layout
- examples with co-located prompts, profiles, `SKILL.md`, and `build_pipeline()`
- trust/discovery behavior that does not execute untrusted code during discovery

Done when: a pipeline script can be discovered and run without Megaplan-specific wiring.

### M5: Megaplan as a Pipeline Binding

Outcome: Megaplan's planning loop is implemented as a pipeline binding over reusable primitives.

Deliverables:

- Megaplan package manifest
- `build_pipeline()` for the Megaplan planning flow
- binding of Megaplan-specific gate recommendations, artifact classifiers, and receipt builders
- dual-run oracle comparing legacy path and pipeline path

Done when: old and new Megaplan planning paths replay the same traces with matching artifacts and state transitions.

### M6: Chain/Epic Layer Separation

Outcome: chain orchestration becomes policy over a generic pipeline/node runner.

Deliverables:

- `supervisor/pipeline_runner.py`
- chain-specific adapter for milestone specs, Git/PR lifecycle, completion contract, and ladder tickets
- generic cursor/checkpoint/outcome loop
- no chain-specific Git/PR code in the generic runner

Done when: chain runs through the generic node runner while preserving existing chain behavior.

### M7: Non-Megaplan Proof

Outcome: prove the abstraction is real.

Deliverables:

- one non-Megaplan pipeline using the same runtime, runner, and contracts
- zero imports from `arnold.pipelines.megaplan` in that pipeline
- declared ports or schemas for all inter-step data
- replayable artifacts and receipts

Done when: the same primitives support a different pipeline without Megaplan vocabulary leaking in.

## What Stays Inside Megaplan

In the target world, Megaplan still owns:

- the planning workflow semantics
- the names `plan`, `critique`, `revise`, `gate`, `finalize`, `execute`, `review`
- gate recommendations like `PROCEED`, `ITERATE`, `ESCALATE`
- Megaplan artifact naming conventions
- `plan_vN.md`, `critique_vN.json`, `gate.json`, `finalize.json`, execution batches
- profile / robustness / depth policy
- phase-model routing defaults
- human override semantics
- review/rework policy
- chain milestone specs
- Git/PR/merge policy
- completion contract policy
- Evidence-First authority/provenance policy

Megaplan becomes a consumer and provider of reusable steps, not the owner of the base runtime.

## What Moves To Generic Arnold Pipeline Runtime

The generic runtime should own:

- run state cache mechanics
- event journal mechanics
- artifact identity and hash tracking
- receipt base shape
- lock/lease primitives
- model/runtime budget accounting
- key pool and provider resolution substrate
- sandbox context and protected-root mechanics
- worker dispatch protocol
- pipeline graph and edge representation
- generic runner loop for ordered nodes

The generic runtime should not know about `GateRecommendation`, `STATE_CRITIQUED`, Megaplan profiles, PR merges, or `.megaplan/briefs` conventions.

## What The Core Megaplan Runner Could Look Like

The first practical API can be intentionally small.

```python
# arnold/pipelines/megaplan/runner.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StepOutcome:
    plan: str
    step: str
    exit_code: int
    previous_state: str
    current_state: str
    output_path: Path | None
    phase_result: dict[str, Any] | None
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def next_steps(plan: str, *, root: Path | None = None) -> list[str]:
    """Load state for `plan` and return currently valid step names."""
    ...


def run_step(
    plan: str,
    step: str,
    *,
    root: Path | None = None,
    profile: str | None = None,
    phase_model: list[str] | None = None,
    extra_args: dict[str, Any] | None = None,
) -> StepOutcome:
    """Validate and run one existing Megaplan step in-process."""
    ...


def run_pipeline(
    plan: str,
    steps: list[str],
    *,
    root: Path | None = None,
    stop_on_error: bool = True,
) -> list[StepOutcome]:
    """Run a caller-provided sequence of valid steps."""
    outcomes: list[StepOutcome] = []
    for step in steps:
        if step not in next_steps(plan, root=root):
            raise ValueError(f"{step!r} is not valid for current plan state")
        outcome = run_step(plan, step, root=root)
        outcomes.append(outcome)
        if stop_on_error and not outcome.ok:
            break
    return outcomes
```

Example simple script:

```python
from pathlib import Path
from arnold.pipelines.megaplan.runner import next_steps, run_step

ROOT = Path.cwd()
PLAN = "my-plan-20260607"

max_iterations = 5

for _ in range(max_iterations):
    if "plan" in next_steps(PLAN, root=ROOT):
        run_step(PLAN, "plan", root=ROOT)

    if "critique" in next_steps(PLAN, root=ROOT):
        run_step(PLAN, "critique", root=ROOT)

    if "gate" in next_steps(PLAN, root=ROOT):
        gate = run_step(PLAN, "gate", root=ROOT)
        if gate.current_state == "gated":
            break

    if "revise" in next_steps(PLAN, root=ROOT):
        run_step(PLAN, "revise", root=ROOT)
```

That script does not implement worker routing, schema validation, model capture, event logs, receipts, or artifact hashing. It only composes existing steps.

## What The Megaplan Pipeline Binding Could Look Like

After the runner API exists, Megaplan's own package can expose a pipeline definition:

```python
# arnold/pipelines/megaplan/planning_pipeline.py

from arnold.pipeline import Pipeline
from arnold.pipelines.megaplan.steps import (
    plan_step,
    critique_step,
    revise_step,
    gate_step,
    finalize_step,
    execute_step,
    review_step,
)


def build_pipeline() -> Pipeline:
    return (
        Pipeline.builder("megaplan")
        .step(plan_step())
        .step(critique_step())
        .step(gate_step())
        .edge("plan", "critique")
        .edge("critique", "gate")
        .edge("gate", "finalize", when="proceed")
        .edge("gate", "revise", when="iterate")
        .edge("revise", "critique")
        .edge("finalize", "execute")
        .edge("execute", "review")
        .build()
    )
```

This is where Megaplan's domain semantics live. The generic runtime just executes graph nodes and records evidence.

## Project Risks

- Extracting before Evidence-First lands could preserve unsafe state semantics in a nicer API.
- Moving `model_seam.py` too early could break active Step-IO / Evidence-First behavior.
- A YAML-first push would create a second unstable surface.
- Generic runtime extraction could create import cycles because current `_core` modules are imported early.
- If the non-Megaplan proof is skipped, Megaplan-specific vocabulary will leak into the generic layer.

## Recommended Priority

1. Continue and finish Evidence-First Pipeline Semantics.
2. Keep this project as the follow-on generalization epic.
3. File or link tickets from the existing reliability/generalization notes into that future epic.
4. Start with characterization tests and a read-only `StepContract` mirror.
5. Only then expose `run_step` / `run_pipeline`.

The abstraction should be earned by making current behavior explicit, tested, and replayable before moving it.

