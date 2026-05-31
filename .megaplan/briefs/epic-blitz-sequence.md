# Add the Epic Blitz executable sequence

## Outcome

Add a first-class executable megaplan pipeline sequence named **Epic Blitz**.
Epic Blitz critiques an epic through three ordered critique/revise rounds:

```text
draft epic
  -> high-abstraction five-critic panel
  -> senior revision
  -> mid-abstraction five-critic panel
  -> senior revision
  -> low-abstraction five-critic panel
  -> senior revision / readiness output
```

The sequence must be runnable through the existing pipeline registry and CLI,
not just documented as a manual process.

## Scope

In scope:

- Add a new registered pipeline discoverable as `epic-blitz`, following the
  current Python pipeline module pattern used by
  `megaplan/pipelines/writing_panel_strict.py`.
- The pipeline should accept an epic draft document as its primary input.
- It should run three critique panels, each with five independent critic
  lenses.
- After each panel, it should run a senior reviser step that decides which
  critiques to accept, reject, defer, clarify, or escalate.
- The final step should produce a readiness-oriented revised epic artifact that
  can be used as input to `megaplan chain` planning.
- Add co-located prompts and, if consistent with current pipeline conventions,
  a `SKILL.md` describing when and how to invoke Epic Blitz.
- Add tests that prove the pipeline is registered, has metadata, has the
  expected topology, runs with a deterministic fake worker, writes panel and
  revision artifacts, and appears in the CLI/listing surface.
- Update docs only where needed to explain the new executable sequence.

Out of scope:

- Do not automatically run `megaplan chain`.
- Do not automatically generate final `chain.yaml` unless the existing pipeline
  machinery makes that trivial. A readiness/revised-epic artifact is enough.
- Do not change the normal sprint-plan `critique -> gate -> revise` behavior.
- Do not merge the Epic Blitz checks into the existing sprint critique check
  registry unless the plan proves that is the right abstraction.
- Do not refactor unrelated pipeline runtime code.

## Locked decisions

- This must be an executable code sequence, not a human checklist.
- The product/user-facing name is **Epic Blitz**.
- The CLI-visible pipeline name should be `epic-blitz`, so users can run:

  ```bash
  megaplan run epic-blitz path/to/epic.md
  ```

  or the equivalent `--inputs draft=...` form already supported by
  `megaplan run`.
- Use the current pipeline registry/discovery mechanism where possible:
  `megaplan/pipelines/<name>.py` with `build_pipeline()`, metadata constants,
  and optional co-located prompt/profile/skill resources.
- Prefer existing `Pipeline`, `ParallelStage`, `PanelReviewerStep`,
  `AgentStep`, and builder APIs over inventing new primitives.
- Critics are intentionally adversarial. Reviser steps are intentionally
  judgment-based and must not blindly apply every critique.

## Critic rounds

### High abstraction

Five critics:

- `existing_system_reuse`: does the repo already have concepts, commands,
  schemas, workflows, or artifacts that solve this?
- `conceptual_fit`: does this belong in megaplan's current model, or should an
  existing concept be extended?
- `missing_abstraction`: is there a shared abstraction that would simplify
  multiple milestones or avoid repeated custom logic?
- `epic_decomposition`: are milestones sliced at the right boundaries, with
  real dependencies and sprint-sized deliverables?
- `strategic_risk`: is this solving the right problem, or optimizing around a
  temporary pain or unclear user value?

### Mid abstraction

Five critics:

- `codebase_convention_fit`: does the approach match nearby handlers, prompts,
  schemas, configs, artifacts, and state transitions?
- `data_artifact_model`: are files, state fields, schemas, and artifacts shaped
  correctly and inspectable?
- `orchestration_semantics`: do phase transitions, retries, failures, resume,
  and partial panel failures make sense?
- `agent_model_assignment`: are the right agents/models doing the right jobs?
- `blast_radius`: what commands, modes, profiles, tests, or chains could
  regress?

### Low abstraction

Five critics:

- `implementation_feasibility`: can an implementation agent execute each
  milestone without guessing?
- `testability`: are concrete tests and fixtures specified?
- `edge_cases`: what happens on empty findings, malformed output, failed
  critics, repeated flags, resumed runs, stale versions, and interrupted
  revision?
- `cli_ux_details`: are names, flags, summaries, artifacts, and errors clear?
- `migration_backcompat`: does this preserve existing plan directories,
  critique schemas, robustness behavior, profiles, and chain specs?

## Reviser contract

Each reviser step should receive:

- The current epic artifact.
- The current panel outputs.
- Prior revision summaries when available.
- Prior accepted/rejected/deferred/clarified/escalated decisions when available.

Each reviser step should output:

- A revised epic artifact.
- A concise change summary.
- A decision table over panel findings:
  `accept`, `reject`, `defer`, `clarify`, or `escalate`.
- Any open questions or human decisions.

The final revision/readiness artifact should make it clear whether the epic is
ready to become a `chain.yaml` plus milestone briefs.

## Current code touchpoints

Likely relevant files:

- `megaplan/_pipeline/types.py`
- `megaplan/_pipeline/builder.py`
- `megaplan/_pipeline/patterns.py`
- `megaplan/_pipeline/steps/panel.py`
- `megaplan/_pipeline/steps/agent.py`
- `megaplan/_pipeline/registry.py`
- `megaplan/_pipeline/run_cli.py`
- `megaplan/pipelines/writing_panel_strict.py`
- `megaplan/pipelines/writing-panel-strict/`
- `tests/test_pipeline_registry.py`
- `tests/test_pipeline_run_cli.py`
- `tests/_pipeline/test_registry_python_discovery.py`
- `tests/_pipeline/test_writing_panel_e2e.py`

The deliverable is the executable sequence.

## Done criteria

- `registered_pipelines()` includes `epic-blitz`.
- `megaplan run --list` includes Epic Blitz with a useful description.
- `megaplan run epic-blitz path/to/epic.md --plan-dir <dir>` works with a
  deterministic test worker or test harness.
- The pipeline has exactly three critique panels and three revision/readiness
  stages in the intended order.
- Each panel has the five expected critic IDs.
- Panel outputs feed into the corresponding revision step.
- Later rounds consume the latest revised epic, not only the original draft.
- Tests cover registration, metadata, topology, and an end-to-end fake-worker
  run.
- Existing built-in pipeline registry behavior remains unchanged.
