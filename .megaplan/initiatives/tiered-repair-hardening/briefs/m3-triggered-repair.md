# M3 - Failure-Triggered Repair

## Objective

Start repair soon after known bad states without waiting for the hourly watchdog, while preserving the same fixer of record: the bounded one-hour repair loop. Runtime hooks must enqueue small repair requests and return; they must not run long repair synchronously.

## Files And Areas To Change

- `arnold_pipelines/megaplan/cloud/repair_requests.py`
  - Add immutable request writer, dedupe key, queue scanner, stale/superseded rejection, busy/coalesced events, and redacted root-cause hint hashing.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
  - Read queue, resolve current target, acquire shared lock, coalesce duplicates, dispatch the normal repair loop or watchdog one-shot path.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
  - Scan the request queue at the start of `scan_once()` so systemd path installation is not the only trigger.
- Optional systemd units:
  - `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.path`
  - `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service`
- Highest-signal hooks only:
  - `arnold_pipelines/megaplan/auto.py::_record_lifecycle_failure()`
  - `arnold/pipeline/steps/human_gate.py::HumanGateStep.run()` for mechanical clarification gates / `awaiting_human_verify`
- Tests:
  - `tests/cloud/test_repair_requests.py`
  - wrapper adapter tests for trigger dispatch/coalesce/stale suppression
  - focused hook tests that assert request file content only.

## Feature Flags

- `REPAIR_REQUESTS_OBSERVE_ONLY` or equivalent: hooks write observable requests but trigger dispatch is disabled.
- `REPAIR_TRIGGER_ENABLED` or equivalent: repair-trigger dispatch can be enabled after queue/dedupe tests pass.

## Verifiable Completion Criterion

- Duplicate failure events coalesce without rewriting immutable request records.
- Timestamp drift does not fragment the same incident.
- Distinct redacted root-cause hints do not collapse into one incident.
- Stale parent requests are rejected by resolver evidence.
- Concurrent hourly and failure-triggered repair contend on the shared lock; only one mutates.
- `latest_failure` and `awaiting_human_verify` hooks write request markers and return quickly.
- Watchdog polling path can process a queued request even if systemd path is absent.

## Guardrails

- Do not add broad backend/guardian hook coverage until this narrower path has proven stable.
- Do not run repair directly inside state writers or event emitters.
- Do not enable systemd-only triggering as the sole mechanism.
