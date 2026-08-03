# a01-s04-authority-ownership-execute: authority-ownership × execute

## Verdict

FAIL. Three P0 authority-mutation gaps and two P1 ownership/status gaps remain.

P0 means an unowned or projection-derived completion can mutate execute authority. P1 means dispatch, redispatch, liveness, or completion reporting can be wrong without independently proving a terminal mutation.

## Intended canonical contract

The repository contract says `finalize.json`, `state.json`, execution batch artifacts, chain state, cloud markers, and repair sidecars are not authority; legacy artifacts must not be silently promoted, and accepted updates require explicit scope and evidence (`.megaplan/initiatives/runauthority-sprint-1/NORTHSTAR.md:30-41`).

The canonical execute path is:

- Persist batch scope, dispatch identity, and result envelopes before merge (`execute/batch.py:3123-3140`).
- Validate those envelopes through `_grant_aware_validate_entries` and `_validate_and_merge_batch` (`execute/merge.py:1214-1263`).
- Derive completion only from accepted envelope projections (`orchestration/authority_readers.py:565-575`, `664-757`).
- Feed scheduling through `effective_execute_completed_task_ids` (`orchestration/authority_readers.py:381-434`).

No single end-to-end execute reducer owns every mutation today. Consolidation should therefore target this existing merge-validator plus accepted-attempt projection, not introduce another authority system.

## Evidence and complete path inventory

I searched with `rg --files` and `rg -n` across `arnold_pipelines/megaplan`, `tests`, `.megaplan`, and `docs` for `active_step`, `set_active_step`, `clear_active_step`, `execute`, `dispatch`, `result_envelopes`, `authority`, `fallback`, `scratch`, `output_path`, `status`, and `legacy`. I then inspected every execute writer/caller/consumer and the route registry.

In-scope writers and callers are:

- Active ownership: `handlers/execute.py:848-857` calls `set_active_step`; tier routing calls it again at `execute/batch.py:3721-3730` and `5734-5747`; completion clears using the first token at `handlers/execute.py:935-939`.
- Worker completion: `workers/hermes.py:1497-1501` and `2399-2409` invoke reconstruction; `_run_and_merge_batch` stamps current metadata and merges at `execute/batch.py:3123-3148`.
- Failure/restart reconciliation: `execute/merge.py:1333-1380`; replay uses it with `require_dispatch_wbc=False` (`execute/batch.py:2056-2090`); auto invokes reconciliation after callback failure (`auto.py:6293-6300`).
- Artifact/finalize consumers: batch artifacts and `finalize.json` are written at `execute/batch.py:3230-3235`; auto applies overrides and rewrites `finalize.json` at `execute/batch.py:5948-5952`, `6011-6015`.
- Completion readers: canonical adapter at `orchestration/authority_readers.py:381-434`; raw status consumers include prior-artifact overlay at `execute/batch.py:3601-3626`, circuit admission at `handlers/execute.py:864-875`, and aggregate completion union at `execute/batch.py:6018-6033`.
- The repository’s own route inventory records execute raw-status routes EXEC-01 through EXEC-06 as `WARN_ONLY` (`orchestration/authority_readers.py:1415-1465`).

## Adherence gaps

1. **P0 — authority mutation: no-metadata merge fails open.**

Observed: `_grant_aware_validate_entries` accepts every in-scope entry when dispatch identity and result envelopes are absent, recording `legacy_no_authority_metadata` (`execute/merge.py:627-664`). Those accepted entries are then merged into task and sense-check records (`execute/merge.py:1214-1263`, `1290-1314`).

Observed: scope validation precedes this fail-open branch, so an S4 artifact with valid `batch_scope` but no authority metadata can reach it (`execute/merge.py:1356-1380`). This contradicts the canonical resolver, which explicitly quarantines missing dispatch identity (`authority/batch_scope.py:217-249`).

Inference: a legacy or forged scoped artifact can mark a task done or acknowledge a check without grant, owner, fence, or evidence identity. This is direct authority mutation, not status misreporting.

2. **P0 — authority mutation: execute scratch/checkpoint recovery re-owns old payloads.**

Observed: reconstruction selects the numerically latest `execute_batch_*_output.json` without an attempt, batch, run, or owner binding (`workers/hermes.py:2795-2811`), then falls back to the latest batch artifact (`workers/hermes.py:2821-2838`). The reconstructed task updates are returned when JSON parsing fails (`workers/hermes.py:1497-1501`) or structural validation fails (`workers/hermes.py:2404-2409`).

Observed: the caller subsequently stamps current dispatch metadata and result envelopes before merging (`execute/batch.py:3123-3148`).

Inference: a stale prior-attempt scratch/checkpoint payload can be adopted as the current worker’s result and receive current authority metadata. Existing tests explicitly bless both behaviors (`tests/workers/test_hermes_execute_recovery.py:9-90`, `93-170`). This is an owner bypass and direct authority mutation.

3. **P0 — authority mutation: artifact-level evidence synthesizes completion outside the accepted-attempt path.**

Observed: `apply_authoritative_execute_overrides` reads batch artifacts, matches top-level `files_changed` or `commands_run` to one pending task, then sets `status="done"` and creates executor notes (`orchestration/execution_evidence.py:81-107`, `151-219`). It also synthesizes a sense-check acknowledgement (`orchestration/execution_evidence.py:221-225`).

Observed: this mutator runs in the auto aggregate before `finalize.json` is rewritten (`execute/batch.py:5948-5952`, `6011-6015`) and also runs inside validation (`orchestration/execution_evidence.py:236-253`).

Inference: top-level evidence, a projection explicitly described as non-authoritative by the contract, can mint terminal task authority without accepted result envelopes. The existing test only protects terminal command fields from replacement, not pending-to-done promotion (`tests/execute/test_durable_evidence_accounting.py:173-211`).

4. **P1 — ownership/status misreporting: tier routing creates a second active owner.**

Observed: canonical `set_active_step` creates a new UUID when `run_id` is omitted and overwrites `state["active_step"]` (`_core/state.py:1828-1883`). Both execute tier paths call it without retaining the returned token (`execute/batch.py:3727-3730`, `5740-5747`). The outer handler retains the original token and clears with it (`handlers/execute.py:848-855`, `935-939`); `clear_active_step` refuses a mismatched token (`_core/state.py:1914-1922`).

Inference: tiered execution can leave a stale active step after successful completion. Watchdog and chain consumers read that projection (`watchdog/signals.py:82-94`, `chain/__init__.py:5457-5473`), causing false liveness, blocked redispatch, or wrong phase ownership. This is status/ownership misreporting, not proven task-authority mutation.

5. **P1 — status/control bypass: raw task labels remain parallel scheduling inputs.**

Observed: prior artifact statuses are copied into `batch_status_overlay` before the canonical adapter is called (`execute/batch.py:3601-3626`); circuit admission independently selects only raw `pending` tasks (`handlers/execute.py:864-875`); aggregate completion unions canonical IDs with `_durably_evidenced_finalized_task_ids` (`execute/batch.py:6018-6033`), whose implementation trusts raw `done`/`skipped` records (`execute/batch.py:2571-2592`).

The adapter exists and is intended to centralize this decision (`orchestration/authority_readers.py:418-434`). These bypasses can misreport readiness, skip circuit checks, or terminate/redispatch incorrectly. The evidence establishes status/control divergence; direct authority mutation is not established for every route.

## Incident reachability and severity

The JSON-decode/empty-output incident reaches Gap 2 directly through both reconstruction call sites (`workers/hermes.py:1497-1501`, `2404-2409`). Failure-boundary reconciliation reaches Gap 1 through `auto.py:6293-6300` and `execute/merge.py:1333-1380`. Normal successful dispatch does stamp metadata (`execute/batch.py:3123-3140`), so the highest risk is malformed-output, retry, restart, and callback-failure paths.

No live execution or cloud state was used; reachability is established by static call paths. Severity is therefore based on deterministic control flow, not observed incident frequency.

## Minimal generalized remediation

- Make `_grant_aware_validate_entries` fail closed whenever authority metadata is absent. Preserve legacy artifacts only as quarantined observations; do not pass their entries to `_validate_and_merge_batch`.
- Remove scratch glob and latest-checkpoint promotion from `_reconstruct_execute_payload`. Recovery must consume only an exact caller-issued attempt path, or replay an artifact through `resolve_batch_authority_metadata` and the accepted-attempt projection.
- Delete the mutation portion of `apply_authoritative_execute_overrides`. If compatibility evidence is needed, emit an advisory projection only; accepted envelopes remain the sole completion writer.
- Change tier routing to update the existing active-step record while preserving its `run_id`, or return and propagate the replacement token. Do not invoke `set_active_step` as a second owner.
- Route all execute completion, circuit, prerequisite, and aggregate decisions through `effective_execute_completed_task_ids`; remove raw-status unions and overlays after migration.

This is narrower than a rewrite because the canonical validator, projection, CAS/fence checks, and adapter already exist.

## Required tests and retirement proof

Add deterministic tests for:

- Valid `batch_scope` with missing identity/envelopes: task and sense-check records remain unchanged and quarantine is emitted.
- Stale scratch/checkpoint from an earlier attempt, malformed provider response, retry, and restart: no completion mutation; current attempt with valid accepted envelopes succeeds.
- Top-level files/commands without an accepted envelope: cannot change pending to done or acknowledge checks.
- Duplicate/replayed envelopes, stale fence, wrong provider/worker identity, and mutation after owner loss: fail closed.
- Tier map with multiple batches: exactly one active `run_id`; successful and failed paths clear it; stale heartbeat/clear cannot affect a replacement owner.
- Two containers and distinct PID namespaces: PID is observational only; run/fence identity controls ownership and stale workers cannot mutate or clear state.

Retirement proof must include deletion of the legacy acceptance branch, scratch/checkpoint fallback, and override callers/tests; `rg` must find no executable references to `legacy_no_authority_metadata`, `execute_batch_*_output.json` reconstruction, or `apply_authoritative_execute_overrides` as a mutator. Tests must assert the old paths are unreachable, not merely wrapped.

## Unknowns

No runtime trace was collected, so the frequency of stale-file collisions and cross-container races is unknown. The report also does not establish whether any external wrapper writes additional execute artifacts outside the searched repository paths.