## 1. ADJUDICATED ROOT CAUSE

**First broken contract.** The gate-to-finalize critique-custody contract produced a state that runtime A could not consume: finding `CF-0B506E1EDCD92E90C192` was persisted as `accepted_tradeoff` with a traceable fixed-plan mutation, but without `verified=true`, a `gate_resolution`, or a v5 `gate_carry` entry. Runtime A, bound at `d5848010695e` with content SHA-256 `e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6`, consequently raised `critique_finding_unresolved`. Runtime B, commit `77b76e3a4`, adds the exact missing `accepted_tradeoff && gate_expected && fixed_claim` resolution branch and clears all 95 findings.

**Deeper issue.** The pipeline lacks one versioned, machine-readable contract tying critique resolution semantics to gate carry, finalize policy version, runtime content identity, and authorized runtime history. A valid semantic result can therefore become unreadable when the consumer is bound to an earlier policy version. The same failure family in `critique-ledger-bigbang-20260716` proves this is a cross-pipeline category, not an isolated finding.

**Adherence versus missing structure.**

- The occurrence adhered to its recorded runtime binding. Runtime A failed closed as implemented; substituting B merely because it is a descendant would violate authority.
- The v5 `PROCEED` result remains durable and hash-pinned. It does not prove finalize completion.
- Missing structure includes the absent carry/verification envelope, absent A→B rebind event, absent finalize-specific repair authority, unpopulated state CAS metadata, no explicit finalize occurrence-idempotency key, an unclosed earlier revise request, and no authoritative category-level signature policy.
- No live lock, lease, claim, quota, or runner blocks recovery. That administrative clearance is not execution authority.

**Canonical owner.** The canonical defect owner is the Megaplan critique-custody contract spanning the gate producer and finalize consumer, centered on `arnold_pipelines/megaplan/orchestration/critique_custody.py`. Run Authority, Custody, WBC, runtime binding, the fixer, and notifications are enforcement participants, not alternate owners.

**Overrides and qualifications.**

- **FQ-01 override:** the raw report refutes the existence of a selector→producer→declared-output→artifact→finalize-consumer mapping and classifies it `MISSING_STRUCTURE`. The supplied summary’s gloss that there is “no declaration gap” is incorrect. Whether that absent structure is required by the current framework is **INDETERMINATE** because the current structural validator requires only step sections. Stage-1 nevertheless made selector/output integrity a mandatory stop gate, so it cannot be waived here.
- **FQ-05 override:** immutable gate evidence and zero observed committed finalize effects are supported. Affirmative same-occurrence CAS/idempotency proof is **INDETERMINATE**: `_state_meta` is empty, no occurrence-level finalize idempotency key is persisted, finalize publication CAS was never exercised, and attempt three lacks `phase_end`. The compound “supported” verdict does not authorize re-entry.
- **FQ-03 qualification:** the driver stop and absence of local persisted finalize effects are supported. Complete exclusion of unrecorded external or interrupted-attempt effects is not proven.
- **FQ-09 correction:** there were 12 best-effort `emit_transition` TypeErrors, not two. They are non-causal observability noise and not an independent integrity stop.
- FQ-02, FQ-04, FQ-06, FQ-07, FQ-08, and FQ-10 are otherwise accepted as scoped.

## 2. HORIZON A (agent_actionable: true)

**Disposition: quarantine.**

The occurrence cannot presently be authorized for finalize under either A or B. A will deterministically fail; B is not recorded as authorized; affirmative occurrence-level CAS is missing; the selector/output stop-gate conflict remains unresolved; and the sibling recurrence triggers the systemic-failure stop gate.

The smallest safe action available now is to route this blocker once through the canonical repair-request producer and obtain a machine-readable Run Authority quarantine/blocked decision. No custody claim, WBC reservation, rebind, finalize attempt, or notification may follow until every release gate below is satisfied.

**Authoritative preconditions and identity checks.**

Before any effect, the recovery owner must verify:

- Exact session, workspace, plan, chain, schedule, occurrence ID, and occurrence key.
- Chain spec SHA-256 `da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1`.
- Plan v5 SHA-256 `4537c985a9e8f1258af71d97d1d631b8ba6d0bcfc83b9a56fbd29cb327160f46`.
- Gate `PROCEED` SHA-256 `9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b`.
- Chain remains blocked at milestone index 0 with no completed milestone or later authoritative cursor.
- The old runner remains dead and its lease remains terminal; all relevant locks remain unheld and no occurrence claim has appeared.
- Request `74403266…` is not reused. It is revise-scoped, queued but unclaimed, and has no materialized repair authority.
- Runtime A remains the recorded current identity. Runtime B must be identified by commit, import root, content SHA-256, editable-install provenance, and policy hash—not commit ancestry alone.
- No notification intent, outbox entry, effect, or dedupe record exists for this blocker.
- The evidence fingerprint and all authoritative artifacts are unchanged.

**One canonical path.**

1. Use the canonical repair-queue producer, `enqueue_bound_repair_request`/equivalent supported producer seam, to mint one new blocker-specific request for phase `finalize`, exact occurrence, exact failure fingerprint, gate hash, plan hash, chain revision/incarnation, coordinator attempt, fence, lease, grant, and custody epoch. If the full normalized identity cannot be produced, accept the canonical `zero_authority_rejected` result and emit the blocked/quarantine decision through the supported authority path; do not create an ad hoc receipt.
2. Run Authority evaluates the request. Under the current record it must deny execution and record quarantine because the gates below are missing. It must not reuse the unmaterialized grant/lease identifiers embedded in request `74403266…`.
3. Only after a later authority decision satisfies every gate may Custody create exactly one occurrence claim with a new lease and epoch, bound to the authority grant, blocker fingerprint, expected state, fence, and content-addressed runtime.
4. WBC may then reserve exactly one attempt and one effect key. The ordinary fixer—not a direct phase command—may retrigger finalize exactly once for the canonical occurrence.
5. The real validator must accept the resulting task/result envelopes and all after-state proofs before WBC records success and Custody releases the claim.

Do not hand-edit `state.json`, chain state, gate/carry/fault records, runtime metadata, requests, leases, or SQLite stores. Do not use `--fresh`, force-proceed, restart, direct finalize invocation, or notification as a recovery mechanism.

**A→B boundary and missing release gates.**

The supported marker seam is `runtime_cutover.update_marker_runtime` with `marker_runtime_rebind.v1`, but current evidence does not establish an occurrence-safe transaction updating both the session marker and chain `runtime_binding`. Quarantine remains mandatory until all of these exist:

- Explicit operator/Run Authority authorization naming A’s full prior identity and B’s full target content identity.
- CAS against the previous marker and chain-binding digests.
- One canonical rebind/migration event persisted in both authoritative identity surfaces, or an authority-approved migrated-child receipt proving equivalent custody.
- A verified active editable-runtime identity; the recorded bind-time `.pth` is missing, and B’s live content identity is not durably recorded.
- A canonical rule for the next runner fence. Whether it must strictly exceed fence 1 is **INDETERMINATE**.
- Populated state-version/CAS metadata and a persisted occurrence-level finalize idempotency key.
- An effect-barrier receipt accounting for the interrupted third attempt and all external-effect domains.
- A canonical validator decision resolving the FQ-01 selector/output requirement.
- A category-risk decision addressing the sibling recurrence.
- A notification suppression/admission identity fixing the occurrence and conduit.
- A materialized finalize-specific grant, lease, custody epoch, and WBC reservation.

These are the exact missing gates for the blocked receipt.

**Bounded retry and rollback.**

- While quarantined: zero retries and zero effects.
- After a new release adjudication: exactly one new claim and one WBC finalize attempt.
- Any identity drift, CAS conflict, lease/fence loss, duplicate claim, validator rejection, repeated custody error, new error family, missing `phase_end`, or notification ambiguity immediately re-quarantines the occurrence. No automatic second attempt.
- If failure occurs before a committed effect, abandon the WBC attempt and release/expire custody through canonical seams.
- If a rebind or effect has committed, do not reverse it by hand. Preserve its append-only history, suppress further work, and require a new authority-reviewed rollback or migration decision.
- An admitted notification intent must be reconciled by its dedupe key; it must never be resent directly.

**Required after-proof.**

Release from Horizon A requires:

- Real finalize validator success under the recorded content-addressed runtime—not a source inspection, reproduction, PID, heartbeat, or prose assertion.
- Accepted task and result envelopes bound to the request, grant, claim, WBC attempt, occurrence, plan/gate hashes, fence, lease, and custody epoch.
- Matching runtime content identity across process provenance, marker, chain binding, validator receipt, and WBC outcome.
- Exactly one claim and one post-quarantine attempt.
- Successful immutable finalize publication or its verified idempotent no-op receipt.
- Plan cursor/state and chain milestone advancement beyond the blocked finalize boundary.
- Custody release and WBC terminal success records.
- Notification remains suppressed for this recovery: zero notification intents and zero effects, with authoritative suppression custody.

## 3. HORIZON B (epic_update_required: true, agent_actionable: false)

**Complete category fix.** Update the existing epic `.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/`; do not create an occurrence-only patch epic.

The first broken contract is the unversioned gate-to-finalize resolution envelope. The missed backstop is that neither gate validation nor runtime admission checked whether the accepted artifact set was consumable by the exact bound finalize policy. The canonical owner remains critique custody.

**Machine-readable contract and identity history.**

Adopt one authoritative `arnold.megaplan.recovery_admission.v1` envelope containing:

- Session, chain, plan, milestone, occurrence, request, and blocker-family identities.
- Source/current plan versions and SHA-256 values.
- Finding/flag identity, status, severity, addressed version, fixed claim, location, and descendant-mutation proof.
- Gate expectation, action, rationale, evidence, gate artifact hash, and complete carry history.
- Validator name/version/result/receipt hash.
- Runtime policy version and content-addressed runtime-binding history: prior/target commit, import root, source/editable revisions, content SHA-256, installation provenance, authority grant, request, claim, epoch, fence, reason, previous-record digest, and rebind/migration event digest.
- WBC idempotency key, attempt/effect outcome, custody release, and notification intent/effect key.

The envelope must be append-only and content-addressed. Component stores may retain their existing schemas, but admission must fail unless all referenced records hash back to this envelope.

**Required pipeline changes.**

- **Run Authority:** grant only against the complete envelope; materialize every grant before a request can claim it; make self-recovered requests terminally stale/superseded; scope grants to exact blocker family, occurrence, runtime transition, epoch, and fence.
- **Custody:** persist resolution carry on every gate iteration; prohibit contradictory `accepted_tradeoff`/fixed/verified combinations; require explicit release/expiry events; enforce one occurrence claim.
- **WBC:** reserve one occurrence-level attempt/effect key; persist started, completed, abandoned, and quarantined outcomes; link validator and notification receipts.
- **Gate and validators:** validate producer→consumer compatibility against the bound finalize policy before `PROCEED`; validate selector/output structure if adopted; reject missing carry or unsupported runtime policy at gate time rather than finalize.
- **Finalize:** consume only the versioned envelope; keep immutable/CAS publication; require populated state versions and occurrence-level idempotency.
- **Fixer/backstop:** mint blocker-specific requests only through the canonical producer; never directly resume a blocked phase; cluster exact fingerprints and broader failure families; enforce one-attempt containment.
- **Runtime binding:** make rebind/migration an atomic CAS transaction across marker, chain state, Run Authority, Custody, and WBC; reconcile editable-install provenance before admission.
- **Observer:** distinguish absence from proof, exact finding fingerprints from error-family recurrence, and authoritative effects from best-effort telemetry. Correct the TypeError count and surface missing `phase_end`.
- **Notifications:** persist intent only after an authority-defined terminal outcome; bind intent and effect to the recovery envelope; use one deterministic dedupe key; default to suppression during quarantine.

**Concrete implementation surface.**

Update or validate:

- `orchestration/critique_custody.py`
- `handlers/finalize.py`
- `orchestration/finalize_authority.py`
- `chain/execution_binding.py`
- `cloud/runtime_cutover.py`
- `cloud/runtime_provenance.py`
- `runtime/execution_environment.py`
- `cloud/repair_requests.py`
- `cloud/repair_lock.py`
- `observability/work_ledger.py`
- `auto.py`
- `cloud/incident_notification.py`
- `notification_safety.py`
- `custody/outbox.py`
- `resident/delivery_effects.py`
- `resident/delivery_status.py`
- The plan-structure validator if selector/output declarations become mandatory.

Required tests include:

- Carried `accepted_tradeoff` plus traceable descendant mutation.
- Missing/contradictory carry rejected before `PROCEED`.
- Runtime-policy incompatibility and atomic A→B rebind CAS.
- Stale marker, absent editable provenance, stale fence, duplicate claim, and lease-loss cases.
- Crash injection at request, grant, claim, WBC start, finalize publish, custody release, notification intent, and delivery effect boundaries.
- Automatic terminalization of a repair request after self-recovery.
- R7 and bigbang failure-family replay fixtures.
- Reserved-key sanitization for `emit_transition_activity`.
- Exactly-once notification admission and dedupe.
- Selector/output positive and negative validation once the policy decision is made.

**Migration and observability.**

- Append migration receipts; never rewrite historical plan, gate, fault, chain, or request artifacts.
- Backfill normalized envelopes from hash-pinned records where provenance is complete. Quarantine incomplete records rather than synthesizing authority.
- Terminalize orphaned queued requests such as the revise request through a reviewed migration rule.
- Do not auto-rebind chains with missing runtime history.
- Add metrics for unresolved-finding family, missing carry, runtime drift, unmaterialized authority, request age, duplicate claims, missing phase completion, CAS conflicts, quarantines, and intent/effect divergence.

**Rollout and rollback.**

1. Replay historical fixtures in shadow mode.
2. Dual-write the new envelope while old readers remain authoritative.
3. Compare gate/finalize decisions and quarantine disagreements.
4. Canary the new admission path on bounded non-critical chains.
5. Enforce the contract for new occurrences, then migrate eligible blocked occurrences.
6. Roll back by disabling new admission while preserving append-only envelopes and committed binding history. Never roll back by deleting rebind, WBC, custody, or notification records.

**Very-hard decisions — INDETERMINATE.**

- Whether fixed `accepted_tradeoff` is semantically equivalent to verified mutation without a repeated gate envelope.
- Exact-finding versus error-family category identity.
- Whether A→B should preserve the occurrence or require a migrated child.
- Whether selector/output mappings become mandatory.
- Whether all legacy blocked states can receive CAS versions safely.
- Which notification conduit and occurrence identity own a terminal recovery message.

**Parallelizable work.**

- Contract/schema and historical migration.
- Critique/gate/finalize validator work.
- Run Authority/Custody/WBC/runtime-binding transaction work.
- Fixer/backstop/observer and telemetry work.
- Notification intent/effect custody and chaos testing.

These lanes may proceed in parallel after the envelope schema freezes; enforcement and migration remain integration-gated.

**Epic crosswalk.**

Add explicit workstreams to `critique-ledger-accountability-v3-r7-20260805` for:

- CL2 resolution-envelope and gate-carry ownership.
- Run Authority/Custody/WBC recovery admission.
- Runtime binding and migration history.
- Finalize validator and occurrence idempotency.
- Repair queue/fixer/backstop lifecycle closure.
- Observer and work-ledger correctness.
- Notification intent/effect custody.
- Historical migration and R7/bigbang category replay.

**Category-closure proof.**

A retroactive replay must ingest the immutable R7 and bigbang evidence, produce exactly one repair occurrence, exactly one custody claim, exactly one WBC attempt, and at most one notification effect per logical recovery. Inject retries and crashes at every boundary and prove dedupe. Both replays must pass the real validator, preserve runtime/authority lineage, advance their cursor or milestone, and leave no orphan request, lease, claim, reservation, intent, or effect.

## 4. PROOF GATES

**Authoritative before-state.**

- Chain: `blocked`, milestone index 0, `completed=[]`, runtime A bound, `rebind_events=[]`.
- Plan: iteration 5, `blocked`, resume target `finalize`.
- Accepted plan v5: SHA-256 `4537c985…`.
- Gate: `PROCEED`, SHA-256 `9df95825…`.
- Runtime A: commit `d5848010…`, content SHA-256 `e8b12504…`.
- Runtime B: commit `77b76e3a4…`, not authorized and lacking a persisted content identity for this occurrence.
- No finalize request, grant, lease, claim, WBC attempt, finalize artifact, notification intent, or notification effect.
- Old runner stopped; fence 1; no live ownership.
- All ten Flash-report hashes match `swarm-index.json`.

**Required authoritative after-state.**

- One blocker-specific repair request and terminal Run Authority decision.
- If execution is authorized: one materialized grant, one custody claim/epoch/lease, one WBC attempt/effect key, and one content-addressed runtime binding or migration event.
- Real validator success attached to accepted task/result envelopes.
- Exact match among request, occurrence, blocker, plan/gate hashes, runtime identity, grant, fence, lease, epoch, attempt, and result.
- Immutable finalize publication with CAS receipt or a validated idempotent no-op.
- Custody release and WBC terminal success.
- Plan cursor and chain milestone advance beyond the blocked finalize boundary.
- Notification custody proving zero effects for Horizon A; category replay may permit one intent and at most one deduplicated effect.

This run may claim the failure category closed only after the Horizon B contract is enforced, both R7 and bigbang family fixtures pass retroactive and crash-injected replay, all supported runtime lineages pass the real validator, every replay yields exactly one repair occurrence/claim/attempt, notification effects are bounded to at most one, and no unresolved authority, custody, CAS, runtime, request, selector/output, or effect discrepancy remains. That condition is not presently met.

## 5. FINAL FINGERPRINT LINE

sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9