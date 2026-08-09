# Evidence Pack — R7 Superfixer occurrence v4 (backstop retry)

occurrence_id: occ_critique_r7_superfixer_retry_20260806_v4_14834310cdddb1f2b0eed77e
occurrence_key: sha256:14834310cdddb1f2b0eed77efb40585bd2d7ce1e73cd64497bad74246bd5c856
schedule_id: sched_critique_r7_superfixer_retry_20260806_v4 (revision 1, generation 1)
observer model/transport: hermes:deepseek:deepseek-v4-flash / resident managed subagent (run subagent-20260806-130215-69f23ad9)
observed_at (UTC): 2026-08-06T13:02Z .. 13:20Z
fingerprint-before sha256: 74c28bb57d9ee5a0159980fc3ba4e18331fbd1013a58838da0e96b15c54a16f9
prior incident evidence: .megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/
  (occurrence v1 full protocol: evidence-pack.md, sol-stage1.md, swarm/ fq-01..fq-10, sol-stage2.md,
   repair-producer-attempt.json -> zero_authority_rejected; no receipts written)

## 1. Identity

- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- chain spec: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml
  (sha256 da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1)
- plan: cl2-wbc-backed-ledger-20260805-2140 (milestone index 0 `cl2-ledger-replay`)
- chain state: .megaplan/plans/.chains/chain-880bd6e04632.json
  (current_milestone_index 0, last_state "blocked", completed [], target_base_ref d5848010695e,
   runtime_binding bound_at 2026-08-05T21:40:53Z current_identity d5848010695e/content e8b12504, rebind_events [])
- plan state: state.json iteration 5, current_state "blocked",
  resume_cursor {"phase": "finalize", "retry_strategy": "repair_phase_contract"}
- latest_failure (recorded 2026-08-06T00:53:46Z):
  deterministic_phase_failure phase=finalize error=critique_finding_unresolved
  "finding CF-0B506E1EDCD92E90C192 / flag CF-0B506E1EDCD92E90C192 remains 'accepted_tradeoff';
   it needs a traceable plan mutation plus verification, or an evidence-backed invalidation"
  repeated 3x (max_attempts 3), iteration 25
- launch checkout (project): refs/heads/fix/r7-fresh-child-launch-20260805 @ d5848010695e (tracked clean; untracked .megaplan artifacts only)
- pinned runtime root: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805
- fresh child admission: fresh_child_admission.json
  (occurrence_digest sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5,
   wbc_attempt_id ...:attempt:1, glek glek:cf80b573..., authority_grant_id grant:fresh-child:8ef0d95e...,
   custody_lease_id lease:arnold.megaplan.fresh_child_admission.v1:8ef0d95e...)

## 2. Runtime identity — timeline (facts)

- 13:03Z: pinned runtime provenance (wrapper env, --expected-revision 8667ffff6f354b3ab7e23072656d77cb74a14c45):
  ok:true, runtime_revision=8667ffff6..., content_sha256=4e9745357769b7db20e8326e4cf7acc46fbf4a749990c80c806405e21413bfff
  (matches the contract pin exactly). Editable install root == pinned root (pth entry present, readable).
- 13:04Z: run_mp chain status: execution binding match (expected==active c628b6b07d92);
  runtime binding DRIFT expected=e8b12504130b (launch-time d5848010) active=4e9745357769 (8667ffff).
- 13:06Z and 13:10Z: git reflog of the pinned runtime advanced by EXTERNAL actor "Arnold Recovery Bot"
  <arnold-recovery@localhost>:
    aa4d277db fix(agent): preserve heredoc command boundaries in terminal fence (13:06:27Z)
    7fb101d74 test(agent): lock terminal heredoc fence behavior (13:10:14Z)
  Both are descendants of 8667ffff (merge-base --is-ancestor 8667ffff HEAD == yes). Same branch
  fix/r7-fresh-child-launch-20260805. Launch checkout untouched. These commits touch
  arnold/agent/tools/environments/local.py + tests (agent terminal fence), NOT megaplan orchestration.
- 13:14Z: pinned runtime provenance vs contract pin now FAILS: ok:false errors=['source_revision_mismatch'],
  runtime_revision=7fb101d747c294a060879f52126bbe9c03a829ab (content_sha256 82969df632fdb08970537b33007258379fefd980f3b86aeb6a97439f328a5822).
- Interpretation: the pinned runtime lineage advanced during observation by the operator-side recovery bot;
  same-lineage descendant of the contract pin. Not an unaccepted boundary; recorded for Sol.

## 3. Canonical state (facts)

- Chain: blocked at milestone 0, plan cl2-wbc-backed-ledger-20260805-2140, completed=[].
- Events seq stopped at 3098 (00:53:46Z). Heartbeats stopped 00:53Z. state.json mtime 00:53Z.
- Gate v5 (00:53:17Z) recommendation PROCEED, passed=true, gate.json hash 9df9582599..., gate_carry.json written 00:53.
- Finalize attempts 00:53:27-00:53:46Z: three identical internal_error failures -> chain blocked.
- Process custody: marker pid 629623 DEAD; liveness lease status="stopped" expires 2026-08-06T00:53:46.682173Z;
  no chain/watchdog/repair process alive at observation (only resident listener pid 1/7 + this backstop worker).
- Repair queue: NO finalize-blocker request. Single existing request 74403266... is the earlier revise-phase
  request (created 00:13:08Z, decision accepted/queued, self-recovered at 00:21:31Z; unused).
- No r7 repair-data/blocked-receipt/no-action-receipt files exist. No notification intent/effect records.
- Prior occurrence v1 executed the repair producer: outcome zero_authority_rejected
  ("no canonical finalize attempt record exists (attempt field empty)" per repair_delegation.py F01 tuple).
  No request, claim, WBC attempt, or receipt was minted by v1/v2/v3.

## 4. Root-cause reproduction (proven facts, this occurrence)

- Deterministic blocker: finalize critique-custody resolution.
- Registry faults.json: CF-0B506E1EDCD92E90C192 and duplicate CF-B67C1E37D72114DDCF70 both
  status="accepted_tradeoff", severity="significant", resolution.kind="fixed" (addressed_in plan_v2.md),
  verify_rationale present, verified=false, NO gate_resolution key.
- Evaluator verdict v2 (22:39Z) adjudicated both as outcome=accepted_tradeoff with rationale;
  flags.py apply_flag_verifications writes status="accepted_tradeoff" + verify_rationale but NO gate_resolution.
- Gate v2 recommended ITERATE (resolutions not persisted); gate v3/v4/v5 no longer mention the flags
  (dropped from later critiques); gate v5 accepted_tradeoffs do NOT include them; gate_carry.json has no entry.
- Finalize consumer critique_custody._resolution_for_finding requires for accepted_tradeoff:
  gate_resolution.action=="accept_tradeoff" with non-empty rationale (or verified+fixed_claim, or gate_disputed+evidence).
  None present -> CritiqueCustodyError("critique_finding_unresolved").
- READ-ONLY reproduction (this occurrence, wrapper env, current runtime 7fb101d74, real plan data,
  full sweep of all 95 findings across custody receipts v1-v5): EXACTLY 2 failures
  CF-0B506E1EDCD92E90C192 and CF-B67C1E37D72114DDCF70, error text byte-identical to the chain log.
- Same sweep under fix candidates 77b76e3a4 (arnold-r7-fresh-child-20260805-77b76e3a4) and
  079927677 (arnold-r7-fresh-child-20260805-a-fix): 0 failures, both flags resolve to verified_plan_mutation.
- Both candidates add the identical 16-line branch to critique_custody.py:
  `if status == "accepted_tradeoff" and gate_expected and fixed_claim: -> verified_plan_mutation`.
  Current runtime lacks this branch. First broken contract: producer (evaluator/gate carry) writes
  accepted_tradeoff without the exact gate_resolution envelope the finalize consumer requires, and the
  finalize consumer has no relaxation for traceable fixed-plan mutations on accepted tradeoffs.

## 5. Contracts / validators (facts)

- chain.yaml: driver.require_editable_runtime_match=true; phase_timeout 10800; max_iterations 60;
  on_failure abort stop_chain; finalize phase model codex:gpt-5.6-sol:high.
- plan config: robustness thorough, completion_contract_mode shadow.
- The supported runtime-rebind seam exists: `run_mp chain runtime-rebind` (chain subcommand).
- The supported repair-request producer exists (repair_delegation.py / repair-queue); it returned
  zero_authority_rejected for v1 because no canonical finalize attempt tuple existed.

## 6. Sibling / negative search (facts)

- No other session shares this failure fingerprint (prior pack searched; confirmed again this occurrence).
- Prior occurrences v1/v2/v3 of this schedule ended without receipts or effects; none is in flight
  (no live owner process, no managed-child custody lease with fresh heartbeat).
- Unknowns: none material for the deterministic blocker; all reproductions are side-effect free.

## 7. Inference (separate from facts)

- The chain is deterministically blocked on an engine defect whose smallest fix is proven (16-line
  relaxation branch, identical in two independent candidates, resolves 95/95 findings).
- The operator's charge for this occurrence authorizes repairing the named R7 editable runtime within
  scope: create the A-lineage descendant (current pinned runtime + the proven branch), reinstall editable,
  prove provenance, run the focused regression, rebind through the supported seam, then route finalize
  through Run Authority -> Custody -> WBC -> ordinary fixer and prove cursor advancement.
- No mutation has been performed by this observer. All reproductions were read-only.
