# Workflow Fixture Normalization

This directory holds the canonical M2 explicit-node workflow fixture matrix.
The fixtures are product-neutral semantic shapes, not behavioral rewrites of
existing Megaplan goldens.

## Files

- `canonical_megaplan_shapes.yaml` — deterministic expected topology shapes
  compiled from `arnold.workflow.Pipeline` + `arnold.patterns` constructors.

## Normalization Rules

1. **Stable IDs**: node and edge IDs are authored explicitly and preserved by
   the compiler.  The compiler rejects duplicate IDs rather than deriving hidden
   names.
2. **Deterministic ordering**: conformance tests compare sets and dictionaries
   keyed by stable ID.  YAML lists are ordered for readability, but the runner
   may sort nodes and edges by ID.
3. **Condition refs**: route conditions are durable `module:qualname` strings or
   stable condition identifiers such as `retry`, `retry-revise`, or
   `retry:retry`.  Live callables, lambdas, closures, and bound methods are
   rejected.
4. **Bounded reentry**: loop, revise, and retry shapes express recursive
   behavior through explicit `SuspensionRoute.reentry_id` values paired with
   `LoopPolicy.max_iterations`.  Arbitrary directed cycles are invalid.
5. **Capability suspension**: `human_gate` shapes use generic
   `CapabilityRequirement` + `SuspensionRoute` carriers, not human-specific
   kernel primitives.
6. **Subpipeline by hash**: nested manifests are referenced by
   `SubpipelineRef(manifest_hash, alias)`, not embedded runner objects.
7. **Tiebreaker rounds**: the tournament shape exposes two full tiebreaker
   rounds as explicit branch nodes (`tourney-tiebreak-1`, `tourney-tiebreak-2`)
   and labeled `tie` routes, not as a one-shot opaque subpipeline.
8. **Control labels**: override/fallback, escalation, compensation, supervisor
   promotion, and feedback shapes use stable edge labels (`fallback`,
   `escalate`, `compensate`, `promote`, `feedback`) without changing node IDs.
9. **Robustness and dynamic overlays**: budget policy slots and dynamic event
   metadata are stored as serializable, hash-stable values.  No runtime state,
   closures, or live objects cross the compile boundary.
10. **No banned authoring language**: fixtures do not use `PipelineBuilder`, `Stage`, public `Edge`, decorators, or fluent chaining.

## Volatile Fields

Locked volatile fields for behavioral goldens:

- `run_id`
- `event_id`
- `timestamp`
- `duration_ms`
- `absolute_path`
- `model_latency`
- `token_count`

Canonical transforms:

- Replace volatile scalar values with `"<normalized>"`.
- Sort object keys and route lists lexicographically by stable ID.
- Preserve versioned artifact names as `vN.<ext>` paths.
- Preserve seeds when present; otherwise omit seed fields.
- Do not rewrite `tests/fixtures/golden/pipeline_*.json` for import/package-only
  moves. If behavior legitimately changes, add a sibling `.explanation.md`
  artifact that names the behavioral reason.

New volatile fields require the amendment protocol in
`docs/arnold/workflow-manifest-amendments.md`.
