---
superseded_by: custody-control-plane
---

# M3 - Failure-Triggered Repair

## Objective

Start repair soon after known bad states without waiting for the hourly watchdog, while preserving the same fixer of record: the bounded one-hour repair loop. Runtime hooks must enqueue small repair requests and return; they must not run long repair synchronously.

This milestone must also absorb the live cloud failures found while launching this
epic. Those fixes overlap with failure-triggered repair because they decide
whether a trigger sees a real failure, a live orphaned runner, or a PR-merge
advancement case. Treat the current hotfixes as acceptance examples, then make
them durable and general rather than one-off scripts.

## Files And Areas To Change

- `arnold_pipelines/megaplan/cloud/repair_requests.py`
  - Add immutable request writer, dedupe key, queue scanner, stale/superseded rejection, busy/coalesced events, and redacted root-cause hint hashing.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
  - Read queue, resolve current target, acquire shared lock, coalesce duplicates, dispatch the normal repair loop or watchdog one-shot path.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
  - Scan the request queue at the start of `scan_once()` so systemd path installation is not the only trigger.
  - Preserve process-aware liveness in the no-tmux path: a matching `chain start --spec`, `epic-chain start --spec`, or active plan worker must classify as alive before any waiting/stopped/relaunch decision.
  - When `awaiting_pr_merge` is observed under auto policy, reconcile GitHub PR state, local chain state, and local git object availability before deciding whether to merge, advance, or queue repair.
- `arnold_pipelines/megaplan/cloud/cli.py`
  - Make `cloud chains` and `cloud status --chain` report marker, tmux, process, and active-step evidence separately.
  - Exclude watchdog progress/repair sidecar JSON files from canonical chain-session listings.
- `arnold_pipelines/megaplan/chain/__init__.py`
  - Make completion guard PR-target diffing fetch missing remote objects and retry before blocking on `fatal: bad object`.
  - Ensure a merged PR can advance the chain even when the local checkout did not yet have the merge commit.
- Chain/workspace hygiene:
  - Move or ignore runtime chain state/log artifacts so `.megaplan/initiatives/<initiative>` remains a clean committed source tree.
  - Remove any need for operator-only workarounds such as manual remote spec edits, `git update-index --assume-unchanged`, or hand-fetching PR refs.
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
  - status/listing tests for marker-only live chain processes and filtered sidecar markers.
  - completion-guard tests for missing PR merge objects fetched from origin before diffing.
  - end-to-end-ish watchdog tests for merged/open PR state reconciliation under auto policy.

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
- Missing tmux plus live chain/process evidence is observed as alive, not stopped, and does not dispatch duplicate repair.
- `cloud chains` shows one canonical row per real chain session and does not count `.repair-progress.json` or `.chain-health.progress.json` sidecars as sessions.
- A merged milestone PR advances automatically under auto policy after fetching any missing merge/head commit object required by completion guards.
- Tracked runtime artifacts no longer dirty initiative sources or block `git_tracked` launch preconditions.
- The exact live case is covered: M1 PR merged on GitHub, local chain state stale/open, merge commit absent locally, and the next watchdog/trigger pass fetches, reconciles, and advances without a human.

## Guardrails

- Do not add broad backend/guardian hook coverage until this narrower path has proven stable.
- Do not run repair directly inside state writers or event emitters.
- Do not enable systemd-only triggering as the sole mechanism.
- Do not use local-index hiding (`assume-unchanged`) as a product fix; runtime artifacts must live outside committed source paths or be ignored by design.
