# Workflow Manifest Contract

`arnold.workflow.manifest.v1` is the canonical serialized workflow contract
for M1 and the compile target for the M2 explicit-node authoring surface. The
manifest is neutral data: it describes topology, stable refs, policy slots,
capability requirements, and replay coordinates. It does not execute workflow
code, import product packages, or carry live Python objects.

The implementation source of truth is the frozen dataclass set in
`arnold/manifest/manifests.py`, plus stable reference helpers in
`arnold/manifest/refs.py`. This document names the field-level contract that
later DSL, compiler, inspect, dry-run, and runtime work must preserve.

## Version And Identity

- `schema_version`: must be `arnold.workflow.manifest.v1`.
- `id`: human-chosen workflow alias. It is validated with
  `canonical_alias()` and is not enough for runtime identity by itself.
- `version`: optional author/package version string. It is descriptive and is
  included in `manifest_hash`, but not in `topology_hash`.
- `manifest_hash`: `sha256:` hash of canonical JSON for the full manifest body
  with both hash fields removed. Runtime events, registries, replay, and
  deletion gates identify a manifest by alias plus this hash.
- `topology_hash`: `sha256:` hash of topology-defining fields only:
  `schema_version`, `id`, each node's `id`, `kind`, `inputs`, `outputs`, and
  `subpipeline`, and each edge's `id`, `source`, `target`, `label`, and
  `condition_ref`.

Canonical JSON uses sorted keys, compact separators, and deterministic tuple
ordering. The `WorkflowManifest` constructor sorts nodes and edges by `id`
before hashing.

## Manifest Fields

- `nodes`: required tuple of `WorkflowNode`. Node IDs must be unique and are the
  stable coordinates used by refs, diagnostics, inspect, dry-run, and replay.
- `edges`: optional tuple of `WorkflowEdge`. Edge IDs must be unique. Edge
  sources and targets must name manifest node IDs.
- `capabilities`: manifest-level tuple of `CapabilityRequirement`.
- `policy`: optional manifest-level `WorkflowPolicy` for policy slots that apply
  to the workflow as a whole.
- `source_span`: optional `SourceSpan` pointing at the authored pipeline source.
- `metadata`: serializable extension data. It must not contain runtime state,
  journal data, or hash overrides.

M2 authoring compiles explicit node data into these fields. Authors construct a
pipeline object with stable step IDs and route data; `WorkflowManifest` remains
compiler output, not hand-authored package source.

## Node Fields

- `id`: stable node coordinate. It must be explicit in M2-authored pipelines and
  durable across processes.
- `kind`: neutral node family such as an agent, branch, fanout, retry,
  suspension, subpipeline, merge, or external call shape. Product-specific
  execution policy belongs behind capabilities and registries, not in the kind
  string.
- `label`: optional display label. It is not topology identity.
- `inputs` and `outputs`: tuples of stable value names. A value ref uses the
  node ID plus the value name, optionally with a schema hash.
- `capabilities`: node-level `CapabilityRequirement` entries.
- `policy`: optional node-level `WorkflowPolicy`.
- `source_span`: optional authored-source coordinate used for diagnostics and
  replay provenance.
- `subpipeline`: optional `SubpipelineRef` to a nested manifest by hash. Nested
  manifests are referenced, not embedded runner objects.
- `metadata`: serializable node extension data. Reserved runtime keys include
  `manifest_hash`, `topology_hash`, `runtime_state`, and `event_journal`.

## Edge Fields

- `id`: stable edge coordinate. Compiler-generated IDs must be deterministic.
- `source`: source node ID.
- `target`: target node ID.
- `label`: route label, defaulting to `default`.
- `condition_ref`: optional durable condition reference, resolved by registry at
  runtime. It must not be a live callable.
- `metadata`: serializable edge extension data.

Edges describe forward topology. M2 loop-back must not rely on arbitrary graph
cycles; it is represented through explicit bounded control topology as
described below.

## Policy And Control Fields

`WorkflowPolicy` is a carrier for optional policy slots. The manifest names the
slots and durable refs; the runner owns the concrete algorithms.

- `budget`: optional `BudgetPolicy` with `max_cost`, `max_seconds`,
  `max_attempts`, and `token_budget`.
- `retry`: optional `RetryPolicy` with `max_attempts`, `backoff`, and
  `retry_on`.
- `loop`: optional `LoopPolicy` with `max_iterations` and `until_ref`. M2 loop
  semantics require a finite bound through `max_iterations` unless a later
  amendment defines an equivalent bounded proof.
- `fanout`: optional `FanoutPolicy` with `mode`, `width`, and `reducer_ref`.
- `suspension_routes`: tuple of `SuspensionRoute` values.
- `timing`: optional `TimingPolicy` for node timeout, deadline refs, and TTL.
- `idempotency`: optional `IdempotencyPolicy` for replay-safe node execution.
- `effects`: tuple of string-keyed `EffectRef` values resolved by runtime
  registries.
- `reducers`: tuple of string-keyed `ReducerRef` values resolved by runtime
  registries.
- `compensation`: optional `CompensationPolicy` declaring reversal targets.
- `escalation`: optional `EscalationPolicy` declaring neutral escalation
  targets.
- `control_transitions`: tuple of `ControlTransitionSlot` values for generic
  override, fallback, escalation, supervisor-promotion, compensation, and
  overlay transitions.
- `topology_overlays`: tuple of `TopologyOverlaySlot` values. These reserve
  dynamic overlay metadata in the manifest, but applied overlays are recorded
  later as runtime control-transition events and must not mutate the canonical
  manifest hash.
- `authority`: tuple of `AuthorityRequirement` values checked before accepting
  authority-gated runtime mutations.

`SuspensionRoute` is product-neutral:

- `route_id`: stable route name.
- `capability_id`: optional capability gate required to resume or service the
  route.
- `reentry_id`: optional stable cursor used to resume into bounded control
  topology.
- `payload_schema_hash`: optional schema hash for route payloads.
- `resume_schema_hash`, `resume_schema_ref`, and `resume_payload_ref`: optional
  resume payload contract fields.

## Bounded Loop And Reentry Semantics

M2 distinguishes intentional recursive workflow behavior from accidental graph
cycles:

- Arbitrary directed cycles in `edges` are invalid for the M2 compiler target.
- Intentional loop/revise behavior is explicit control topology: the owning
  node or manifest carries `WorkflowPolicy.loop`, the loop has a stable
  `SuspensionRoute.reentry_id`, and runtime cursors may include that `reentry_id`
  via `ManifestCursor`.
- The loop must be bounded. The current v1 carrier is
  `LoopPolicy.max_iterations`; `until_ref` may describe the stop condition but
  does not by itself prove a bound.
- Reentry routes identify where replay/resume returns after suspension or
  iteration. They are not edges and do not widen topology hashing beyond the
  existing policy fields included in `manifest_hash`.
- Pattern and compiler code may lower branch, revise, retry, fanout, and
  suspension shapes into these carriers, but no constructor object or live
  runtime loop crosses the compile boundary.

Validation tasks following this contract should reject untyped cycles and accept
only explicit bounded reentry shapes.

## Reference Fields

Stable refs are strings derived from dataclasses in `arnold.workflow.refs`:

- `NodeRef`: `node:<node_id>`.
- `EdgeRef`: `edge:<source_id>-><target_id>:<label>`.
- `SourceSpan`: `source:<path>:<start_line>:<start_column>-<end_line>:<end_column>`.
- `SourceRef`: `source-ref:<id>` optionally anchored to a `SourceSpan`.
- `ValueRef`: `value:<node_id>.<name>` optionally followed by a schema hash.
- `ManifestCoordinate`: `workflow:<alias>@<manifest_hash>`.
- `ManifestCursor`: a coordinate plus optional node, edge, value, and
  `reentry:<reentry_id>` segments.

Refs are durable coordinates. They do not expose live values, Python control
flow, or product-owned runtime objects.

## Serialization Rules

- Serialized manifests are canonical JSON objects.
- `None` fields are omitted from hash payload normalization.
- Tuples serialize as arrays.
- Mappings sort by stringified key.
- Hash fields are removed before `manifest_hash` computation.
- `topology_hash` intentionally ignores node display labels, policies,
  capabilities, metadata, and source spans except for the topology fields listed
  above. Edge route labels are topology fields.

Any change that alters serialized meaning, hash inputs, required fields, or
replay compatibility must follow `workflow-manifest-amendments.md`.
