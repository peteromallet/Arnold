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

## Required Anchor

This epic is governed by `docs/arnold/megaplan-native-representation-report.md`.
It is the primary epic responsible for making canonical Megaplan converge on
that report's end state.

`docs/arnold/megaplan-native-representation-alignment-plan.md` is the required
enforcement plan. Every milestone brief must cite the matrix rows it owns,
produce the required proof artifacts, and guard against the listed false-pass
scenarios.

The final Megaplan source should make the real product workflow visible:
prep clarification is a gate, critique/gate/revise is a bounded loop,
tiebreaker is a subworkflow, review rework is an explicit cycle, execution is
not hidden behind one opaque handler, and human suspension, override,
retry/timeout, model-routing, and resume semantics are represented by declared
workflow structure or policy. If any of those remain hidden, this epic must
produce a named deferral with a downstream owner and proof gate.

Doctrine precedence for this epic: canonical Megaplan product semantics are
owned by visible compositional Python workflow source, declared workflow policy,
or audited pure phase bodies. `WorkflowManifest` is the normalized
runtime/replay/inspection artifact compiled from that source, and
`Pipeline.native_program` is compatibility dispatch substrate. Neither a flat
manifest graph nor a projected native shell may be treated as final conformance
without proving the canonical source carries the semantics.

No report-owned Megaplan semantic may remain solely in handler refs. Retained
handlers require a purity inventory and source-invariant tests proving they do
not own product routing, loop exits, retries, fanout, suspension, override
dispatch, or implicit `next_step`/`current_state` transitions.

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
- `docs/arnold/megaplan-native-representation-report.md` has a row-by-row
  alignment proof showing which report requirements are implemented, which are
  intentionally deferred, and which tests or rendered topology views prove the
  final shape.
- `docs/arnold/megaplan-native-representation-alignment-plan.md` has no
  composition-owned row left as `missing` or merely `enabled`; each such row is
  implemented or explicitly deferred with downstream owner and blocking proof.
- Report-owned Megaplan semantics are not deferred past this epic merely
  because they remain inside handlers, metadata constants, route labels,
  rendered manifests, native traces, or `native_program` shells. Deferrals from
  this epic are allowed only for genuinely platform-only production guarantees
  or explicitly rejected scope, and each deferral must name the blocking proof
  that prevents accidental closure.

## Still Not Done

- Production credential isolation, worker fleets, DB-backed durability,
  worktree reconcile, shared pack/version rollout, and broker content audit are
  not complete until the platform follow-up epic lands.
