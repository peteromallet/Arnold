# Megaplan Native Parity Oracle Synthesis

## Purpose

This document records the strongest answers to the ten oracle questions from
`docs/arnold/megaplan-native-current-codebase-map.md` and turns them into
engineering guidance for the corrective epic.

This is not a replacement for:

- `docs/arnold/megaplan-native-representation-report.md`;
- `docs/arnold/megaplan-native-current-codebase-map.md`;
- `docs/arnold/megaplan-native-parity-corrective-plan.md`.

It is the judgement layer: where the target, current codebase, and plan meet.

## Core Verdict

Use `.pypeline` lowering into the existing DSL/manifest runtime as the canonical
execution substrate. The generator-native runtime remains useful machinery, but
making it the canonical Megaplan runtime would combine two migrations: semantic
extraction and runtime replacement.

The immediate high-risk function is
`arnold_pipelines/megaplan/workflows/planning.py::build_pipeline()`. It
currently reads the `.pypeline` but rebuilds runtime behavior from
`components.py`. That is where source improvements can become decorative. Fix,
replace, or quarantine that path before any extraction milestone can close.

## Substrate Decision

### Chosen Direction

Canonical Megaplan should execute through `.pypeline` lowering into the existing
DSL/manifest runtime.

Reasons:

- existing auto-drive, CLI, resume, installed-package, and `.megaplan` state
  surfaces already target the manifest runtime;
- generator-native runtime does not currently carry enough Megaplan-specific
  execute DAG, long-lived human gate, and auto-drive semantics to justify
  switching the runtime at the same time as semantic extraction;
- an equivalence bridge is dangerous because it can become a new wrapper layer
  that rots after the first proof.

### Guardrail

The lowering step must not become a hidden semantic owner. Every source
construct that proves a traceability row must lower to a corresponding manifest
construct or declared policy, with source-span evidence and behavior parity.

## Minimum Semantic Checker

The checker should stay deliberately constrained. It should reject unknown or
unresolvable source rather than attempt general Python analysis.

Required minimum:

1. **Callee provenance rule.** For every report-owned call in canonical source,
   resolve the callee transitively inside the Megaplan package. Fail if it ends
   in `components.py` metadata, `handler_ref`, `route_bindings`, runtime route
   dispatch, or a function that assigns/derives `current_state`, `next_step`, or
   `route_signal`.
2. **Row-anchor shape rule.** Every row maps to a source span whose AST shape
   matches the row: branch, loop, `parallel_map`, typed decision, human gate,
   declared policy, or subworkflow. A bare call expression is not sufficient for
   report-owned semantics.
3. **Dead-delete mutation rule.** Stub or disable legacy carriers such as
   `route_bindings`, `_branch_edge_id`, `route_dispatch`, and compatibility
   native projections; deterministic routing traces for the corrected scenario
   suite must not change.

Do not build a general points-to analyzer. Keep the authoring subset small and
fail closed.

## Product Topology Litmus Test

A semantic is product topology if it changes any of:

- which named phase runs next;
- when the workflow suspends or terminates;
- fanout cardinality or join semantics.

Must be lifted:

- prep clarification gate;
- gate decision;
- reprompt to downgrade;
- no-progress/cap termination with severity split;
- review outcome classification and rework cap;
- tiebreaker decision;
- override routing;
- execute approval gates;
- blocked-task retry routing;
- no-review terminal path;
- finalize baseline fallback.

May remain phase-local if typed outputs are returned:

- gate signal building;
- payload normalization and model output parsing;
- blast-radius derivation;
- finalize task shaping and scrubbing;
- sense-check generation;
- batch command execution;
- debt record writing.

Gray zones:

- severity classification is phase-local data, but severity-to-route threshold
  is topology;
- critique lens selection is phase-local data, but selected-lens fanout
  cardinality is topology.

## Policy Boundary

A legitimate declared policy contains scalars, enums, bounded numerics, model
resource selectors, and generic retry/timeout/authority parameters.

A hidden routing table contains workflow node IDs, edge targets, handler refs,
callables, target refs, action dispatch, fanout contracts, reducer routes, or
Megaplan-specific fallback destinations.

Checker rule:

- policy may say how many retries, what timeout, which model route, or which
  authority is required;
- policy may not decide which Megaplan phase runs next;
- if a failure path needs a destination, the destination is written as a source
  branch at the source construct site.

## Execute DAG Target

True concurrent DAG execution is not required for semantic parity.

Deterministic batching is enough if:

- the batching function is pure and source/policy-visible over the finalized
  task list;
- child checkpoint paths are stable, keyed by task ID and batch index;
- blocked, partial-failure, and resume routes are visible loop branches;
- ready batches can be recomputed per iteration if blocked tasks mutate the
  effective dependency set.

Concurrency is a platform optimization. Source-visible dependency semantics are
the parity requirement.

## Compatibility Rules

Safe long-term compatibility:

- CLI as operator surface, if it delegates to canonical entry points;
- graph projection and rendered topology as views;
- `workflow.py` as a proven non-semantic re-export shim;
- old reports as historical receipts.

Drift factories unless deleted or quarantined:

- `manifest_backend._branch_edge_id` or equivalent handler-output-string to edge
  translation;
- `route_dispatch.py` over component `route_bindings`;
- `LEGACY_ALIASES` into handler-private override functions;
- auto-drive next-step derivation independent of canonical workflow events;
- executable compatibility `native_program` projections.

Rule:

Adapters that translate data may remain. Adapters that translate decisions must
die or be fenced as legacy.

## Risk-Dominating Scenarios

The corrected suite should include at least these ten scenarios:

1. Gate reprompt with unresolved blocking flags downgrades proceed to iterate.
2. Critique/gate/revise cap exhausted with critical flags blocks, while
   cosmetic-only unresolved work force-proceeds.
3. Prep blocking questions suspend, resume clarify, then proceed to planning.
4. Tiebreaker human replan restarts planning and rejoins the normal finalize
   path.
5. Execute batch 2 of 4 blocks, override recover-blocked resumes from batch 2
   with identical checkpoint paths.
6. Destructive execution without approval suspends; approval resumes execution.
7. Review needs rework, scoped re-execute runs, re-review passes.
8. Review cap exhausted with blocking items blocks; advisory-only force
   proceeds.
9. Bare/light robustness exercises critique skip and no-review terminal path.
10. Override force-proceed from blocked reaches finalization/done, and override
    abort mid-loop reaches terminal aborted.

## Typed Outcomes

Use closed, boring sum types:

- one domain module;
- sealed union per decision family;
- frozen dataclass variants carrying reason/evidence refs;
- exhaustive `match` plus `assert_never`;
- `to_wire()` / `from_wire()` confined to compatibility adapters.

Checker rule:

- no string literal may be a branch condition for a report-owned decision in
  canonical source.

The strength comes from checker enforcement, not type-system ceremony.

## Migration Order

1. Build checker, row-evidence schema, baseline failure, and compatibility
   quarantine.
2. Make `build_pipeline()` consume lowered `.pypeline` topology for a real
   vertical slice, or replace/quarantine it.
3. Establish typed outcomes and retained-handler interfaces.
4. Extract the front-half loop as one coupled unit: prep, critique, gate,
   revise.
5. Extract tiebreaker.
6. Extract execute batching/approval/resume.
7. Extract review/rework/caps.
8. Extract override/control routing.
9. Collapse component semantics incrementally. Each extraction milestone deletes
   or quarantines its own component carriers; do not defer all component
   collapse to the end.

Legacy execution may remain behind a per-plan flag only until that milestone's
parity scenarios pass. Delete the flag per milestone, not at the end.

## Legitimate Narrowing

Some target language is over-idealized and should be narrowed deliberately:

- Model routing should be a declared pure routing function referenced from
  phase source, not necessarily a static table.
- The whole pipeline should be readable from `workflow.pypeline` plus named
  subworkflows, not one enormous file.
- Auto-drive liveness can remain operational supervisor code if it emits events
  consumed by the canonical workflow and cannot route independently.
- Config-only overrides can remain effects; only routing overrides need source
  branches.
- Evidence should regenerate at final commit; excessive per-row intermediate
  hash ceremony is less important than reproducible final evidence.

Any narrowing requires:

- a checker rule that still blocks the original false-pass pattern;
- a behavior scenario proving the narrowed carrier cannot smuggle routing.

## Risks The Plan Must Still Answer

### Resume Identity

- What happens to a plan suspended under old semantics when deployed code moves
  that path to native source: resume, quarantine, or force replan?
- Are new fanout child paths and batch checkpoint cursors compatible with old
  resume cursors?
- Which loop counter is authoritative on resume: native source `LoopState` or
  persisted `.megaplan` state?

### Checker Rot

- Who reviews checker rule changes?
- Does weakening a checker rule require the same process as behavior changes?
- Are negative fixtures permanent mutation tests?
- Is the checker a permanent CI gate after closure?

### Fixture Staleness

- How are model-dependent scenarios made deterministic?
- Are prompt refs pinned or hashed for parity scenarios?
- Does a prompt change count as semantic when it can change route decisions?

### Error Routing

- Where do worker crashes, unhandled exceptions, timeout expiries, and malformed
  outputs route?
- Is each error path source-visible or runtime-generic?

### Effects and Partial Failure

- If one parallel-map child fails, what happens to siblings?
- Are artifact writes, debt records, and checkpoints idempotent under retry
  after partial write?

### External Consumers

- Which dashboards, tools, scripts, and `.megaplan` files read `current_state`
  or `next_step`?
- Is serialized state versioned independently from typed outcomes?
- Is the compatibility adapter the only writer of old public fields?

### Authority

- Who can force-proceed, approve destructive execution, or resume a human gate?
- Is authority declared at the human gate and audited?

### Operations

- Does finer topology increase checkpoint I/O or wall clock beyond acceptable
  limits?
- Is there a fenced kill switch for routing an individual plan back to legacy?

### Document Authority

- When the end-state report and corrective plan conflict after deliberate
  narrowing, which document wins?
- Is the traceability ledger generated from the authoritative source, or
  manually maintained as a fourth truth?
