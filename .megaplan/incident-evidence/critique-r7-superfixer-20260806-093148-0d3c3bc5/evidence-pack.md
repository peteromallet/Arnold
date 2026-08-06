# Evidence Pack — R7 Superfixer occurrence

occurrence_id: occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee
occurrence_key: sha256:70c522f651d6859e134250ee47500aa6e1dbbd824a69ac1b119444f1610f0142
schedule_id: sched_critique_r7_superfixer_retry_20260806_v1 (revision 1, generation 1)
observer model/transport: hermes:deepseek:deepseek-v4-flash / resident managed subagent
observed_at (UTC): 2026-08-06T09:32:00Z .. 09:52:00Z (window)

## 1. Identity

- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- chain spec: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml
  (sha256 da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1; revision-verification sha e5e4a789dc4472c22ce72fcb20b029c6fb661bea1c9f7a2227ea637ea6aca43c)
- plan: cl2-wbc-backed-ledger-20260805-2140 (milestone index 0 `cl2-ledger-replay`)
- chain state: .megaplan/plans/.chains/chain-880bd6e04632.json (last write 2026-08-06T00:53:46Z)
- plan state: .megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/state.json (iteration 5, current_state blocked)
- launch checkout (project): refs/heads/fix/r7-fresh-child-launch-20260805 @ d5848010695e28ddb9d9cbee8675d7ebe725caae (dirty: .megaplan artifacts; upstream 0/0)
- bound chain runtime (A): /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 @ d5848010695e (content_sha256 e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6)
- resident/pinned runtime (B): /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 @ 77b76e3a487809a2d1c89ea6785aac473c8931c8
  (B = A + 1 commit `77b76e3a4 fix(critique): carry verified tradeoffs across gate iterations`, touching
   arnold_pipelines/megaplan/orchestration/critique_custody.py (+16) and tests/orchestration/test_critique_custody.py (+39);
   git merge-base --is-ancestor A B == true; B NOT ancestor of A)
- installed runtime (default python import): B (77b76e3a4) — `arnold_pipelines.megaplan.__file__` resolves under -77b76e3a4
- session marker: /workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.json
  (attempt_id 02e5c83b-e50f-4d4c-be5c-6f0b3aa8c1e7; run_id 9f46fff6-7f30-4978-99c8-f039368b8f66; pid 629623; launch_outcome status running at 21:40:56Z)
- fresh child admission receipt: plans/cl2-wbc-backed-ledger-20260805-2140/fresh_child_admission.json
  (occurrence_digest sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5;
   wbc_attempt_id ...:attempt:1; glek glek:cf80b5736a31cfe40c87e8227f55d6d27ba1e42665c0be97feb02577705e61fc;
   authority_grant_id grant:fresh-child:8ef0d95eb34a7a55563cfeb5; custody lease lease:arnold.megaplan.fresh_child_admission.v1:8ef0d95eb34a7a55563cfeb5...)

## 2. Canonical state (facts)

- `megaplan introspect --plan cl2-wbc-backed-ledger-20260805-2140` (2026-08-06T09:36:55Z):
  plan_state=blocked, display_state=blocked, execution_state=blocked, iteration=5,
  binary_git head=d5848010695e, dirty=true.
- chain state last_state=blocked; events: ["milestone cl2-ledger-replay starting"];
  milestone_boundary_evidence cl2-ledger-replay contract_id chain.milestone.start.1; completed=[].
- plan state history (state.json):
  init success 21:40:56Z; prep success 21:51:10Z (cost $0.22); plan error 21:57:37Z (structural audit);
  plan success 22:05:19Z (v1); critique success 22:22:22Z (24 flags); gate error 22:24:09Z (enum);
  gate success 22:26:26Z ITERATE; revise error 22:30:49Z (missing fields); revise success 22:35:53Z (v2);
  critique 22:52:23Z (12 flags); gate blocked 22:59:46Z ITERATE; revise success 23:04:57Z (v3);
  critique 23:36:25Z (17 flags); gate success 23:39:49Z ITERATE; revise error 23:45:18Z; revise success 23:51:31Z (v4);
  critique 00:06:01Z (12 flags); gate success 00:08:07Z ITERATE; revise success 00:21:31Z (v5);
  critique 00:48:31Z (30 flags); gate success 00:53:17Z **PROCEED** (gate.json hash 9df9582599f9fe096df87ab1ff23665a9e116ea959deae3e3102feab9dbead3b).
- phase_result.json: phase=gate, exit_kind=success, artifacts gate_signals_v5.json, gate.json, gate_carry.json.
- plan_versions: v1 f2e00315... 22:05:19Z; v2 e16d1225... 22:35:53Z; v3 ff25676b... 23:04:57Z;
  v4 4541645f... 23:51:30Z; v5 4537c985... 00:21:31Z.
- finalize attempts (chain log + events.ndjson seq 3089-3098):
  phase_start finalize 00:53:27.893Z; phase_end 00:53:36.371Z (fail); 00:53:36.908Z (fail);
  00:53:45.577Z (fail); 00:53:46.130Z (3rd); chain blocked at 00:53:46Z.
- Deterministic failure payload (chain log, repeated 3x):
  "[auto cl2-wbc-backed-ledger-20260805-2140] phase 'finalize' exited with internal_error:
   {\"success\": false, \"error\": \"critique_finding_unresolved\", \"message\":
   \"critique_finding_unresolved: finding CF-0B506E1EDCD92E90C192 / flag CF-0B506E1EDCD92E90C192 remains
   'accepted_tradeoff'; it needs a traceable plan mutation plus verification, or an evidence-backed invalidation\", ...}"
  Final: "[chain] plan cl2-wbc-backed-ledger-20260805-2140 ended blocked: phase 'finalize' repeated the same internal_error 3 times".

## 3. Process / lease / liveness (facts)

- Marker pid 629623: DEAD (ps shows no such process).
- Liveness lease /workspace/.megaplan/cloud-sessions/...liveness-lease.json:
  status="stopped", expires_at=2026-08-06T00:53:46.682173Z, publisher_pid=629623, runner_fence=1, sequence=2315.
- Liveness fence: runner_fence=1 (schema arnold.megaplan.runner_liveness_fence.v1).
- No chain driver / megaplan auto / codex process for this session running at observation time
  (ps aux: only resident listener pid 1/7 and this backstop's own subagent worker 844068/844069).
- Last plan-dir writes 00:53:46Z (state.json, events.ndjson, .events.projection.seq). No fresh activity for ~8.5h.
- Prior backstop occurrence subagent-20260806-090508-e36c9344 (occ_critique_r7_superfixer_test_20260806_bf20f42338959ee452085fdb):
  status interrupted at 09:14:45Z (KeyboardInterrupt/SIGTERM, terminal_outcome interrupted); result.md empty;
  NO live owner process; no receipts written. Does NOT constitute recovery-in-flight.

## 4. Run Authority / Custody / WBC (facts)

- authority dir: .megaplan/authority/run-authority.sqlite3 (36KB, mtime 21:40), wbc.sqlite3 (100KB, mtime 21:40),
  custody/ contains only the fresh-child admission lease (state.json, history.jsonl, lock).
- Repair queue: only ONE request for this session:
  requests/74403266d5cb0592770cffe5f8c0d31c627dff7ef62577994808df588c603bd7.json
  created 2026-08-06T00:13:08Z, source lifecycle_failure, problem_signature phase_failed current_state=critiqued
  phase_or_step=revise attempt=6 (this was the earlier revise structural-audit failure at 00:13 era; the run later
  self-recovered at 00:21:31Z revise success). decision accepted/queued (decisions/20260806T001308Z-...json).
  NO repair request exists for the finalize blocker (no request created >= 00:53:17Z).
- No repair custody lease/claim/attempt for the finalize blocker.

## 5. Root-cause reproduction (proven facts)

- Finding CF-0B506E1EDCD92E90C192 ("plan unilaterally bypasses verify_cl2_admission ... should be explicitly accepted
  by the gate rather than inherited silently"): raised in critique_v1 (custody v1, blocking=true), registry (faults.json)
  status="accepted_tradeoff", severity="significant", addressed_in=plan_v2.md,
  resolution={kind:fixed, claim:"BRIDGE bypass documented...", where:"Overview (BRIDGE scope deviation), Step 14..."},
  NO gate_resolution key, verified=false.
- Latest gate (v5) accepted_tradeoffs = [CF-CCF03AAFF3C69AF4DF35, CF-8F19D157FEE360DC5050, CF-671323AC99A1FF9A93A6]
  — CF-0B506E1EDCD92E90C192 NOT carried; gate_carry.json has no entry for it.
- faults.json mtime 00:53:12.98Z (gate write); finalize attempts 00:53:27-00:53:46Z read this registry.
- Runtime A (bound chain runtime d5848010) `_resolution_for_finding` has NO
  `status=="accepted_tradeoff" and gate_expected and fixed_claim` relaxation branch.
  REPRODUCTION (read-only, PYTHONPATH=A, real plan data): RAISED
  CritiqueCustodyError critique_finding_unresolved ... CF-0B506E1EDCD92E90C192 remains 'accepted_tradeoff' (exact match).
- Runtime B (installed/pinned 77b76e3a4) `_resolution_for_finding` HAS the relaxation branch (added by commit 77b76e3a4).
  REPRODUCTION (read-only, PYTHONPATH=B, same data): returns disposition verified_plan_mutation for the same flag.
- Full sweep over all 95 findings in custody receipts v1-v5 with runtime B: 0 failures (all resolve).
- Therefore: the deterministic blocker is a runtime-version contract mismatch in finalize critique-custody resolution;
  the chain launched under runtime A before the lineage fix (77b76e3a4) landed; the currently installed/pinned runtime
  is B, which contains exactly the fix for this failure category.

## 6. Contracts / validators (facts)

- finalize custody contract: arnold_pipelines/megaplan/orchestration/critique_custody.py
  `_resolution_for_finding` (line ~1215) raises CritiqueCustodyError("critique_finding_unresolved", ...) (line ~1326)
  when a flag status has no acceptable resolution path:
    * verified + fixed_claim -> verified_plan_mutation
    * accepted_tradeoff + gate_expected + fixed_claim -> verified_plan_mutation (B only; absent in A)
    * gate_disputed + evidence -> invalidated_with_evidence
    * accepted_tradeoff + gate_expected + gate_resolution.action==accept_tradeoff + rationale -> minor_tradeoff
    * open/verified non-blocking minor -> tracked_nonblocking_observation
    * addressed + !gate_expected + fixed_claim -> plan_mutation_light_workflow
    * else -> critique_finding_unresolved
- fixed_claim = resolution.kind==fixed AND claim AND where AND resolution_targets_admitted_descendant AND plan_mutated
  (plan_mutated = current plan sha != source plan sha; descendant = source_version < addressed_version <= current_version).
- Chain driver: chain.yaml driver.require_editable_runtime_match=true; phase_timeout 10800; max_iterations 60;
  on_failure abort stop_chain; finalize phase model codex:gpt-5.6-sol:high (finalize CLI).
- plan config: robustness thorough, profile partnered-5-glm, vendor codex, completion_contract_mode shadow.

## 7. Sibling / negative search (facts)

- No other session with same failure fingerprint found (search of /workspace/.megaplan cloud-sessions markers;
  v5/r5, v3-r2/r3 markers present but untouched and unrelated).
- repair-queue contains no other r7 request; no no-action-receipt.json / blocked-receipt.json exists for this session.
- No notification intent/effect records found for this blocker (no notification custody files for r7).
- Watchdog report /workspace/watchdog-report.json is dated 2026-08-03 (pre-r7; not authoritative for this session).
- Unknowns: exact in-memory registry at the moment of the 00:53:36 finalize failure (faults.json on disk == gate write
  at 00:53:12; reproduction against on-disk data under runtime A fails identically, so on-disk state is consistent
  with the observed failure). The two `TypeError: emit_transition() got multiple values` lines in the chain log are
  noted as secondary anomalies (work_ledger observability), not the terminal blocker.

## 8. Inference (separate from facts)

- The chain reached a legitimately gated/proceed state; finalize is the only phase that cannot complete under runtime A.
- The lineage fix (B) is a pure descendant of the launched runtime (A) and is the currently pinned/installed runtime.
- Horizon A candidate (for Sol adjudication): re-attempt finalize for the same occurrence through the canonical
  repair-request seam (rerun_phase finalize) under the installed runtime B — i.e., the ordinary fixer retriggers the
  phase exactly once. Whether this requires an authority-approved runtime rebind/migration (A->B) or is a
  same-lineage resume is a Sol judgement call.
- No mutation has been performed by this observer. All reproductions were read-only computations.
