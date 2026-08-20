# Exact implementation/conflict map — gated stall recovery and transition notification

Date: 2026-08-02  
Mode: read-only preparation; no source, Git, cloud, provider, owner, or acceptance mutation  
Required starting tree: accepted T1.5 candidate `9642193a063d91a6be364f2d11a04b221eae30cf` (tree `27a3d61dff39a4c1a26a8a736dc85ce727c57b7c`, parent `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`)

## Executive result

The smallest safe lane is **not** a watchdog/notification rewrite. It is an exact owner-adapter patch, followed by a quiet compatibility retirement. Start from a clean worktree at `9642193…`; preserve T1.5 as the sole occurrence/claim/attempt authority; admit the gated-stall occurrence at the failure source; immediately call `run` for that owner-returned occurrence; let an owner-controlled three-hour selector call `reconcile` for the same ID; and keep provider notification at zero until an independently accepted notification outbox exists.

Four interface gaps must be closed before the incident path is operational:

1. `auto.py` has no current owner-issued `CustodyTargetKey` or accepted occurrence reference. It still synthesizes F01 using path, mtime, environment, default attempt `1`, and `sha256:unknown`. The finalizer/run owner must hand an exact target or already accepted occurrence into `auto`; `auto` cannot manufacture it.
2. The production owner protocol exposes only `intake`, `run`, `reconcile`, `observe`, and `fix-the-fixer`. The typed provenance transition exists only on `TestOnlyHermeticRecoveryOwner.record_delegation_provenance_error()`.
3. Owner observations authenticate revision/fence and result bytes, but expose no owner-issued `accepted_state_version`. A notification intent cannot lawfully use a locally derived version.
4. The installed immediate/reconciler units invoke `run`/`reconcile` with no occurrence ID, while `OwnerServiceClient.request()` requires an exact `occurrence_id`. The comments claim owner scanning, but the production protocol has no due-scan operation; only the test owner has `run_due()`/`reconcile_due()`.

These are blockers to production completion, not reasons to revive the legacy queue, watchdog, diagnostic agent, or direct Discord fallback.

## Exact minimal production delta, in order

### 1. Freeze the owner handoff first

The upstream finalizer/run owner must expose one of these two owner-issued values at the failure source:

- a complete, non-legacy `CustodyTargetKey`; or
- an accepted occurrence reference containing at least `occurrence_id`, `owner_revision`, `owner_fence`, and `accepted_state_version`.

For an accepted T1.4 deterministic finalizer rejection, the second form wins: the later five-poll generic stall reuses that occurrence and never performs a second intake. For a stall with no prior finalizer occurrence, the first form is passed to T1.5 intake exactly once. No callable resolver, environment-selected backend, queue marker, plan-directory lookup, or projection-derived target is permitted.

This handoff does not exist on `9642193…`. The eventual accepted T1.4 finalizer-owner composition must provide it. Until then, the correct behavior is a local lifecycle failure plus zero recovery/provider effect; do not substitute partial identity.

### 2. Extend the fixed owner protocol, without adding a Megaplan store

File: `arnold/recovery/simple_fixer.py`

Exact seams:

- `ExactOccurrence.from_mapping()` (`155-166`) and `.occurrence_id` (`173-174`) stay authoritative and unchanged in meaning.
- `_PUBLIC_SCHEMA_DOCUMENT` (`374-392`) adds a typed quiet operation, for example `record-provenance-error`, with the exact request shape `{occurrence_id, error_code, subject, detail}`. `detail` is projection-only; dedupe is exactly `(occurrence_id, error_code, subject)`.
- `OwnerServiceClient.request()` operation shapes (`455-475`) accept that operation and continue fixed-socket peer authentication and response digest verification (`477-568`).
- Every owner result/observation adds a non-empty owner-issued `accepted_state_version`. It changes only when the owner accepts a durable occurrence state transition. It is inside the authenticated result bytes; clients must not hash local state, prose, timestamps, or poll output to create it.
- Production implementation of the quiet operation must match the conformance behavior at `TestOnlyHermeticRecoveryOwner.record_delegation_provenance_error()` (`1896-1954`): one obligation, one quiet transition, `notification_dispatched=false`, `retry_scheduled=false`.

The fixed production service for `/run/arnold/recovery-owner-v1.sock` is not implemented in this repository. Its schema/version, request handler, durable state-version assignment, and quiet-transition transaction must be deployed in lockstep. Updating only this client would be schema-digest drift and must fail closed.

File: `arnold_pipelines/megaplan/cloud/simple_fixer.py`

- Keep `SimpleFixerOccurrence.from_custody()` (`68-74`) and `intake_simple_fixer_occurrence()` (`115-129`) as the only exact intake adapter.
- Add a typed result decoder that requires the owner-returned `occurrence_id`, `owner_revision`, `owner_fence`, and `accepted_state_version`; never return a caller-computed version.
- Add `record_delegation_provenance_error(occurrence_id, *, error_code, subject, detail)` as a thin fixed-owner request.
- Keep `run_simple_fixer()` (`132-135`), `reconcile_simple_fixer()` (`138-143`), and `observe_simple_fixer()` (`146-149`) exact-ID-only.

Do not call `TestOnlyHermeticRecoveryOwner` from production and do not add SQLite, files, locks, budgets, or outboxes under Megaplan.

### 3. Repair immediate and three-hour trigger plumbing

Files/seams:

- `arnold/recovery/cli.py:build_parser()` and `main()` (`32-99`)
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.service`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`

Minimal split:

- Immediate: after successful intake/projection, the ordinary failure-source process calls `run_simple_fixer(owner_occurrence_id)`. This is the first and only ordinary dispatch request for that occurrence.
- Three-hour: add an owner-controlled due-selection operation (for example `reconcile-due`, empty request) whose implementation selects already accepted occurrence IDs inside the sole owner and invokes the same `reconcile` transaction for each exact ID. The installed timer may call only that operation. A filesystem glob/queue/marker cannot select occurrences.
- Remove the misleading optional zero-argument `run`/`reconcile` CLI behavior. Exact-ID commands require an ID; the owner-owned due command accepts none.

The existing `TestOnlyHermeticRecoveryOwner.run_due()`/`reconcile_due()` (`1882-1894`) supplies conformance intent, but it is not a production service implementation.

### 4. Admit the occurrence at `auto.py`, then retire the legacy enqueue

File: `arnold_pipelines/megaplan/auto.py`

Exact seams:

- `drive()` stall detector (`5170-5295`): preserve task/event/active-step/in-flight-LLM resets. At the first threshold crossing, consume the owner handoff. Poll count, iteration, failure wording, provider/model/tier, paths, and time remain projection only.
- `_record_lifecycle_failure()` (`2152-2229`): accept an owner-issued recovery reference/target. If an existing accepted finalizer occurrence is supplied, reuse it. Otherwise intake the exact `CustodyTargetKey`, decode the accepted result, persist the returned occurrence reference, then call exact-ID `run` once.
- `_enqueue_lifecycle_failure_request()` (`2232-2329`): remove it from this route. Do not call `enqueue_occurrence_bound_repair_request()` after T1.5 intake.
- `_derive_fence_token()`, `_derive_plan_revision()`, `_derive_chain_path()`, `_derive_attempt_from_metadata()`, `_derive_blocker_hash()`, and `_derive_evidence_cursor_digest()` (`2424-2515`): no gated-stall recovery call may use them. Delete them only if no unrelated non-recovery caller remains; otherwise leave them unreachable from this seam and add a static assertion.

File: `arnold_pipelines/megaplan/store/plan_repository.py`

- Extend `PlanRepository.record_lifecycle_failure()` (`492-541`) with a validated optional owner occurrence projection. Persist only owner-returned fields under `latest_failure.recovery`: `occurrence_id`, `owner_revision`, `owner_fence`, `accepted_state_version`; do not persist a second identity or local send flag.
- Crash order is owner intake first, plan projection second. If the process dies between them, restart replays intake from the same owner-issued target (or reuses the prior finalizer occurrence) and receives the same ID before rewriting the projection.

Canonical blocker identity remains the brief's digest of `{current_state, normalized_failure_kind, phase_or_step, task_or_finalizer_candidate_pointer, deterministic_rejection_or_phase_result_digest}`. That digest must be minted/bound by the upstream owner record; `auto.py` does not derive it from `phase_result.json` bytes or mtimes.

### 5. Retire the pre-identity diagnostic route

Files:

- `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-human-review-diagnostic`

Replace `launch_human_review_diagnostic()` (`384-571`) and its resident-launch/fallback machinery with a typed compatibility command that requires an existing owner `occurrence_id` and calls only the production quiet-transition adapter. Missing provenance records `DELEGATION_PROVENANCE_ERROR` / `resident_delegation` once. It creates no task/evidence/state directory, launches no resident agent, requests no retry, and calls no notification provider. `main()` must never return blank pre-identity `escalation_id`/`state_path` as send authority.

The wrapper remains a thin installed delegate to this typed command or becomes a typed fail-closed tombstone. It must not regain Discord, webhook, Kimi/meta repair, or relaunch capability.

### 6. Preserve watchdog retirement; do not port the incident shell

File: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`

On `9642193…` this is already a four-line `RETIRED_FAIL_CLOSED` tombstone with `mutation_authority=false`, `mutation_effects=0`, and `agent_launches=0`. Keep it byte-equivalent in behavior. The old `launch_chain_tick()`, `emit_current_needs_human_sidecar()`, `notify_needs_human()`, Kimi/meta-repair, relaunch, Discord, and webhook functions are not present on the assumed base and must not be resurrected.

`arnold_pipelines/megaplan/cloud/watchdog.py` is only a generic check/result compatibility helper on this tree; it is not the incident shell and needs no mutation. If a UI needs recovery status, use `observe_simple_fixer()` from an existing read-only status projection. Observation may report `PENDING/CLAIMED/RUNNING/SUCCEEDED/FAILED/UNKNOWN/INDETERMINATE`, but it cannot run, intake, notify, or advance a gate.

### 7. Notification interface: specify now, produce zero effects now

There is no accepted `incident_notification.py` on `9642193…`. Do not create a local notification store or cherry-pick the failed T1.10 prototype.

The future accepted notification owner must take an owner observation/transition containing:

```text
occurrence_id
accepted_state_version
notification_kind
owner_authorized_recipient
stable_payload_digest
```

and define:

```text
notification_intent_id = H(
  occurrence_id,
  accepted_state_version,
  notification_kind,
  owner_authorized_recipient,
  stable_payload_digest
)
```

`accepted_state_version` comes from the recovery owner result, not plan state or an observer. The payload digest excludes timestamp, wording, paths, poll count, diagnostic attempts, model/provider, and process identity. Re-admission returns the same intent. Provider delivery requires the notification owner's singleton claim and durable receipt; response loss is terminal indeterminate. Until that owner is independently accepted and composed, notification intents and provider messages are both zero. Missing resident provenance never selects a fallback recipient.

## Required focused tests

### `tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`

Add a hermetic owner-port fixture and prove:

1. five unchanged `gated/finalize` observations intake one occurrence and request one immediate run;
2. process restart plus five identical observations returns/persists the same owner occurrence;
3. 200 additional unchanged polls call observation only and leave intake/run counts at one;
4. heartbeat/task/event/active-step progress resets the detector;
5. message, stall count, iteration, model, or tier changes alias the same occurrence;
6. changed authoritative state, blocker/result digest, plan revision, or fence yields a different owner occurrence;
7. a supplied accepted finalizer occurrence is reused and no generic stall intake occurs;
8. missing owner target/reference stays quiet and never falls back to `_derive_*` or the repair queue.

### `tests/cloud/test_simple_fixer.py`

Keep and extend existing conformance:

- immediate/reconciler two-process race (`test_two_process_initializers_and_immediate_reconciler_race_converge`, `198-220`);
- crash/restart terminal replay (`test_crash_restart_at_each_attempt_boundary`, `223-253`);
- restart plus 200 observers (`test_restart_budget_replay_local_forgery_and_200_observers_cannot_amplify`, `278-295`);
- missing provenance detail drift dedupe (`test_delegation_provenance_v2_is_one_obligation_one_quiet_transition`, `697-709`).

Add production-protocol tests with a peer-authenticated fake owner endpoint proving the new quiet operation and `accepted_state_version` are schema-bound/authenticated, and that changed/free-form detail cannot change the quiet-transition key. Add exact same-occurrence `run` + owner-due `reconcile` restart coverage and assert one claim, one attempt, one result/receipt. Corruption/response-loss remains unknown/indeterminate and non-redispatchable.

### Retirement/installed parity

- `tests/cloud/test_simple_fixer_retirement.py`: preserve `test_retired_wrapper_sources_are_tombstones_or_exact_owner_delegates` and `test_systemd_has_one_immediate_and_one_three_hour_non_agentic_route`; update assertions to distinguish exact-ID immediate from owner-controlled due reconciliation. Preserve the installed schema/help digest test.
- `tests/cloud/test_human_review_diagnostic.py`: replace resident launch/retry/fallback expectations with existing-occurrence-required, one quiet transition, zero files, zero agents, zero providers, restart replay.
- `tests/cloud/test_watchdog_wrappers.py`: do not reactivate historical extracted-shell tests. Add only a tombstone/no-effect replay: 200 invocations across fresh processes remain typed retired and make zero owner mutations/providers/agents. Exercise 200 owner observations in the simple-fixer/status test, not through a revived watchdog.
- installed wheel/materialized wrapper probe: source, `python -P`, installed scripts, and materialized wrappers expose the same schema digest, require exact occurrence IDs where specified, and retain watchdog/repair/meta retirement.

End-to-end invariant for one unchanged occurrence across two restarts and 200 observations:

```text
occurrences = 1
ordinary_fixer_attempts <= 1
resident_agent_launches = 0
notification_intents = 0   # until accepted notification owner composition
provider_messages = 0      # until accepted notification owner composition
```

After accepted notification composition, only the last two ceilings become `<= 1`, keyed by `(occurrence_id, accepted_state_version, kind, recipient, payload_digest)`.

## Conflict and integration map

Use a new clean worktree rooted exactly at `9642193…`. Do not implement in the current checkout: current `HEAD` is `36a10988717f9dfb0ab31d49baf05cc89bcfa989`, `9642193…` is not its ancestor (merge base `3744b91d2ff937e270b289faa1ef385fcba05cfb`), and the root worktree is heavily dirty, including `auto.py` and `arnold-watchdog`.

Intentional overlaps with T1.5:

- `arnold/recovery/simple_fixer.py` and `tests/cloud/test_simple_fixer.py` are the only files changed by `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec..9642193a063d91a6be364f2d11a04b221eae30cf`. Extend them in place and preserve T1.5's authenticated effect receipt/replay validation.
- Protocol/schema edits necessarily change `SCHEMA_DIGEST`; update CLI/help/installed parity together. Never resolve a conflict by retaining an old digest with a new operation.

High-risk divergence from current `HEAD` exists in every main seam: `arnold/recovery/{cli.py,simple_fixer.py}`, `auto.py`, `store/plan_repository.py`, cloud simple-fixer/diagnostic/watchdog wrappers, and all named tests differ between `9642193…` and current `HEAD`. Resolve by replaying the narrow patch onto the eventual clean composite base, not by copying current dirty files.

Future T1.4 finalizer work will overlap `auto.py` and must land its owner-issued occurrence handoff first. Future notification work must consume the accepted-state interface but should not touch recovery claim/attempt tables. The failed T1.10 implementation must not be cherry-picked wholesale; only an independently accepted, owner-backed outbox can lift the zero-notification interim.

## Blockers / stop conditions

1. **Owner-target blocker:** no exact owner-issued target/occurrence is available to `auto.py` on the assumed base. Stop rather than derive it locally.
2. **Production-service blocker:** the fixed recovery-owner server is external to this repo. Its quiet-transition, due-selection, and state-version support must be available with the same protocol/schema before source integration can pass.
3. **Notification-owner blocker:** no accepted notification authority exists on this tree. Provider effect remains zero.
4. **Base blocker:** current dirty `HEAD` is not a lawful mutation base. Use a clean `9642193…` worktree, then rebase/merge only after upstream owner interfaces freeze.

No cloud/provider/owner probe or acceptance claim is implied by this map.
