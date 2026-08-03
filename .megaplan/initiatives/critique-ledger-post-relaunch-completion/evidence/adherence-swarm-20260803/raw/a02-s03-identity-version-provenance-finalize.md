# a02-s03-identity-version-provenance-finalize: identity-version-provenance × finalize

## Verdict

**FAIL.** Finalize has strong partial primitives, but no complete identity envelope reaches the durable artifact, receipt, validation, and retry-routing consumers.

**P0 — authority mutation:** reachable execute, recovery, chain, and backstop writers mutate `finalize.json` outside the finalize-bound custody/version path.

**P1 — status/evidence misreporting:** receipts hard-code attempt `1`, discard artifact hashes, phase results lack the required identity vector, and promotion evidence is only logged.

## Intended canonical contract

The intended model boundary is already separated correctly: `finalize_model_output.json` is model-owned, while `finalize_capture.json` is the richer harness projection; harness-owned validation and baseline fields are excluded from model capture (`arnold_pipelines/megaplan/schemas/runtime.py:1236-1244,1275-1308,1330-1336`). `STEP_CONTRACTS` selects those schemas for finalize (`arnold_pipelines/megaplan/step_contracts.py:99-107`).

The canonical finalize path should therefore be:

`set_active_step` identity → shared `promote_scratch` → `_validate_finalize_payload` → `_write_finalize_artifacts` → receipt/phase-result/WBC handoff.

The repository has each component: active state records run, invocation, attempt, and runner incarnation (`arnold_pipelines/megaplan/_core/state.py:1894-1963`); scratch promotion is shared and expected-path-only (`arnold_pipelines/megaplan/handlers/structured_output.py:123-237`); finalize writes the multi-artifact projection (`arnold_pipelines/megaplan/handlers/finalize.py:2028-2166`); finalize is registered with phase WBC contracts (`arnold_pipelines/megaplan/custody/phase_wbc.py:136-150`).

No complete canonical implementation exists because those values are not propagated as one binding into artifacts, receipts, phase results, or all mutation callers.

## Evidence and complete path inventory

I searched with `rg -n` over Python, tests, docs, and schemas for `finalize.json`, `finalize_output.json`, `finalize_snapshot`, `write_plan_artifact_json`, `atomic_write_json`, `phase_result`, `build_receipt`, WBC, runtime provenance, and JSON decode handling; I then inspected every matching writer/caller and relevant tests.

Writers/callers in scope:

- Canonical finalize: `_write_finalize_artifacts` writes `finalize.json`, `finalize_snapshot.json`, `contract.json`, `final.md`, and user actions (`arnold_pipelines/megaplan/handlers/finalize.py:2144-2166`).
- Execute mutation/reconciliation: `execute/batch.py` repairs gates (`:210-246`), performs multiple direct/raw finalize writes (`:3232,3872,3897,5030,5097,5302,5346,5590`), and rewrites authoritative execute overlays (`:5948-6016`).
- Timeout recovery writes finalize without contract context (`arnold_pipelines/megaplan/execute/timeout.py:247-306`).
- Failure-boundary merge does the same (`arnold_pipelines/megaplan/execute/merge.py:1439-1508`).
- Full-suite baseline recovery uses raw `atomic_write_json` (`arnold_pipelines/megaplan/orchestration/full_suite_backstop.py:53-89`).
- Auto escalation directly rewrites task tiers (`arnold_pipelines/megaplan/auto.py:1995-2037`).
- Chain recovery directly rewrites task statuses (`arnold_pipelines/megaplan/chain/__init__.py:4863-4897`).

The wrapper does not enforce a shared provenance contract: `PlanRepository.write_artifact_json` only blocks a legacy payload when a context is supplied and enforcement is enabled; `contract_context=None` permits raw writes (`arnold_pipelines/megaplan/store/plan_repository.py:238-287,544-557`).

Readers/consumers include finalize validation and promotion (`handlers/finalize.py:2218-2304`), execute admission and overlays (`execute/batch.py:3528-3584`), timeout/merge recovery, chain completion guards, auto routing (`auto.py:4645-4696`), semantic health (`semantic_health.py:1772-1831`), and snapshot loading (`_core/io.py:1122-1123`). Receipt and phase-result consumers are emitted by `_finish_step` (`handlers/shared.py:924-1010`).

## Adherence gaps

1. **P0 — authority mutation; cross-attempt artifact mixing.**  
   Finalize’s canonical writer uses a StepIO context (`handlers/finalize.py:2155-2162`), but downstream writers use `contract_context=None` or raw atomic writes (`execute/timeout.py:301`, `execute/merge.py:1508`, `full_suite_backstop.py:89`, `auto.py:2037`, `chain/__init__.py:4896`). These paths mutate the same authoritative `finalize.json` without rebinding the mutation to run, invocation, attempt, incarnation, schema/version, or launch provenance. `finalize_snapshot.json` is only written by the canonical finalize path (`handlers/finalize.py:2163`), so later `finalize.json` mutations can diverge from the snapshot. This is an authority mutation, not merely display drift.

2. **P1 — authority gating; WBC is shadow-only and incomplete.**  
   Finalize WBC events carry run, invocation, ordinal, attempt ID, and basic code/config/template versions (`custody/phase_wbc.py:722-765`), but omit runner incarnation and runtime launch provenance. The WBC facade explicitly sets `PromotionMode.ACTION_OFF` and `enforcement_enabled=False` (`phase_wbc.py:675-687`). Worker dispatch has the same omissions and disabled enforcement (`custody/worker_dispatch_wbc.py:159-172,334-401`). The typed ledger itself has no incarnation or launch-provenance fields (`arnold/workflow/execution_attempt_ledger.py:423-502,508-577,607-641`).

3. **P1 — status misreporting; receipts are not identity-bound.**  
   `build_receipt` explicitly discards `output_file` and `artifact_hash`, hard-codes `"attempt": 1`, and emits no run ID, invocation ID, runner incarnation, or launch provenance (`arnold_pipelines/megaplan/receipts/__init__.py:55-69,110-141`). The `Receipt` schema confirms those fields are absent (`receipts/schema.py:12-45`). Boundary receipts add run and invocation but still omit attempt/incarnation/launch binding (`handlers/shared.py:790-854`).

4. **P1 — status misrouting; phase-result freshness is weaker than identity freshness.**  
   `PhaseResult` contains only phase and invocation among lifecycle identity fields (`orchestration/phase_result.py:330-350,369-386`). Auto routing accepts a result when `phase_result.json` changed in mtime/size and its phase matches; it does not compare the result invocation against the invocation admitted before dispatch (`auto.py:4618-4653`). Cleanup later performs an invocation CAS (`auto.py:3609-3660`), but routing has already consumed the result. A same-phase stale rewrite can therefore drive retry/escalation decisions.

5. **P1 — evidence loss; promotion evidence is non-durable.**  
   `build_promotion_evidence` detects fallback, wrong-path, missing-receipt, and missing-phase-result cases but is explicitly read-only (`handlers/structured_output.py:327-353`). Finalize only sends the returned records to `LOGGER.debug`; it does not persist them into the artifact, receipt, phase result, or WBC event (`handlers/finalize.py:2289-2301`).

6. **P1 — schema/launch provenance is computed but not handed off.**  
   Worker launch preflight computes runtime source revision and `runtime_vector_sha256` and validates them before dispatch (`workers/_impl.py:7009-7079`), but `WorkerResult` has no corresponding identity/version fields (`workers/_impl.py:2308-2342`). The proof therefore guards launch locally but cannot bind the resulting finalize decision.

Semantic health detects only artifact-hash and reference drift, as warnings (`semantic_health.py:1783-1830`); existing tests cover that warning (`tests/arnold_pipelines/megaplan/test_semantic_health.py:1244-1270`), not identity-vector mismatch.

## Incident reachability and severity

Observed: malformed JSON is broadly converted to “missing/unavailable” in baseline backstop and auto tier-repair paths (`orchestration/full_suite_backstop.py:53-58`, `auto.py:1995-2003`), while merge returns a non-reconciled reason (`execute/merge.py:1466-1473`). This can misclassify a JSONDecode failure without a bound attempt.

Inferred from reachable code: a finalize attempt can produce valid artifacts and receipts, then an execute/recovery/chain writer can mutate `finalize.json` under a different lifecycle occurrence without updating the original binding. Auto can also route from a same-phase result whose invocation was not proven current. The P0 classification is based on reachable authority writes; no production execution was performed, so actual incident frequency is unknown.

## Minimal generalized remediation

Consolidate on `set_active_step` + `phase_wbc` + shared `promote_scratch`, extending them with one immutable `DecisionBinding` reference containing:

`run_id, invocation_id, attempt, attempt_id, runner_incarnation, schema_hash, code/config/template versions, provider/model/fallback evidence, runtime source revision, runtime vector hash, and parent artifact hash`.

Have canonical finalize capture persist that binding with `finalize_snapshot.json`, `phase_result.json`, and the boundary receipt. Persist promotion evidence there as well.

Add one locked `mutate_finalize_projection` writer for legitimate execute/recovery status overlays. It must reread the current binding, require the expected parent hash and current occurrence, and emit a mutation receipt. Replace every direct/raw finalize writer listed above; do not merely wrap them. Keep `finalize_snapshot.json` immutable and treat `finalize.json` as a bound projection.

For migration, mark old plans unbound/read-only for authoritative routing; require re-finalization or an explicit deterministic rebind before execute. Do not silently synthesize missing identity.

## Required tests and retirement proof

- Concurrent finalize/execute/recovery writers: exactly one binding wins; stale parent hash and invocation are rejected.
- Restart/resume: same invocation remains same attempt; a new attempt increments deterministically.
- Provider fallback: configured, attempted, selected, actual provider/model, and failure reason all match the binding.
- Mutation tests: every legitimate overlay updates parent hash and receipt; raw/direct writes fail.
- Malformed/truncated JSON: route becomes indeterminate/quarantined, never success or retry authorization.
- Two-container/PID-namespace and PID-reuse cases: foreign namespace requires exact lease; mismatched process start identity is rejected, consistent with existing liveness tests (`tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py:62-102,181-245`).
- Phase routing must reject changed-but-wrong invocation, not only stale mtime/size.
- Static/AST retirement test: no reachable `finalize.json` writer remains outside the canonical writer or mutation helper; no `contract_context=None` finalize call remains. Existing `rg` inventory is the baseline proof, and CI should fail on any reintroduction.

## Unknowns

No runtime/cloud state was inspected or modified. It is unknown whether `ACTION_OFF` is an intentional temporary shadow mode, whether external wrappers add provenance not visible here, and whether all listed recovery writers are enabled in production. Those uncertainties do not remove the source-level authority and status gaps.