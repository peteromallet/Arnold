# M5a: Move Megaplan Prompts, State, Profiles, Schemas, And Control

## Outcome

Move Megaplan prompt builders, planning state, schemas, profile policy, and control/status projection into the Megaplan plugin.

## Scope

In:
- Move prompt builders/files into plugin-local `prompts/`, preserving dynamic prompt code where needed.
- Move planning state constants and gate payload schemas into plugin-local `state.py` and `schemas.py`.
- Move `DEFAULT_AGENT_ROUTING`, `ROBUSTNESS_LEVELS`, depth/tier/prep semantics, and profile phase validation into plugin-local profile policy.
- Move Megaplan control binding/status projection into plugin-local `control.py`.
- Keep generic profile validation parameterized by target pipeline declared stage keys.
- Support dotted profile keys by validating the declared stage prefix generically; sub-slot meaning belongs to the plugin or step.
- Specify composed-pipeline profile scoping: parent default, named child profile, or nested profile map validated against the child's declared keys. Implementation may defer where no child overrides exist.

Out:
- Do not move execute/review/orchestration policy internals here; that is M5b.
- Do not rename package or CLI.
- Do not preserve old import paths through shims.

## Locked Decisions

- Megaplan owns robustness levels, depth/tier policy, critique lens selection, gate/tiebreaker semantics, profile metadata, and status/control projection.
- Arnold owns generic profile loading/inheritance/agent-spec validation and passes unknown metadata to plugin validation.
- Prompt API remains `str | Callable[[StepContext], str]`; no static-only prompt model.

## Required Outputs

- Choose one canonical source of truth for Megaplan profile defaults. If both Python constants and TOML exist, document which is authoritative and which is overlay/serialization.
- Retire `register_prompt()` as canonical API. It may remain only as an internal migration bridge; new prompt resolution is bundle-scoped.

## Constraints

- Do not flatten dynamic prompt modules when they compute from state, diffs, tickets, contracts, robustness, unresolved findings, or tiebreaker decisions.
- Preserve profile tests for user/project/system layers, invalid keys, prep model fallback, tier models, depth/critic/vendor metadata.

## Done Criteria

- Megaplan prompts/state/schemas/profiles/control are plugin-local.
- Generic Arnold code imports no Megaplan state constants or profile policy.
- Generic profile validation works for non-Megaplan pipelines.
- Generic profile loading for non-Megaplan pipelines does not silently fall back to Megaplan defaults, constants, or validation rules.
- Megaplan profile validation still enforces Megaplan depth/tier/prep/robustness rules.

## Touchpoints

- `megaplan/prompts/`
- `megaplan/types.py`
- `megaplan/profiles/__init__.py`
- `megaplan/planning/control_binding.py`
- `arnold/pipelines/megaplan/`
- profile/control tests

## Anti-Scope

- Do not move execute/review policy.
- Do not update authoring docs beyond necessary references.
