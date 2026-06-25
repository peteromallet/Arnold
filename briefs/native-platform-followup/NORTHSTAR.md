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

## Still Not Done

- Graph visualization UI, hot migration of already-running workflows across
  incompatible versions, automatic propagation of shared-unit updates, and
  multi-region distribution remain deferred unless a later epic explicitly
  takes them on.
