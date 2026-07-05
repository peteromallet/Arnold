# Native Platform Operations Runbook

This runbook is for fleet operators. It does not replace product workflow
guidance; it covers platform admission, durability, reconcile, rollout, and
rollback.

## Production Matrix

| Operation | Production-covered path | Local-only path | Operator rule |
| --- | --- | --- | --- |
| Admit run | Create or claim a project lease with owner ID, token, expiry, heartbeat, and durable run ID. | Temporary file-backed lease store. | Refuse admission when an active lease exists. |
| Heartbeat | Extend lease expiry and update progress timestamps. | Fixed-clock heartbeat assertions. | Treat missing heartbeat as takeover candidate, not automatic permission to mutate. |
| Resume after interruption | Load durable state, run reconcile, then continue/skip/block from the reconcile action table. | Synthetic resume cursors in tests. | Reconcile before every continue after process death. |
| Expired takeover | Require expired lease, resume-trust allowance, and reconcile decision before claim. | Fake decisions that model clean/blocked states. | Clock expiry alone is insufficient. |
| Stuck run escalation | Apply restart delay, retry budget, and quarantine policy with manual clear for crash loops. | Deterministic restart policy and temporary state. | Do not spin restart loops without persisted backoff/quarantine. |
| Approval pause/resume | Persist suspension state and resume only from explicit approval result. | In-process fake approval result. | Do not bypass approval gates to unstick a run. |
| Cancellation | Persist terminal cancellation before stopping workers and release/finish the lease as cancelled. | Local transition assertion. | Do not keep mutating after cancellation is visible. |
| Rollout | Run focused local conformance, installed-package conformance, canary, and operator sign-off. | Checkout-only test pass. | Do not enable production fleet-wide from checkout-only evidence. |
| Rollback | Stop new admission, drain or cancel leases, preserve audit/durable state, revert config/code, then reconcile remaining worktrees. | Delete temp state after tests. | Do not delete durable DB/audit state to roll back. |

## Rollout Steps

1. Build the package artifact and run installed-package conformance for
   workflow source, docs, handlers, and fixtures.
2. Pin the exact package artifact and pack dependency set in the rollout
   lockfile. Record the previous pin before any re-pin or upgrade.
3. Run structural diffs for workflow topology, policy attachments, source-path
   reconciliation, and package-resource inclusion before canary admission.
4. Enable broker production mode for a canary with provider proxy configured.
5. Admit a limited set of leased runs and verify heartbeats, reconcile,
   approval gates, audit lookup, and cancellation.
6. Promote only after operator sign-off records the canary evidence.

## Reconciliation Checklist

| Check | Required evidence | Blocks rollout when |
| --- | --- | --- |
| Pack IDs | Every installed shared pack has a stable ID and package-resource path. | A workflow depends on an unpackaged checkout path. |
| Dependency metadata | Pack dependencies list name, version, source distribution, and owner. | Dependency metadata is missing or only implied by imports. |
| Lockfile pins | Rollout records exact wheel filename/hash and pack versions. | The canary runs an unpinned local checkout or editable install. |
| Structural diffs | Workflow topology, policy, source, and fixture diffs are reviewed. | Diff evidence is absent or generated from stale dot paths. |
| Cycle/depth checks | Workflow graph and package dependency graph are checked for unbounded cycles and depth growth. | A new cycle lacks an explicit bounded loop/reentry carrier. |
| Re-pin or upgrade | Operator records why the pin changed and which proof suites were rerun. | A pin changes without installed-wheel conformance evidence. |
| Full design-doc reconciliation | `docs/arnold/native-platform.md` classifies deferred/out-of-scope design items. | A production claim has no proof, owner, or deferral. |

## Rollback Steps

1. Disable new run admission.
2. Let healthy leased runs drain, or persist cancellation for runs that cannot
   finish safely.
3. Preserve durable DB rows and audit records.
4. Revert the feature/configuration change.
5. Run reconcile on any worktree touched by interrupted runs before returning it
   to the pool.
