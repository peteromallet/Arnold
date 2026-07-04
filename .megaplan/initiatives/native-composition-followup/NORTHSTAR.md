# Native Composition Follow-Up North Star

Arnold's native pipeline layer becomes a compositional workflow system:
authors write ordinary Python steps and workflows, workflows can invoke other
workflows as normal Python calls, loops and decisions route through Python
control flow over recorded state, and every run receives tree-structured
traces, path-addressed checkpoints, and resume automatically.

The authoring target is **native Python, not a Python-shaped graph DSL**.
Decorators, policy objects, and invocable metadata annotate normal Python
functions; they do not replace `if`/`elif` branches, `while`/`for` loops,
typed return values, or direct subworkflow calls with manual node construction,
route tables, component constants, handler refs, or manifest-authoring APIs.
If the canonical source reads like a list of graph nodes connected by
`SOURCE_*`-style component calls, the epic has not met the target even if the
compiled manifest, trace, or rendered topology looks correct.

Author-facing workflow source uses the `.pypeline` extension. A `.pypeline`
file is Python syntax under Arnold's workflow contract: structured, validated,
replayable, and compilable into manifests/traces, but not a general-purpose
Python module and not an explicit graph-definition file. Ordinary `.py` files
remain valid for reusable implementation functions, pure phase bodies, runtime
code, tests, and import compatibility shims, but the canonical Megaplan
workflow source should end as `workflow.pypeline`.

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

The canonical Megaplan source must therefore read as proper native Python:
normal branches, normal loops, normal function/subworkflow calls, and typed
domain results such as gate, review, override, and execution outcomes.
Workflow-in-workflow composition must be authored as calling another decorated
Python workflow, not by manually assembling child manifest nodes or dispatching
through a generic component/handler registry.
The canonical authoring file should be `arnold_pipelines/megaplan/workflows/workflow.pypeline`;
any remaining `workflow.py` entrypoint is compatibility glue that loads or
re-exports the `.pypeline` source and may not become a second semantic owner.

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

No report-owned Megaplan semantic may be implemented by a Python-shaped wrapper
around the old graph-era stage/component model. A wrapper fails conformance if
the author-facing source still uses component constants, route-label tables, or
generic stage calls as the product control-flow skeleton, even when those calls
are nested inside decorated workflows.

## Done Means

- A new workflow author can write decorated Python workflows without manually
  constructing graph nodes, trace records, checkpoint paths, or runtime hooks.
- The canonical Megaplan workflow is idiomatic Python orchestration: reviewers
  can follow the main product flow through Python branches, loops, calls,
  subworkflow calls, and typed outcomes without consulting component tables or
  handler-local state transitions.
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
- A structural anti-wrapper test rejects any final `workflow.pypeline` where
  `critique`, `gate`, `tiebreaker`, `execute`, `review`, `override`, or their
  subworkflows are primarily expressed as `SOURCE_*`-style component calls,
  manifest node builders, handler refs, route tables, or generic stage
  dispatch instead of native Python control flow and typed calls.
- Any compatibility `workflow.py` must be mechanically proven to delegate to
  or re-export the `.pypeline` source without adding product routing, loop
  exits, fanout, suspension, override dispatch, or implicit state transitions.

## Still Not Done

- Production credential isolation, worker fleets, DB-backed durability,
  worktree reconcile, shared pack/version rollout, and broker content audit are
  not complete until the platform follow-up epic lands.
