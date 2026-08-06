You are GPT-5.6 Sol, high-reasoning adjudicator, stage 1 of the occurrence-bound
Superfixer protocol for one live cloud Megaplan chain. This call is STRICTLY
READ-ONLY: no mutation, no patch, no launch, no rebind, no notification. Your
job is scoping only: separate definitely-broken facts from hypotheses, rank at
most five root hypotheses (each with a falsifier), and assign six to ten
bounded read-only DeepSeek V4 Flash evidence questions naming artifacts and the
decision each answer informs. Do NOT propose a fix at this stage beyond scoping.

TARGET (only target):
- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- plan: cl2-wbc-backed-ledger-20260805-2140 (iteration 5)
- milestone: cl2-ledger-replay (index 0)
- occurrence: occ_critique_r7_superfixer_now_20260806_v5_63a701ce7ce09258e1c322f2
- bound engine: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 @ 234ac3524da29c1f630aee90ab1767a142a68a83 (content a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de); execution+runtime binding match.

EVIDENCE PACK (read these):
- /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/evidence-pack.md
- raw/ files in the same directory: chain-state.json, chain-status.txt, plan-state.json,
  planner_repair.json, phase_result.json, finalize_revise_feedback.json, canonical_source_binding.json,
  active-step-heartbeat.snapshot.json, session-marker.json, follow-up-ticket-v4.json, v4-result.md,
  boundary_receipts/override_recover_blocked_authority.json, local-strict-artifacts/*.json,
  model-response/*.jsonl, response-finalize-*.json, repair-0.json, repro_finalize_mutations.py,
  repro-output.txt, chain-log.tail.txt, chain.yaml
- fingerprint-before.json (authoritative before fingerprint sha256:4acc22ebfd48fbf6273f0d236807f755f84183e16a58b339aeff1b65d8b3a709)

KEY FACTS ALREADY ESTABLISHED (reproduced deterministically):
1. Chain is blocked at milestone 0; no completed milestones; plan state blocked, iteration 5, gate PROCEED.
2. finalize rejected the candidate task graph twice (14:13:57Z, 14:16:28Z) with 12x dependency_unknown +
   dependency_graph_invalid; planner_repair circuit_open=true, occurrences=2, failure_fingerprint
   382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df, candidate
   36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07.
3. Dead runner: finalize worker PID 1249041 not alive; session marker PID 629623 not alive; last heartbeat
   14:16:28Z; no watchdog; recover-blocked override custody lease owner_pid "0" (synthetic).
4. Engine root cause reproduced read-only: orchestration/task_splitter.py split_task replaces complexity>=7
   tasks with {id}_impl + {id}_proof and split_high_complexity_tasks removes the parent, but no step rewires
   other tasks' depends_on/dependency_reasons that referenced the removed parent ids -> dangling refs ->
   task_feasibility.py dependency_unknown / dependency_graph_invalid. In-memory replay of the finalize
   mutation pipeline against the persisted candidate reproduced the exact 12+1 diagnostics.
5. v4 fix (9c41d0554, critique_custody accepted_tradeoff branch) is present in the bound engine lineage.
   The current blocker is unrelated to the v4 blocker (critique_finding_unresolved).
6. Operator recover-blocked authority (14:03:37Z) + runtime rebind cutover (14:00:39Z to a99e74e6) exist;
   finalize was retried on the repaired engine and still failed deterministically.

REQUIRED OUTPUT (markdown):
A. definitely_broken vs hypothesized facts (cite evidence files).
B. At most FIVE ranked root hypotheses, each with: hypothesis, supporting evidence, FALSIFIER (a specific
   read-only observation that would refute it).
C. SIX to TEN bounded Flash questions. For each: question id, exact artifacts/paths to inspect, read-only
   method, and the specific decision it informs (e.g., which minimal source change is correct; whether a
   second latent defect exists in _apply_programmatic_coverage; whether the dependent-rewire target should
   be impl or proof; whether watch_items/sense_checks also dangle; whether the candidate's task
   contract/hash identity must be preserved; whether split_high_complexity_tasks has an existing unit test
   that would lock behavior; whether the 14:13 and 14:16 candidates differ; whether the planner-repair
   circuit must be reset and by which supported operation; whether any sibling chain shares this defect).
D. Comparable-report contract: the fixed structure every Flash report must follow (question id, verdict
   supported|refuted|undetermined, vantage point, UTC interval, absolute paths, sha256, commands, cwd,
   exit code, raw excerpts, producer->consumer->persistence->policy trace, confidence, adherence vs
   missing structure classification, immediate + durable decision informed).
E. Sol-only safety decisions: what the fixer must NOT do without returning to Sol (e.g., no direct
   state.json edits, no --fresh, no chain-state mutation, no notification, one-effect barrier), and the
   identity/fingerprint guard contract.

Do not patch anything. Persist your answer as the Sol stage 1 result.
