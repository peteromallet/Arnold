You are Sol (gpt-5.6-sol, high reasoning), stage 2 of the superfixer-debug protocol for the dead-blocked R7 Megaplan chain. This is a READ-ONLY adjudication pass: do NOT edit, launch, resume, rebind, or mutate any target artifact. You MAY write only inside the evidence directory named below. Your deliverable is a validated, content-addressed recovery handoff (Horizon A executable by the fixer) plus Horizon B planning, and you must decide the judgement calls reserved to you.

# Target and occurrence

- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- chain spec: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml (bound sha256 da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1)
- plan: cl2-wbc-backed-ledger-20260805-2140 (milestone 0 cl2-ledger-replay, iteration 5)
- chain state: .megaplan/plans/.chains/chain-880bd6e04632.json (last_state blocked, milestone 0, completed [], runtime rebound 14:00:39Z to a99e74e6/234ac3524)
- plan state: state.json (current_state blocked, meta.planner_repair circuit_open true occurrences 2 implementation_dispatch_allowed false failure_fingerprint 382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df)
- fresh-child occurrence digest: sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5
- this fixer run: subagent-20260806-145651-4c581f6a (observer hermes:deepseek:deepseek-v4-flash), operator grant grant_codex_critique_r7_superfixer_20260806_v2 approved 2026-08-06T14:53:54Z (max intent execution) — the occurrence-bound Run Authority charge to get this preserved occurrence moving
- pinned runtime: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 @ 234ac3524da29c1f630aee90ab1767a142a68a83 (content a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de), provenance ok:true, worktree clean, execution+runtime binding match. The approved editable runtime root for Horizon A.
- evidence dir (you may write here only): /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/

# Inputs to read (complete evidence; do not rely on this prompt alone)

- evidence pack: <evidence-dir>/evidence-pack.md
- raw snapshots: <evidence-dir>/raw/ (chain-state.json, chain-status.json, plan-state.json, plan-state-summary.json, planner_repair.json, failure-candidate-record.json, events-tail.ndjson, work-ledger-tail.ndjson, repro_splitter_feasibility.py + .out.txt)
- Sol stage 1: <evidence-dir>/sol-stage1.md
- swarm index: <evidence-dir>/swarm-index.json
- Flash reports: <evidence-dir>/swarm/fq-01.txt .. fq-08.txt (+ .meta.json), briefs in <evidence-dir>/briefs/
- report contract: <evidence-dir>/flash-report-contract.md
- prior occurrences: .megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/ (v1), ...-130215-69f23ad9/ (v4: handoff sha256:0e3c1467d6f0b1484168d1bca455171b28f8587754d4d763d6843c4e69599e06, blocked-receipt checkpoint, repro_finalize_sweep.py), ...-142036-1ea42c25/ (v5 evidence pack, cancelled as obsolete)
- existing follow-up ticket: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/follow-up-superfixer-v4-20260806-1329.json (content hash sha256:13e0aceb2ccc21dbdf66a75357a66381b8b175b1aa1f2102dc0d66a65507946f, Horizon B for the critique-custody category)
- runtime source (read-only): arnold_pipelines/megaplan/orchestration/task_splitter.py (split_task line 212; split_high_complexity_tasks line 461), orchestration/task_feasibility.py (dependency_unknown lines 305-307), orchestration/graph_admission.py (record_rejected_candidate, clear_planner_repair), handlers/finalize.py (_write_finalize_artifacts line 2031, feasibility 2080/2146, TaskFeasibilityError ~line 114, _route_finalize_task_feasibility_failure_to_revise line 1770), tests/arnold_pipelines/megaplan/test_task_splitter.py

# Established facts (verify only if you doubt)

1. Dead runner behind a deterministic blocker; recovery required; no recovery in flight (v5 cancelled; no live owner process, lease, or heartbeat for any prior occurrence).
2. Deterministic blocker: finalize rejects the candidate task graph: 12x dependency_unknown + dependency_graph_invalid, fingerprint 382e25a2…, occurrences 2, planner-repair circuit OPEN, implementation_dispatch_allowed false, no prior admitted finalize/feasibility hash.
3. Root cause (reproduced byte-identically this run): split_high_complexity_tasks/split_task remove original task ids (complexity>=7 → {id}_impl + {id}_proof) without rewiring downstream depends_on/dependency_reasons; feasibility rejects the dangling ids. Candidate had 19 tasks; 6 splits (T1,T2,T3,T4,T5,T7) → 25; the 12 recorded unknown pairs match the post-split repro exactly.
4. Second, masked reference-closure defect: critique_resolution_coverage[].task_ids and sense_checks[].task_id (and possibly validation coverage / user_actions[].blocks_task_ids / plan_steps_covered[].finalize_item_ids) name original ids that splitting removes; post-split custody validates coverage against the transformed set (fq-03, Sol stage-1).
5. Circuit ownership: record_rejected_candidate (write/increment/open) and clear_planner_repair (clear) are owned by the finalize handler under plan-lock publication CAS; the 14:03:37Z override (Run Authority→Custody→WBC, action_type repair) owns only the blocked→gated re-entry admissibility boundary (fq-04; Sol notes an unenforced/write-only edge — adjudicate).
6. Supported re-entry seam exists (fq-05): Run Authority → Custody → WBC → ordinary fixer finalize re-entry; v4 handoff operations list the exact producer path; 14:03:37Z override is the demonstrated instance.
7. Focused regression inventory exists (fq-06): tests/arnold_pipelines/megaplan/test_task_splitter.py and feasibility/finalize/graph-admission/circuit tests; the fix must add a downstream-rewire regression.
8. No sibling fingerprint (fq-07 refuted): 382e25a2… appears only in this plan + evidence copies; 0 in repair-data; 0 in r2/r5/r6 workspaces.
9. Liveness/notification negatives (fq-08): no live runner/lease/claim/WBC effect/notification records for this session.
10. Authoritative before fingerprint (42 canonical artifacts, incl. chain state, plan state, events, work ledger, planner_repair, candidates, receipts, leases, session marker, authority/wbc dbs, git heads+tracked status of project and runtime): sha256:5583a44e156adc23d3414eb4db0d2085d24c326030dc1000318f06561e12b17c — byte-identical before and after Sol stage 1 + swarm.
11. The v4 runtime fix (9c41d0554 critique-custody) is already installed and bound; it is NOT the current blocker. The splitter bug predates it (module last changed at m8 commit 86c1de74c) and is latent in the bound lineage.

# Your judgement calls (Sol-only; decide explicitly)

1. Fix scope: dependency fields only vs complete task-ID reference closure (depends_on, dependency_reasons, critique_resolution_coverage, sense_checks, validation coverage, user_actions blocks_task_ids, plan_steps_covered finalize_item_ids, any other task-ID-bearing field you find). Map each reference family to _impl vs _proof semantics.
2. Same-occurrence continuation vs authority-approved migrated child vs quarantine. Prefer same-occurrence continuation if the occurrence digest, chain/plan identity, and runtime lineage are unbroken (they are).
3. Whether planner-repair circuit clearing is owned by successful finalize (clear_planner_repair) while the blocked-state admission is the override/repair seam already satisfied at 14:03:37Z — or whether an additional authority transition is required. State the exact precondition and the machine-checkable condition for the circuit to be considered cleared.
4. Whether the existing follow-up ticket ticket-r7-superfixer-v4-20260806-1329 should be updated (append the splitter/finalize-graph category) or a new single ticket created. Exactly one canonical follow-up ticket must exist before recovery effects; record its id and content hash.
5. Sufficiency of the focused regression set and any additional tests the fix must add.
6. Any Flash conclusion you override, and why; mark unresolved conflicts INDETERMINATE.

# Required output structure

## Horizon A — immediate_route (agent_actionable: true, executable by THIS fixer run)

Must be an execution charge, not a report. Include:
- disposition: same-occurrence resume (repair_control_plane_then_migrate style) with explicit preconditions;
- the exact editable runtime root (/workspace/runtime-candidates/arnold-r7-fresh-child-20260805), the descendant creation steps (git switch -c recovery/... on the pinned branch, apply the minimal source change), `python -m pip install -e` reinstall, runtime provenance + content identity capture, and the CAS `chain runtime-rebind` command shape (from-runtime-sha256 a99e74e6… to-runtime-sha256 <new>, expected-current-milestone cl2-ledger-replay, expected-current-plan cl2-wbc-backed-ledger-20260805-2140, direction cutover, actor arnold-recovery, reason naming this occurrence, plus --runtime-identity/--runtime-provenance-receipt);
- the minimal source-level change: rewrite downstream task-ID references when split_high_complexity_tasks replaces an original id (dependencies + reasons + every task-ID-bearing field you adjudicate in scope), with collision/duplicate/self-reference/double-split edge handling; name the exact module/function/lines;
- the focused regression command(s) (pytest on test_task_splitter.py + task_feasibility + a new downstream-rewire test) and the iteration_loop (edit → test → observe → evidence delta → return to Sol stage 2 on failure; no hard budget);
- the one canonical request → Run Authority decision → Custody claim/epoch → WBC attempt/effect → verification path for re-entering finalize for THIS occurrence after the rebind (name the exact supported producer/API seam; if the seam needs the circuit cleared, state the exact supported transition and its authority basis — do NOT propose hand-editing state.json or sqlite);
- after-proof: real validator success (feasibility admitted true), accepted finalize task/result envelopes, matching runtime/request/grant/claim/WBC identities, custody released, WBC terminal success, plan cursor past finalize, chain milestone advanced beyond index 0;
- stop gates and the external_gate field (null unless a genuinely external approval/provider is the only remaining gate).

## Horizon B — long_term (agent_actionable: false)

Smallest complete cross-pipeline fix: first broken contract, missed backstop, canonical owner, machine-readable contract/identity to adopt, module/schema/test/migration/observability/notification changes, rollout/rollback, parallel work, very-hard decisions, epic/ticket crosswalk (epic critique-ledger-accountability-v3-r7-20260805; existing ticket ticket-r7-superfixer-v4-20260806-1329), and category-closure proof (replay exactly one occurrence/request/claim/WBC attempt/notification effect).

## Machine-readable handoff envelope

Emit the validated envelope at <evidence-dir>/recovery-handoff.json with schema arnold.superfixer.recovery_handoff.v1 and the full field set (handoff_id, target, evidence, horizon_a with route/agent_actionable/canonical_owner/preconditions/operations/focused_tests/iteration_loop/deployment_or_rebind_proof/external_gate/return_condition, horizon_b with epic_update_required/epic_slug/ticket_or_crosswalk/first_broken_contract/category_closure_proof, stop_gates, notification_key). handoff_id = "sha256:" + hex(sha256(canonical UTF-8 JSON of the envelope with handoff_id omitted, sorted keys, comma/colon separators)). You may also write <evidence-dir>/sol-stage2.md as the human-readable rendering with clearly delimited Horizon A (agent_actionable: true) and Horizon B (agent_actionable: false) blocks.

Constraints: read-only on all target artifacts; write only inside <evidence-dir>. Do not create or update any ticket yourself (the fixer does that after envelope validation, using your ticket_or_crosswalk decision). Do not launch/rebind/migrate. Do not emit a quarantine-only answer: Horizon A must be executable.
