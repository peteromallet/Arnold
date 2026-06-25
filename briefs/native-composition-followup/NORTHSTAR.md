# Native Composition Follow-Up North Star

Arnold's native pipeline layer becomes a compositional workflow system:
authors write decorated Python steps and workflows, workflows can invoke other
workflows as reusable units, loops and decisions route only on recorded state,
and every run receives tree-structured traces, path-addressed checkpoints, and
resume automatically.

The load-bearing primitive is the **invocable interface**: steps and workflows
are distinct internally, but both expose stable identity plus declared
inputs/outputs so callers can invoke either without reading the body. Tooling
keeps the full structure for validation, tree traces, path addressing, static
queries, and future versioning.

The derived composition graph is a first-class artifact, not just execution
plumbing: tooling can ask what a workflow contains, what it invokes, and which
stable units and declared interfaces are involved without running the workflow.

This epic deliberately builds on the native-first completion epic and stays on
the existing native runtime substrate. It does not claim to finish DBOS/Postgres
durability, worker fleets, credential brokerage, production security, or the
full shared-library/versioning product. Those are explicit follow-up platform
work, not silently completed here.

Canonical Megaplan is the first real migration target after the composition
contract is defined. The contract comes first so Megaplan cannot accidentally
define permanent semantics through one-off runtime hacks; Megaplan then proves
the abstraction against Arnold's hardest workflow.

## Done Means

- A new workflow author can write decorated Python workflows without manually
  constructing graph nodes, trace records, checkpoint paths, or runtime hooks.
- Workflows can invoke workflows through declared interfaces and stable IDs,
  including repeated child use and at least three levels of nesting.
- Static tooling can inspect the derived graph before execution.
- Runtime tooling can inspect tree traces and resume from stable paths after
  interruption.
- Routing is validated at the authoring/registration boundary, and replay
  consistency is tested in CI.
- Canonical Megaplan uses the same general composition model as the examples;
  any temporary Megaplan-only path has been generalized or deleted by the end of
  the epic.

## Still Not Done

- Production credential isolation, worker fleets, DB-backed durability,
  worktree reconcile, shared pack/version rollout, and broker content audit are
  not complete until the platform follow-up epic lands.
