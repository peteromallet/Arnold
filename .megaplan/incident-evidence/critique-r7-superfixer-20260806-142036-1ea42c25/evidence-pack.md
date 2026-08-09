# R7 Superfixer v5 — Evidence Pack

Incident: critique-ledger-accountability-v3-r7 — deterministic finalize blocker
Occurrence: `occ_critique_r7_superfixer_now_20260806_v5_63a701ce7ce09258e1c322f2`
Run: `subagent-20260806-142036-1ea42c25` (model `hermes:deepseek:deepseek-v4-flash`)
Evidence dir: `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-142036-1ea42c25/`
Pack written (UTC): 2026-08-06T14:31Z

---

## 1. Identity

| Field | Value |
|---|---|
| session | `critique-ledger-accountability-v3-r7-launch-20260805` |
| workspace | `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold` |
| chain spec | `.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml` (chain_spec_sha256 `da4b317822a3d2e9c4c5944dd832edbff0f4c01c413a8d32a6b2b5098d21f0d1`) |
| session marker | `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.json` |
| plan | `cl2-wbc-backed-ledger-20260805-2140` (iteration 5) |
| milestone | `cl2-ledger-replay` (index 0) — `in_progress`, completed: none |
| chain state path | `.megaplan/plans/.chains/chain-880bd6e04632.json` |
| run_id (session marker) | `9f46fff6-7f30-4978-99c8-f039368b8f66` |
| target_base_ref | `d5848010695e28ddb9d9cbee8675d7ebe725caae` |
| project checkout | branch `megaplan/critique-ledger-accountability-v3-r7-20260805/cl2-ledger-replay` @ `d5848010…` (tracked clean; status_sha256 `a52bfd1c…`) |
| bound engine (runtime) | `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805` @ `234ac3524da29c1f630aee90ab1767a142a68a83` (branch `fix/r7-fresh-child-launch-20260805`, status_sha256 `e3b0c442…` = clean) |
| runtime content identity | `a99e74e6c6f6a14c556b42deb9ab92e8f15538c52bf7e34e286c34d4a1df21de` |
| execution binding | `match` (expected `c628b6b07d92` == active) |
| runtime binding | `match` (expected `a99e74e6…` == active) |
| wrapper | `env -u PYTHONHOME PYTHONSAFEPATH=1 PYTHONPATH=$R7_ENGINE_DIR MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan` |

Authoritative before fingerprint: `sha256:4acc22ebfd48fbf6273f0d236807f755f84183e16a58b339aeff1b65d8b3a709`
(manifest: `fingerprint-before.json`; covers chain state, plan state, receipts, leases, repair queues, candidates, session marker, git heads/tracked-status of project + engine, untracked state excluding this occurrence's own evidence/run dirs).

## 2. Canonical state (facts)

- `run_mp chain status`: milestone 0 `cl2-ledger-replay` `in_progress`; remaining 3 milestones; `last_state: blocked`; no completed milestones; `dirty_flag: false`; `pr_number: null`.
- Plan `state.json`: `current_state: blocked`, `iteration: 5`, `last_gate.recommendation: PROCEED` (58 flags resolved; weighted score 20.5 → 10.0).
- History (last two entries):
  - `finalize` @ 2026-08-06T14:13:57Z result `planner_repair_required` then `error`: **"Finalize rejected a candidate task graph before publication (dependency_unknown ×12, dependency_graph_invalid). The last admitted graph and accepted task authority remain unchanged; repair only the candidate graph."**
  - `finalize` @ 2026-08-06T14:16:28Z result `planner_repair_blocked` then `error`: identical message. `raw_output_file: finalize_v5_raw.txt`.
- `planner_repair.json` (14:16:28Z): `candidate_id: candidate:36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07`, `failure_fingerprint: 382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df`, `occurrences: 2`, `circuit_open: true`, `prior_admitted_finalize_sha256: null`, `implementation_dispatch_allowed: false`.
- `meta.overrides` (state.json): operator `recover-blocked` override @ 2026-08-06T14:03:37Z, `from_state: blocked`, `to_state: gated`, `resume_cursor: {phase: finalize, retry_strategy: repair_phase_contract}`, `phase_contract_repair: {failure_kind: deterministic_phase_failure, phase: finalize, repair_commit: 234ac3524da29c1f630aee90ab1767a142a68a83, failure_fingerprint: 4a772446d29148efccc408bc04eaf07ce5fca741a7e2b1288df78218e4a8bc32, repair_scope: engine_runtime, repair_root: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805, authority: explicit_repair_commit_bound_to_engine_runtime}`.
- `boundary_receipts/override_recover_blocked_authority.json` @ 14:03:37Z: Run Authority grant `recover-blocked:cl2-wbc-backed-ledger-20260805-2140:9d5418d618d54e9b:grant` **satisfied**; coordinator fence 1253577917 **satisfied**; custody lease `lease:recover-blocked:cl2-wbc-backed-ledger-20260805-2140` epoch=1 **satisfied** (owner `override-wbc`, owner_pid `0` — synthetic, not a live process); WBC attempt `override:recover-blocked:…:9d5418d618d54e9b` **satisfied**; `action_boundary: {gate_result: authorized, action_type: repair}`; actor `operator` role `human.override`.
- Chain runtime rebind (`chain-state.json` metadata): @ 2026-08-06T14:00:39Z actor `arnold-recovery`, reason `occurrence-v4-14834310-critique-custody-fix`, direction `cutover`, `from_runtime_sha256 e8b12504…` → `to_runtime_sha256 a99e74e6…` (the currently bound engine). Engine lineage includes v4 fix commit `9c41d0554 fix(critique): admit verified tradeoffs across gate iterations` (verified present: `critique_custody.py` `accepted_tradeoff && gate_expected && fixed_claim → verified_plan_mutation` branch at lines 1259–1272).
- Phase result (`phase_result.json` @ 14:16): `exit_kind: success` (harness step record), `artifacts_written: [planner_repair.json, finalize_revise_feedback.json]` — i.e. the phase harness completed while the finalize candidate was rejected. `cli_provenance.phase_model.finalize = codex:gpt-5.6-sol:high`.

## 3. Process custody / liveness (facts)

- Session marker PID `629623` — **not alive** (ps: no such process).
- Finalize worker PID `1249041` (heartbeat `runner_incarnation.worker_pid`; model `gpt-5.6-sol`; run_id `5be081a3-8197-451f-8b7f-a039404636da`; session `019fd765-148e-7481-a3d2-c67880db7f11`; started 14:14:06Z) — **not alive**.
- Last heartbeat: `active-step-heartbeat.snapshot.json` `last_heartbeat.occurred_at: 2026-08-06T14:16:28Z`; `last_activity_detail` = item.completed for local-strict artifact `finalize-15274aaf….candidate.json` (sha256 `cfc7d701c18c070ba15679d5279cc943119ec9d4fa412b8ef4d02115a75c76c8`, 77557 bytes). No heartbeat since.
- No watchdog/supervisor/relauncher process for this session (ps scan: none).
- Chain log `cloud-chain-critique-ledger-accountability-v3-r7-launch-20260805.log` last write 2026-08-06T00:53 (the 14:13–14:16 finalize writes went to plan state/heartbeat, not the launch log).
- Live processes observed: resident Discord listener (PIDs 1, 7 — orchestrator, not chain runner) and this occurrence's own managed subagent worker (PID 1271702/1271703).
- Session marker `updated_at` / `liveness_claimed_at`: 2026-08-05T21:40 (stale).
- Scheduled r7 superfixer schedules: all `exhausted`/`paused`; this occurrence fired `sched_critique_r7_superfixer_now_20260806_v5` (one-shot) at 14:19:31Z.

**Verdict (liveness gate): the canonical run is NOT progressing with a live authoritative runner and NOT merely slow. It is a dead runner behind a deterministic blocker. Recovery is required.**

## 4. Contract graph / failure payload (facts)

- Deterministic failure digest (canonical): `planner_repair.json` → candidate `36bcefaf…`, fingerprint `382e25a2…`.
- Candidate graph (raw model output): 19 tasks T0–T18, all `depends_on` refs resolve within the candidate; `sense_checks` 19 (SC0–SC18); `user_actions: []`; `validation_jobs: []` (harness-owned).
- Handler path: `handlers/finalize.py::_write_finalize_artifacts` mutates the raw candidate (in order): `_ensure_verification_task` → `_ensure_user_actions_pre_gate_task` (no-op: no before_execute user_actions) → `_ensure_user_actions_post_gate_task` (no-op) → `_apply_programmatic_coverage` → `_normalize_task_complexity` → `_split_finalize_tasks` (split_high_complexity_tasks) → `compile_validation_jobs` → `compile_task_feasibility` (twice: pre-baseline and final persistence boundary).
- **Reproduction (read-only, in-memory; `raw/repro_finalize_mutations.py` → `raw/repro-output.txt`):** replaying the exact mutation order against the persisted candidate produces **byte-for-byte the same diagnostic set: 12× `dependency_unknown` + `dependency_graph_invalid`**:
  - `T2_impl→T1`, `T3_impl→T2`, `T4_impl→T1`, `T5_impl→T4`, `T6→T1`, `T8→T7`, `T9→T1`, `T10→T3`, `T11→T1`, `T13→T5`, `T15→T3`, `T15→T5` (dependency_unknown), then `dependency_graph_invalid: Unknown dependency ID 'T1' for task 'T2_impl'`.
- **Root cause (engine defect, in approved editable runtime):** `orchestration/task_splitter.py::split_task` replaces every complexity ≥ `_SPLIT_THRESHOLD` (7) task with `{task_id}_impl` + `{task_id}_proof` (ids at lines 294–295) and `split_high_complexity_tasks` swaps the parent out of the task list (lines 486–507), but **no step rewrites the `depends_on`/`dependency_reasons` of other tasks that referenced the removed parent id**. Dangling refs to removed parents (T1, T2, T3, T4, T5, T7) are then rejected by `orchestration/task_feasibility.py` lines 303–307 (`dependency_unknown`) and line 331 (`dependency_graph_invalid` via `compute_task_batches` ValueError). Split parents in this candidate: T1–T5, T7 (25 tasks after split, 19 before).
- Secondary splitter diagnostics (non-blocking): `split_mutating_validation` for T10, T13, T16 (test-kind tasks declaring write paths).
- `_apply_programmatic_coverage` in repro raised `KeyError: -1` with the minimal fake state; in the real run it reads `latest_plan_path(plan_dir, state)` — harmless to the dependency failure (repro reproduced the exact canonical diagnostics even with coverage skipped).

## 5. Recovery / observer records (facts)

- v4 occurrence (`occ_critique_r7_superfixer_retry_20260806_v4_14834310cdddb1f2b0eed77e`, run `subagent-20260806-130215-69f23ad9`, status `failed` @ 13:41:09Z) repaired the earlier `critique_finding_unresolved` blocker (fix `9c41d0554`, present in bound engine lineage), created follow-up ticket `ticket-r7-superfixer-v4-20260806-1329` (`follow-up-ticket-v4.json`, handoff `sha256:0e3c1467d6f0b1484168d1bca455171b28f8587754d4d763d6843c4e69599e06`), and left an on-disk `blocked-receipt.json` that its own result.md flags as schema-invalid (`effects.launched: true` with no launch; the actor must regenerate with `launched: false`).
- After v4: recover-blocked override (14:03:37Z) + runtime rebind cutover (14:00:39Z) + two finalize attempts (14:13, 14:16) that failed on the **new** deterministic blocker (dependency_unknown graph) → `planner_repair` circuit open.
- Notification intent/effect: none observed for this occurrence (silent).

## 6. Sibling fingerprint search (bounded negative)

- Search scope: `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/` sibling plans for `dependency_unknown` / `dependency_graph_invalid` / `planner_repair`:
  - No sibling plan under this workspace contains a `planner_repair.json` with this fingerprint (checked plan dir listing: only `cl2-wbc-backed-ledger-20260805-2140` and `resident-subagents` + `.chains`).
- Same failure text in engine code/tests: `dependency_unknown` only emitted by `task_feasibility.py`; `split_high_complexity_tasks` is used by finalize and m8a reporting. No other live chain is bound to this engine (cloud sessions registry shows only this r7 session for this chain family; r6 sessions historical).

## 7. Facts vs inference

**Facts:** dead runner; blocked chain; exact finalize rejection payload; planner_repair circuit open; reproduced diagnostic set byte-identical to canonical failure; splitter rewiring gap in `task_splitter.py`; engine lineage contains v4 fix; binding match; fingerprint before `sha256:c87809d8…`.

**Inference (marked):** the missing rewiring is the proximate cause (high confidence — deterministic reproduction); the "correct" dependent-target mapping (impl vs proof) is a design judgement for Sol; whether `_apply_programmatic_coverage`'s `KeyError: -1` in the repro indicates a second latent defect is **unknown** (it did not affect the reproduced diagnostics; may be an artifact of the minimal fake state).

**Unknowns/negatives:** no authoritative child-custody lease with a live owner exists for any recovery (owner_pid `0` synthetic); no fresh heartbeat; no watchdog; no notification custody record for this occurrence.

## 8. Decision each evidence item informs

- Fingerprint + identity → pre/post Sol guard and Horizon A applicability check.
- Failure payload + repro → the exact minimal source change candidate (rewire dependents after split, or map removed parent ids → impl/proof) and the focused regression (finalize mutation pipeline → feasibility admitted).
- Liveness/custody evidence → recovery required; no in-flight recovery to wait on.
