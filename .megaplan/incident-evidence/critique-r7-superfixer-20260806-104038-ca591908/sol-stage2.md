## 1. ADJUDICATED ROOT CAUSE

### Facts

- The chain remains blocked at milestone 0, plan iteration 5, with no completed milestones. The final events are a third `finalize` start and `state_written`, with no matching `phase_end`. The runner is dead and its liveness lease is stopped. Evidence: [current delta pack](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/evidence-pack-delta.md), [state.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/state.json), [events.ndjson](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/events.ndjson).
- Gate v5 durably returned `PROCEED`, hash `9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b`. Finding `CF-0B506E1EDCD92E90C192` remained `accepted_tradeoff` with a fixed-plan claim but no `verified=true`, no explicit `gate_resolution`, and no v5 carry entry. Evidence: [gate.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/gate.json), [faults.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/faults.json), [gate_carry.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/gate_carry.json).
- Bound runtime A rejects that state. Runtime B adds exactly the missing `accepted_tradeoff && gate_expected && fixed_claim` branch and resolves the 95-finding sweep, but B is not an authorized chain binding. The chain requires an exact editable-runtime match and records no rebind event. Evidence: [full evidence pack](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/evidence-pack.md), [FQ-02](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/swarm/fq-02.txt), [FQ-07](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/swarm/fq-07.txt), [chain.yaml](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml).
- The one canonical producer invocation was rejected because the F01 `attempt` field was empty; no finalize request, authority decision, claim, epoch, or WBC attempt was created. Evidence: [repair-producer-attempt.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/repair-producer-attempt.json), [repair_delegation.py](/workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan/cloud/wrappers/repair_delegation.py).

### Adjudication

The prior root-cause adjudication is confirmed and refined.

**First broken contract:** the gate-to-finalize resolution contract admitted `PROCEED` without proving that the exact artifact set was consumable by the exact bound finalize policy. Runtime A then failed closed on the resulting `accepted_tradeoff` representation. The deeper defect is the absence of a versioned, content-addressed resolution envelope linking finding state, plan mutation, gate decision/carry, validator policy, and runtime identity.

**Missed backstop:** before `PROCEED`, no compatibility validator exercised the accepted findings against runtime A’s finalize policy. A second recovery backstop also failed: the lifecycle coordinator did not leave a canonical finalize-attempt/repair-identity record after the phase subprocess failed, so the repair producer could not acquire authority.

The empty attempt is **not repairable retrospectively by an ordinary fixer**. Current state has neither `active_step` nor a repair-identity seed; reconstructing an attempt from event labels, liveness, iteration counts, or projections is expressly non-authoritative. A prospective source fix can prevent recurrence, but cannot turn this historical record into authority. Recovery of this occurrence therefore requires external Run Authority/operator approval for a content-addressed rebind or an authority-approved migrated child.

### Flash overrides and qualifications

- FQ-02 is accepted: B’s custody change is the uniquely relevant A→B behavioral delta.
- FQ-04’s statement that a fresh enqueue seam exists is qualified: the seam exists, but the current occurrence cannot satisfy its mandatory F01 tuple.
- FQ-05’s “zero committed effects” finding is limited to observed local finalize artifacts. Whether the interrupted third attempt caused an unrecorded external effect remains **INDETERMINATE**.
- FQ-07 controls the runtime decision: B’s ancestry and successful reproduction are not authorization.
- FQ-01 remains `MISSING_STRUCTURE`; whether selector/output declarations are mandatory under the current framework is **INDETERMINATE**.
- FQ-09’s twelve work-ledger TypeErrors are non-causal observability defects, not an independent retry authority.
- The prior Sol2 quarantine-only Horizon A is overridden because it does not satisfy the current recovery-handoff contract.

## 2. HORIZON A — `agent_actionable: true`

**Decision: option (ii), a genuinely external Run Authority/operator gate.**

The completed checkpoint route is:

1. The executor validates this envelope and confirms the authoritative fingerprint remains `sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9`.
2. It materializes exactly one recovery handoff and one follow-up ticket in the existing epic, assigns them to the Run Authority/operator owning execution binding and recovery admission, and leaves the schedule active. No new notification is admitted for this repeated poll.
3. Run Authority/operator must choose and authorize one supported route:

   - an atomic, CAS-protected A→B rebind naming A’s full prior identity and B’s computed content identity, updating both marker and chain binding; or
   - an authority-approved migrated child with fresh runtime, fence, attempt, grant, custody, and WBC identity.

   A marker-only `update_marker_runtime` call is insufficient.
4. The authorization must also account for the missing historical finalize attempt. It must create a canonical recovery-dispatch attempt through an authority-owned seam; it must not backfill authority from `events.ndjson`, `state.json`, PID, or liveness.
5. Only after that attempt exists may the canonical repair producer be rerun **once**. It must mint exactly one blocker-specific request.
6. The request then follows one ordered path: Run Authority decision → one Custody claim/epoch/lease → one WBC attempt/effect key → one ordinary-fixer finalize invocation → real validator and after-proof.
7. Any rejection, identity drift, CAS conflict, missing effect-barrier receipt, duplicate request/claim/attempt, lease or fence loss, repeated custody error, absent `phase_end`, new error family, or notification ambiguity returns the occurrence to quarantine with zero further retries.

The source-level owner for prospective attempt durability is the Megaplan auto/lifecycle coordinator in `arnold_pipelines/megaplan/auto.py`, persisted through `PlanRepository.record_lifecycle_failure`. That repair belongs to Horizon B because it cannot retroactively authorize this occurrence.

Focused release tests must include:

- `tests/orchestration/test_critique_custody.py`
- `tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py`
- `tests/arnold_pipelines/megaplan/test_chain_execution_binding.py`
- `tests/cloud/test_runtime_cutover.py`
- `tests/cloud/test_repair_delegation.py`
- `tests/cloud/test_repair_requests.py`
- `tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py`

Required deployment/rebind proof is a content-addressed candidate, focused-test receipt, supported cloud deployment provenance, Run Authority authorization, matching marker and chain CAS receipts, runtime import-root verification, canonical recovery-attempt record, and one producer result. B’s complete content identity is not durably recorded in the supplied evidence and is therefore **INDETERMINATE until computed by the supported deployment path**.

**Next owner:** Run Authority/operator for this session’s execution binding and recovery admission.

**Return condition:** an authoritative receipt names the chosen rebind or migrated-child route, exact prior/target runtime identities, CAS parents/results, effect-barrier result, new fence rule, and canonical recovery-dispatch attempt. The next attempt is the first configured active schedule fire after that receipt validates; its exact UTC timestamp is **INDETERMINATE** from the allowed evidence.

**After-proof:** exactly one request, one grant, one claim/epoch, one WBC attempt, one validated finalize publication or validated idempotent no-op, matching runtime identity across all surfaces, milestone advancement, terminal Custody/WBC receipts, and zero Horizon A notification effects.

## 3. HORIZON B — `epic_update_required: true`, `agent_actionable: false`

Update the existing [critique-ledger-accountability-v3-r7-20260805 initiative](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/README.md). Do not create another authority epic.

The smallest complete category fix is one append-only `arnold.megaplan.recovery_admission.v1` contract referencing versioned subrecords for:

- critique resolution and complete gate-carry history;
- canonical phase dispatch/attempt and failure CAS;
- prior/current runtime identity and rebind/migration history;
- request, Run Authority decision/grant, Custody claim/epoch/lease, and WBC attempt/effect;
- validator task/result envelopes;
- notification intent/effect and dedupe identity.

Every record must be content-addressed and linked by previous-record digest. Projections remain non-authoritative.

Required changes:

- **Critique/gate/finalize:** update `orchestration/critique_custody.py`, `handlers/gate.py`, `handlers/finalize.py`, and `orchestration/finalize_authority.py` so contradictory or unsupported resolution state fails before `PROCEED`.
- **Attempt ownership:** update `auto.py` and `store/plan_repository.py` to persist a canonical phase-attempt record before subprocess dispatch and retain it through pre-WBC exceptions, missing phase results, cleanup, and deterministic-failure publication.
- **Run Authority/Custody/WBC:** require exact occurrence, runtime, fence, epoch, and CAS bindings; terminalize self-recovered requests; enforce one claim and one attempt.
- **Runtime binding:** make rebind/migration atomic across `chain/execution_binding.py`, `cloud/runtime_cutover.py`, `cloud/runtime_provenance.py`, session marker, chain state, authority journal, Custody, and WBC.
- **Fixer/observer:** keep `cloud/wrappers/repair_delegation.py` fail-closed; expose missing canonical attempt as a typed recovery-admission gate; distinguish authoritative absence from projection absence; surface missing `phase_end`.
- **Notifications:** place intent after the authority-defined terminal decision, with one deterministic occurrence/conduit key and an at-most-once effect.
- **Observability:** fix the duplicate `transition` keyword path in `observability/work_ledger.py`; add metrics for missing carry, policy mismatch, attempt-loss, unmaterialized authority, runtime drift, CAS conflict, duplicate claims, missing phase completion, quarantine, and intent/effect divergence.

Migration must append receipts without rewriting historical gate, fault, state, chain, request, or lease artifacts. Complete provenance may be backfilled as evidence; incomplete provenance must remain quarantined and cannot acquire authority.

Epic crosswalk:

- **CL2:** resolution envelope, phase-attempt persistence, WBC replay, migration fixtures.
- **CL3:** observer/fixer consumption and exact evidence-set briefing identity.
- **CL4:** gate/finalize compatibility validation, carry completeness, disposition semantics.
- **CL5:** atomic runtime cutover, recovery admission, notification custody, legacy retirement.

Dependencies are schema freeze → attempt/runtime authority transaction → gate/finalize enforcement → migration and replay → CL5 cutover. Schema/migration, critique validation, authority transaction, observer/fixer, and notification work may proceed in parallel after the schema freezes.

Unfinished very-hard decisions remain **INDETERMINATE**: fixed-tradeoff equivalence, exact-finding versus family identity, same-occurrence rebind versus migrated child, mandatory selector/output declarations, legacy CAS backfill eligibility, and terminal notification conduit ownership.

Category closure requires retroactive R7 and bigbang replay with crash injection at every boundary, yielding exactly one repair occurrence, one claim, one attempt, at most one notification effect, real validator success, preserved runtime/authority lineage, cursor advancement, and no orphan request, grant, lease, claim, reservation, intent, or effect.

## 4. MACHINE-READABLE ENVELOPE

<arnold.superfixer.recovery_handoff.v1 envelope>

```json
{
  "schema": "arnold.superfixer.recovery_handoff.v1",
  "handoff_id": "sha256:<content-hash>",
  "target": {
    "session": "critique-ledger-accountability-v3-r7-launch-20260805",
    "plan": "cl2-wbc-backed-ledger-20260805-2140",
    "occurrence": "occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee"
  },
  "evidence": {
    "pack": "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/evidence-pack-delta.md",
    "sol_stage1": "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/sol-stage1.md",
    "swarm_index": "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/swarm-index.json",
    "sol_stage2": "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/sol-stage2.md"
  },
  "horizon_a": {
    "route": "external_run_authority_gate_then_authorized_rebind_or_migrated_child_then_one_canonical_repair",
    "agent_actionable": true,
    "canonical_owner": "Run Authority/operator owning chain execution binding and recovery admission; after approval, the Megaplan lifecycle coordinator owns canonical attempt production",
    "preconditions": [
      "Envelope validates and its handoff_id is computed over the exact envelope bytes",
      "Authoritative pre-effect fingerprint equals sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9",
      "Chain spec sha256 equals da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1",
      "Plan v5 sha256 equals 4537c985a9e8f1258af71d97d1d631b8ba6d0bcfc83b9a56fbd29cb327160f46",
      "Gate sha256 equals 9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b and recommendation remains PROCEED",
      "Chain remains blocked at milestone index 0 with completed empty",
      "No live runner, in-flight recovery, finalize repair request, finalize claim, or finalize WBC attempt exists",
      "Runtime A remains the recorded binding and runtime B remains unauthorized until the external gate is satisfied",
      "The interrupted third finalize attempt is covered by an authority-accepted effect-barrier receipt",
      "Exactly one follow-up ticket and one handoff receipt are materialized while the schedule remains active"
    ],
    "operations": [
      "Materialize this blocked checkpoint and exactly one follow-up ticket assigned to the Run Authority/operator; do not notify on this repeated poll",
      "Await explicit authority approval for either an atomic content-addressed A-to-B rebind or an authority-approved migrated child",
      "Persist the approved runtime transition in every authoritative identity surface using CAS; a marker-only rebind is forbidden",
      "Create a canonical recovery-dispatch attempt through an authority-owned seam; do not infer the missing historical attempt from labels, events, liveness, PID, or projections",
      "Rerun the canonical repair producer exactly once after the complete attempt tuple exists",
      "Submit exactly one blocker-specific request for Run Authority decision",
      "After a grant, acquire exactly one Custody claim with a fresh lease and epoch",
      "Reserve exactly one WBC attempt and effect key",
      "Invoke finalize exactly once through the ordinary fixer under the authorized runtime",
      "Run the real validator and collect immutable publication, state, chain, Custody, WBC, runtime, and notification after-proof"
    ],
    "focused_tests": [
      "tests/orchestration/test_critique_custody.py",
      "tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py",
      "tests/arnold_pipelines/megaplan/test_chain_execution_binding.py",
      "tests/cloud/test_runtime_cutover.py",
      "tests/cloud/test_repair_delegation.py",
      "tests/cloud/test_repair_requests.py",
      "tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py"
    ],
    "deployment_or_rebind_proof": [
      "Content-addressed candidate commit, tree, import root, and runtime content sha256",
      "Focused-test receipt bound to the candidate content identity",
      "Supported cloud deployment provenance showing the executable imports the authorized candidate",
      "Run Authority approval naming runtime A prior identity and the exact target identity",
      "Matching CAS receipts for session marker and chain runtime_binding, or an authority-approved migrated-child receipt",
      "Canonical recovery-dispatch attempt and one successful producer result",
      "Post-effect fingerprint and validator receipts matching the authorized occurrence"
    ],
    "external_gate": "Explicit Run Authority/operator approval is required because runtime B is not an authorized binding and no canonical finalize attempt exists. The authority owner must authorize an atomic content-addressed rebind plus canonical recovery-dispatch attempt, or authorize a migrated child. Ordinary fixers may not reconstruct the missing attempt or mint rebind authority.",
    "return_condition": "Resume only after the external authority receipt, runtime transition or migrated-child receipt, effect-barrier receipt, new fence rule, and canonical recovery-dispatch attempt all validate. Then run one producer, one request, one decision, one claim/epoch, one WBC attempt, and one finalize verification. The scheduled next attempt is the first configured active schedule fire after this condition; exact UTC time is INDETERMINATE."
  },
  "horizon_b": {
    "epic_update_required": true,
    "epic_slug": "critique-ledger-accountability-v3-r7-20260805",
    "ticket_or_crosswalk": ".megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/ recovery-admission crosswalk for CL2 attempt persistence, CL3 observer/fixer, CL4 gate-finalize compatibility, and CL5 runtime cutover/notification custody; pending executor materialization in the existing epic",
    "first_broken_contract": "Gate-to-finalize critique-resolution compatibility was not versioned or validated against the exact bound finalize policy before PROCEED",
    "category_closure_proof": [
      "Replay immutable R7 and critique-ledger-bigbang failure-family fixtures",
      "Produce exactly one repair occurrence per logical recovery",
      "Produce exactly one Custody claim and one WBC attempt per repair occurrence",
      "Produce at most one notification effect per logical recovery",
      "Pass the real validator with content-addressed runtime and authority lineage",
      "Advance the plan cursor or chain milestone without rewriting historical evidence",
      "Leave no orphan request, grant, lease, claim, reservation, notification intent, or notification effect",
      "Pass crash injection at request, decision, claim, WBC start, finalize publication, custody release, notification intent, and delivery effect boundaries"
    ]
  },
  "stop_gates": [
    "Authoritative fingerprint mismatch",
    "Envelope validation or handoff hash failure",
    "Canonical state advanced or occurrence identity changed",
    "Live runner, recovery owner, custody claim, or WBC attempt appears",
    "External Run Authority/operator approval absent, ambiguous, or unsigned",
    "Runtime B content identity absent or not authorized",
    "Marker and chain runtime bindings disagree or lack atomic CAS proof",
    "Canonical recovery-dispatch attempt remains absent",
    "Effect-barrier receipt for the interrupted third finalize attempt is absent",
    "Selector/output policy remains required but unresolved",
    "Category-risk decision remains required but unresolved",
    "Fence or lease rule is ambiguous at admission",
    "Canonical producer returns zero_authority_rejected or any non-delegated outcome",
    "Duplicate request, decision, claim, attempt, or notification identity appears",
    "Validator rejects, phase_end is missing, custody error repeats, or a new error family appears",
    "Any notification intent or effect is ambiguous"
  ],
  "notification_key": "sha256:70c522f651d6859e134250ee47500aa6e1dbbd824a69ac1b119444f1610f0142"
}
```

The `sol_stage2` path above is the executor’s materialization target; this read-only pass did not create it.

## 5. SAFETY

This Sol pass was strictly read-only. It did not edit files, mint a request, claim custody, reserve WBC, launch, resume, restart, rebind, notify, update the epic, create a ticket, or alter the schedule. The launch checkout remains untouched.

The recorded fingerprints before prior Sol1, after prior Sol1, after prior Sol2, and before this fire are all `sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9`: [prior before](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/fingerprint-before.json), [prior after](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/fingerprint-after.json), [current before](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/fingerprint-before.json).

The executor must validate the envelope and verify pre/post fingerprints byte-for-byte. It must execute no Horizon A effect unless the pre-fingerprint matches, the external authority gate is satisfied, and every applicable stop gate is clear.