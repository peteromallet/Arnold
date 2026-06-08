# Arnold Abstraction Vetting Synthesis

Date: 2026-06-01
Branch: `arnold-epic`
Run artifacts: `/tmp/arnold-abstraction-vetting-20260601-182856`

## Panel

- DeepSeek V4 Pro: five simple-plugin ergonomics probes.
- Codex: five complex edge-case probes.
- DeepSeek V4 Pro: five Megaplan interaction/package-structure probes.

All probes completed successfully.

## Consensus

The boundary is directionally right:

- Arnold should generalize mechanics, carriers, validation, resource bundles, graph execution, drivers, and optional operation seams.
- Megaplan should keep robust-planning meaning: phase vocabulary, auto loop policy, workflow state machine, prompts, orchestration, execute/review policy, profile semantics, and override meanings.

The main risk is not missing abstraction; it is making advanced abstractions visible to simple plugin authors.

## Decisions Added To The Plan

### Simple plugins stay simple

A simple plugin exports only metadata constants and `build_pipeline()`. It does not import `PluginOperations`, envelopes, or capabilities. If it has no custom operations, `arnold run` uses the generic graph executor.

### Capabilities are runtime-derived

`PluginCapabilities` is not a required plugin export. Arnold derives capabilities from manifest data, graph inspection, and optional operation registrations.

### Operations are independently optional

Do not use one wide required `PluginOperations` implementation. Complex plugins may advertise independent operations such as `run_phase`, `status`, `resume`, `list_overrides`, `apply_override`, and `validate_profile`.

### Dataflow validation is a milestone gate

`p.flow(...)` validates control flow only. `reads=[...]`, `writes=[...]`, typed ports, and artifact refs validate dataflow. Required reads must be satisfiable on every incoming path unless marked optional, external, or late-bound.

### `reads`/`writes` are Level-1 sugar

Simple string artifact names are sugar over the same artifact/port model as typed `produces`/`consumes`. Typed ports remain progressive, not mandatory for small plugins.

### Prompt API stays simple

Scaffolds show `prompt="draft.md"`, inline prompt strings, and callable prompt builders. They do not show `PromptRegistry`, `prompt_key`, or import-side-effect prompt registration.

### Resource bundles are runtime-internal

Plugin authors see directories: `prompts/`, `SKILL.md`, optional `profiles/`. Arnold assembles the `PipelineResourceBundle`.

### Package moves need a disposition manifest

M-1 must produce `docs/arnold/package-disposition.md`, with one row per module/package and explicit disposition. No horizontal package moves by directory name.

### Megaplan gets a rich plugin package

Megaplan needs `operations.py`, `auto.py`, `workflow.py`, `state.py`, `control.py`, `orchestration/`, `execute_policy/`, `prompts/`, `profiles/`, and plugin-local tests. This is how the plugin captures sophistication without leaking policy into Arnold runtime.

## Ambiguities Left For M-1

- Which `execute/` symbols are pure batch mechanics versus Megaplan execution policy.
- Which `runtime/` and `observability/` modules can move after removing Megaplan defaults.
- Whether `plugin.toml` remains for complex plugins; it is not part of the simple scaffold unless explicitly kept.
- Which `orchestration/` helpers, if any, are generic enough after parameterization. Default assumption: keep them Megaplan-local.

## Raw Outputs

- Codex complex probes: `/tmp/arnold-abstraction-vetting-20260601-182856/codex/*.out`
- DeepSeek reports: `/tmp/arnold-abstraction-vetting-20260601-182856/deepseek-results/*.txt`
