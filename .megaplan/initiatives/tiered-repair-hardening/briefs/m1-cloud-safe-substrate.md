---
superseded_by: custody-control-plane
---

# M1 - Cloud-Safe Repair Substrate

## Objective

Create the minimum safe substrate for all later repair layers: a backward-compatible repair evidence contract, current-target resolver in observe mode, shared repair lock, redaction API, escalation ledger skeleton, feature flags, and a rollback-capable cloud runbook. This sprint must not introduce new autonomous repair behavior beyond richer evidence and observe-only decisions.

## Files And Areas To Change

- `arnold_pipelines/megaplan/cloud/repair_contract.py`
  - Add JSON/NDJSON helpers for mutable current snapshots, immutable incident/attempt records, repair event append, validation, legacy loading, atomic writes, and redacted summaries.
  - Preserve existing repair-data keys for old watchdog/auditor readers.
- `arnold_pipelines/megaplan/cloud/current_target.py`
  - Add a minimal resolver over marker JSON, plan state, chain state, tmux/process evidence, event cursors, needs-human sidecars, repair-progress sidecars, and sibling sessions.
  - Return `target_id`, authoritative source, ignored artifacts, rationale, current plan/chain refs, and event cursors.
  - Wire initially in observe mode only.
- `arnold_pipelines/megaplan/cloud/repair_lock.py`
  - Add atomic mkdir-style lock with owner metadata, target id, pid, command, started timestamp, timeout, stale inspection, and context-manager/helper API.
  - Do not silently delete stale locks; record evidence.
- `arnold_pipelines/megaplan/cloud/human_blockers.py` or `repair_contract.py`
  - Add the first true-human-blocker classifier and escalation ledger writer skeleton.
  - Convert `<session>.needs-human.json` into a current pointer shape while preserving compatibility.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
  - Emit additive contract fields through embedded Python without changing repair decisions.
  - Record resolver output in repair data.
  - Pass prompt-visible and human-visible snippets through redaction before persistence or dispatch.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
  - Use resolver output for diagnostics/observe-only reporting where practical.
  - Keep existing stale sidecar and sibling-session behavior unchanged unless the new resolver exactly agrees.
- `docs/ops/tiered-repair-implementation-plan.md`
  - Update sprint/runbook notes if implementation choices differ from the plan.
- `docs/cloud.md` or `docs/ops/recovery-runbooks.md`
  - Add preflight/rollback steps for wrapper refresh, feature flag disablement, old sidecar compatibility, and repair lock cleanup/drain.
- Tests:
  - `tests/cloud/test_repair_contract.py`
  - `tests/cloud/test_current_target.py`
  - `tests/cloud/test_repair_lock.py`
  - focused additions to `tests/cloud/test_watchdog_wrappers.py`
  - redaction tests for Discord/prompt/report-shaped payloads.

## Feature Flags

Introduce flags or equivalent config so behavior-changing paths can stay off:

- contract writing can be additive and safe by default;
- resolver enforcement remains off or observe-only;
- escalation ledger write can be enabled only after tests pass;
- trigger/meta/auditor autonomy remains disabled.

## Verifiable Completion Criterion

- New contract helpers validate legacy and new repair-data.
- Resolver returns deterministic records for live child, active plan, stale parent, stale needs-human, and missing state fixtures.
- Lock tests prove exactly one actor acquires the lock and losing actors report busy without mutating.
- Redaction tests cover API keys, bot tokens, auth headers, command lines, env-shaped strings, stderr, and event payloads.
- Existing watchdog and repair-loop characterization tests still pass.
- A local fixture `arnold-watchdog --once` or wrapper-equivalent scan records resolver evidence without altering repair decisions.
- Cloud rollback/preflight doc exists.

## Guardrails

- Do not enable failure-triggered repair yet.
- Do not change model/provider order in the repair loop.
- Do not delete or rewrite historical needs-human or repair-progress sidecars.
- Do not add broad wrapper refactors; keep extraction to the new Python modules and small embedded calls.
