## A. RE-ADJUDICATED ROOT CAUSE

The prior adjudication is confirmed but refined.

The first broken contract is the gate-to-finalize resolution envelope. The registry permitted two significant findings—`CF-0B506E1EDCD92E90C192` and `CF-B67C1E37D72114DDCF70`—to remain `accepted_tradeoff` with a traceable fixed-plan claim but without `gate_resolution`. Later gate iterations excluded `accepted_tradeoff` from unresolved inputs, so gate v5 issued `PROCEED` without proving that runtime A’s bound finalize policy could consume every retained finding.

The immediate failure is runtime A’s fail-closed `_resolution_for_finding`: both records fall through to `critique_finding_unresolved`. The ten other accepted-tradeoff records succeed because they have `gate_resolution.action=accept_tradeoff` and rationale.

The missed backstops were:

1. No pre-`PROCEED` compatibility check ran all retained findings through the exact bound finalize policy.
2. The deterministic finalize failure was recorded after its authoritative active-step identity disappeared, leaving no blocker-specific coordinator attempt, repair request, Custody claim, or WBC attempt.

Canonical ownership is split correctly:

- Gate/registry/finalize contract: Megaplan critique lifecycle maintainers, specifically `flags.py`, `handlers/gate.py`, and `orchestration/critique_custody.py`.
- Missing recovery identity: Megaplan auto/lifecycle coordinator and `PlanRepository.record_lifecycle_failure`.
- This occurrence’s admission: the Run Authority/operator owning execution binding and recovery authority.

The prior editable-runtime-identity gate is satisfied: runtime A provenance is `ok:true`, and execution/runtime bindings match. The prior A→B gate is obsolete because runtime B is expressly excluded. An external gate still remains, but for a different reason: repairing runtime A changes its exact bound content identity, and the existing evidence cannot mint the missing historical repair attempt. Run Authority must authorize both an A-lineage content-addressed cutover and a fresh prospective recovery identity.

Flash conclusions overridden or qualified:

- FQ-02’s technical A→B delta is accepted as diagnosis and regression evidence, but B is overridden as an immediate deployment route.
- FQ-07’s principle that ancestry is not authority remains valid; its B-authorization route is superseded by the operator’s exclusion.
- FQ-04 is overridden insofar as it called the fresh enqueue seam actionable: the API exists, but current state cannot supply its complete F01 identity.
- FQ-05’s A→B remedy is replaced by the equivalent focused fix deployed in runtime A’s lineage. Its finding of no observed local finalize effect remains evidence, not complete external-effect proof.
- FQ-01 is removed as an immediate stop gate: selector/output mapping is absent but is not a current framework requirement.
- FQ-03, FQ-06, FQ-08, FQ-09, and FQ-10 otherwise stand: same-occurrence recovery is not precluded; notification remains suppressed; the failure family is systemic; the ledger TypeError is non-causal; no live lock/lease/claim blocks admission.

## B. HORIZON A — immediate_route

Decision: precise external gate; `agent_actionable: false` until it clears.

Registry repair is not a supported route:

- `megaplan gate` requires `critiqued` state; this plan is `blocked` with a finalize cursor.
- Gate signals include only `open`, `disputed`, and `addressed` flags. Both target records are already `accepted_tradeoff`, so rerunning the producer would not re-admit them.
- The persisted PROCEED `gate.json` contains no resolution for either record; `state.last_gate` also does not resolve either.
- `update_flags_after_gate` is an internal reducer helper, not an operator repair API.
- `force-proceed` cannot recover this deterministic-finalize blocked state and would represent a new semantic waiver.
- Direct changes to `faults.json`, `gate.json`, or `gate_carry.json` would rewrite accepted evidence and are prohibited.

Therefore, the only viable runtime-A repair is the focused source change in `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/critique_custody.py`: admit `accepted_tradeoff && gate_expected && fixed_claim` as `verified_plan_mutation`, preserving failure for records without a complete fixed claim. Runtime B is evidence for the predicate and test, not a permitted deployment source.

That source change is not authorized by the existing launch boundary. The chain binds exact revision `d5848010695e28ddb9d9cbee8675d7ebe725caae` and content identity `e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6`; modifying runtime A creates a new identity. The current operator instruction excludes B but does not itself authorize an A-source modification.

Required external receipt: the Run Authority/operator must issue a signed, content-addressed approval naming:

- logical occurrence `sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5`;
- prior runtime-A revision, content identity, and import root;
- approved clean A-lineage candidate commit and computed content identity;
- explicit exclusion of runtime B;
- exact source scope and focused-test/provenance receipt digests;
- an accepted effect barrier covering all three prior finalize invocations;
- the new runner fence and complete `megaplan-repair-identity-v1` tuple;
- authority for exactly one request, decision, Custody claim/epoch, repair effect, phase-WBC attempt, and finalize invocation.

After approval, the ordered route is:

1. Land only the focused runtime-A change and regression. Tests must cover both real record shapes, retain failure without `fixed_claim`, and run the listed custody, recovery, binding, repair, WBC, and one-shot-finalize suites.
2. Produce the candidate identity through `arnold_pipelines.megaplan.cloud.runtime_provenance.runtime_provenance` and `runtime_provenance_receipt`.
3. Use the supported `python -P -m arnold_pipelines.megaplan chain runtime-rebind` seam for chain state and `arnold_pipelines.megaplan.cloud.runtime_cutover.update_marker_runtime` for the session marker. Operands must come from fresh CAS/provenance reads. The import root must remain runtime A’s path.
4. Run Authority creates a fresh prospective identity with `build_normalized_repair_identity`, then calls `enqueue_occurrence_bound_repair_request` exactly once.
5. Persist exactly one accepted decision through `write_decision`; claim it through `claim_active_repair_request`.
6. Acquire exactly one lease/epoch through `CustodyLeaseStore.acquire`, bound to the new grant, fence, WBC reference, and logical occurrence.
7. Reserve one effect through `delegate_to_simple_fixer` and `CanonicalRunner`. `adopted`, `in_flight`, `indeterminate`, `exhausted`, or `unchanged` stops the route.
8. Within that one ordinary-fixer effect, invoke `python -P -m arnold_pipelines.megaplan override recover-blocked` with `--repair-scope engine_runtime`, the approved A-lineage commit, and exact failure fingerprint `4a772446d29148efccc408bc04eaf07ce5fca741a7e2b1288df78218e4a8bc32`.
9. Invoke `python -P -m arnold_pipelines.megaplan finalize --plan cl2-wbc-backed-ledger-20260805-2140` exactly once. The normal handler owns phase-WBC activation and terminalization.
10. After finalize proof, resume the existing chain only through `python -P -m arnold_pipelines.megaplan chain start` under the matching binding.

Expected effects are a new content-addressed A identity, matching marker/chain rebind events, one recovery lifecycle, and `critique_clearance.json` resolving both target records as `verified_plan_mutation`. The accepted plan, gate, faults, and carry artifacts must remain unchanged.

After-proof requires:

- runtime provenance `ok:true`, marker and chain binding `match`, and no B identity;
- one request, accepted decision, request claim, Custody epoch, repair-effect reservation, and phase-WBC attempt;
- successful finalize `phase_end`, complete critique coverage, state no longer blocked, and chain cursor advancement;
- no duplicate or orphan authority records;
- zero Horizon-A notification intents or effects.

Any identity drift, missing effect barrier, incomplete repair identity, CAS conflict, duplicate lifecycle record, custody repetition, absent terminal WBC/result, validator rejection, new failure family, or notification admission stops immediately. The next scheduled retry is the first active retry after the complete approval/identity/effect-barrier return condition validates; its UTC time is INDETERMINATE.

## C. HORIZON B — long_term

`agent_actionable: false`; update the existing epic rather than creating another authority epic.

The smallest complete cross-pipeline fix is a versioned, append-only `arnold.megaplan.recovery_admission.v1` contract binding:

- logical occurrence and state version;
- every finding occurrence, disposition, plan mutation, gate resolution/carry, and reopen predicate;
- exact gate and finalize policy digests;
- runtime identity and rebind/migration lineage;
- canonical phase dispatch attempt and failure CAS;
- Run Authority decision/grant, Custody lease/epoch/fence, and WBC attempt/effect;
- validator result;
- notification intent/effect and deterministic dedupe identity;
- previous-record digest and content digest.

Required implementation:

- `flags.py`, `handlers/gate.py`, `orchestration/gate_signals.py`, and `critique_custody.py`: preserve complete resolution lineage and validate it against the bound finalize policy before `PROCEED`.
- `handlers/finalize.py` and `orchestration/finalize_authority.py`: consume only the versioned envelope and publish with immutable/CAS authority.
- `auto.py` and `store/plan_repository.py`: persist the canonical attempt before dispatch and retain its repair-identity seed through every failure/cleanup boundary.
- `cloud/repair_requests.py`, `cloud/wrappers/repair_delegation.py`, Custody lease storage, and phase-WBC lifecycle: enforce one request, decision, claim, epoch, and attempt per logical recovery.
- `chain/execution_binding.py`, `cloud/runtime_cutover.py`, and `cloud/runtime_provenance.py`: make runtime transition proof coherent across marker, chain, Run Authority, Custody, and WBC.
- Notification storage/outbox: admit intent only after an authority-defined terminal decision and enforce at most one effect.
- `observability/work_ledger.py`: fix the duplicate `transition` argument and emit metrics for missing carry, policy mismatch, attempt loss, runtime drift, duplicate authority, missing terminal phase, quarantine, and notification divergence.

Migrations must append provenance without rewriting historical artifacts. Complete evidence may be backfilled as non-authoritative provenance; incomplete evidence remains quarantined.

Rollout is schema freeze → immutable R7/bigbang replay → crash/fault suite → exact-runtime validation → one coordinated CL5 cutover. Rollback restores the whole prior content-addressed runtime/configuration, rebuilds projections from append-only evidence, and never leaves mixed gate/finalize policies.

Very-hard decisions remain INDETERMINATE:

- whether `fixed_claim` is semantically equivalent to independent verification for accepted tradeoffs;
- exact-finding versus failure-family identity;
- same-occurrence rebind versus migrated child;
- mandatory selector/output declarations;
- eligibility of legacy attempt/CAS backfill;
- terminal notification conduit ownership.

After schema freeze, gate/finalize validation, attempt/authority persistence, runtime cutover, observer/fixer, migration/replay, and notification work can proceed in parallel.

Epic crosswalk:

- Update `README.md` and `NORTHSTAR.md`, including their stale r6 naming and the recovery-admission contract.
- Create the currently absent `.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/UNFINISHED_WORK.md`.
- CL2: durable occurrence/attempt/WBC replay and migration fixtures.
- CL3: exact briefing/evidence-set and observer identity.
- CL4: complete disposition/carry and bound gate/finalize compatibility.
- CL5: atomic runtime cutover, recovery admission, notification custody, replay, and retirement.
- Retain and cross-link ticket `01KZBC4GX4C8SN38Z53RSWZJEG`.

Category closure must replay R7 and bigbang with crash injection and prove, per logical recovery: one occurrence, one accepted decision, one Custody claim/epoch, one WBC attempt/effect, at most one notification effect, cursor advancement, unchanged historical evidence, and no orphan authority or notification record.

## D. MACHINE-READABLE ENVELOPE

```json
{"evidence":{"pack":"/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-113119-171252f9/evidence-pack-delta.md","sol_stage1":"/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/sol-stage1.md","sol_stage2":"/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-104038-ca591908/sol-stage2.md","swarm_index":"/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/swarm-index.json"},"handoff_id":"sha256:d5e9aa809be2f7018ece44d891ed0575e82ad1cfdb1df6acd2574a45b7d5bc2c","horizon_a":{"agent_actionable":false,"canonical_owner":"Run Authority/operator owning chain execution binding and recovery admission; engine-runtime maintainer owns the approved A-lineage patch; Megaplan lifecycle coordinator owns the single repair execution","deployment_or_rebind_proof":["Approved clean runtime-A descendant commit at import_root /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 with computed content_sha256 and provenance ok:true","Focused-test receipt bound to that exact commit and content identity, including failure without fixed_claim and success for both real record shapes","arnold.megaplan.chain_runtime_rebind.v1 event and arnold.megaplan.marker_runtime_rebind.v1 event with matching from/to digests and CAS parents/results","Post-cutover execution_binding and runtime_binding both report match; runtime B is absent from every identity surface","One request, accepted decision, claim, Custody epoch, repair-effect reservation, phase-WBC attempt, finalize terminal receipt, and validator after-proof"],"external_gate":"Run Authority/operator must approve an A-lineage source repair and prospective recovery admission. Required receipt: an operator-signed, content-addressed approval naming logical occurrence sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5, prior runtime A revision/content, candidate A-lineage commit/content/import_root, explicit exclusion of runtime B, focused-test and provenance receipt digests, accepted effect barrier, new runner fence, full megaplan-repair-identity-v1 tuple, and permission for exactly one request/claim/Custody epoch/repair effect/finalize invocation; execution must then produce matching arnold.megaplan.chain_runtime_rebind.v1, arnold.megaplan.marker_runtime_rebind.v1, and repair_request_decision records.","focused_tests":["tests/orchestration/test_critique_custody.py","tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py","tests/arnold_pipelines/megaplan/test_chain_execution_binding.py","tests/cloud/test_runtime_cutover.py","tests/cloud/test_repair_delegation.py","tests/cloud/test_repair_requests.py","tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py","tests/arnold_pipelines/megaplan/test_finalize_one_shot_cli.py"],"operations":["Apply only the approved _resolution_for_finding accepted_tradeoff-and-gate_expected-and-fixed_claim branch in runtime A and add the focused regression; do not copy or bind runtime B","Generate runtime identity and provenance with arnold_pipelines.megaplan.cloud.runtime_provenance.runtime_provenance and runtime_provenance_receipt for the approved runtime-A commit","Cut over the chain with the supported megaplan chain runtime-rebind command and the session marker with arnold_pipelines.megaplan.cloud.runtime_cutover.update_marker_runtime, using machine-derived CAS operands and preserving runtime A's import_root","Build the fresh authority-owned identity with build_normalized_repair_identity and enqueue exactly one request with enqueue_occurrence_bound_repair_request","Persist one accepted Run Authority decision with write_decision; reject or quarantine any duplicate or non-claimable request","Acquire exactly one request claim with claim_active_repair_request and one Custody lease/epoch with CustodyLeaseStore.acquire, all bound to the logical occurrence and new fence","Reserve exactly one repair effect through delegate_to_simple_fixer and CanonicalRunner; indeterminate or in-flight reservations stop without redrive","Inside that one ordinary-fixer effect, run the supported megaplan override recover-blocked seam with the exact compact_failure_identity fingerprint, approved A-lineage repair commit, and repair_scope engine_runtime, then invoke the supported megaplan finalize phase exactly once","Verify critique clearance, phase-WBC start/terminal/result, finalize phase_end, state transition out of blocked, runtime identity agreement, and zero notification effects","After finalize proof, resume the existing chain only through megaplan chain start under the same authorized binding; require milestone/cursor advancement before closing the repair"],"preconditions":["Authoritative fingerprint equals sha256:a8c4416eb4e87db1d2bf52c2ee18c4f39c050206803f73bcac27867729c0e68b and only the known follow-up ticket differs from sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9","Logical occurrence remains sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5; chain remains blocked at milestone 0 and plan iteration 5","Plan v5 remains sha256:4537c985a9e8f1258af71d97d1d631b8ba6d0bcfc83b9a56fbd29cb327160f46 and gate remains PROCEED at sha256:9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b","Runtime A remains the only permitted lineage and import root; runtime B commit 77b76e3a487809a2d1c89ea6785aac473c8931c8 is excluded","No live runner, recovery owner, finalize request, Custody claim, phase-WBC attempt, or notification effect exists","Run Authority accepts an effect-barrier receipt for all three failed finalize invocations","The approved A-lineage candidate has a clean commit, focused-test receipt, runtime-provenance receipt, and computed content identity","Run Authority supplies a fresh prospective megaplan-repair-identity-v1 tuple; no field is reconstructed from labels, PID, liveness, projections, or the missing historical attempt"],"return_condition":"Return on the first active scheduled retry after the signed approval validates, the A-lineage candidate is provenance-valid, marker and chain bindings match its content identity, the fresh repair identity is complete, the effect barrier is accepted, and no stop gate is present. Success requires exactly one request, one accepted decision, one claim/epoch, one repair-effect reservation, one phase-WBC attempt, one successful finalize, chain cursor advancement, and zero notification effects; exact UTC is INDETERMINATE.","route":"external_run_authority_gate_then_runtime_a_lineage_source_fix_content_addressed_rebind_and_one_canonical_repair"},"horizon_b":{"category_closure_proof":["Replay immutable R7 and critique-ledger-bigbang fixtures through one versioned recovery-admission contract","For each logical recovery, prove one occurrence, one accepted Run Authority decision, one Custody claim/epoch, one WBC attempt/effect, and at most one notification effect","Reject missing carry, unsupported disposition, runtime-policy mismatch, incomplete attempt identity, stale lease/fence, duplicate effect, and ambiguous prior effect before mutation","Pass crash injection at request, decision, claim, WBC start, finalize publication, custody release, notification intent, and delivery effect boundaries","Advance the canonical plan/chain cursor with unchanged historical gate/fault/event evidence and no orphan request, grant, lease, claim, reservation, intent, or effect"],"epic_slug":"critique-ledger-accountability-v3-r7-20260805","epic_update_required":true,"first_broken_contract":"Gate-to-finalize critique-resolution compatibility was not versioned or validated against the exact bound finalize policy before PROCEED","ticket_or_crosswalk":"Update .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/README.md and NORTHSTAR.md; create .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/UNFINISHED_WORK.md; cross-link briefs/cl2-ledger-persistence-and-replay.md, briefs/cl3-evaluator-routing-and-briefings.md, briefs/cl4-reconciliation-reviser-gate.md, and briefs/cl5-big-bang-cutover-and-retirement.md; retain follow-up ticket 01KZBC4GX4C8SN38Z53RSWZJEG"},"notification_key":"sha256:86e40e1e0058ad7934f251c001a766e432730da1ca7b4cd57477982206b10899","schema":"arnold.superfixer.recovery_handoff.v1","stop_gates":["Authoritative fingerprint differs from sha256:a8c4416eb4e87db1d2bf52c2ee18c4f39c050206803f73bcac27867729c0e68b outside the known ticket-only delta","Logical occurrence, plan, gate, milestone cursor, or accepted-work hashes change","Any route selects or imports runtime B","Run Authority approval is absent, unsigned, incomplete, or authorizes direct registry editing","Candidate A-lineage source, tests, provenance, marker, or chain binding disagree","Fresh megaplan-repair-identity-v1 is incomplete or derived from non-authoritative historical evidence","Effect barrier for any prior finalize invocation is absent or indeterminate","A live runner, request, claim, Custody lease, WBC attempt, or repair effect appears before admission","Duplicate request, decision, claim, epoch, attempt, effect, or notification identity appears","Registry/gate producer would rewrite the accepted PROCEED decision or synthesize the two missing gate resolutions","override recover-blocked rejects the exact repair commit/failure fingerprint/engine_runtime scope","Repair effect or phase-WBC state is adopted, in-flight, indeterminate, exhausted, or unchanged","Critique custody repeats, phase_end is absent, validator rejects, or a new failure family appears","Runtime bindings disagree after either rebind write","Any notification intent or effect is admitted during Horizon A"],"target":{"occurrence":"sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5","plan":"cl2-wbc-backed-ledger-20260805-2140","session":"critique-ledger-accountability-v3-r7-launch-20260805"}}
```

## E. SAFETY STATEMENT

This pass performed read-only inspection and computation only. It did not modify or create a file, invoke a producer or lifecycle mutation, launch/resume/restart a runner, rebind a runtime, mint a request/claim/attempt, notify, or alter the epic.

Exact supplied fingerprints and identities:

- Current authoritative before: `sha256:a8c4416eb4e87db1d2bf52c2ee18c4f39c050206803f73bcac27867729c0e68b`
- Prior authoritative fingerprint: `sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9`
- Runtime A content identity: `e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6`
- Chain specification: `da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1`
- Plan v5: `4537c985a9e8f1258af71d97d1d631b8ba6d0bcfc83b9a56fbd29cb327160f46`
- Gate v5: `9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b`
- Logical occurrence: `sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5`
- Prior handoff: `sha256:96fdcee6e5b9e88df587c43283afcebcf9f9afa346c9c86ce52d73ed80070dd4`