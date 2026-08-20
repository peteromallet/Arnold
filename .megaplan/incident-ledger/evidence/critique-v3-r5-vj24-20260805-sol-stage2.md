## Adjudicated root cause

The first broken contract is the selector/task-output contract at VJ24. `tests/arnold/critique_ledger/test_replay_v2.py` was declared as a prospective T18 output in both plan metadata revisions and recognized that way by VJ19, yet VJ24 could not resolve it as a declared output. No persisted, content-addressed normalized selector→producer map identifies what VJ24 actually consumed. This is both:

- adherence failure: VJ19, VJ24, plan finalization, and execution admission did not demonstrably consume the same declaration;
- missing structure: there is no immutable selector contract joining plan revision, validator identity, runtime identity, and accepted task outputs.

The selector is not an accepted T18 output—T18 never ran—but it may still be a legitimate intended T18 output. It must be classified from pinned-runtime evidence as:

1. legitimate prospective T18 output, making VJ24’s declaration reader wrong;
2. stale plan declaration, requiring a new plan revision;
3. revision split, where VJ19 and VJ24 used different plan/runtime/normalizer identities.

Current evidence cannot safely select among those three.

The deeper issue is loss of one immutable, occurrence-bound causal history across execution evidence, runtime binding, repair custody, observation, and effects. Earlier claim/diff, write-set, test-budget, and acknowledgement mismatches were not failed closed; runtime/chain bindings changed without a supplied accepted migration event; and VJ24 produced no canonical repair occurrence. This is also both missing adoption and missing structure.

The canonical owner is the existing Custody Control Plane composition:

- Run Authority decides whether the occurrence may be acted upon and supplies the coordinator fence.
- Custody owns the occurrence claim, renewable lease, and epoch.
- WBC owns the repair attempt, effects, outcomes, and accepted evidence.
- The Canonical Run-State Resolver classifies the blocked state but grants no positive authority.

Watchdogs, repair queues, PID locks, markers, status snapshots, incident projections, and notification schedulers are not alternate owners.

Luna disagreements resolve as follows:

- L1 is correct that no output was produced, but “not a legitimate T18 output” is too strong if read as a declaration judgement. It is an unproduced, plan-declared candidate output whose legitimacy remains unresolved.
- L4’s quarantine-and-migrate recommendation controls: same-occurrence resume is unsafe without an already accepted immutable migration record, and none is supplied.
- L8’s VJ24 event is the earliest trustworthy checkpoint for the current blocker, not a trustworthy checkpoint from which earlier execution claims may be reused.
- L6 does not prove duplicate provider delivery. Notification delivery is unknown, so ambiguous effects must be suppressed rather than replayed.

## Immediate recovery decision

The only safe immediate action is authoritative reconciliation and quarantine. The r5 VJ24 occurrence must not be resumed directly. The epic may move only through an accepted migrated child run revision/new attempt.

1. **Capture the authoritative before-state host-side.** Use the owning Megaplan host/provider status API and authoritative Run Authority, Custody, and WBC readers. Do not fall back to SSH from inside the workload. Record a read-coherent snapshot containing:

   - session `critique-ledger-accountability-v3-r5-20260803`;
   - plan `cl2-wbc-backed-ledger-20260803-1357`;
   - chain state `chain-a5c760402ea2`;
   - `state=blocked`, `phase=execute`, `retry_strategy=repair_validation_failure`;
   - VJ24 event time and exact blocker text;
   - pending T18/T23 and empty batch-15 result envelopes;
   - stopped lease and runner fence 11;
   - all Run Authority, Custody, WBC, repair, binding, and notification records, including authoritative absence records where supported.

2. **Obtain—not synthesize—the missing identities.**

   - immutable run ID and run revision;
   - canonical occurrence ID and normalized VJ24 fingerprint;
   - plan revision and hashes of plan metadata, chain bytes, and selector contract;
   - source commit/tree;
   - runtime content SHA, validator source hash, interpreter/import roots, wrapper/config/schema hashes;
   - chain-execution binding and any accepted migration predecessor;
   - current Run Authority decision/grant and coordinator fence;
   - Custody lease ID, owner, host, and epoch;
   - WBC contract version, attempt, effect, and result-envelope IDs;
   - repair request, decision, claim, lease, and attempt IDs;
   - notification intent key, outcome, and provider receipt or typed `INDETERMINATE`.

   The known source head `c116f38…`, runtime SHA `d0fa249a…`, PID, marker digest, and runner fence alone do not complete this identity set.

3. **Classify the selector using pinned-runtime evidence.** Read the exact VJ19 and VJ24 declaration readers from the pinned runtime, normalize the selector consistently, and compare:

   - VJ19 and VJ24 selector→task maps;
   - `plan_v1.meta.json` and `plan_v2.meta.json` hashes;
   - validator source hashes and runtime/import identities;
   - the machine-readable T18 output declaration;
   - accepted output-envelope hashes.

   Then:

   - If both revisions canonically declare the selector for T18, repair the declaration reader/scheduling contract. Do not create the file as a preflight workaround.
   - If the canonical task contract does not require it, supersede the stale declaration through an accepted new plan revision.
   - If any plan, runtime, validator, or normalizer identity differs, classify a revision split and require migration.
   - If the evidence cannot discriminate, retain `INDETERMINATE` and keep the run quarantined.

4. **Quarantine the failed occurrence and suspect execution authority.** Preserve state, history, VJ19, VJ24 raw output, batch 15, binding refusals, and all earlier audits append-only. Earlier outputs may be reused only after they are independently re-admitted under complete WBC envelopes; prose claims or old task labels are not reusable authority.

5. **Submit the canonical repair operation.** The path is:

   `request → accepted Run Authority decision → Custody claim/lease/epoch → WBC repair attempt → fenced effect → terminal or INDETERMINATE outcome → independent verification`

   The request must target the exact VJ24 occurrence and immutable identities, use a deterministic idempotency key, and request either selector-contract repair or migration/new-attempt creation. A legacy repair-data file or watchdog queue entry may only project this canonical record.

6. **Create an accepted migrated child revision.** Because the existing occurrence crossed unjoined binding changes, it cannot resume semantically. The migration receipt must preserve VJ24 as its parent, identify superseded and replacement plan/runtime/chain contracts, and establish a fresh Run Authority fence, Custody epoch, and WBC attempt.

7. **Relaunch only after all admission gates pass.** Use the Megaplan chain lifecycle CLI/API’s supported migration/new-attempt operation as defined by the pinned runtime. The available evidence does not establish safe literal syntax. Require its durable launch-admission/migration receipt and CAS result. A generic `resume`, `recover-blocked`, execute retry, supervisor restart, or `chain start` acknowledgement is insufficient.

We must not fabricate `test_replay_v2.py`; edit or clear state; use `--fresh`, force-proceed, hand-advance, or generic `recover-blocked`; rebind in place; replay ambiguous notifications; trust VJ19 deferral, worker prose, PID/tmux/heartbeat/marker state, or launch acknowledgement as success.

## Durable architecture

Adopt the existing Run Authority/WBC/Custody architecture; do not build a second control plane.

1. **One selector/task-output contract.** Finalization emits a machine-readable, content-addressed contract containing normalized selectors, producing task, output type/path, validation timing, declared writes, test budget, and plan revision. Planner, executor, validator, repository auditor, and authority reader consume the same hash. Deferred output is a typed state, never a pass.

2. **Immutable run/runtime/chain identity.** Adopt `arnold.megaplan.chain_execution_binding.v1` and extend its launch manifest to bind chain bytes, plan contract, source tree, runtime content, interpreter/import roots, wrappers/configuration, and schema versions. Binding changes require an append-only, operator/authority-approved migration transaction creating a new run revision.

3. **Occurrence-bound repair custody.** Every deterministic blocker mints one occurrence through the Canonical Run-State Resolver. Run Authority, Custody, and WBC are reread conjunctively before request acceptance, claim, effect, retry, and terminal transition.

4. **Host-side authoritative observer.** Host/provider code reads authoritative stores and emits a redacted, read-coherent snapshot. In-container status remains a local projection and must never obtain host SSH credentials or become positive authority.

5. **Notification intent/effect custody.** Key intents by occurrence, accepted state version, target, and effect class. Persist intent before delivery and persist provider receipt, rejection, or `INDETERMINATE` afterward. Repeated/stale observations reuse the same key and cannot generate another effect.

6. **Fail-closed validation and backstops.** Missing selector contracts, revision disagreement, incomplete envelopes, undeclared writes, exhausted test budgets, attribution mismatch, stale authority, or missing custody produce typed blockers before dispatch. The backstop must mint exactly one occurrence-bound repair request and must never launch a fixer directly.

Legacy repair queues, repair-data JSON, PID locks, watchdog reports, session markers, incident projections, cloud snapshots, scheduler metadata, and notification sidecars become projections/adapters behind these owners. The append-only incident ledger remains an explanatory projection, not an authority ledger.

## Implementation cutline

### Must ship before relaunch

- Selector contract and admission:

  - `arnold_pipelines/megaplan/orchestration/plan_contracts.py`
  - `test_selection.py`
  - `task_satisfaction.py`
  - `evidence_contract.py`
  - `authority_readers.py`
  - `arnold_pipelines/megaplan/handlers/finalize.py`
  - `handlers/execute.py`
  - `execute/batch.py`, `aggregation.py`, `quality.py`

  Add a content-addressed `selector_task_output_contract.v1` schema and accepted task-result envelope schema.

- Canonical blocked transition and repair admission:

  - `run_state/model.py`, `resolver.py`, `classifiers.py`, `evidence.py`
  - `cloud/repair_contract.py`, `repair_requests.py`
  - `cloud/wrappers/arnold-watchdog`
  - `cloud/wrappers/arnold-repair-trigger`

  Add `repair_validation_failure` as a typed resolver outcome and `repair_occurrence.v1` carrying run revision, occurrence, authority fence, Custody epoch, WBC attempt, binding, and idempotency identities. Wrappers may request/project; only canonical custody may claim or dispatch.

- Immutable migration:

  - active chain lifecycle code under `arnold_pipelines/megaplan/chain/`
  - `runtime/execution_environment.py`
  - `cloud/cli.py`

  Implement/adopt the missing execution-binding and migration transaction behind `arnold.megaplan.chain_execution_binding.v1`.

- Authoritative observation:

  - `cloud/status_snapshot.py`
  - `cloud/cli.py`
  - `cloud/providers/ssh.py`

  Add a host-side coherent authoritative read. Prevent workload-side fallback to host SSH.

- Notification gate:

  - `resident/scheduler.py`, `resident/discord.py`
  - `incident/schema.py`, `incident/ledger.py`, `incident/projection.py`
  - `cloud/incident_bridge.py`

  Add `notification_intent_effect.v1`; stale or ambiguous effects fail closed.

Required pre-relaunch regressions:

- VJ19 and VJ24 consume and persist the identical normalized map/hash.
- A prospective T18 selector defers legally before T18 and cannot be mistaken for an accepted output.
- A stale selector requires a new plan revision.
- A plan/runtime/normalizer split fails closed and requires migration.
- Empty or incomplete result envelopes cannot advance T18/T23.
- Binding drift cannot resume without an accepted migration receipt.
- Repeated observer polls cannot create repair or notification effects.
- Host status succeeds without nested SSH from the workload.

### Follow-up work

- Retire direct writers/readers of repair-data, PID locks, mutable marker authority, scheduler-local dedupe, and sidecar-driven dispatch under M11 zero-reader/zero-writer gates.
- Re-admit or permanently quarantine earlier batch evidence.
- Add provider-specific reconciliation for `INDETERMINATE` notification delivery.
- Backfill historical lineage where possible without converting missing evidence into inferred success.

The very-hard/high-stakes items are immutable migration semantics, fencing/CAS across Run Authority–Custody–WBC, safe historical evidence re-admission, and provider-effect ambiguity. Selector-contract implementation, host observer work, notification persistence, and independent regression fixtures are parallelizable, but their conformance tests must converge on the same identity schemas.

A mandatory retroactive regression must replay the exact VJ24 text with the same session, plan, phase, selector, accepted state version, and occurrence identity through repeated watchdog polls and concurrent repair triggers. Acceptance is exactly one canonical repair request, one Custody claim, one WBC fixer attempt, one notification intent, and at most one provider effect; all duplicates must resolve as idempotent no-ops. The same text under a new accepted state version must create a distinct occurrence only when the resolver’s recurrence policy says so.

## Proof gates

### Authoritative before-state

A signed/content-addressed coherent read must establish:

- the exact r5 blocked occurrence, cursor, VJ24 fingerprint, and state version;
- stopped or absent active custody, with current RA/Custody/WBC records;
- immutable plan, chain, source, runtime, import, validator, and selector-contract identities;
- VJ19 as deferred, no VJ24 success artifact, T18/T23 pending, and no accepted batch-15 envelopes;
- all existing repair and notification intents/effects, including typed absence or `INDETERMINATE`;
- quarantine status for earlier non-authoritative task evidence.

### Authoritative after-state

Evidence must show:

- the original VJ24 occurrence remains immutable and quarantined;
- an accepted migration receipt links it to a fresh run revision and attempt;
- current Run Authority grant/fence, Custody lease/epoch, and WBC attempt agree;
- the repaired selector contract has one hash consumed by finalizer, executor, and validator;
- VJ24 has a real accepted success result bound to that contract, runtime, source tree, and attempt;
- T18 and T23 each have accepted result envelopes with declared and observed writes, tests, budgets, acknowledgements, content/tree hashes, and WBC acceptance;
- the canonical cursor/state version has advanced beyond the failed execute occurrence into the next valid phase or chain milestone;
- notification intent/effect records demonstrate no duplicate delivery, or one effect plus a reconciled provider receipt;
- any later blocker has a different occurrence/fingerprint and does not overwrite VJ24.

### Acceptance

The epic is “moving” only when authoritative state records accepted VJ24 success, accepted T18/T23 envelopes, and a CAS-protected cursor or milestone advance under the migrated lineage. A PID, process, tmux session, marker, heartbeat, lease renewal alone, launch acknowledgement, model prose, raw command output, or deferred validation does not count.

## Sol overrides and confidence

Rejected or qualified Luna recommendations:

- L1’s “not a legitimate T18 output” is narrowed to “not an accepted T18 output.” Its legitimacy as a prospective declaration remains unresolved.
- No report may infer that repeated notifications were actually delivered; provider delivery is unknown.
- A generic new plan is insufficient. It must be a causally linked, authority-approved migrated child revision.
- Adding `repair_validation_failure` only to the legacy repair queue is insufficient. The transition must enter canonical Run Authority/Custody/WBC custody.
- VJ24 is the current blocker checkpoint, but not permission to reuse earlier execution results.
- The final pinned runtime path and launch verification do not cure prior binding drift without an accepted migration manifest.

Remaining unknowns are the exact pinned-runtime VJ24 reader and map, remote plan/validator artifact hashes, whether unreported canonical authority records exist, the precise supported migration CLI/API syntax, notification provider receipts, and how much earlier output can be independently re-admitted.

Confidence is high that r5 is stopped, VJ19 is not a pass, T18/T23 lack accepted results, direct same-occurrence resume is unsafe, and quarantine plus migration is required. Confidence is medium on the selector’s ultimate classification and exact code cut because the local checkout differs from the pinned remote runtime.

The safe immediate decision is therefore reconciliation and quarantine—not relaunch.