# Workflow Runtime Semantics

This document describes the manifest workflow runtime implemented in
`arnold.execution`.  The runtime is product-neutral: it executes compiled
`WorkflowManifest` instances through protocol registries and a journal-backed
backend.

## Entry point

```python
from arnold.execution import run

result = run(
    manifest,
    artifact_root="/path/to/root",
    registries=ExecutionRegistries(...),
    backend=LocalJournalBackend(...),
    resume_cursor=ManifestCursor(...),  # optional
)
```

`arnold.execution.runner.run` validates that `manifest` is a
`WorkflowManifest`, then delegates to `ExecutionBackend.run_manifest`.

## Artifact store

`LocalJournalBackend` creates a `FileBackedArtifactStore` at `artifact_root`.
Artifacts are written through `ArtifactSpec` outcomes and recorded with
`artifact_written` events carrying content hashes and provenance.  Content-type
validation is performed by the registry-backed content-type system in
`arnold.kernel.artifacts`.

## Resume and replay

A run can be resumed by passing a `ManifestCursor` built from
`arnold.manifest.manifest_coordinate(...).cursor(...)`.

On resume:

1. The existing `events.ndjson` is read.
2. `project_routing_state` reconstructs runnable state from events.
3. `_check_authority("resume", ...)` verifies the manifest's
   `AuthorityRequirement` if one exists.
4. A `node_resumed` event is appended and execution continues from the cursor
   coordinate.

Replay is deterministic because routing is a pure function of the manifest plus
the event journal.

## Suspension

A node returns `NodeState.SUSPENDED` (via the backend's `_execute_node_payload`).
The runtime appends `node_suspended`, releases the budget reservation, and
raises `_TerminalState(ExecutionState.SUSPENDED)`.  The returned
`ExecutionResult.resume_cursor` points at the suspended coordinate and carries
the `reentry_id` from the node's `SuspensionRoute`.

## Cancellation

A backend may return `NodeState.CANCELLED`.  The runtime appends
`node_cancelled`, releases the budget, and raises
`_TerminalState(ExecutionState.CANCELLED)`.

## Timeout and deadline

Per-node `TimingPolicy.timeout_seconds` is enforced in `_run_node_body` by
comparing monotonic elapsed time; a timeout produces a `node_timeout` event
followed by `node_failed`.

Manifest-level `TimingPolicy.ttl_seconds` and `deadline_ref` are checked at the
start of each loop iteration in `_check_deadline_ttl`, producing `ttl_expired`
or `manifest_deadline` and failing the run.

## Capability and effect dispatch

Before a node executes, each `CapabilityRequirement` is checked through
`ExecutionRegistries.capabilities`.  Denied required capabilities fail the node
immediately.

Declared `EffectRef` items are executed through `ExecutionRegistries.effects`
after the node succeeds.  Effects require an idempotency key derived from the
run, node ref, and effect id.

## Budget ledger

Each node reserves a `BudgetReservation` before execution and settles or
releases it afterward.  The governor state is folded from journal events by
`arnold.kernel.governor.fold_governor_state` and enforces limits from the
manifest- or node-level `BudgetPolicy`.

## Control transitions

Declared `ControlTransitionSlot` and `TopologyOverlaySlot` items on a node are
dispatched through `ExecutionRegistries.controls` before node execution.
Resulting transitions are journaled as `control_transition` events with kind
`override`, `fallback`, `escalation`, `supervisor_promotion`, or `overlay`.
Overlays are applied by `project_routing_state` without mutating the manifest
hash.

## Compensation

When a node fails and carries a `CompensationPolicy`, the runtime builds
compensation steps from completed predecessors (reverse manifest order) and
executes their effects through the effect ledger.  Compensation events are
scoped and idempotent.

## Backend protocol

`ExecutionBackend` (in `arnold.execution.backend`) is the protocol seam.
Implementations must provide `run_manifest(...)`.

`LocalJournalBackend` is the reference implementation.  Product integrations can
subclass it and override hooks such as `_execute_node_payload`, `_select_branch`,
`_execute_fanout_child`, `_reduce`, `_execute_effect`, `_check_authority`,
`_load_subpipeline_manifest`, and `_execute_subpipeline_scope`.

## Fake backend

`tests.arnold.execution.conftest.FakeBackend` subclasses
`LocalJournalBackend` and overrides the hooks above with deterministic, in-memory
behaviors for unit tests.  It is the canonical example of a backend that does
not import product pipeline code.
