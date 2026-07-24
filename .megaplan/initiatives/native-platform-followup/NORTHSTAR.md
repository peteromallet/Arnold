# Native Platform Follow-Up North Star

Arnold's compositional workflow system becomes a production-grade agentic
workflow platform. The native composition epic proves the primitive locally:
stable invocable steps/workflows, nested composition, static graph queries, tree
traces, path resume, and routing validation. This epic adds the operating
posture the original design doc requires for real agent work across repos.

The target platform provides:

- safe side effects through idempotency keys and worktree reconcile-on-resume;
- agent credential isolation through a broker, scoped tokens, branch protection,
  and approval gates;
- a reusable shared library model with stable IDs, packs, dependency metadata,
  structural diffs, and deliberate re-pin/upgrade;
- durable, backend-swappable execution with at least one real DB-backed
  production-capable backend path, without changing the composition model;
- worker-fleet supervision with leases, heartbeats, progress signals,
  cancellation, poison-project quarantine, and staggered restart;
- production docs and conformance proving the platform boundaries.

This epic should not weaken the composition contract. It consumes the native
composition layer as the primitive and hardens the world around it.
Platform durability, events, manifests, worker leases, brokers, and reconcile
logic are consumers of the composition contract. They must not become a second
semantic owner for Megaplan routing, loop exits, override behavior, model
routing, suspension, or execute/review decisions.

## Required Anchor

This epic is governed by `docs/arnold/megaplan-native-representation-report.md`.
The composition epic should make Megaplan look like the report; this platform
epic makes that shape safe for real long-running agent work.

`docs/arnold/megaplan-native-representation-alignment-plan.md` is the required
enforcement plan. Platform milestones must cite the matrix rows they affect and
rerun structural alignment checks after durability, broker, worker, and
reconcile changes.

Platform work must preserve the visible-native Megaplan semantics while adding
production guarantees: durable checkpoints, DB-backed resume, side-effect
fences, brokered credentials, approval gates, cancellation, worker leases,
audit lookup, and reconcile-on-resume. If platform machinery requires hiding
workflow semantics back inside product handlers, that is a regression against
the report and must fail the epic's conformance gate.

Platform work must also preserve the native-Python authoring contract delivered
by the composition epic. The canonical Megaplan workflow and its subworkflows
must remain ordinary Python orchestration: branches, loops, function calls,
subworkflow calls, typed outcomes, and declared policies. Platform durability,
brokerage, manifests, reconcile hooks, worker leases, and event streams are
consumers of that source; they may not replace it with a Python-shaped graph
wrapper, generic component registry, route table, or handler-dispatch skeleton.
The canonical authoring source remains `workflow.pypeline`; any `workflow.py`
compatibility shim remains non-semantic after platform hardening.

## Done Means

- Production-covered side effects are idempotent, auditable, and reconciled on
  resume before execution continues.
- Production-covered credentialed actions go through a broker; raw credentials
  are not visible to the agent process through env vars, config files, logs, or
  broker responses.
- Approval-gated operations can durably pause, resume, deny, or cancel across
  process death.
- Shared packs use stable IDs, lockfile pins, transitive dependency queries,
  cycle/depth checks, structural diffs, and deliberate re-pin/upgrade.
- The native runtime has a real DB-backed durable backend path for checkpoints,
  trace indexes, audit refs, human waits, and resume/reattach.
- Worker supervision enforces ownership leases, capacity gates, stuck-run
  escalation, cancellation, poison-project quarantine, and staggered restart.
- A single end-to-end conformance scenario exercises composition, packs,
  brokered credentials, approval pause/resume, DB-backed durability, reconcile,
  audit lookup, worker lease, cancellation, and stuck-run escalation.
- The production conformance scenario includes a Megaplan-native-representation
  alignment check proving that platform hardening did not collapse report-level
  workflow structure back into opaque handlers or runtime side effects.
- The production conformance scenario reruns the native-Python anti-wrapper
  check proving that platform hardening did not turn canonical Megaplan back
  into component calls, route tables, handler refs, generic stage dispatch, or
  manifest/node builders as the author-facing control-flow skeleton.
- The platform conformance pass reruns the handler-purity inventory and
  structural conformance checks from
  `docs/arnold/megaplan-native-representation-alignment-plan.md`.

## Still Not Done

- Graph visualization UI, hot migration of already-running workflows across
  incompatible versions, automatic propagation of shared-unit updates, and
  multi-region distribution remain deferred unless a later epic explicitly
  takes them on.
