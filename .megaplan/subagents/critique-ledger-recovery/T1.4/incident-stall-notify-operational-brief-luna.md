# Operational patch brief — gated stall, one fixer dispatch, transition-only notification

Date: 2026-08-02  
Posture: read-only diagnosis/specification  
Implementation authority: none  
Target integration point: **after the eventual independently accepted T1.5 `simple_fixer` commit**

## Verdict

The critique epic did not complete. Plan `cl2-wbc-backed-ledger-20260731-1411`
stopped in `gated/finalize` after five unchanged iterations and was projected as
`manual_review`. The five-iteration detector worked. The failure was what
happened next: observation, repair admission, diagnostic launch, and Discord
delivery did not share one durable occurrence/effect state machine.

No durable fixer or diagnostic agent launch can be inferred. The provenance
exception happened before diagnostic state was created, and the surviving
records do not contain the required claim -> attempt -> result chain.

The notification loop was deterministic:

1. the watchdog repeatedly observed the same gated stall;
2. it appended another `opened` ledger record, but did not use that ledger as a
   send-admission gate;
3. `launch_human_review_diagnostic()` resolved resident provenance before
   computing/persisting diagnostic identity;
4. missing `resident_delegation` raised `DelegationProvenanceError`;
5. the top-level exception projection returned blank `escalation_id` and
   `state_path`, with fallback delivery requested;
6. the watchdog directly sent another Discord fallback; and
7. because `state_path` was blank, the successful send could not be reconciled,
   so the next poll repeated it.

The captured incident evidence reports 203 `opened` and 201 `delivered` records
for the same stable escalation identity, with distinct Discord message IDs.
The stable ID existed; it was not authoritative admission.

Model failures contributed to reaching the stall, but no model caused the
notification loop. DeepSeek V4 Pro surfaced unresolved preparation blockers,
which auto-approval unsafely converted to assumptions. GLM-5.2 repeatedly
failed structured planning/finalization contracts. GPT-5.6 Sol produced seven
graphs rejected by deterministic feasibility checks. That graph gate behaved
correctly; the missing bounded recovery transition after rejection was the
control-plane defect. The later Flash -> Pro -> GLM tier list proves only that
routes were tried without advancement, not that one of those models caused the
loop.

## Minimal invariant

Use the accepted T1.5 exact F01 occurrence as the **only** recovery identity.
Do not add a watchdog fingerprint, repair-queue identity, escalation identity,
local lock, or notification-specific blocker identity that can compete with it.

For a gated stall, the F01 `blocker_or_phase_result_hash` must be the canonical
digest of:

```text
{
  current_state,
  normalized_failure_kind,
  phase_or_step,
  task_or_finalizer_candidate_pointer,
  deterministic_rejection_or_phase_result_digest
}
```

It must exclude poll time, failure prose, `stall_count`, loop iteration,
watchdog report path, model/provider name, and tier history. The other F01
fields bind environment, session, chain, plan revision, phase, task, plan
attempt, and current authority fence.

Consequences:

- same session + plan revision + state + failure class + blocker = same
  occurrence across restart, repoll, message drift, and model-tier drift;
- changed state, changed authoritative blocker/result digest, changed plan
  revision, or changed fence = a new occurrence;
- a counter moving from five to six unchanged polls is not a new occurrence;
- a model swap is not a new occurrence unless it produces a genuinely different
  admitted phase result/blocker;
- incomplete identity is one terminal, non-claimable intake plus one linked
  obligation. It is never repaired by synthesizing `unknown`, a path, mtime, or
  process-local fence.

## Exact patch seams

### 1. Create the occurrence at the failure source

File: `arnold_pipelines/megaplan/auto.py`

Functions/seams:

- the `drive()` stall branch around `stall_count >= stall_threshold`;
- `_record_failure()` / `_record_lifecycle_failure()`;
- `_enqueue_lifecycle_failure_request()` and its `_derive_*` helpers on the
  T1.5 lineage.

Required delta:

1. Preserve the existing progress-sensitive detector: task/event/active-step
   progress or an in-flight LLM resets the counter. At the first threshold
   crossing, record one durable `gated_stall`/`stalled` terminal-or-recovery
   transition.
2. Obtain the already owner-bound `CustodyTargetKey`/F01 values from the current
   run/plan/finalizer record. Do **not** derive authority from workspace paths,
   plan-directory mtimes, environment fallbacks, `sha256:unknown`, or default
   attempt `1`.
3. Call the accepted T1.5 intake once and persist only the owner-returned
   `occurrence_id` with `latest_failure`/the canonical phase-result record.
4. If T1.4 has already created an occurrence for the exact deterministic
   finalizer rejection, reuse it. The later generic stall observation must not
   create a second “stall” occurrence for the same rejected candidate.
5. Retire the legacy lifecycle repair-queue enqueue at this seam. An accepted
   queue marker is not a claim or execution receipt and must not coexist with
   `simple_fixer` as a second scheduler.

The T1.5 candidate currently contains best-effort `_derive_fence_token()`,
`_derive_plan_revision()`, `_derive_attempt_from_metadata()`, and
`_derive_blocker_hash()` fallbacks in this route. They are not acceptable for
this patch. The accepted T1.5 lineage must either already remove them or this
patch must make incomplete owner identity fail closed.

### 2. Dispatch exactly one ordinary fixer attempt

Files:

- `arnold/recovery/simple_fixer.py`
- `arnold_pipelines/megaplan/cloud/simple_fixer.py`
- the accepted production recovery-owner adapter/service

Functions/seams:

- `ExactOccurrence.from_mapping()` and `ExactOccurrence.occurrence_id`;
- `intake_simple_fixer_occurrence()`;
- `run_simple_fixer()` and `reconcile_simple_fixer()`;
- the owner `run`/`reconcile` singleton claim and terminal replay;
- the typed provenance-incident operation corresponding to the conformance
  owner's `record_delegation_provenance_error()`.

Required delta:

1. The immediate trigger invokes `run` for the owner-accepted occurrence. The
   three-hour backstop invokes `reconcile` for that exact occurrence. Both must
   converge on the same atomic claim, attempt intent, result, and receipt.
2. Repeated `run`, `reconcile`, watchdog polls, restarts, and concurrent callers
   return the stored result or current state; they cannot mint another attempt.
3. A further attempt requires an explicit owner-authenticated transaction under
   the accepted T1.5 fix-the-fixer/retrigger contract. A poll, new process,
   model swap, rewritten message, deleted projection, or expired local lock is
   never such authority.
4. `DelegationProvenanceError` is not a fixer-launch prerequisite and must not
   launch a resident diagnostic. Record it once as a typed obligation/quiet
   transition keyed by `(occurrence_id, error_code, subject)`. Free-form detail
   is projection only. Never report an agent unless a durable launch manifest
   and result identity exist; under the T1.5 leaf topology this route should
   launch zero child agents.
5. Missing/corrupt owner state, response loss, or ambiguous provider
   application is terminal `UNKNOWN`/`INDETERMINATE` and non-redispatchable.

Do not weaken the T1.5 owner contract or add a second SQLite/local store in
Megaplan. If the accepted owner does not expose the typed quiet-transition
operation, add it to the authenticated owner protocol; do not call a test-owner
method from production.

### 3. Make the watchdog observation-only

File: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`

Functions/seams:

- `launch_chain_tick()`;
- `emit_current_needs_human_sidecar()`;
- `notify_needs_human()`;
- `dispatch_kimi_repair()`, `dispatch_meta_repair()`, mechanical relaunch, and
  direct Discord/webhook fallback branches reachable from the stalled path.

Required delta:

1. Resolve the occurrence reference recorded by the plan and perform only an
   owner `observe`/`reconcile` request. Do not reconstruct F01 from shell
   variables.
2. `PENDING`/`CLAIMED`/`RUNNING`: report “recovery in progress”; do not relaunch,
   dispatch another fixer, launch a diagnostic, or notify.
3. `SUCCEEDED`: report the accepted result and let the ordinary plan/chain
   owner perform any lawful state transition. The watchdog must not hand-advance
   `gated` or weaken the gate.
4. `FAILED`/`UNKNOWN`/`INDETERMINATE`/invalid intake: report the terminal owner
   state. Admit a human notification only if the canonical policy says a human
   decision is genuinely required.
5. Preserve `emit_current_needs_human_sidecar()` only as a read-only projection.
   Replace `notify_needs_human()` provider/diagnostic behavior with a call to
   the canonical notification admission boundary, or hard-fail closed if that
   boundary is unavailable. Remove direct calls to `arnold-discord-dm`, curl
   webhook fallback, resident diagnostic launch, Kimi/meta repair, and direct
   relaunch from this occurrence.

### 4. Admit notification only on an occurrence/state transition

Preferred file after T1.10 acceptance:
`arnold_pipelines/megaplan/cloud/incident_notification.py`

Relevant seams already prototyped there:

- `IncidentNotificationStore.admit()`;
- `IncidentNotificationStore.record_diagnostic_terminal()`;
- `CanonicalNotificationDeliveryWorker.run_once()`;
- `arnold_pipelines/megaplan/cloud/notification_worker.py`.

Required identity:

```text
notification_intent_id = H(
  occurrence_id,
  accepted_state_version,
  notification_kind,
  owner-authorized recipient,
  stable_payload_digest
)
```

The stable payload excludes timestamps, poll counts, paths, message wording,
and repeated diagnostics. Re-admitting the same occurrence/state returns the
same intent with `duplicate=true`; the watchdog emits no provider effect.
Provider delivery requires the outbox worker's singleton claim and durable
receipt. Response loss is `INDETERMINATE`, not permission to resend.

Resident reply provenance and alert routing are separate concerns. If resident
provenance is absent, record one terminal diagnostic transition and launch no
resident agent. A single alert may still go to an independently owner-approved
operations recipient policy; absence of such a policy means zero delivery, not
an arbitrary/direct fallback.

Default reminder policy is none. If an explicit human-reminder policy already
exists, each reminder must have a durable due time and ordinal and therefore a
new owner-approved transition/intent. `notify_every_check`, polling frequency,
process restart, and repeated `manual_review` observation can never create a
reminder.

Until T1.10 is independently accepted, use no unaccepted notification store as
production authority. The safe interim behavior after T1.5 is one quiet owner
transition and zero direct Discord calls.

### 5. Retire the pre-identity diagnostic compatibility path

Files on the deployed incident lineage:

- `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`

`launch_human_review_diagnostic()` currently calls `_resolve_provenance()`
before `_escalation_id()` and state creation; `main()` converts that exception
to blank state coordinates. Do not merely reorder those calls and keep the
resident fallback topology. After T1.5, the compatibility command should be a
typed retirement/delegation shim that accepts an existing owner occurrence,
records one provenance-unavailable transition, launches zero agents, and sends
zero notifications. The canonical fixer and notification workers own the only
effects.

## Regression matrix

Add focused tests on the accepted T1.5 lineage:

1. `tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`
   - five unchanged `gated/finalize` iterations create one owner occurrence;
   - restart and another five identical observations return the same occurrence;
   - progress heartbeat resets the stall counter;
   - state or authoritative blocker digest change creates a new occurrence;
   - stall-count/message/model-tier changes do not.
2. `tests/cloud/test_simple_fixer.py`
   - immediate + reconciler race and 200 observers produce one claim, one
     ordinary attempt, and one terminal result;
   - restart/repoll preserves the same result;
   - no owner-authorized further attempt means no second dispatch;
   - provenance failure with two different details produces one obligation,
     one quiet transition, zero retry, and zero child launch;
   - response loss/corruption stays indeterminate/unknown and non-redispatchable.
3. `tests/cloud/test_watchdog_wrappers.py`
   - replay the pasted `manual_review; state=gated; failure=stalled` snapshot 200
     times, including fresh watchdog processes: one occurrence, one ordinary
     fixer dispatch, at most one admitted notification, no identical DMs;
   - the exact missing-provenance exception records once, confirms no agent,
     and remains quiet across restart/repoll;
   - changed state/blocker admits a second occurrence/transition;
   - direct Discord, webhook, Kimi/meta repair, diagnostic, and relaunch helpers
     are never invoked.
4. `tests/cloud/test_human_review_diagnostic.py`
   - replace retry/fallback expectations with typed retirement: existing
     occurrence required, no pre-identity blank result, zero resident launches,
     zero provider calls, idempotent terminal provenance record.
5. Notification tests on the accepted T1.10 lineage
   - same occurrence/state/payload across process restart returns the same
     intent and provider claim;
   - one provider success receipt prevents all re-delivery;
   - ambiguous response forbids re-dispatch;
   - reminder only fires for an explicit due ordinal;
   - malformed/missing provenance never selects an arbitrary recipient.
6. `tests/cloud/test_simple_fixer_retirement.py` and installed-wheel/materialized
   wrapper tests
   - every historical watchdog/repair/meta/diagnostic entry point is either an
     observation-only delegate to the fixed owner or exits typed fail-closed;
   - installed behavior and help/schema digests match the tested source.

The critical end-to-end assertion is measurable: for one unchanged gated-stall
occurrence after 200 polls and two process restarts, counts are
`occurrences=1`, `ordinary_fixer_attempts<=1`, `resident_agent_launches=0`,
`notification_intents<=1`, and `provider_messages<=1`. With missing notification
authority or recipient policy, both latter counts are zero.

## Composition and rollout order

1. Wait for an independently accepted T1.5 commit/tree. Rebase this narrow
   adapter patch onto that exact tree; do not merge the unaccepted T1.5
   conformance owner or revive its retired queue/wrapper paths.
2. Preserve T1.5 as the sole occurrence/claim/attempt authority. This patch adds
   only failure-source admission, observation wiring, and notification
   transition projection.
3. When accepted T1.4 finalizer admission exists, its deterministic rejection
   occurrence wins; gated-stall handling reuses it instead of opening another.
4. When accepted T1.10 notification custody exists, connect the transition to
   its outbox. Before then, fail closed and quiet rather than direct-message.
5. Validate focused concurrency/restart tests, dependency closure, installed
   wheel, materialized wrappers, and static bypass scans before any deployment.
6. This patch must not resume or hand-advance the poisoned v2 plan. Its false
   predecessor evidence and mixed runtime history remain. After the recovery
   generation is accepted and deployed, launch a fresh successor plan/occurrence
   and prove ordinary plan -> critique -> gate -> finalize advancement.

## Custody note

Before the read-only custody correction arrived, an isolated worktree and
branch had already been created:

- worktree: `/private/tmp/arnold-critique-recovery-incident-stall-notify-20260802`
- branch: `fix/critique-recovery-incident-stall-notify-20260802`
- base/HEAD: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- state at stop: clean; no source edits and no commits

It was preserved untouched. Nothing was deleted or reset. No cloud, provider,
owner, checklist, source, or Git mutation was performed after the correction.
