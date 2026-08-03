# a03-s04-retry-effect-budgets-execute: retry-effect-budgets × execute

## Verdict

FAIL. The repository has strong effect/WBC primitives, but execute does not enforce one durable occurrence-wide budget and idempotency identity across provider retry, repair, delegation/fallback, compensation, escalation, and completion replay.

Highest risk is P0 authority mutation: configured provider fallback can redispatch after an external provider may already have acted. Additional P0/P1 issues cause effect-key divergence, missing shared budgets, stale ownership, and replay/status mutation without WBC proof.

## Intended canonical contract

The canonical effect contract is `arnold/workflow/effect_protocol.py:1-30,140-153`:

- reserve one global logical effect identity;
- persist durable intent before provider dispatch;
- pass one provider idempotency key;
- accept exactly one terminal outcome through CAS;
- permit redispatch only with the same provider key or authoritative `NOT_APPLIED` reconciliation plus fenced transfer;
- treat `UNKNOWN`, query failure, or missing provider capability as indeterminate/no-dispatch (`arnold/workflow/effect_protocol.py:342-400`).

The execute-specific WBC adapter is the canonical dispatch wrapper: deterministic dispatch/attempt identity (`arnold_pipelines/megaplan/execute/wbc.py:60-99`), durable start/terminal events, and SQLite storage (`arnold_pipelines/megaplan/execute/wbc.py:203-237`; `arnold_pipelines/megaplan/custody/common_worker_dispatch.py:86-161`).

No canonical occurrence-wide retry/repair/delegation/effect budget exists. `GovernorBudget` only tracks cost, seconds, and tokens (`arnold/kernel/governor.py:16-23,92-117`); `RunEnvelope.retry_budget` is only a carrier (`arnold/runtime/envelope.py:77-119`) and has no execute consumer found by search. `BudgetAuthority` tracks cost keyed by `(lease_id,fencing_token)` (`arnold_pipelines/megaplan/runtime/budget_authority.py:1-18,123-163`), not occurrence-wide attempts/effects.

## Evidence and complete path inventory

I searched with `rg --files`, then `rg -n` across `arnold`, `arnold_pipelines/megaplan`, `tests`, and `docs` for `retry`, `budget`, `idempotency`, `occurrence`, `dispatch`, `active_step`, `effect`, `worker`, `repair`, `delegation`, `redispatch`, and all relevant function names. I inspected definitions, writers, readers, callers, consumers, and tests with `nl -ba`.

Inventory:

- Execute handler establishes ownership, invokes batch/auto execution, then clears the original run ID (`arnold_pipelines/megaplan/handlers/execute.py:848-939`).
- `_run_and_merge_batch` creates one deterministic dispatch identity and one WBC dispatch spec (`arnold_pipelines/megaplan/execute/batch.py:2749-2797`), then calls configured provider fallback (`arnold_pipelines/megaplan/execute/batch.py:2941-2956`).
- Fallback loops providers and reuses the same `wbc_dispatch` object (`arnold_pipelines/megaplan/execute/batch.py:1292-1338`). It only compares local workspace fingerprints before redispatch (`arnold_pipelines/megaplan/execute/batch.py:1339-1369`).
- `run_step_with_worker` has a legacy bypass when `wbc_dispatch is None` (`arnold_pipelines/megaplan/workers/_impl.py:6796-6848`); with WBC it wraps the entire legacy callback (`arnold_pipelines/megaplan/workers/_impl.py:6850-6876`).
- Provider calls and execute-specific retry suppression are in `arnold_pipelines/megaplan/workers/_impl.py:7091-7228,6491-6607`. JSON repair recursively calls the provider again (`arnold_pipelines/megaplan/workers/_impl.py:5768-5833`).
- Batch completion writes artifacts and `finalize.json` directly (`arnold_pipelines/megaplan/execute/batch.py:3230-3235`); merge mutates task authority fields directly (`arnold_pipelines/megaplan/execute/merge.py:803-844`).
- Existing WBC result validation is present (`arnold_pipelines/megaplan/execute/merge.py:1133-1163,550-607`), but replay explicitly disables WBC validation (`arnold_pipelines/megaplan/execute/batch.py:2056-2091`).
- The generic backend writes node/effect/budget events, executes registry effects, compensates, escalates, and redispatches (`arnold/execution/backend.py:352-410,972-1075,1187-1210,1382-1494,1647-1879`).
- Tests cover isolated retry, compensation, escalation, and WBC protocol behavior (`tests/arnold/execution/test_runner.py:100-145`; `tests/arnold/execution/test_compensation_escalation.py:137-184,245-317`; `tests/m10/test_fault_matrix_replay_migration.py:324-390`), but not their shared occurrence-wide budget.

## Adherence gaps

1. **P0 — authority mutation: provider fallback bypasses effect redispatch gates.**  
   Fallback catches a retryable provider error, proves only that the local checkout is unchanged, and invokes the next provider inside the same WBC attempt (`arnold_pipelines/megaplan/execute/batch.py:1321-1358`). The WBC wrapper records one start and one terminal around the whole callback (`arnold_pipelines/megaplan/custody/common_worker_dispatch.py:86-150`); it does not create per-provider effect identities or call `EffectProtocol.can_redispatch`. An external provider can therefore apply remotely, return an error, leave the local fingerprint unchanged, and be followed by another provider dispatch. This is an inference from the reachable control flow; actual provider behavior is an unknown.

2. **P0 — authority mutation: generic effects bypass the canonical protocol.**  
   `LocalJournalBackend._wbc_effect_protocol()` returns `None` by default (`arnold/execution/backend.py:401-410`), so `_run_effect` persists journal intent and calls `EffectRegistry.execute` directly (`arnold/execution/backend.py:1423-1488`; `arnold/execution/registries.py:146-164`). The canonical protocol’s durable outbox, authority/custody checks, provider capability checks, and reconciliation are therefore absent. The execute-specific `ExecuteEffectGate` exists (`arnold_pipelines/megaplan/execute/effect_gate.py:102-127,168-263`) but has no production caller found by the call-site search; execute imports WBC, not this gate (`arnold_pipelines/megaplan/execute/batch.py:93-102`).

3. **P1 — authority mutation/idempotency divergence: inherited node policy is lost.**  
   `_run_effect` correctly falls back to the node’s idempotency policy for validation (`arnold/execution/backend.py:1396-1405`), but derives its journal key only from `effect_ref.idempotency` (`arnold/execution/backend.py:1423-1429`). `_execute_effect` separately derives the provider key using the inherited policy (`arnold/execution/backend.py:360-375`). Thus the durable journal key and provider key can differ for effects inheriting node policy.

4. **P1 — authority mutation: compensation key is recorded but not dispatched.**  
   Compensation records `step.idempotency_key` in its intent and terminal events (`arnold/execution/backend.py:1647-1695`), then calls `_execute_effect`, which derives a normal effect key instead (`arnold/execution/backend.py:1697`; `352-375`). Compensation also has no governor reservation or shared retry budget (`arnold/execution/backend.py:1730-1813`).

5. **P1 — authority mutation: escalation bypasses normal routing and occurrence accounting.**  
   `_execute_escalation_target` constructs a fresh `RouteCoordinate` with default attempt 1 and directly calls `_execute_coordinate` (`arnold/execution/backend.py:1815-1843`). Escalation admission uses only `coordinate.attempt >= max_attempts` (`arnold/execution/escalation.py:38-69`) and journals `escalation_routed` without an idempotency key (`arnold/execution/backend.py:1863-1879`). The existing test confirms same-node escalation can execute again and suppress terminal failure (`tests/arnold/execution/test_compensation_escalation.py:278-317`).

6. **P1 — status misreporting and retry-budget corruption.**  
   Effect failure emits `node_failed` without `attempt` or `iteration` (`arnold/execution/backend.py:1190-1209`), while routing defaults missing values to attempt 1 (`arnold/execution/routing.py:83-106`). A failure on a later retry can therefore be projected as the first attempt.

7. **P1 — status/ownership misreporting.**  
   Tiered execute calls `set_active_step` without the outer `run_id` (`arnold_pipelines/megaplan/execute/batch.py:3721-3730,5734-5747`). `set_active_step` generates a new UUID when omitted (`arnold_pipelines/megaplan/_core/state.py:1894-1963`), while the handler later clears only the original ID and refuses mismatches (`arnold_pipelines/megaplan/_core/state.py:1994-2002`). Tiered runs can leave stale active ownership after completion.

8. **P1 — authority mutation: restart replay bypasses WBC.**  
   `_replay_proven_batch_artifacts` explicitly passes `require_dispatch_wbc=False` (`arnold_pipelines/megaplan/execute/batch.py:2080-2091`), and the validator skips WBC checks when authority metadata is absent (`arnold_pipelines/megaplan/execute/merge.py:1148-1154`). Existing artifacts can consequently mutate current task status without a current durable dispatch/attempt proof.

9. **P2 — enforcement gap: canonical execute WBC is action-off.**  
   The adapter hard-codes `PromotionMode.ACTION_OFF`, with enforcement defaulting false (`arnold_pipelines/megaplan/execute/wbc.py:203-237`). This is currently status/evidence-only, but it leaves no enforced production action boundary.

## Incident reachability and severity

The P0 fallback path is reachable from normal execute dispatch (`batch.py:2790-2797,2941-2956`). If a provider mutates an external target and then reports a retryable failure, the local fingerprint guard does not detect it; fallback can invoke another provider. This is an inferred duplicate-side-effect path, currently constrained by M10 action-off settings but unsafe if real provider execution is enabled.

The stale active-step and missing-attempt defects are deterministic status failures. The replay and compensation defects can mutate durable task/effect authority without the same occurrence-wide key.

## Minimal generalized remediation

Consolidate on `EffectProtocol`/`SqliteAttemptLedgerStore` for every execute provider, repair, fallback, compensation, escalation target, and publication effect. Extend its durable store with an occurrence budget reservation covering retry, repair, delegation, and effect counts, plus one stable provider key per logical effect.

Then:

- create one WBC/effect attempt per provider dispatch, not one around a multi-provider callback;
- require reconciliation and `can_redispatch` before fallback;
- pass the resolved idempotency policy through all key derivations;
- dispatch compensation using its declared key;
- enqueue escalation as a durable routed child occurrence instead of direct `_execute_coordinate`;
- pass the original active-step `run_id` through tier changes;
- include attempt/iteration in every lifecycle event;
- remove `require_dispatch_wbc=False` after quarantining or migrating legacy artifacts.

This is narrower than a rewrite: it preserves existing WBC identity, merge validation, journal, and SQLite stores while eliminating bypass seams.

## Required tests and retirement proof

Add deterministic tests for:

- concurrent same-key dispatch from two processes/containers: one reservation and one provider call;
- crash after provider apply before terminal, restart, `APPLIED`, `NOT_APPLIED`, `UNKNOWN`, query failure, and missing-provider-capability cases;
- provider mutates externally then returns retryable failure: fallback must not redispatch without authoritative reconciliation;
- repair retry, provider fallback, compensation, and escalation all consume one shared occurrence budget;
- inherited node idempotency policy produces identical journal/provider keys;
- effect failure on retry preserves attempt/iteration;
- tiered execute clears the original active-step ownership;
- replayed artifacts without valid WBC evidence are quarantined;
- shared SQLite/file-lock behavior across PID namespaces/two containers and stale-fence rejection.

Retirement proof must include an AST/`rg` gate showing no execute caller passes `wbc_dispatch=None`, no `require_dispatch_wbc=False` mutation path remains, no direct provider call exists outside the canonical adapter, and old fallback/compensation/escalation implementations are deleted or unreachable. Tests should monkeypatch every provider sink and assert exactly one canonical dispatch per logical effect.

## Unknowns

The snapshot does not establish whether real configured providers can mutate externally before returning an error, nor whether M10 action-off is enabled in every deployment. It also does not prove whether replayed legacy artifacts are intentionally exempt during migration. Two-container behavior depends on the deployment sharing the execute SQLite ledger and filesystem lock domain.