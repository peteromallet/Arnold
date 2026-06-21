# Workflow Manifest Amendment Protocol

The M1 manifest/kernel contract is versioned deliberately. Downstream
milestones must not widen the contract silently.

## Version Bumps

Bump `arnold.workflow.manifest.v1` only when a serialized manifest meaning
changes, a required field is added, a hash input changes, or replay cannot
interpret old events without an alias gate. Additive optional metadata that
does not affect hashes may stay within v1 if validation remains deterministic.

## Proposal Requirements

Every amendment must name:

- The contract field or kernel event family being changed.
- Whether `manifest_hash`, `topology_hash`, or both change.
- How in-flight runs behave: replay with original manifest, replay through an
  explicit compatibility alias, or quarantine with operator-visible rationale.
- Any new volatile golden field and its canonical normalization transform.
- The milestone that owns implementation and the tests proving compatibility.

## M2 Clarifications

M2 does not replace the M1 dataclass manifest with a new schema layer. The
compile target remains `WorkflowManifest` and its nested dataclasses in
`arnold.workflow.manifests`.

The M2 explicit-node DSL lowers to the existing v1 fields:

- Authored steps become `WorkflowNode` entries with explicit stable `id`
  values.
- Authored control routes become `WorkflowEdge` entries where they describe
  forward topology, and `WorkflowPolicy` / `SuspensionRoute` entries where they
  describe policy, suspension, or reentry.
- Authored hook, condition, reducer, and stop-condition references become
  durable string refs such as `condition_ref`, `until_ref`, or `reducer_ref`;
  live callables and runtime objects are not manifest fields.
- Package `build_pipeline()` returns the M2 authoring pipeline object. A
  `WorkflowManifest` is compiler output.

Loop-back behavior is a semantic tightening, not a new v1 field.  Arbitrary graph cycles are not valid M2 topology; intentional recursive behavior must be expressed with explicit bounded loop/reentry carriers:

- `WorkflowPolicy.loop.max_iterations` supplies the finite bound.
- `WorkflowPolicy.loop.until_ref` may name the durable stop condition.
- `SuspensionRoute.reentry_id` supplies the stable reentry cursor segment used
  by resume/replay.
- `ManifestCursor.reentry_id` names the runtime position for a specific manifest
  coordinate.

If later compiler work proves those carriers insufficient, the change must be a
separate manifest amendment that states whether `manifest_hash`,
`topology_hash`, or both change.

## Fixture Changes

Behavioral goldens cannot change for import/package-only moves. Legitimate
behavior changes need a sibling `.explanation.md` artifact that names the
behavioral reason and references the milestone.

## Replay Rule

The original manifest reference carried by journaled events is authoritative.
If a newer manifest version cannot resolve a historical event, the resolver
must return an explicit alias or quarantine decision; it must not infer runtime
state from Python object graphs or product package internals.
