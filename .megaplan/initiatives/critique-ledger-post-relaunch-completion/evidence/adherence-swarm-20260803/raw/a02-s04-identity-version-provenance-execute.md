# a02-s04-identity-version-provenance-execute: identity-version-provenance × execute

## Verdict

Not adherent. The execute path has a strong canonical identity/WBC implementation, but several callers and compatibility paths bypass it. The most serious gap is authority mutation during restart/replay from scope-only artifacts with WBC validation explicitly disabled.

## Intended canonical contract

The canonical chain is:

`DispatchIdentity` → `SubjectAttempt`/`Claim` → `EvidenceEnvelope` → optional `Decision`, validated by `validate_relationships` and reduced by `reduce_run_authority` ([contracts.py:432-482](arnold_pipelines/run_authority/contracts.py:432), [reducer.py:294-305](arnold_pipelines/run_authority/reducer.py:294)).

Execute extends this with `ResultEnvelope`, which requires dispatch, attempt, claim, evidence, grant, subject, capability, run, revision, coordinator, fence, and CAS consistency ([binding.py:384-426](arnold_pipelines/megaplan/authority/binding.py:384)). Worker completion is guarded by `CommonWorkerDispatchSpec.run`, which records reserve/start/terminal WBC events ([common_worker_dispatch.py:86-145](arnold_pipelines/megaplan/custody/common_worker_dispatch.py:86)).

This contract does not currently carry `runner_incarnation`, launch provenance, or validated provider/session identity. `DispatchIdentity` contains only grant, fence, prerequisite digest, worker ID, and CAS ([binding.py:83-112](arnold_pipelines/megaplan/authority/binding.py:83)); WBC provenance contains actor/tool, adapter, and version data ([wbc.py:171-200](arnold_pipelines/megaplan/execute/wbc.py:171)).

## Evidence and complete path inventory

I searched with `rg` for `DispatchIdentity`, `ResultEnvelope`, `run_step_with_worker`, `set_active_step`, `wbc_dispatch`, `result_envelopes`, raw terminal-status reads, replay functions, provider/fallback fields, `runner_incarnation`, and `launch_provenance` across `arnold_pipelines/run_authority`, `arnold_pipelines/megaplan/{authority,custody,execute,workers,orchestration}`, handlers, and execute/M9 tests.

Writers:

- `set_active_step` writes run ID, invocation ID, attempt, PID, orphan fence, and runner incarnation ([state.py:1894-1963](arnold_pipelines/megaplan/_core/state.py:1894)).
- `_build_dispatch_identity` derives run, revision, coordinator attempt, fence, scope, prerequisite digest, and deterministic worker ID ([batch.py:1594-1634](arnold_pipelines/megaplan/execute/batch.py:1594)).
- `_stamp_result_envelopes` moves prior-fence receipts and writes current envelopes ([batch.py:1852-1961](arnold_pipelines/megaplan/execute/batch.py:1852)).
- Normal dispatch creates WBC before worker execution ([batch.py:2784-2797](arnold_pipelines/megaplan/execute/batch.py:2784)).

Readers/consumers:

- Merge validates dispatch, revision, coordinator, fence, prerequisite digest, worker ID, evidence, CAS, and authority echoes ([merge.py:550-607](arnold_pipelines/megaplan/execute/merge.py:550)).
- `effective_execute_completed_task_ids` prefers accepted envelopes, then falls back to evidence/status compatibility logic ([authority_readers.py:418-434](arnold_pipelines/megaplan/orchestration/authority_readers.py:418), [authority_readers.py:494-523](arnold_pipelines/megaplan/orchestration/authority_readers.py:494)).
- Batch scheduling calls that adapter ([batch.py:974-999](arnold_pipelines/megaplan/execute/batch.py:974)).
- Restart/replay calls the scoped merge path ([batch.py:2056-2107](arnold_pipelines/megaplan/execute/batch.py:2056)).
- Timeout, reducer, prompt, and dependency helpers still read raw statuses ([timeout.py:371-387](arnold_pipelines/megaplan/execute/timeout.py:371), [reducer.py:261-284](arnold_pipelines/megaplan/execute/_binding/reducer.py:261), [prompts/execute.py:159-170](arnold_pipelines/megaplan/prompts/execute.py:159), [batch.py:4407-4421](arnold_pipelines/megaplan/execute/batch.py:4407)).

## Adherence gaps

1. **P0 — Authority mutation: replay disables WBC validation.**

   `_replay_proven_batch_artifacts` invokes scoped merge with `require_dispatch_wbc=False` ([batch.py:2080-2091](arnold_pipelines/megaplan/execute/batch.py:2080)). Merge therefore only validates WBC when authority metadata or WBC is present; a scope-only artifact can still have its task updates merged ([merge.py:1148-1163](arnold_pipelines/megaplan/execute/merge.py:1148)).

   `BatchScope` is explicitly documented as compatibility scope, not authority ([batch_scope.py:217-225](arnold_pipelines/megaplan/authority/batch_scope.py:217)). Nevertheless, the no-pending restart path replays these artifacts into `finalize_data` ([batch.py:5574-5592](arnold_pipelines/megaplan/execute/batch.py:5574]). This permits stale scope/status evidence to mutate terminal task state without run, attempt, incarnation, version, or launch proof.

2. **P1 — Authority mutation: compatibility status fallback can unblock or complete work.**

   Prior artifact `task_updates[].status` is copied into `batch_status_overlay` without validating artifact identity ([batch.py:3580-3618](arnold_pipelines/megaplan/execute/batch.py:3580)). If no accepted-envelope projection exists, `effective_execute_completed_task_ids` explicitly adds explained skips/no-ops based on raw status and notes ([authority_readers.py:508-523](arnold_pipelines/megaplan/orchestration/authority_readers.py:508), [authority_readers.py:923-945](arnold_pipelines/megaplan/orchestration/authority_readers.py:923)). Those IDs feed prerequisite scheduling.

   The route inventory acknowledges these execute routes as `WARN_ONLY`, not enforced ([authority_readers.py:1414-1495](arnold_pipelines/megaplan/orchestration/authority_readers.py:1414)).

3. **P1 — Authority mutation: incarnation, launch, and provider provenance are not bound to completion.**

   Active-step state records PID namespace and process-start identity ([state.py:1933-1941](arnold_pipelines/megaplan/_core/state.py:1933)), and worker launch preflight validates runtime provenance ([workers/_impl.py:7009-7079](arnold_pipelines/megaplan/workers/_impl.py:7009)). Neither is copied into `DispatchIdentity`, `ResultEnvelope`, or the WBC summary.

   Provider fallback reuses the same dispatch/WBC identity across configured providers ([batch.py:1292-1338](arnold_pipelines/megaplan/execute/batch.py:1292)). Actual model/provider data is recorded only as routing observability ([batch.py:3057-3090](arnold_pipelines/megaplan/execute/batch.py:3057), [workers/_impl.py:2308-2342](arnold_pipelines/megaplan/workers/_impl.py:2308)). A completion from a different provider, process incarnation, or PID namespace can therefore satisfy the same run/revision/fence identity. This is an observed missing binding; the stale-completion consequence is an inference from the validator’s accepted fields.

4. **P1 — Status/ownership misreporting: tier routing replaces the active owner, but cleanup uses the original run ID.**

   The handler saves the initial `run_id` and later clears only that ID ([handlers/execute.py:848-855](arnold_pipelines/megaplan/handlers/execute.py:848), [handlers/execute.py:935-939](arnold_pipelines/megaplan/handlers/execute.py:935)). Tier routing calls `set_active_step` without preserving it, generating a new run ID and invocation ([batch.py:3721-3730](arnold_pipelines/megaplan/execute/batch.py:3721), [batch.py:5734-5747](arnold_pipelines/megaplan/execute/batch.py:5734)). `clear_active_step` refuses to clear a mismatched owner ([state.py:1994-2003](arnold_pipelines/megaplan/_core/state.py:1994)). Successful execution can thus leave a stale active owner persisted.

5. **P1 — Status/ownership misreporting: execute has a direct worker bypass.**

   `run_step_with_worker` falls back to `_run_step_with_worker_legacy` when `wbc_dispatch is None` ([workers/_impl.py:6796-6848](arnold_pipelines/megaplan/workers/_impl.py:6796)). The repair-adoption branch constructs a fake worker directly with `auth_metadata=None` instead of running through WBC ([batch.py:2861-2939](arnold_pipelines/megaplan/execute/batch.py:2861)). Current merge fails closed by clearing updates when WBC is missing ([merge.py:1156-1163](arnold_pipelines/megaplan/execute/merge.py:1156), so the observed effect is blocked/misreported completion rather than accepted authority.

6. **P2 — Status-only misreporting: raw diagnostic readers remain.**

   Timeout summaries count raw `done/skipped` rows even while labeling them uncorroborated ([timeout.py:371-387](arnold_pipelines/megaplan/execute/timeout.py:371)). Prompt rerun guidance treats raw terminal labels as completed ([prompts/execute.py:159-170](arnold_pipelines/megaplan/prompts/execute.py:159)). The reducer’s raw reads are currently used for uncorroborated diagnostics, not its completion decision ([reducer.py:261-284](arnold_pipelines/megaplan/execute/_binding/reducer.py:261)). These are not authority mutations but prevent retirement proof.

7. **P2 — Duplicate effect implementation is not used by execute.**

   `ExecuteEffectGate` defines an alternate effect identity/protocol ([effect_gate.py:102-276](arnold_pipelines/megaplan/execute/effect_gate.py:102)). Repository-wide call-site search found no execute caller. It is unreachable duplicate surface and should be deleted or statically fenced.

## Incident reachability and severity

The P0 replay path is reachable whenever execute finds no pending tasks and reloads existing batch artifacts ([batch.py:5574-5592](arnold_pipelines/megaplan/execute/batch.py:5574)). A scope-valid artifact lacking WBC can therefore affect `finalize.json`; this is authority mutation, not merely reporting.

The P1 raw-status path is reachable during per-batch prerequisite calculation and compatibility fallback. The P1 incarnation/provider gaps are reachable on restart, concurrent dispatch, and configured provider fallback. The active-step bug is reachable whenever tier routing changes the model.

## Minimal generalized remediation

Consolidate on `DispatchIdentity`/`ResultEnvelope` plus `CommonWorkerDispatchSpec`:

- Add immutable launch provenance, runner-incarnation digest, provider/model/session binding, and invocation ID to dispatch identity and WBC attempt identity; require exact echoes at merge.
- Make replay require dispatch identity, accepted result envelopes, and verified WBC. Quarantine scope-only artifacts; do not “migrate” them by manufacturing proof.
- Remove positive raw-status fallback. Represent skip/no-op as signed/current authority claims; retain raw labels only for diagnostics.
- Preserve the handler’s original owner ID when changing tier metadata, or provide a model-update operation that does not create a new invocation.
- Run repair adoption through the same WBC path and delete the `wbc_dispatch=None` execute route.
- Delete `ExecuteEffectGate` after confirming the zero-call-site search.

## Required tests and retirement proof

Add deterministic tests for:

- two concurrent dispatches, including separate PID namespaces/containers: distinct launch/incarnation identities; stale completion rejected; exact replay remains idempotent;
- restart and PID reuse: old active-step heartbeat/completion cannot clear or complete the new owner;
- provider fallback: provider A failure followed by provider B completion has explicit chained provenance; late A completion is rejected;
- mutation: scope-only, raw-status, skipped/no-op, and missing-WBC artifacts cannot change `finalize.json` or scheduling;
- WBC ledger restart, reservation races, revision/fence mismatch, and provider/session mismatch;
- AST/call-site retirement assertions proving every execute worker call receives WBC, the fake-worker bypass is gone, `require_dispatch_wbc=False` is absent from authority-mutating execute paths, and `ExecuteEffectGate` has no callers.

Existing tests cover revision, fence, CAS, worker identity, scope, duplicate idempotency, and missing WBC in the normal merge path ([test_authority_dispatch_validation.py:403-504](tests/execute/test_authority_dispatch_validation.py:403), [test_merge_scope.py:719-740](tests/execute/test_merge_scope.py:719), [test_append_only_attempts.py:122-223](tests/execute/test_append_only_attempts.py:122)). They do not cover the replay bypass, incarnation, provider, or two-container cases.

## Unknowns

This read-only audit cannot establish whether deployment wrappers add external provenance not persisted into execute artifacts, or whether concurrent callers are operationally prevented before reaching `_run_and_merge_batch`. The repository contract itself does not prove either condition.