# M3a: Relocate Neutral Pipeline Runtime Mechanics

## Outcome

Move the runtime mechanics already classified as neutral into `arnold.pipeline`, preserving existing non-Megaplan pipeline behavior and keeping Megaplan policy out of the generic runtime.

## Scope

In:
- Relocate or split neutral registry, executor, builder, generic steps, patterns, prompt-loading interface, artifact interface, and related tests according to the M-1 disposition manifest.
- Preserve non-Megaplan pipelines such as `doc`, `creative`, `select-tournament`, and `writing-panel-strict`.
- Ensure generic Arnold runtime tests pass without importing the Megaplan plugin.

Out:
- Do not redesign decision routing; that is M3b.
- Do not introduce new dataflow/subpipeline/fanout contracts beyond what is required to preserve existing neutral behavior; that is M3c.
- Do not move Megaplan stages/prompts/state/control; that is M4+M5.

## Locked Decisions

- Every move must be justified by `docs/arnold/package-disposition.*`.
- No horizontal package relocation by directory name.
- Generic runtime must not import `arnold.pipelines.megaplan`.

## Carrier Awareness

- The canonical prompt type is `str | Callable[[StepContext], str]`: `.md` strings resolve against the plugin bundle prompt directory, other strings are inline literals, and callables receive `StepContext`.
- Prompt resolution is bundle-scoped through `PipelineResourceBundle` or an equivalent narrow resolver. Relocated generic code must not reach into Megaplan modules for prompt paths.
- Import-side-effect `register_prompt()` into a global registry is only a migration bridge for existing Megaplan handlers; new generic code must not use it.
- Relocated executor/builder code must not import `Pipeline.run_phase()` or `_phase_arg_overrides`.

## Required Outputs

- Which existing tests become generic Arnold tests versus Megaplan plugin tests.
- Inventory of any neutral step that still carries hidden `plan_dir`, `planning`, or Megaplan artifact assumptions, with disposition for each finding.

## Constraints

- Preserve current runtime behavior.
- Keep boundary tests green.
- Use objective parity gates to backstop mechanical moves.
- Every moved module must pass the M0 boundary gates: no Megaplan imports, no `"planning"` literal, and no Megaplan gate literals as typed policy.
- Old paths are deprecated/re-exported or left as bridges; deletion happens in M7.

## Done Criteria

- `arnold.pipeline` contains classified neutral mechanics.
- Non-Megaplan pipeline tests still pass.
- Generic tests pass with Megaplan plugin tests skipped/absent where feasible.
- No Megaplan phase/gate/profile/state literals appear in generic Arnold runtime.
- Registry `SKILL.md` lookup still works for sibling-file and package pipelines.

## Touchpoints

- `megaplan/_pipeline/registry.py`
- `megaplan/_pipeline/executor.py`
- `megaplan/_pipeline/builder.py`
- `megaplan/_pipeline/steps/`
- `megaplan/_pipeline/pattern*`
- `arnold/pipeline/`
- pipeline tests

## Anti-Scope

- Do not delete old paths until M7.
- Do not broaden the operation contract.
- Do not change Megaplan policy.
