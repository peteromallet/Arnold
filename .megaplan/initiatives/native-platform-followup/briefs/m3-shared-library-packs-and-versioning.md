# M3 - Shared Library Packs And Versioning

## Objective

Turn compositional workflows into reusable units that can be shared safely.
Full marketplace mechanics are not required, but packs, stable unit IDs,
dependency metadata, lockfile-style pinning, structural diff, and deliberate
re-pin/upgrade flow must exist at a practical level.

## Files To Change And Instructions

- `arnold/pipeline/native/ir.py`
  Ensure stable unit IDs and declared interfaces are exposed for dependency
  metadata.
- `arnold/pipeline/native/graph_projection.py` or static graph tooling
  Expose transitive dependency queries: what this workflow contains, what uses
  this unit, and what versions a run used.
- New pack metadata module
  Define pack manifests: exported steps/workflows, versions, declared
  dependencies, lockfile/pin format, and compatibility metadata.
- Registry/discovery surfaces
  Register pack units without making callers import implementation internals.
- Structural diff tooling
  Classify interface changes, removed/renamed units, reordered already-executed
  paths, added branches, and internal step body changes as breaking or
  non-breaking where possible.
- Tests
  Cover a shared step used by two workflows, a shared workflow used as a child,
  a nested transitive dependency chain, a deliberate re-pin, a breaking-change
  diagnostic, pack-boundary cycle detection, and refusal to run when a required
  pin/lockfile entry is missing or ambiguous.

## Verifiable Completion Criterion

- A pack can export both a step and a workflow.
- A workflow can depend on a pinned pack unit and record the version used.
- Dependents do not auto-upgrade when a shared unit changes.
- A re-pin/upgrade command or helper shows what changed and whether the move is
  breaking.
- Transitive "what uses this?" and "what version did this run use?" queries
  work for at least one nested workflow.
- Publishing or loading packs detects transitive dependency cycles and enforces
  the nesting/dependency depth bound from the composition contract.
- A pack A -> workflow B -> step C dependency records the exact versions used
  by a run; a breaking change to C produces a transitive impact query and a
  deliberate re-pin/upgrade flow.

## Native Representation Alignment

- Matrix rows owned or affected: Source readability; Canonical source path reconciliation; Path-addressed checkpoints.
- Expected status change: platform `enabled` for shared unit identity/versioning while preserving the composition contract.
- Proof artifacts: pack manifest tests, lockfile/pin tests, transitive dependency query tests, structural diff tests, cycle/depth rejection tests.
- False-pass guard: pack reuse must not require callers to import implementation internals or flatten away stable child workflow identity.
- Deferrals: marketplace mechanics, hot migration, and automatic update propagation remain out of scope unless later epics take them on.
- Canonical paths/imports: pack metadata must expose stable IDs and declared interfaces from the composition IR, not separate product-specific names.

## Risks And Blockers

- Do not build a marketplace. This milestone is about the local/distribution
  contract needed for safe reuse.
- Stable IDs and declared interfaces from the composition epic are prerequisites;
  do not reinvent them here.

## Dependencies

- Depends on M1.
