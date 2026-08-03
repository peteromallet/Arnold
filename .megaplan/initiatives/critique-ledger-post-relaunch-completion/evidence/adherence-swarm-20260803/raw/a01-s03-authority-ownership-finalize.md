# a01-s03-authority-ownership-finalize: authority-ownership × finalize

## Verdict

Not conformant.

A canonical finalize implementation exists, but authority ownership is bypassed after publication. The highest-risk gap is a stale full-document rewrite of `finalize.json` from the auto driver without the plan lock or compare-and-swap protection. This can erase newer execution status and evidence.

Findings:

- **P0 — authority mutation:** unlocked whole-document `finalize.json` rewrites can overwrite concurrent execution/finalization mutations.
- **P1 — authority mutation:** execute, timeout, merge, backstop, and auto paths independently rewrite the canonical artifact, bypassing one field-scoped mutation owner and typed write context.
- **P1 — status/retry misreporting:** finalize is invoked with `read_only=False`, disabling configured provider fallback even though model invocation itself does not mutate the checkout.
- **P1 — status/evidence misreporting:** promotion evidence hashes the persisted schema instead of the model-capture schema and is only debug-logged.
- **P2 — duplicate handoff logic:** Hermes independently reads, repairs, and accepts scratch/output payloads before the canonical model seam validates them.
- **P2 — sidecar hygiene:** `finalize_snapshot.json` is written but has no active reader; the non-atomic scratch template can expose transient malformed JSON.

## Intended canonical contract

The model may author only `finalize_model_output.json`’s schema. `STEP_CONTRACTS["finalize"]` explicitly separates `finalize_model_output.json` from the richer `finalize_capture.json` projection (`arnold_pipelines/megaplan/step_contracts.py:99-107`). Runtime schema comments state that the handler alone enriches the model payload before publishing canonical `finalize.json` (`arnold_pipelines/megaplan/schemas/runtime.py:1330-1336`).

The canonical finalizer:

1. validates the model payload and semantic constraints (`arnold_pipelines/megaplan/handlers/finalize.py:429-468`);
2. performs handler-owned task, validation-job, baseline, and feasibility mutations (`arnold_pipelines/megaplan/handlers/finalize.py:2028-2151`);
3. writes `finalize.json` through the typed artifact context (`arnold_pipelines/megaplan/handlers/finalize.py:2154-2166`);
4. completes the phase and emits the `finalize_artifacts` or `finalize_fallback` boundary (`arnold_pipelines/megaplan/handlers/finalize.py:2341-2361`; `arnold_pipelines/megaplan/handlers/shared.py:109-112, 880-1060`).

Rejected feasibility candidates are explicitly prevented from replacing the authoritative graph (`arnold_pipelines/megaplan/orchestration/graph_admission.py:1-7, 71-125`).

## Evidence and complete path inventory

I searched active code, tests, schemas, docs, and call sites with `rg` for `finalize.json`, `finalize_output.json`, `finalize_snapshot`, `capture_step_output`, `promote_scratch`, `write_plan_artifact_json`, `atomic_write_json`, provider fallback, boundary receipts, and `load_finalize_snapshot`. I excluded archived tests when assessing production paths.

Writers:

- Canonical finalizer: `arnold_pipelines/megaplan/handlers/finalize.py:2028-2166`.
- Execute mutations: `arnold_pipelines/megaplan/execute/batch.py:3232, 3872, 3897, 5030, 5097, 5302, 6012`; merge `execute/merge.py:1508`; timeout `execute/timeout.py:301`.
- Auto tier escalation: `arnold_pipelines/megaplan/auto.py:1992-2030`, called at `auto.py:5136`.
- Full-suite baseline backstop: `arnold_pipelines/megaplan/orchestration/full_suite_backstop.py:53-89`, reached from chain orchestration (`arnold_pipelines/megaplan/chain/__init__.py:4076-4086`).
- Scratch seed: `arnold_pipelines/megaplan/prompts/finalize.py:205-225`.

Readers/consumers:

- Execute admission and repair adoption: `arnold_pipelines/megaplan/handlers/execute.py:687-709, 941-947`.
- Authority inventory: `arnold_pipelines/megaplan/authority/inventory.py:536-539, 998-1030`.
- Status projection: `arnold_pipelines/megaplan/cli/status_view.py:676-715`.
- Review and prompt projections: `arnold_pipelines/megaplan/handlers/review.py:1944-2010`; `arnold_pipelines/megaplan/prompts/review.py:447-548, 969-1001`.
- Receipts and warrants: `arnold_pipelines/megaplan/receipts/extractors.py:181-185, 363`; `arnold_pipelines/megaplan/store/warrant_sources.py:120-142`.
- `load_finalize_snapshot` has only its definition and no active call site (`arnold_pipelines/megaplan/_core/io.py:1122-1123`).

Model-boundary callers:

- Generic capture and recovery are centralized in `arnold_pipelines/megaplan/model_seam.py:221-425, 546-604, 1578-1743`.
- Finalize calls `promote_scratch` and then canonical validation (`arnold_pipelines/megaplan/handlers/finalize.py:2250-2313`).
- Hermes separately parses scratch, performs repairs with `validate=False`, normalizes, then eventually calls `capture_step_output` (`arnold_pipelines/megaplan/workers/hermes.py:1443-1466, 1570-1618, 2370-2403`).

## Adherence gaps

1. **P0 — unlocked stale authority rewrite.**  
   `_pin_tasks_to_tier` reads all of `finalize.json`, changes one task, and replaces the entire file without acquiring `load_plan_locked` or checking an expected hash (`arnold_pipelines/megaplan/auto.py:1992-2030`). It is called from the auto loop while execute phases use a separate plan lock (`arnold_pipelines/megaplan/auto.py:5136`; `arnold_pipelines/megaplan/handlers/execute.py:687-709`). This is an authority mutation, not merely status rendering. The stale write can erase task status, evidence, or newer tier changes.

2. **P1 — multiple canonical writers without a shared mutation owner.**  
   Execute helpers mutate `finalize_data` and independently publish it through either `write_plan_artifact_json(..., contract_context=None)` or raw `atomic_write_json` (`execute/batch.py:3232, 3872, 3897, 5030, 5097, 5302, 6012`; `execute/merge.py:1508`; `execute/timeout.py:301`). The repository writer only enforces typed policy when a context is supplied (`store/plan_repository.py:238-265, 544-554`). These are legitimate execution-state changes in some cases, but there is no canonical field allowlist, expected-version check, or single execute mutation function. This is authority mutation with status-divergence consequences.

3. **P1 — provider fallback is disabled for finalize.**  
   `handle_finalize` calls `_run_worker` without `read_only=True` (`handlers/finalize.py:2249-2250`; `handlers/shared.py:335-346`). The configured fallback routine refuses fallback whenever `read_only` is false (`workers/_impl.py:6709-6723`). Finalize model invocation therefore cannot use the configured provider chain for retryable provider failures; only narrower ambient auth/connection fallback remains (`workers/_impl.py:7359-7445`). This is status/retry misreporting, not authority mutation.

4. **P1 — promotion evidence is not bound to the actual model schema.**  
   Finalize computes promotion evidence using `SCHEMAS["finalize.json"]` (`handlers/finalize.py:2277-2295`), while the worker contract is `finalize_model_output.json` (`step_contracts.py:99-107`). The evidence is then only logged (`handlers/finalize.py:2296-2302`). This can misstate which producer schema was enforced and leaves fallback/wrong-path evidence non-durable. It affects status and audit confidence, not canonical payload authority.

5. **P2 — Hermes duplicates the canonical handoff.**  
   Hermes reads `finalize_output.json`, accepts content, performs two repair paths without schema validation, and only later reaches `capture_step_output` (`workers/hermes.py:1443-1466, 1570-1618, 2387-2403`). The final handler still validates, so this is not a direct authority write, but it duplicates acceptance and retry routing.

6. **P2 — sidecar/template issues.**  
   The template is written with plain `Path.write_text` (`prompts/finalize.py:218-225`), and `finalize_snapshot.json` is a duplicate sidecar with no active reader (`handlers/finalize.py:2163`; `_core/io.py:1122-1123`). These are status/restart hazards, not canonical-authority writes.

## Incident reachability and severity

The JSON-decode failure class is reachable when a reader observes an incomplete or malformed `finalize_output.json`; `promote_scratch` explicitly catches decode errors and classifies invalid scratch (`handlers/structured_output.py:55-64, 208-227`). Canonical `finalize.json` writes are individually atomic, so the more severe reachable failure is semantic stale overwrite rather than partial JSON.

The P0 race can cause lost task completion, reverted retry state, or incorrect execution admission. P1 gaps can cause a valid provider fallback not to occur, a boundary to report the wrong schema, or forensic status to omit the actual scratch path outcome.

## Minimal generalized remediation

Consolidate on the existing finalizer for initial publication, and add one narrowly scoped `mutate_finalize_execution_fields` owner for post-finalization execution mutations. It must:

- acquire the plan lock;
- reread current `finalize.json`;
- permit only executor-owned fields;
- require the expected canonical hash/version;
- write through typed artifact context;
- reject stale writers deterministically.

Migrate every execute, merge, timeout, auto, and backstop writer to that function. Where possible, move baseline backstop data to its own artifact and let finalize-owned code merge it. Delete the direct writers; wrapping them is insufficient.

Set finalize’s worker invocation to the explicit model-only fallback capability, not a generic mutable/read-only boolean. Route all provider parsing and scratch recovery through `model_seam` and `promote_scratch`; remove Hermes’ finalize-specific scratch acceptance and repair paths.

Use `finalize_model_output.json` for promotion evidence, persist the evidence in the boundary receipt, replace the scratch seed writer with atomic JSON output, and retire the unused snapshot writer/reader pair.

## Required tests and retirement proof

- Static AST/`rg` gate: zero active `finalize.json` writes outside the canonical finalizer or the new field-scoped mutator.
- Concurrent auto/execute/backstop writers: stale expected hash is rejected and no task status/evidence is lost.
- Restart injection after every artifact write: no boundary receipt or completed phase may exist without the canonical artifact and matching hash.
- Provider matrix for finalize: timeout, connection, auth, schema rejection, and successful fallback across providers; assert attestation uses `finalize_model_output.json`.
- Mutation tests: model payload cannot write handler-owned fields; executor mutator cannot change task graph, dependencies, or authority attempts.
- Malformed/truncated scratch, duplicate JSON keys, non-finite numbers, wrong-path writes, and Hermes/Codex/Shannon parity.
- Two containers sharing a plan mount: only one process may mutate; separate PID namespaces must not cause stale-lock clearance of a live owner. Separate mounts must fail closed because filesystem locks cannot coordinate.
- Retirement proof: repeat the writer inventory, assert no Hermes finalize scratch reader/repair caller remains, and assert no active `load_finalize_snapshot` caller exists.

## Unknowns

Production provider profiles may intentionally omit a finalize fallback chain; no active finalize-specific fallback test was found, only execute-chain coverage (`tests/arnold_pipelines/megaplan/test_tiered_execute_provider_fallback.py:104-145`). I also found no runtime two-container test proving `.plan.lock` behavior across PID namespaces.