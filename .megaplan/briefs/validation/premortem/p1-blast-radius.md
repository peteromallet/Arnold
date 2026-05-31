# Pre-mortem p1 — Indirect blast radius of the pipeline-unification epic

**Lens:** the NON-OBVIOUS breakages — subsystems the 6 milestone briefs did not name as
touchpoints. The four pillars (c1–c7) are assumed validated; this hunts what they didn't.
Grounded in the actual code, 2026-05-28.

---

## Verdict (ranked, top breakages)

### 1. The whole observability/liveness layer is built on per-phase subprocesses that m3 deletes. **SEVERITY: CRITICAL.**
- **What breaks:** `doctor`'s `_check_orphan_subprocesses` (doctor.py:367) and `introspect`'s
  `_process_tree` (introspect.py:388) scan `psutil` for `megaplan <plan>` child processes. In-process
  auto means **one** long-lived PID spanning all phases — these always return empty/"no orphans",
  silently blind. `_check_phase_timeout` (doctor.py:258) and `_compute_liveness`'s
  `timeout-imminent` (introspect.py:217) compute against `active_step.started_at` + a per-phase
  3600s cap; in-process one process holds `active_step` across the whole run, so "phase running
  Ns > 80% of timeout" fires spuriously or never. The liveness state machine (`progressing/quiet/
  stalled/timeout-imminent`) loses its physical basis.
- **Why:** m3 anti-scope ("no broader cloud SSH hardening", "in-process") never lists doctor/
  introspect as consumers of the subprocess model. The brief treats the subprocess boundary as
  purely an isolation/timeout mechanism; it is also the **observability substrate**.
- **Milestone:** m3. **Fix:** m3 must redefine liveness/timeout against in-process stage cursors
  + event recency (not PIDs/`active_step.started_at`), and rewrite both psutil scanners or mark them
  legacy. Add to m3's `test_auto_drive.py` parity oracle.

### 2. `megaplan resume` and the MegaLoop engine are a 2nd + 3rd subprocess driver the epic ignores. **SEVERITY: HIGH.**
- **What breaks:** `_core/workflow.py::resume_plan` spawns `python -m megaplan <phase>` via
  `_default_resume_runner` (workflow.py:314) and maps phases with a hardcoded planning-phase dict
  `_RESUME_ACTIVE_STATES` (workflow.py:330: prep/plan/critique/gate/revise/finalize/execute/review/
  feedback). Separately, `megaplan/loop/engine.py` ("MegaLoop") is a **completely independent**
  `subprocess.Popen` phase driver (engine.py:249) with its own LoopState and hardcoded plan/execute
  phases. The epic only ever names auto.py as "the production engine."
- **Why:** validation found auto.py; it did not enumerate the other two subprocess drivers. m3
  unifies one engine and leaves two parallel ones intact — and m4's pack-ification breaks
  `_RESUME_ACTIVE_STATES`'s planning-phase keys and MegaLoop's `phase="plan"/"execute"` literals.
- **Milestone:** m3 (drivers diverge) + m4 (phase-name keys). **Fix:** explicitly scope resume +
  MegaLoop in m3; replace hardcoded phase maps with pack-declared slots in m4.

### 3. `cloud run-next` imports `auto.py::_phase_command`; m3 deletes it → remote break, no static check. **SEVERITY: HIGH.**
- **What breaks:** `cloud/cli.py:225` does `from megaplan.auto import _phase_command`, then SSH-execs
  `megaplan <argv>` remotely. `_phase_command` (auto.py:486) is a subprocess-command builder
  (`execute`→`--confirm-destructive --user-approved`, `feedback`→`feedback workflow`, multi-token
  `override force-proceed` split). Porting auto.py in-process is exactly when a private helper like
  `_phase_command` gets inlined/removed — the cloud import then ImportErrors at runtime on the
  operator's machine.
- **Why:** m3 anti-scope says it re-points the SSH coupling onto the **pinned status contract** —
  but the *status reader* is not the only auto.py→cloud coupling; this *command builder* import is a
  second, un-pinned one. m1 pins the status JSON, not `_phase_command`.
- **Milestone:** m3 (and m1 for the missed pin). **Fix:** promote `_phase_command` to a stable
  public mapping pinned in m1's contract, or move the next_step→argv translation cloud-side.

### 4. Three parallel next-step encodings — m4 collapses one and leaves two that feed status/override/cloud. **SEVERITY: HIGH.**
- **What breaks:** next-step is computed THREE ways: (a) `workflow_next`/`infer_next_steps`
  (workflow.py:282-302, robustness-transition graph), (b) `inprocess_step._label_for`/`_gate_next_step`
  (the one m4 retires), (c) Pipeline graph edges. `infer_next_steps` is consumed by `override` (9
  action handlers), `handle_status` (status_view.py:748, the field cloud reads), `require_state`,
  `doctor._check_outstanding_flags` (recoverable_via), and `introspect._compute_block_details`. m4
  collapses (b)→(c) and declares "Pipeline graph edges the single source of truth" — but
  `infer_next_steps` (a) keeps producing the labels everyone else reads. If (a) and (c) diverge
  (e.g. relocated-planning slot names vs phase names), `status.next_step` and the cloud `_phase_command`
  mapping silently desync.
- **Why:** m4 names only the inprocess encoding; it does not reconcile `workflow_next` as a third
  source feeding the entire override/status/doctor/introspect surface.
- **Milestone:** m4. **Fix:** m4 must reconcile `workflow_next` against the graph edges, or pin
  `workflow_next` as the canonical label source and route the graph through it.

### 5. `next_step_runtime` + cost-by-phase + `feedback workflow` are planning-phase-keyed; pack-ification orphans them. **SEVERITY: MEDIUM.**
- **What breaks:** (i) `build_next_step_runtime`/`_emit_phase_notice` key on `PHASE_RUNTIME_POLICY`
  (shared.py) — a relocated/renamed pack slot yields `next_step_runtime=None` in the status JSON
  cloud reads, degrading remote timeout hints. (ii) `cost.py` aggregates `ev.get("phase")`
  (cost.py:98, `--by-phase`); in-process emission must keep tagging events with stable phase labels
  or cost-by-phase silently empties. (iii) `feedback workflow` hard-asserts
  `current_state==STATE_REVIEWED`→`STATE_DONE` (feedback.py:406) — a non-planning pack with no
  "reviewed" state can never run the feedback transition.
- **Why:** these are downstream of m4 (slot relocation) + m3 (emission home) but listed in neither's
  touchpoints. The epic's "creative/doc packs prove genericity" is a false proof — those packs never
  exercise feedback/cost-by-phase/next_step_runtime.
- **Milestone:** m4 + m3. **Fix:** make phase-keyed maps slot-parameterized; assert emission tags
  phase in-process; gate feedback on pack-declared terminal slots.

### 6. `schema_version` rollout: old state.json silently mis-read by ~10 unversioned consumers. **SEVERITY: MEDIUM.**
- **What breaks:** m1 adds `schema_version` + a load-time validator, but the existing direct readers
  — `doctor`/`introspect` do `json.loads(state.json)` raw (doctor.py:262, introspect.py:201),
  `cost._load_state`, `status_view`, `override`, `feedback` all `load_plan`/raw-read without going
  through the validator. If the validator lives only in one load path, raw readers bypass it; if it
  raises on absent version, every pre-epic plan on disk (and cloud workspaces) breaks until migrated.
- **Milestone:** m1. **Fix:** route ALL state reads through one validated loader; ship the migration
  shim as read-time auto-upgrade, never a hard reject.

### 7. `state["config"]` is read in 30+ files far outside handlers; m5's HandlerContext can't reach them. **SEVERITY: MEDIUM.**
- **What breaks:** m5 measured 81 config fields "read in handlers" and migrates `handle_*` to
  `(root, state, hctx)`. But `state["config"]` is read directly in `receipts/`, `forms/`,
  `_core/modes.py`, `_core/workflow.py`, `workers/shannon.py`, `execute/batch.py`, and **every
  creative/doc pipeline prompt module** — 63 sites, mostly non-handler. These keep reaching into
  `state["config"]` raw while handlers move to `hctx`, so the "typed config surface" is authoritative
  in only half the codebase; the two drift.
- **Milestone:** m5. **Fix:** scope m5 honestly to "handler-layer reads only," document the
  raw-`state["config"]` readers as deliberately out of scope, and keep `state["config"]` as the
  single serialized source `hctx` is built from (not a parallel truth).

---

## Surface area the epic FAILED to capture (named explicitly)

1. **Observability as a consumer of the execution model** — doctor + introspect liveness/timeout/
   orphan-process checks are physically coupled to per-phase subprocesses (PIDs, `active_step`,
   per-phase 3600s cap). m3 treats the subprocess boundary as isolation only.
2. **The other two subprocess drivers** — `resume_plan` (workflow.py) and the entire MegaLoop engine
   (`megaplan/loop/`). The epic assumes auto.py is the only driver.
3. **The 2nd cloud↔auto.py coupling** — `cloud/cli.py`'s `_phase_command` import, distinct from the
   pinned status reader; m1 pins the wrong/only-one surface.
4. **`workflow_next` as a third next-step source** — feeds override (9 actions), status JSON,
   doctor, introspect; m4 only retires the inprocess encoding.
5. **Planning-phase-keyed downstream maps** — `PHASE_RUNTIME_POLICY` (next_step_runtime),
   cost-by-phase event `phase` tags, `_RESUME_ACTIVE_STATES`, `feedback workflow`'s
   REVIEWED→DONE assertion. The creative/doc packs never exercise these, so genericity is unproven.
6. **Raw `state["config"]` readers outside handlers** (63 sites) — m5's typed surface covers only
   the handler half.
