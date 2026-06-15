# Sprint 4 Chunk B — Real handler ports

The full Sprint-4 plan is at `.megaplan/briefs/sprint-4-elegance.md`. Chunk B
follows Chunk A (typed edges).

## Problem

Today `megaplan/_pipeline/stages/handler_step.py::HandlerStep` shells
out via subprocess to `megaplan <phase>`. The `InProcessHandlerStep`
variant wraps `handle_<phase>(root, args)` but still threads through
the legacy argparse Namespace and the StepResponse dict.

## What ships in Chunk B

1. Eight new files under `megaplan/_pipeline/stages/`:
   - `prep.py`, `plan.py`, `critique.py`, `gate.py`, `revise.py`,
     `finalize.py`, `execute.py`, `review.py`.
   Each file exports a single Step class (e.g. `PrepStep`,
   `CritiqueStep`) whose `run` method:
   - Reads typed inputs from `ctx.inputs` (Mapping[str, Path]).
   - Resolves a model spec via `ctx.profile.model_for(self.slot)`.
   - Resolves a prompt via `resolve_prompt(ctx, self.prompt_key)`.
   - Dispatches the worker (the existing
     `megaplan.workers.run_step_with_worker` is the right primitive).
   - Returns a typed `StepResult` directly. No StepResponse dict,
     no argparse Namespace, no subprocess.

2. Each new Step file is hermetic — no top-level imports from
   `megaplan.handlers.*`. The Step is the new primitive; the legacy
   handler is what we're replacing.

3. The legacy `handle_<phase>` CLI entrypoints in
   `megaplan/handlers/*.py` become thin shims that build a
   single-stage Pipeline (with the new Step class as the only stage)
   and run it via the executor. Existing CLI surface is preserved
   exactly — same flags, same JSON output shape.

4. Update `megaplan/_pipeline/planning.py::build_planning_steps` to
   use the new Step classes instead of the subprocess HandlerStep.

5. Update `megaplan/_pipeline/stages/inprocess_step.py` — it can be
   simplified or deleted entirely since the new Steps replace it.
   If deleted, `tests/test_pipeline_planning_e2e.py` and
   `tests/test_pipeline_resume.py` and `tests/test_pipeline_parity.py`
   are updated to import from the new modules.

## Out of scope for Chunk B

- Modifying `auto.py` (Chunk C).
- Subloop / override executor branches (Chunk D).
- Deleting WORKFLOW (Chunk E).

## Constraints

- The full existing test suite must still pass — particularly
  `tests/test_init_plan.py::test_workflow_mock_end_to_end` and
  `tests/test_legacy_phase_cli_compat.py`. These exercise the
  handler CLI surface.
- Live `megaplan` must keep working — verify after every commit.
- All commits on `decomp/main`.

## Acceptance

- New `tests/test_handler_ports.py` exercises each of the 8 new Step
  classes in isolation under `MEGAPLAN_MOCK_WORKERS=1`. Each test:
  - Constructs the Step.
  - Calls `step.run(ctx)` with a hermetic StepContext.
  - Asserts the StepResult outputs land at the expected paths.
- `tests/test_legacy_phase_cli_compat.py` still passes (CLI surface
  unchanged via the inverted shim).
- `tests/test_pipeline_planning_e2e.py` still produces the same
  artifacts — now via the new ported Steps, not via
  InProcessHandlerStep.
- `tests/test_pipeline_parity.py` still proves byte-identical
  artifacts between direct-handler runs and Pipeline runs.
- Full `pytest tests/` stays green.
- `git grep -nw HandlerStep megaplan/_pipeline/stages/handler_step.py` shows the subprocess shim is gone from production paths (or
  retained only as an optional remote-execution primitive with a
  clear comment).

## Operating principles

Same as Chunk A.
