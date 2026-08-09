# Evidence Pack — R7 Superfixer occurrence (manual relaunch, active)

Incident: critique-ledger-accountability-v3-r7 — deterministic finalize blocker (task-graph splitter rewire bug), dead runner
Occurrence run: `subagent-20260806-145651-4c581f6a` (managed child, resident)
Observer model/transport: `hermes:deepseek:deepseek-v4-flash` / resident managed subagent
Observed at (UTC): 2026-08-06T14:56Z .. 15:10Z
Grant: `grant_codex_critique_r7_superfixer_20260806_v2` (approved 2026-08-06T14:53:54Z, max intent execution, operator codex thread, source envelope digest sha256:04303ffd16bdcb860d1667cf22e35e7d8013db4f8577fcdc40dcd3c38401a2fc)

## 0. Decision under test (safety/liveness gate)

Question: is the canonical run healthy/slow (no action) or blocked/dead (recovery)?
Verdict: **recovery required** — deterministic blocker + dead runner; no recovery in flight.

## 1. Identity

- session: `critique-ledger-accountability-v3-r7-launch-20260805`
- workspace: `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold`
- chain spec: `.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml`
  chain_spec_sha256 (bound): `da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1`
- plan: `cl2-wbc-backed-ledger-20260805-2140` (milestone index 0 `cl2-ledger-replay`, iteration 5)
- chain state: `.megaplan/plans/.chains/chain-880bd6e04632.json`
  - `current_milestone_index: 0`, `current_plan_name: cl2-wbc-backed-ledger-20260805-2140`,
    `last_state: "blocked"`, `completed: []`, `dirty_flag: false`, `pr_number: null`
  - execution binding `status: "match"` (launched_identity ready, errors []; active ready, errors [])
  - runtime binding `status: "match"` (`active_errors: []`) — current identity
    import_root `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805`,
    source_revision `234ac3524da29c1f630aee90ab1767a142a68a83`,
    content_sha256 `a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de`
  - `rebind_events[0]`: rebound_at `2026-08-06T14:00:39Z`, actor `arnold-recovery`,
    reason `occurrence-v4-14834310-critique-custody-fix`, direction `cutover`,
    from `e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6`
    to `a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de`
  - ground_truth_reconciliation: reconciled_at `2026-08-06T14:05:49Z`, current_state `gated`,
    latest_failure null, last_gate recommendation PROCEED passed true
- plan state `state.json`: `current_state: "blocked"`, `iteration: 5`, `latest_failure: null`,
  `last_gate.recommendation: PROCEED`; `meta.planner_repair`:
  candidate_id `candidate:36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07`,
  failure_fingerprint `382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df`,
  occurrences 2, circuit_open true, implementation_dispatch_allowed false, updated_at 14:16:28Z
- run_id (session marker): `9f46fff6-7f30-4978-99c8-f039368b8f66`; marker pid `629623` DEAD;
  marker liveness_claimed_at/updated_at `2026-08-05T21:40:5xZ` (stale)
- liveness fence: `/workspace/.megaplan/cloud-sessions/.critique-ledger-accountability-v3-r7-launch-20260805.liveness-fence.lock`
  mtime `2026-08-05T21:40:51Z` (stale)
- fresh child admission: occurrence_digest `sha256:f3b952beb7881acc80f5efc98b1f21b64a911cc6d17dd87b220e1d336b4e55c5`,
  wbc_attempt_id `...:child:cl2-wbc-backed-ledger-20260805-2140:attempt:1`,
  glek `glek:cf80b5736a31cfe40c87e8227f55d6d27ba1e42665c0be97feb02577705e61fc`,
  authority_grant_id `grant:fresh-child:8ef0d95eb34a7a55563cfeb5`,
  custody_lease_id `lease:arnold.megaplan.fresh_child_admission.v1:8ef0d95e...`
- project checkout: branch `megaplan/critique-ledger-accountability-v3-r7-20260805/cl2-ledger-replay`
  @ `d5848010695e28ddb9d9cbee8675d7ebe725caae` (tracked clean)
- pinned runtime: `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805`
  branch `fix/r7-fresh-child-launch-20260805` @ `234ac3524da29c1f630aee90ab1767a142a68a83` (tracked clean)
- runtime provenance (this run, wrapper env): `ok: true`, errors [],
  import_root==editable_root==expected_root, runtime_revision==source_revision==`234ac3524...`,
  runtime_identity.content_sha256 `a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de`,
  pth readable sha256 a2e6bee4907592da90ed9ed56d2e1bfa8dfabf6b9c5cd8b9b5f30d1194eae9ff
  (receipt emitted at 14:57Z; matches contract pin exactly)

## 2. Canonical state (facts)

- `run_mp chain status`: milestone 0 `cl2-ledger-replay` in_progress; `summary.last_state: "blocked"`;
  execution binding match; runtime binding match; `summary.execution_binding.runtime_binding.active_errors: []`.
- Events `events.ndjson` (29,346,999 bytes, mtime 14:16:37Z): last event
  `{"kind":"phase_end","payload":{"phase":"finalize"},...,"seq":3136,"ts_utc":"2026-08-06T14:16:37.415053+00:00",
  "workflow_cursor":{"dispatch_phase":"finalize","next_dispatch_phases":["execute"],"next_phases":["execute"]}}`
  → finalize ended at 14:16:37Z with next phase `execute`; **no phase_start(execute) event exists**.
- Work ledger `work_ledger.ndjson`: auto_loop retry_wait attempt 24 @ 00:53:37Z; then attempt 2 @ 14:16:29Z
  (attempt counter reset ⇒ driver/loop restarted after the 14:00:39Z rebind); no entries after 14:16:29Z.
- History (state.json): `finalize` @ 14:13:57Z result `planner_repair_required` then `error`
  "Finalize rejected a candidate task graph before publication (dependency_unknown ×12, dependency_graph_invalid)...";
  `finalize` @ 14:16:28Z result `planner_repair_blocked` then `error` (identical message).
- `planner_repair.json` and `state.json.meta.planner_repair`: circuit_open true, occurrences 2,
  implementation_dispatch_allowed false, prior_state gated, prior_admitted_finalize_sha256 null.
- Gate v5 (00:53:17Z): recommendation PROCEED, passed true, weighted score 20.5→10.0, 58 flags resolved.
- `meta.overrides` (state.json): operator `recover-blocked` override @ 2026-08-06T14:03:37Z,
  from_state blocked → to_state gated, resume_cursor `{phase: finalize, retry_strategy: repair_phase_contract}`,
  phase_contract_repair `{failure_kind: deterministic_phase_failure, phase: finalize,
  repair_commit: 234ac3524da29c1f630aee90ab1767a142a68a83, repair_scope: engine_runtime,
  repair_root: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805,
  authority: explicit_repair_commit_bound_to_engine_runtime}`.
- `boundary_receipts/override_recover_blocked_authority.json` @ 14:03:37Z: Run Authority grant
  `recover-blocked:cl2-wbc-backed-ledger-20260805-2140:9d5418d618d54e9b:grant` satisfied; coordinator fence
  1253577917 satisfied; custody lease `lease:recover-blocked:cl2-wbc-backed-ledger-20260805-2140` epoch 1
  satisfied (owner `override-wbc`, owner_pid 0 — synthetic, not a live process); WBC attempt
  `override:recover-blocked:…:9d5418d618d54e9b` satisfied; action_boundary `{gate_result: authorized, action_type: repair}`.
- WBC attempt ledger (`.phase_wbc_attempts.sqlite3`): finalize attempts
  `36889f91-b1a7-55cf-b493-a2a72a332266` (started ~14:13:57Z, completed) and
  `cc65bd5d-9be6-5fde-8935-e81eb7183609` (started ~14:16:28Z, completed) — harness-level phase attempts
  recorded; the planner-level candidate rejection is recorded in planner_repair.json.
- Chain log `cloud-chain-critique-ledger-accountability-v3-r7-launch-20260805.log`: last write 2026-08-06T00:53:46Z
  (post-rebind finalize writes went to plan state/events, not the launch log).

## 3. Process custody / liveness (facts)

- Session marker PID `629623`: **not alive**.
- Finalize worker PID `1249041` (runner_incarnation, model gpt-5.6-sol, session 019fd765…, started 14:14:06Z): **not alive**.
- Last heartbeat: `active-step-heartbeat.snapshot.json` last_activity 14:16:28Z (candidate artifact
  `finalize-15274aaf….candidate.json` sha256 cfc7d701…, 77557 bytes). No heartbeat since.
- `ps` full scan at 14:57Z and 15:00Z: only resident Discord listener (PIDs 1, 7 — orchestrator, not chain runner)
  and this occurrence's own managed subagent worker (PIDs 1434127/1434128). No chain driver, no watchdog,
  no relauncher, no repair-loop process. No `nohup`/detached fan.
- Chain poll_sleep is 8s (chain.yaml driver.poll_sleep) — ≥40 min of silence with no process ⇒ driver dead, not slow.
- v5 superfixer occurrence (`subagent-20260806-142036-1ea42c25`) — prior one-shot — was **cancelled as obsolete**
  (this occurrence is the operator's manual relaunch; grant 14:53:54Z). No live process owned by v5.
- **Recovery-in-flight check**: no authoritative managed-child custody with live owner + fresh heartbeat exists
  for any prior occurrence (v1..v5 evidence only; v4 rebind completed; v5 cancelled). No repair request/claim/WBC
  effect with a live owner. Verdict: no recovery in flight.

## 4. Deterministic blocker — reproduction (proven facts)

- Failure fingerprint: `382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df`
  (`finalize_candidates/36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07.json`).
- Diagnostics: 12× `dependency_unknown` ("Dependency must reference a different finalized task."):
  (T2_impl→T1), (T3_impl→T2), (T4_impl→T1), (T5_impl→T4), (T6→T1), (T8→T7), (T9→T1), (T10→T3),
  (T11→T1), (T13→T5), (T15→T3), (T15→T5); 1× `dependency_graph_invalid` ("Unknown dependency ID 'T1' for task 'T2_impl'").
- Report: task_count 25, edge_count 33, root_count 0, batches [], critical_path_task_count 0,
  execute_phase_timeout_minutes 60, warning task_count_high (>24).
- Candidate (`finalize-15274aaf2cb2445487647129704dcccd.candidate.json`, sha256 cfc7d701…): 19 tasks T0..T18,
  internally consistent (every depends_on references an existing id). Complexity ≥7 tasks:
  T1(8), T2(7), T3(8), T4(8), T5(7), T7(8), T10(8), T13(7), T16(7).
- Engine code: `arnold_pipelines/megaplan/orchestration/task_splitter.py`
  - `split_task` (line 212): for complexity ≥ `_SPLIT_THRESHOLD`, replaces the original task with
    `{task_id}_impl` (depends_on inherited from the original) and `{task_id}_proof` (depends_on [impl_id]).
    The original id is **removed** from the task set.
  - `split_high_complexity_tasks` (line 461): applies split_task per task; **no rewiring of downstream
    tasks' `depends_on`/`dependency_reasons` that referenced the removed original id**.
- Engine code: `arnold_pipelines/megaplan/orchestration/task_feasibility.py` line 305-307:
  `if dep not in id_set or dep == task_id: diagnostics.append(FeasibilityDiagnostic("dependency_unknown", ...))`.
- Engine code: `arnold_pipelines/megaplan/handlers/finalize.py` `_write_finalize_artifacts` (line 2031):
  applies `_ensure_verification_task` → `_ensure_user_actions_pre_gate_task` → `_apply_programmatic_coverage`
  → `_normalize_task_complexity` → `_split_finalize_tasks` (line 2059, 2135) → `compile_task_feasibility`
  (lines 2080, 2146); on `not admitted` → `record_rejected_candidate` + raise TaskFeasibilityError
  (lines 2086-2087, 2152-2153). TaskFeasibilityError message lists the codes (line ~114).
- **Reproduction (read-only, this run)**: loaded the 14:16 candidate; ran `split_high_complexity_tasks`
  → 25 tasks (19+6 splits: T1,T2,T3,T4,T5,T7); unknown-dependency pairs after split are **byte-identical**
  to the recorded diagnostics (12 pairs); `compile_task_feasibility` → admitted False, task_count 25,
  diagnostics include all 12 dependency_unknown + dependency_graph_invalid.
  Script: `raw/repro_splitter_feasibility.py`, output `raw/repro_splitter_feasibility.out.txt`.
- Interpretation (facts vs inference): FACT — splitter removes original ids without rewiring downstream
  references; FACT — feasibility rejects exactly those references; FACT — finalize therefore cannot publish
  any candidate whose graph contains a complexity ≥7 task referenced by another task; FACT — plan v5 graph
  contains such tasks; INFERENCE — the minimal engine fix is dependency rewire in the splitter
  (map original_id → impl_id for downstream depends_on/dependency_reasons and coverage references),
  plus a focused regression.

## 5. Contract graph

- Finalize publishes only an admitted candidate (`task_feasibility.json` written only on admission, finalize.py:2156).
- planner_repair circuit: after 2 occurrences of the same fingerprint the circuit is open;
  `implementation_dispatch_allowed: false`; prior admitted finalize/feasibility sha256 null.
- The ordinary fixer may not hand-edit state.json/chain state; the supported re-entry seam is the
  Run Authority → Custody → WBC → ordinary fixer path (see v4 handoff operations and the 14:03:37Z override receipt).
- `critique_resolution_coverage` in the candidate references task_ids incl. T0, T1, T17 — split ids
  (T1) may be referenced there too; downstream execute admission may consume coverage task ids.
- Task splitter tests exist: `tests/arnold_pipelines/megaplan/test_task_splitter.py` (focused regression target).
- Feasibility tests: `tests/arnold_pipelines/megaplan/` (test_task_feasibility* expected).

## 6. Recovery / observer records (prior occurrences, sibling search)

- v1 `...093148-0d3c3bc5/`: full protocol (evidence-pack.md, sol-stage1.md, swarm/ fq-01..fq-10 via fan.py
  deepseek:deepseek-v4-flash, sol-stage2.md, repair-producer-attempt.json → `zero_authority_rejected`).
- v4 `...130215-69f23ad9/`: root cause `critique_finding_unresolved`; fix descendant commit `9c41d0554`
  (`critique_custody.py` accepted_tradeoff branch lines 1259-1272); Sol stage1+2; recovery handoff
  `sha256:0e3c1467d6f0b1484168d1bca455171b28f8587754d4d763d6843c4e69599e06`
  (Horizon A `repair_control_plane_then_migrate`, external_gate null, agent_actionable true,
  return_condition "one accepted finalize result… cursor/milestone advanced beyond index 0");
  follow-up ticket `ticket-r7-superfixer-v4-20260806-1329`; blocked-receipt.json (checkpoint; noted
  `effects.launched: true` was erroneous — no launch occurred).
- Rebind executed @ 14:00:39Z (actor arnold-recovery, occurrence-v4-14834310-critique-custody-fix) to
  a99e74e6/234ac3524 (includes v4 fix + `5f8609549 fix(resident): honor completion-driven fixer execution`
  + `234ac3524 fix(resident): bind managed hermes to approved runtime`).
- v5 `...142036-1ea42c25/`: documented post-rebind dead-runner + dependency_unknown blocker; cancelled as obsolete.
- Sibling search: no other session/plan in this workspace exhibits failure_fingerprint `382e25a2...`
  (bounded search: finalize_candidates dirs under this plan only; r2..r6 repair-data in
  /workspace/.megaplan/cloud-sessions/repair-data/ are other chains, not this fingerprint).
- Schedule: r7 superfixer schedules exhausted/paused per v5 pack; this occurrence is the operator manual relaunch.

## 7. Explicit unknowns / negative evidence

- Unknown: whether `_apply_programmatic_coverage` / verification-task mutation adds tasks that also reference
  split ids in the real pipeline (repro used raw candidate; recorded failure shows only the 12 unknown pairs,
  consistent with coverage/verification tasks not referencing split ids).
- Negative: no live runner, no fresh lease, no live repair claim, no open WBC recovery effect, no notification
  intent/effect records for this session (bounded search of cloud-sessions + plan dir).
- Negative: no no-action-receipt.json exists for any prior occurrence; none written yet for this one.

## 8. Facts vs inference separation

Facts: everything in sections 1-7 marked as facts with paths/hashes.
Inference: root-cause attribution to task_splitter rewiring (supported by byte-identical repro); minimal-fix shape;
Horizon A route. These are for Sol to adjudicate.
