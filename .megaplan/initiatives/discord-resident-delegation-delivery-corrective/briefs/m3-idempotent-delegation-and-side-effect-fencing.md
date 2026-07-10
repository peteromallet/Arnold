# M3 — Request-Idempotent Delegation and Side-Effect Fencing

## Outcome

Make delegated-agent launch and execution unique by resident request id, with durable claim/lease/fence semantics that prevent duplicate execution and reject stale-worker side effects across retries and restarts.

## Scope

In scope: ledger-backed launch intent and execution identity; atomic get-or-create/claim; run-manifest projection; durable launch receipt; lease renewal/reclaim; fencing at execution result and side-effect boundaries; duplicate caller convergence; ambiguous launch recovery; compatibility with existing `arnold-resident-agent-run-v1` and readable legacy manifests. Keep the sprint within roughly two human-weeks.

Out of scope: redesigning the Codex CLI runner, outbound Discord delivery, deleting legacy manifests, or generalizing fencing to all Arnold workflows.

## Locked decisions

- `request_id` is the logical delegation idempotency scope; a new attempt id may exist without creating a second logical execution.
- Checking for an existing directory/manifest is insufficient; uniqueness and claims are durable transactional ledger operations.
- Every committing worker presents the current fence/version. Expired or superseded workers cannot commit results or downstream intents.
- Manifests and `result.md` remain durable evidence/compatibility surfaces but project from ledger identity/state.

## Open questions for the plan

- Which exact point counts as external launch commitment when process creation succeeds but receipt persistence is interrupted?
- How can recovery distinguish an orphaned live process from a safe relaunch without trusting PID alone?
- Which delegated tools/effects beyond terminal result persistence require explicit fence checks in this resident-specific scope?

## Constraints

Preserve sealed stdin, explicit model/reasoning configuration, target workspace, secret handling, and resident-vs-workflow subagent distinction. Concurrent duplicates must converge without busy-looping.

## Done criteria and acceptance evidence

- Concurrent callers using one request id produce one logical execution record and at most one authorized agent execution.
- Crash/timeout tests cover intent-before-spawn, spawn-before-receipt, receipt-before-manifest projection, running lease expiry, and result commit.
- A stale worker cannot publish a result, create terminal delivery intent, or mark the request terminal after its fence is superseded.
- Duplicate legacy/current manifests are reconciled deterministically and surfaced, not silently chosen by path order.
- Existing launcher/status/sweep readers remain compatible and expose the canonical logical execution id plus attempt/fence evidence without secrets.

## Touchpoints

Expected areas: `resident/subagent.py`, resident tool/profile launch handling, process wrapper/manifest code, store APIs, and `tests/resident/test_launch_subagent.py`.

## Anti-scope

Do not broaden resident permissions, introduce remote shell execution, or refactor all process supervision in Arnold.
