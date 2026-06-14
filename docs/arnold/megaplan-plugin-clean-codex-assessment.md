# Codex Assessment: Megaplan Plugin-Clean Gap

Codex reviewed `docs/arnold/megaplan-plugin-clean-gap.md` against the current `arnold-epic` worktree.

## Verdict

The target architecture is coherent: Arnold should own pipeline mechanics, while Megaplan owns planning policy. The important change is not just renaming `megaplan` to `arnold`; it is making the generic runtime unable to know that the Megaplan/planning workflow exists.

The current repo is roughly **5-7 cleanup milestones away** from that target. It is a mid-strangler state: pipeline discovery and graph primitives exist, but the `planning` pipeline is still mostly a wrapper over platform-side planning code.

## Suggested Changes To The Target Doc

- Treat `auto`, `override`, resume, and control bindings as first-class plugin extension points. These are among the hardest current couplings.
- Rename the plugin directly to `megaplan`, not `planning`. Keeping `planning` as the plugin identity preserves the historical leakage the cleanup is meant to delete.

## Current Strengths

- Pipeline discovery exists in `megaplan/_pipeline/registry.py`.
- Generic-ish graph types exist in `megaplan/_pipeline/types.py`.
- Reusable composition exists in:
  - `megaplan/_pipeline/builder.py`
  - `megaplan/_pipeline/steps/agent.py`
  - `megaplan/_pipeline/steps/panel.py`
  - `megaplan/_pipeline/steps/human_gate.py`

## Current Non-Clean Surfaces

- `megaplan/pipelines/planning/__init__.py` and `megaplan/pipelines/planning/steps.py` are mostly wrappers over implementation elsewhere.
- Planning stages still live under `megaplan/_pipeline/stages/`.
- The package namespace is still `megaplan`, not `arnold`.
- Compatibility and legacy compiler paths remain, especially `megaplan/_pipeline/planning.py`.

## Hidden Blockers

- `Pipeline.run_phase()` in `megaplan/_pipeline/types.py` is not generic. It runs one planning phase, imports `_core`, handles `feedback`, parses planning CLI args, and injects `inputs={"_pipeline": "planning"}`.
- `megaplan/auto.py` is hardwired to planning.
- `megaplan/cli/arnold.py` special-cases planning.
- `megaplan/_core/workflow.py` defaults missing pipeline identity to `"planning"`.
- `megaplan/control_interface.py` still supports only `"planning"` string dispatch for legacy binding.
- Prompt ownership is global:
  - `megaplan/prompts/planning.py`
  - `megaplan/prompts/critique.py`
  - `megaplan/prompts/gate.py`
  - `megaplan/prompts/finalize.py`
  - `megaplan/prompts/execute.py`
  - `megaplan/prompts/review.py`
- Tests assert `planning` as the built-in production pipeline, including `tests/test_pipeline_run_cli.py`.

## Actually Reusable Today

- `Pipeline`, `Stage`, `ParallelStage`, `Edge`, `StepContext`, and `StepResult` in `megaplan/_pipeline/types.py`.
- Registry/discovery in `megaplan/_pipeline/registry.py`, after package/name roots are changed.
- Executor loop in `megaplan/_pipeline/executor.py`, after removing `_core.state`, `CliError`, activation, and planning-adjacent state assumptions.
- `AgentStep`, `PanelReviewerStep`, and `HumanDecisionStep`.
- Builder methods such as `.agent()`, `.panel()`, `.human_gate()`, and `.subpipeline()`.

## Megaplan Policy Pretending To Be Generic

- `GateRecommendation = Literal["proceed", "iterate", "tiebreaker", "escalate"]` in `megaplan/_pipeline/types.py`.
- `PipelineBuilder.gate()` hardcodes the four planning outcomes.
- `PipelineBuilder.tiebreaker()` and `TiebreakerStep`.
- `megaplan/_pipeline/planning_bindings.py`.
- `megaplan/_pipeline/stages/inprocess_step.py`, which adapts legacy `handle_<phase>` planning handlers.
- `critique_revise_gate_loop` and related helpers when they assume planning verdicts.

## Milestone Estimate

1. Establish `arnold/` package and move neutral runtime.
2. Rename discovered `planning` pipeline to `megaplan`.
3. Move planning stages, prompts, and control into the plugin.
4. Delete planning compatibility shims and literals from runtime.
5. Make `auto`, `override`, resume, and status dispatch through plugin capabilities.
6. Split generic runtime tests from Megaplan policy tests.
7. Add final boundary gates: no generic `arnold/pipeline/**` imports or string literals for Megaplan policy.

## Recommended First Milestone

Start with **removing privileged planning dispatch without moving everything yet**.

Acceptance criteria:

- `auto`, resume, status/control, and Arnold CLI resolve a pipeline capability, not the hardcoded string `"planning"`.
- `Pipeline.run_phase()` leaves `megaplan/_pipeline/types.py` and becomes a plugin-owned adapter under the current planning plugin during transition, then under `pipelines/megaplan`.
- Add a boundary test banning `"planning"` from generic runtime modules except registry aliases and historical docs.
- Keep behavior intact while making the specialness explicit at the plugin boundary. Once that seam exists, moving stages, prompts, and control into the plugin becomes mechanical instead of invasive.
