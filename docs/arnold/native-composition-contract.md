# Native Composition Contract

This document defines the M0 bridge contract for native composition. It is the
shared authoring and runtime doctrine that later M1-M6 migration work must
preserve while moving Megaplan from compatibility shells to source-owned native
composition.

## Scope And Waiver

- M0 is an additive bridge milestone.
- The contract is anchored to the M7 T1-T5 surface and carries an explicit
  waiver for M7 T1-T5 only.
- M7 T6-T9 are closeout and verification work and are assumed not to change
  canonical import paths, decorator metadata, IR shapes, compatibility aliases,
  or the source/manifest/native-program doctrine recorded here.
- Direct IR construction that still exists in
  `arnold_pipelines/megaplan/_compatibility.py` and
  `arnold_pipelines/megaplan/select_tournament/pipeline.py` is not conformant
  with this contract. Those paths are known M1-M6 migration targets, not M0
  evidence of conformance.

## Public Canonical Imports

The stable author-facing import surface is:

- `from arnold.pipeline import step, workflow`
- `from arnold.pipeline.native import step, workflow, decision, parallel`
- `from arnold.pipeline.native import compile_pipeline, project_graph`
- `from arnold.pipeline.native.ir import NativePhase, NativePipeline, NativeProgram`

Bridge compatibility remains additive:

- `phase` is the compatibility alias for `step`.
- `pipeline` is the compatibility alias for `workflow`.
- `decision` and `parallel` remain public native authoring primitives.
- Internal helpers, direct IR constructors outside `arnold.pipeline.native.ir`,
  and product-specific Megaplan compatibility modules are not public authoring
  imports.

## Doctrine

Three layers remain distinct:

- Decorated Python source owns Megaplan product semantics.
- `WorkflowManifest` is compiled output. It is never hand-authored source of
  truth for Megaplan composition.
- `Pipeline.native_program` is a dispatch substrate and compatibility shell for
  runtime execution and projection. It is not the source-authoritative
  representation of product semantics.

Any implementation that inverts those layers is non-conformant even if it can
execute.

## Invocable Surface

Both steps and workflows satisfy the same additive invocable interface.

Required invocable fields:

- `name`: human-readable callable name.
- `stable_id`: durable semantic identity for the invocable.
- `inputs_schema`: declared input schema metadata.
- `outputs_schema`: declared output schema metadata.
- `description`: optional descriptive text.

M0 keeps existing concrete callable behavior:

- A `@step` or `@phase` target remains a normal callable phase function.
- A `@workflow` or `@pipeline` target remains a normal callable workflow
  generator/function compiled by the native compiler.
- Existing dunder metadata remains supported for compatibility.
- The additive invocable fields must be readable without executing the body.

## Decorator API

### `@step` / `@phase`

`@step(...)` is the preferred authoring name. `@phase(...)` remains supported
with identical behavior.

Declared metadata:

- `name`: display and IR name; defaults to the Python function name.
- `id`: stable semantic ID. If omitted, the compiler may derive a default from
  the canonical callable identity, but authored IDs are the durability
  contract.
- `description`: optional text.
- `inputs`: declared input schema metadata.
- `outputs`: declared output schema metadata.
- `consumes` and `produces`: existing native port metadata; still supported as
  the compatibility shell consumed by current projection and runtime layers.

### `@workflow` / `@pipeline`

`@workflow(...)` is the preferred authoring name. `@pipeline(...)` remains
supported with identical behavior.

Declared metadata:

- `name`: display and IR name; defaults to the Python function name.
- `id`: stable workflow identity.
- `description`: optional text.
- `inputs`: declared workflow input schema metadata.
- `outputs`: declared workflow output schema metadata.

### `@decision`

`@decision` remains the public branch primitive. It does not become `@step`.
Decision vocabulary, human-gate metadata, resume schema metadata, and override
routes remain explicit and are validated separately from step/workflow IO
contracts.

## IR Contract

The public native IR remains concrete frozen dataclasses:

- `NativePhase`
- `NativeDecision`
- `NativeLoopGuard`
- `NativePipeline`
- `NativeInstruction`
- `NativeProgram`
- `ParallelInstruction`

The additive M0 rule is structural, not replacement-based:

- `NativePhase` and `NativePipeline` remain concrete dataclasses.
- They also satisfy the invocable metadata shape via additive fields or
  properties.
- `NativeDecision` keeps its existing decision-specific metadata contract.
- `NativeProgram` remains the compiled dispatch substrate produced by the
  native compiler.

## Stable IDs

Stable IDs are the durable identity contract for composition:

- Step IDs are stable across compilation, projection, trace emission, and
  replay.
- Workflow IDs are stable across parent/child composition boundaries.
- Python function names are readable defaults, not the long-term identity
  contract.
- Display names and stable IDs may differ.
- Legacy Megaplan stage names remain accepted only where they are already
  public compatibility identifiers.

Stable IDs are semantic identities, not instance identities. Repeated use of
the same child workflow or step does not allocate a new stable ID for the
invocable definition; it creates a new call-site identity.

## Declared Inputs, Outputs, And Schemas

Declared input/output metadata is required at the invocable boundary even when
the current runtime still carries port-style compatibility metadata.

Minimum contract:

- `inputs_schema` / decorator `inputs` describe the expected incoming payload.
- `outputs_schema` / decorator `outputs` describe the emitted payload.
- Schema metadata must be serializable and comparable without executing the
  invocable body.
- Runtime-only state, live validators, and ad hoc Python objects are not schema
  metadata.

Schema compatibility classes:

- `identical`: same schema meaning and same stable schema identity.
- `backward-compatible`: producer widened or added optional output; existing
  consumers remain valid.
- `forward-compatible`: consumer accepts a newer producer but older consumers
  may not.
- `breaking`: shape or semantics changed in a way that invalidates existing
  callers, replayers, or validators.

M0 records these classes as doctrine. Full enforcement can land incrementally in
later milestones.

## Call-Site Identity And Static Graph Shape

Composition identity is two-layered:

- Invocable identity: the step/workflow stable ID.
- Call-site identity: the path coordinate where that invocable is used.

Static graph shape rules:

- The authored workflow body must determine topology statically.
- A child workflow call introduces a distinct child call-site even when the
  same child workflow is called more than once.
- Repeated child path segments are allowed only when each segment represents a
  different authored call-site along the tree path.
- Dynamic string-authored path construction is invalid.
- Direct manifest authoring, manual graph nodes, and manual path strings are
  outside this contract.

## Path Rules

Canonical path identity is tree-shaped, not graph-node-string folklore.

Rules:

- A path is derived from authored parent-to-child call sites.
- Each segment is stable for that call site and does not depend on runtime
  object identity.
- Reusing the same child invocable at two authored sites yields two distinct
  paths because the call-site segments differ.
- Repeated segment text is allowed only when it corresponds to repeated
  invocable IDs under different parents or iterations; ambiguity is resolved by
  the full path, not by forbidding repeated names.

Loop iteration path rules:

- Each loop body call site has one static path segment in authored topology.
- Runtime iterations append an iteration coordinate beneath that static body
  path.
- Iteration coordinates are ordered and monotonic within a single attempt.
- Replay reuses the same static path plus recorded iteration coordinates rather
  than inventing new topology.

## Input Mapping And Output Merge Semantics

Input mapping is explicit at the call boundary:

- Parent workflow inputs may flow into child inputs by declared parameter or
  schema field name.
- A child call cannot depend on undeclared ambient Megaplan state as its only
  contract.
- Mapping rules must be derivable from source and metadata, not hidden in
  runtime-only handlers.

Output merge semantics are deterministic by contract:

- A step emits its declared outputs.
- A child workflow returns its declared outputs to the parent call site.
- Merge is by declared field identity, not by ad hoc whole-state replacement,
  unless the authored contract explicitly declares that replacement behavior.
- Parallel or repeated child outputs must merge through declared reducer or
  loop-carried state rules, not through implicit last-writer-wins behavior.

The contract is repeatable, not necessarily byte-for-byte deterministic across
models. Given the same source, metadata, validators, and routing outcomes, the
runtime must replay the same control topology and merge rules even when model
content differs.

## Routing And Validator Rules

Routing validators must enforce:

- Decision outcomes are members of the declared vocabulary.
- Human-gate choices and override routes name declared labels only.
- Routes target declared call sites or terminal outcomes.
- Loop continuation and loop exit routes are explicit.
- Reducer, validator, and routing metadata must be declared structurally; live
  imperative patch-up code is not the contract surface.

Validator doctrine:

- Validators may reject payloads, routing labels, or resume payloads.
- Validators do not author topology.
- Validator directives embedded directly in workflow source as ad hoc control
  language are out of contract for M0.

## Trace And Audit Contract

Trace emission is tree-scoped and attempt-scoped.

Each trace record must preserve enough information to identify:

- workflow stable ID
- invocable stable ID
- call-site path
- parent path when present
- attempt number
- loop iteration number when present
- instruction or decision kind
- routing label or decision outcome when present
- input schema identity and output schema identity when known

Per-attempt audit fields must preserve:

- attempt ordinal
- start and finish timestamps
- resume/replay cause when applicable
- validator outcomes
- route selection basis
- suspension/resume coordinates when applicable
- child invocation coordinates

### Audit Skeleton

Every attempt records a complete audit skeleton through `AuditHooks`.
The `AuditRecord` dataclass carries:

- `attempt_id` — UUID hex string unique per attempt.
- `run_path` — the trace-addressable path of this step in the invocation tree.
- `parent_run_path` — the path of the parent workflow or iteration context.
- `call_site_path` — the authored literal `id=` that created this step.
- `step_path` — the full trace tree coordinate for this step.
- `attempt_start` — timestamp when the attempt began.
- `step_outcome` — the result of the step (`completed`, `failed`, `suspended`).
- `attempt_end` — timestamp when the attempt finished.

The audit skeleton is serializable without capturing live Python frames. It is
the evidence layer for conformance verification, not a debug log. All paths
are trace-addressable and correlate to tree traces via `call_site_path`.

Trace records are structural evidence. They must be serializable without
capturing live Python frames.

## Replay Semantics

Replay is repeatable, not model-deterministic:

- Replay must preserve stable IDs, call-site paths, iteration coordinates,
  declared validators, and merge rules.
- Replay may reproduce different model text or payload details if the effectful
  step is not deterministic.
- A successful replay proof is therefore structural and semantic, not strict
  byte equality of all step outputs.
- Resume/replay must never infer a new topology from `Pipeline.native_program`
  alone when source and compiled metadata disagree; source-owned semantics win.

## Platform Boundaries

The composition contract draws explicit lines between six platform domains.
Each boundary is a declared contract surface: workflow source declares intent;
the platform executes mechanics.

### Durability

Workflow durability (suspension and resume) is defined by declared suspension
points in workflow source, not by handler-local checkpoint calls:

- `suspend(reentry_id=..., resume_schema=...)` declares a suspension point.
- `reentry_id` names the stable resume cursor.
- `resume_schema` describes the expected payload shape at reentry.
- The native runtime owns checkpoint writes and cursor advancement.

### Credentials

Credentials and secrets are never referenced in workflow source or static
metadata:

- Workflow source may declare credential requirements, never key values.
- `StepContext` provides resolved credentials at runtime without exposing
  raw secrets to the trace or audit skeleton.
- Environment reads and credential resolution live in the platform's
  execution layer.

### Worker Fleets

Execution isolation is a platform concern. Workflow source declares *what*
runs; the platform decides *where*:

- `target_worker_pool` hints are metadata, not dispatch directives.
- Parallel fanout items are independent; workflow source must not assume
  co-location.
- Steps must not depend on local filesystem state that would not survive
  worker migration.

### Worktree Reconcile

Artifacts and working directories are owned by the platform:

- File artifacts use `EvidenceArtifactRef` with content-addressed URIs.
- The platform's artifact store owns durability, replication, and cleanup.
- `consumes`/`produces` port contracts reference content types; the platform
  maps these to concrete locations.
- Worktree reconcile uses the recorded trace to reconstruct artifact state
  at reentry points.

### Pack / Version Rollout

Package identity and versioning follow the declared module-level contract:

- `name`, `arnold_api_version`, `driver`, `entrypoint` are the stable identity
  surface.
- `WorkflowManifest` hashes drive rollout gating — version comparisons use
  deterministic hashes, not hand-authored version strings.
- The scaffold template emits `authoring_style = "compositional"` and
  `driver = ("native", "project+validate")`.

### Supervision

Supervision (policy enforcement, escalation, override) is declared in workflow
source and rendered policy metadata:

- Timeout, retry, escalation, and override actions are declared via named
  policy references at call sites.
- The override matrix classifies actions into terminal-route-affecting and
  additive-config-effect categories.
- Handlers consume pre-classified entries; they must not define local
  route-decision functions.
- Model routes are resolved at the policy/profiles layer before step
  invocation.

## Static Queries

The compiled `WorkflowManifest` supports static inspection without executing
workflow bodies:

- `node_ids` and `refs` — declared components and dependencies.
- `suspension_points` — eligible suspension locations.
- `control_routes` — declared routing topology.
- `source_spans` — source-code locations for every call site.
- `hash_inputs` — inputs used to compute the deterministic manifest hash.

Use `arnold workflow inspect` or `arnold workflow explain` for static queries.
Both produce machine-readable JSON with `--format json`. The CLI never imports
or executes workflow source for inspection.

## Megaplan Compatibility Aliases

Public compatibility aliases are limited to legacy Megaplan phase identities
that already appear in persisted plans, status views, cursors, prompts, or
operator-visible routing. The authoritative registry is
`arnold_pipelines.megaplan.step_contracts.STEP_CONTRACTS`.

Public compatibility names currently include:

- `execute`
- `finalize`
- `critique`
- `review`
- `gate`
- `plan`
- `prep`
- `critique_evaluator`
- `revise`
- `prep-triage`
- `prep-distill`
- `prep-research`
- `feedback`
- `loop_plan`
- `loop_execute`
- `tiebreaker_researcher`
- `tiebreaker_challenger`

Internal-only references are not public compatibility promises, even if they
exist in code today:

- direct IR constructor call sites in compatibility modules
- ad hoc helper names
- local graph-projection keys
- manual path literals
- temporary migration shims

Only the registry-backed public names above are compatibility obligations.

## Non-Conformant But Tolerated In M0

The following remain tolerated only as bridge debt:

- direct IR construction in known Megaplan compatibility modules
- projected `Pipeline` shells that still expose compatibility-era shape
- port metadata as the current runtime substrate beside new schema metadata

They are tolerated because M0 defines the contract first. They are not evidence
that direct constructor use, manual path handling, or shell-derived semantics
are canonical.

## Acceptance Summary

An implementation conforms to this M0 contract only if it preserves all of the
following:

- public canonical import paths
- additive `step`/`workflow` aliases with compatibility `phase`/`pipeline`
- concrete native IR dataclasses plus additive invocable metadata
- stable IDs distinct from call-site paths
- declared input/output schema metadata
- explicit input mapping and deterministic merge rules
- tree-shaped path identity with loop iteration coordinates
- validator and routing rules expressed as declared metadata
- tree trace records plus per-attempt audit fields
- source-authoritative doctrine over manifest and native-program shells
