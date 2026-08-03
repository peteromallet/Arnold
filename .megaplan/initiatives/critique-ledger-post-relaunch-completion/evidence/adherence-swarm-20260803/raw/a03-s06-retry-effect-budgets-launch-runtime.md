# a03-s06-retry-effect-budgets-launch-runtime: retry-effect-budgets × launch-runtime

## Verdict

Fail. No P0 is proven from static evidence, but there are four P1 authority-mutation gaps and two P2 status/duplication gaps.

Repair claims are durable and singleton-admitted, but the mutation budget is process/session-local. Resident and cloud launch retries use separate counters and keys, and watchdog fallback relaunches bypass the shared repair/effect budget. Existing effect-protocol and occurrence-key implementations are not wired across launch-runtime.

## Intended canonical contract

The intended contract should be:

1. Normalize one occurrence identity into one durable occurrence key. The F01 repair key already exists in `repair_requests.py:100-114`, and its claim lock is keyed by that fingerprint at `repair_requests.py:613-624`.
2. Reserve one durable occurrence-wide budget/effect record before mutation, delegation, child launch, or runtime relaunch.
3. Replays and retries reuse the same logical effect key. Provider/model/runtime details belong in provenance, not in the occurrence key.
4. A lost acknowledgement is retryable only with the same provider idempotency key or authoritative `NOT_APPLIED` reconciliation. This is already the WBC contract in `arnold/workflow/effect_protocol.py:1-29`.
5. Exhaustion and unknown outcomes are durable status projections, never fresh authority.

Canonical pieces exist, but no single cross-surface implementation exists:

- Repair authority: `cloud/simple_fixer.py:1-29`.
- Repair delegation funnel: `cloud/wrappers/repair_delegation.py:218-245`.
- Durable effect/idempotency protocol: `arnold/workflow/effect_protocol.py:140-153`.
- Durable managed-launch deduplication: `resident/subagent.py:3751-3793`.

`runtime/budget_authority.py:1-18,123-163` is durable and idempotent, but its key is `(lease_id, fencing_token)` and launch-runtime callers do not use it; only loop attribution calls it at `megaplan/loop/engine.py:108-136`.

## Evidence and complete path inventory

I searched with `rg --files`, then recursive `rg` over `arnold_pipelines`, `arnold`, `tests`, `docs`, and `scripts` for `retry`, `budget`, `attempt`, `idempot`, `effect`, `delegate`, `launch`, `spawn`, `tmux`, `container`, `PID namespace`, `provider`, `profile`, and `provenance`. I separately searched definitions and call sites for `MutationBudget`, `delegate_to_simple_fixer`, `launch_subagent_task`, managed-launch functions, cloud tmux launchers, and retry lineage fields.

Observed writers/readers/callers/consumers:

- `simple_fixer.MutationBudget.record_mutation` mutates only in-memory counters at `cloud/simple_fixer.py:411-465`; `SimpleFixerSession.__post_init__` creates a fresh budget at `cloud/simple_fixer.py:473-493`, and `CanonicalRunner.run` creates a fresh session when absent at `cloud/simple_fixer.py:839-872`.
- `delegate_to_simple_fixer` claims, constructs a fresh session, runs, and releases the occurrence claim at `cloud/wrappers/repair_delegation.py:274-314`. Its truth firewall treats `unchanged`/`exhausted` as non-authoritative at `:316-340`.
- Repair request IDs and occurrence claims are durable at `cloud/repair_requests.py:669-694,1596-1628`.
- Repair-contract projections independently calculate `max_attempts`, `used_attempts`, and `remaining_attempts` at `cloud/repair_contract.py:1489-1494,1543-1557`.
- Progress-auditor escalation independently applies deterministic and launch-establishment budgets at `cloud/progress_auditor_escalation.py:63-74,1159-1237`; it persists separate retry lineage at `:1395-1435`. The controller passes that lineage into queued repairs at `cloud/progress_auditor_controller.py:658-670`.
- Repair goals count owners/manifests to allocate retry sequence, but do not enforce a shared budget at `cloud/repair_goal.py:99-119,1094-1124`.
- Resident schedules persist occurrence attempts and independently retry launches at `resident/schedules.py:1221-1270`.
- Managed launches persist queue attempt counts and retry limits at `resident/subagent.py:4007-4059,5589-5654`.
- Managed launch idempotency includes provider/model and `retry_of_run_id` at `resident/subagent.py:3751-3777`; the manifest records that key at `:3948-3960`.
- Callers include schedules (`resident/schedules.py:1221-1228`), profile delegation (`resident/profile.py:3272-3300`), resident CLI queueing (`resident/cli.py:495-504`), human-review diagnostics (`cloud/human_review_diagnostic.py:571-582`), and the public `launch_subagent_task` seam (`resident/subagent.py:7509-7544,7587-7626`).
- Local and SSH providers both consume cloud launch commands through provider execution, but neither adds occurrence budgeting: Docker Compose execution is `cloud/providers/local.py:138-151`; SSH Docker execution is `cloud/providers/ssh.py:2688-2703`.
- Cloud chain and epic-chain launchers are separate provider/marker/persistence flows at `cloud/cli.py:5171-5253` and `:5642-5722`.

## Adherence gaps

1. **P1 — authority mutation: simple-fixer budget resets across delegation/restart/container.**  
   The documented “occurrence-scoped” budget is only a Python object (`cloud/simple_fixer.py:411-465`). Every delegation creates a new one (`cloud/wrappers/repair_delegation.py:301-314`). The occurrence claim prevents concurrent ownership, but release permits a later caller to receive a fresh two-try budget. `rg` found no production reader/writer of `MutationBudget.to_dict()` beyond its definition/tests. Existing tests only exercise in-memory budgets and explicitly construct fresh budgets at `tests/cloud/test_simple_fixer.py:281-344,361-369`.

2. **P1 — authority mutation: resident retry/idempotency is not occurrence-wide.**  
   The managed launch key changes with `backend`, model, and `retry_of_run_id` (`resident/subagent.py:3751-3777`), so a retry or provider switch is a new idempotency identity. Queue retry counts are per manifest successor (`:4007-4059,5589-5654`), not shared with repair, schedule, or escalation budgets. [Inference] A lost acknowledgement or surviving worker can therefore produce a second provider worker under a different key. The workers are explicitly full-permission-capable (`resident/subagent.py:3914-3920`).

3. **P1 — authority mutation: callers can bypass occurrence identity.**  
   `launch_managed_subagent_detached` falls back to `stable_identity("task", task_digest)` when no request ID exists (`resident/subagent.py:3738-3745`). Resident CLI queueing supplies neither request ID nor schedule occurrence (`resident/cli.py:495-504`); human-review diagnosis uses an escalation ID rather than the F01 occurrence and permits `mutation_claim="auto"` (`cloud/human_review_diagnostic.py:575-582`). These paths reach the common launcher but do not prove membership in the same repair/effect budget.

4. **P1 — authority mutation: watchdog direct relaunch bypasses the canonical budget.**  
   `arnold-watchdog` explicitly returns control for direct tmux fallback when repair is unavailable or has exited (`cloud/wrappers/arnold-watchdog:7557-7561,7588-7632`). The caller then resolves a relaunch command and starts a new supervised tmux session (`:8962-9015,9028-9061`), including a direct `chain start` command (`:4211-4213`). The “non-authoritative” gate only prevents accepting relaunch success as repair (`:4242-4249`); it does not budget or idempotently fence the runtime side effect.

5. **P2 — status misreporting: configured schedule cost/token limits are not accounted.**  
   If any cost/token quota is configured, the scheduler immediately dead-letters with `accounting_unavailable_fail_closed` (`resident/schedules.py:1139-1142`) instead of consuming or reporting a shared occurrence budget.

6. **P2 — duplicated cloud launch lifecycle.**  
   Chain and epic-chain launchers separately execute, verify, persist outcomes, and emit provenance (`cloud/cli.py:5171-5253,5642-5722`). No shared occurrence budget call is visible at either seam. Divergent future behavior is inferred, not proven; the duplication itself is observed.

The unreachable compatibility `Popen` block in `arnold-repair-trigger` is not counted as a gap: `meta_dispatch` is assigned `False` at `cloud/wrappers/arnold-repair-trigger:512-518` and is not reassigned in the searched function.

## Incident reachability and severity

The simple-fixer gap is directly reachable through repeated delegation, process restart, or separate containers because the claim is durable but the budget is not. The watchdog gap is reachable after repair dispatch failure or an exited repair loop. The resident gap is reachable through queue retry, provider change, or retry lineage.

These are authority-mutation risks, not merely incorrect labels. No static evidence proves a duplicate production mutation has already occurred, so P1 is appropriate rather than P0. The schedule accounting issue is fail-closed but reports a terminal state unrelated to actual budget consumption, hence P2 status misreporting.

## Minimal generalized remediation

Extend the existing SQLite/WBC effect substrate rather than creating another counter:

- Add one durable occurrence-budget/effect reservation keyed by the normalized F01 occurrence and effect family.
- Make `delegate_to_simple_fixer` reserve/consume that record; make `MutationBudget` a read-only projection, eliminating fresh per-session authority.
- Require occurrence context for mutation-capable `launch_subagent_task` calls. Keep provider/model/runtime in provenance; remove `retry_of_run_id` and provider fields from the logical occurrence idempotency key.
- Route schedule, profile, escalation, cloud CLI, and watchdog relaunches through one launch-runtime reservation helper.
- Convert repair-contract, progress-auditor, repair-goal, schedule, and managed-queue counters into projections of the shared record. Retire their independent mutation gates after migration.
- Delete the watchdog direct fallback or make it impossible to execute without the same reservation. Consolidate chain and epic launch lifecycles behind one helper.

Retirement proof must include source searches showing no direct `tmux new-session` or managed spawn outside the canonical helper, no fresh `MutationBudget()` in delegation/runtime paths, and no independent retry-budget authority remaining.

## Required tests and retirement proof

- Two concurrent processes/containers reserving the same occurrence: exactly one mutation/launch and one durable budget increment.
- Restart after one or two unchanged mutations: a new process observes the prior exhaustion.
- Lost provider acknowledgement: retry reuses the same provider key; unknown/query failure remains action-off.
- Local and SSH providers, plus Hermes/Codex/Claude profiles: identical logical key and shared budget; provider metadata remains provenance only.
- Schedule, profile, human-review, escalation, watchdog, and cloud chain/epic callers all require the same occurrence context.
- Mutation/no-op/productive-change sequences verify the shared counter, including repair followed by delegation and delegation followed by relaunch.
- Two-container/PID-namespace tests ensure a foreign PID collision remains unknown and cannot trigger relaunch, matching `cloud/current_target_liveness.py:187-218` and `tests/cloud/test_current_target_liveness.py:37-62`.
- Restart/provenance tests verify one manifest/key and no second worker after reconciliation, extending `tests/resident/test_subagent_restart_persistence.py:23-85`.

## Unknowns

Cloud execution and provider state were not touched, so actual duplicate-worker incidence is unverified. The launch path does not expose a provider-side idempotency contract, and deployment flags may affect watchdog reachability. Those uncertainties do not remove the observed absence of a shared durable occurrence budget or the reachable bypass paths.