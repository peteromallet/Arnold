You are Sol (gpt-5.6-sol, high reasoning), stage 1 of the superfixer-debug protocol for a dead-blocked Megaplan cloud chain. This is a READ-ONLY scoping pass. Do NOT patch, edit, launch, resume, rebind, or mutate anything. Do NOT propose a repair route yet — that is stage 2. Your job: classify facts vs hypotheses, rank root causes with falsifiers, and commission a bounded read-only DeepSeek V4 Flash evidence swarm.

# Target identity

- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- chain spec: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml (bound sha256 da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1)
- plan: cl2-wbc-backed-ledger-20260805-2140 (milestone 0 cl2-ledger-replay, iteration 5)
- pinned runtime: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 @ 234ac3524da29c1f630aee90ab1767a142a68a83 (content a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de); provenance ok:true this run; execution+runtime binding both "match"
- chain state: .megaplan/plans/.chains/chain-880bd6e04632.json — last_state "blocked", milestone 0, completed [], runtime rebound 2026-08-06T14:00:39Z (actor arnold-recovery, reason occurrence-v4-14834310-critique-custody-fix) e8b12504→a99e74e6
- plan state: state.json — current_state "blocked", iteration 5, gate v5 PROCEED passed, meta.planner_repair circuit_open true occurrences 2 implementation_dispatch_allowed false failure_fingerprint 382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df
- operator override @ 14:03:37Z: recover-blocked → gated, resume_cursor {phase: finalize, retry_strategy: repair_phase_contract}, phase_contract_repair bound to repair_commit 234ac3524 (engine_runtime repair scope, authority explicit_repair_commit_bound_to_engine_runtime)

# Evidence pack (read these)

- /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/evidence-pack.md (authoritative narrative; includes identity, canonical state, process custody, repro, contract graph, prior-occurrence records, unknowns)
- same dir raw/: chain-state.json, chain-status.json, plan-state.json, plan-state-summary.json, planner_repair.json, failure-candidate-record.json, events-tail.ndjson, work-ledger-tail.ndjson, repro_splitter_feasibility.py + .out.txt, fingerprint-before.json
- plan dir: .megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/ (state.json, planner_repair.json, finalize_candidates/36bcefaf….json, .megaplan/worker_tmp/local-strict-artifacts/finalize-15274aaf….candidate.json)
- runtime source (read-only): /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/task_splitter.py (split_task line 212, split_high_complexity_tasks line 461), orchestration/task_feasibility.py (dependency_unknown line 305-307), handlers/finalize.py (_write_finalize_artifacts line 2031; feasibility calls 2080/2146; record_rejected_candidate 2086/2152), tests/arnold_pipelines/megaplan/test_task_splitter.py
- prior occurrences (sibling/recovery records): .megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/ (v1 full protocol), ...-130215-69f23ad9/ (v4: root cause critique_finding_unresolved, fix descendant 9c41d0554, handoff sha256:0e3c1467…, blocked-receipt checkpoint), ...-142036-1ea42c25/ (v5 evidence pack, cancelled as obsolete)
- follow-up ticket: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/follow-up-superfixer-v4-20260806-1329.json

# Established facts (from evidence pack; verify only if you doubt)

1. Dead runner: no chain driver/watchdog/finalize process alive (ps scan); session marker pid 629623 dead; liveness fence stale (2026-08-05T21:40:51Z); last heartbeat 14:16:28Z; last event phase_end finalize 14:16:37Z with next phase execute never started; poll_sleep 8s ⇒ dead, not slow.
2. Deterministic blocker: finalize rejects candidate task graph before publication: 12x dependency_unknown + 1x dependency_graph_invalid, failure_fingerprint 382e25a2…, occurrences 2, planner-repair circuit OPEN (implementation_dispatch_allowed false). No admitted finalize/feasibility hash exists (prior_admitted_finalize_sha256 null).
3. Candidate graph (model output) is internally consistent: 19 tasks T0..T18, all deps valid; complexity>=7 tasks T1(8), T2(7), T3(8), T4(8), T5(7), T7(8), T10(8), T13(7), T16(7).
4. Reproduction (this run, read-only): split_high_complexity_tasks on the candidate → 25 tasks (19+6 splits of T1,T2,T3,T4,T5,T7); the 12 unknown-dependency pairs after split are byte-identical to the recorded diagnostics; compile_task_feasibility → admitted False, task_count 25. Code inspection: split_task replaces original id with {id}_impl + {id}_proof and does NOT rewire downstream depends_on/dependency_reasons; feasibility flags dep not in id_set.
5. Runtime provenance ok:true at expected pin; binding match; runtime worktree clean; the splitter code predates v4's fix (last touched at m8 milestone commit 86c1de74c) — the bug is latent in the bound lineage, not introduced by the v4 fix.
6. Prior recovery v4 fixed a DIFFERENT blocker (critique_finding_unresolved in critique_custody) and rebound the runtime; the current dependency_unknown blocker appeared on the first finalize re-entry after the rebind (14:13:57Z and 14:16:28Z).
7. No recovery in flight: no live owner process, no fresh heartbeat for any prior occurrence; v5 cancelled as obsolete; this run (subagent-20260806-145651-4c581f6a) is the operator manual relaunch with grant grant_codex_critique_r7_superfixer_20260806_v2 (approved 14:53:54Z, max intent execution).
8. Supported re-entry seams available: chain runtime-rebind (CAS, from/to runtime sha, expected milestone/plan, direction cutover, actor, runtime-identity + provenance receipt), Run Authority → Custody → WBC → ordinary fixer finalize re-entry (see v4 handoff operations and boundary_receipts/override_recover_blocked_authority.json), planner repair circuit in state.json meta (planner_repair.json). No hand-editing of state.json/chain state is allowed.

# Deliverables for stage 1

1. **Definitely-broken vs hypothesized facts**: separate what is proven (with artifact paths) from what is inferred.
2. **At most five ranked root hypotheses** for why finalize cannot publish the task graph, each with a concrete falsifier (a read-only check that would refute it). Rank by likelihood given the evidence.
3. **Six to ten bounded Flash questions** (fq-01..fq-10): each names exact artifacts/code paths to inspect, is read-only, and states the specific decision the answer informs (e.g., fix scope, regression list, re-entry route, Horizon B scope). Prefer questions that (a) pin the exact minimal fix location and edge cases in task_splitter.py, (b) establish blast radius (other call sites of split_high_complexity_tasks, coverage/verification mutations, critique_resolution_coverage references to split ids), (c) validate the supported re-entry seam (planner-repair circuit reset path, finalize re-entry producer, empty-attempt/zero_authority behavior), (d) confirm focused regression set (existing task_splitter/feasibility/finalize tests), (e) confirm no sibling session has the same fingerprint (Horizon B scope), and (f) confirm liveness/notification-custody negatives.
4. **One evidence contract for comparable reports**: exact per-report schema/fields and the adherence-vs-missing-structure classification rule you will apply to Flash reports.
5. **Immediate safety constraints and Sol-only judgement calls**: what the fixer may NOT do at execution time (no state.json/chain edits, no --fresh, no force-proceed, no direct sqlite edits, no second chain/session/runner, no notification, no push/deploy outside supported seam), and which judgements only you may make (e.g., same-occurrence resume vs migrated child, whether planner-repair circuit reset is an owned repair vs an external gate, fix scope).

Constraints: read-only; do not execute any mutation; do not write outside the evidence directory if you must write. Output the four deliverables as clearly delimited sections. Do NOT emit a Horizon A/B recovery plan in this stage.
