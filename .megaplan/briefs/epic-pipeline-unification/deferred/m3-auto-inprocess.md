# m3 — Execution-model convergence: `auto.py` in-process · THE HINGE

**Epic:** pipeline-unification (`.megaplan/briefs/pipeline-unification-EPIC.md`, m3 section L95–108).
**Tier:** apex · **Robustness:** extreme/max. **Status:** brief, grounded 2026-05-28 (HEAD `c493f629`).
**Depends on:** m1 (override-complete merged executor + `MEGAPLAN_UNIFIED_DISPATCH`/`dispatch_path`
toggle + pinned `megaplan status` JSON contract). **Blocks:** m4 (pack-ify), m5 (HandlerContext).

This is the riskiest milestone in the epic. Today there are **two** production engines: `megaplan auto`
runs its own ~2,500-LOC subprocess-driving loop in `megaplan/auto.py` (`drive`, auto.py:1065) that
**never touches** `_pipeline/executor.py`; `megaplan run` runs the bare `run_pipeline`
(executor.py:212). m3 collapses the auto engine onto the executor — in-process — without changing
observable behavior. The validation (c1, c4, u1) reframed this from "pick a pipeline function" to
"port the real engine across a process boundary," which is why this milestone is scoped alone.

---

## Outcome

`megaplan auto` drives a plan to completion by walking the **m1-unified executor in-process**, not by
shelling out a fresh subprocess per phase via `_run_megaplan` (auto.py:238). Auto's cross-cutting
recovery/retry/escalate/timeout logic becomes in-process `RuntimePolicy` hooks
(`megaplan/_pipeline/runtime.py`) that the executor consults between stages. The currently-**dead**
`ContextRetry`/`BlockedRetry` (runtime.py:104–142, confirmed unreferenced — c1 Claim 3) and the
unwritten per-stage `ResumeCursor` persistence (resume.py:35–87, confirmed never called by the
executor — c1 Claim 4) become live. Resume collapses to **one** model. The approval-gate semantics are
preserved byte-for-byte. The dispatch toggle from m1 makes the whole cutover reversible.

---

## Scope (work items tied to current file:line)

**S1 — `tests/test_auto_drive.py` FIRST (the parity oracle).** `auto.py` has **zero** direct
behavioral tests of the `drive()` exit-kind matrix today (u1 L50: `test_auto.py` grew but tests
features, not the drive exit matrix). Before any port, characterize the *current* subprocess engine as
the golden oracle. Every exit path of `drive` (the `DriverOutcome.status` values enumerated by the
exit-code map at auto.py:2450–2467: `done/aborted/cancelled/paused/stalled/escalated/cap/blocked/
cost_cap_exceeded/context_retry_exhausted/worker_blocked/failed/awaiting_human/human_required/
tiebreaker_pending/tiebreaker_ready`) gets a test by monkeypatching `_run_megaplan` (auto.py:238) /
`_status` (auto.py:466) with scripted sequences. Cover, at minimum:
- **recovery**: orphaned `active_step` clear (auto.py:1440–1455), execute-callback-failure recovery
  (`_recover_execute_callback_failure_state`, auto.py:818 → loop `continue` at 1302–1304).
- **retry**: context-exhaustion `--fresh` loop (auto.py:1779–1822) incl. cap → `context_retry_exhausted`;
  external-error fresh retry (auto.py:1829–1894); blocked-task retries (auto.py:2059–2213) incl. cap →
  `worker_blocked` and `blocked_by_prereq` → `awaiting_human`.
- **escalate → force-proceed**: the `not next_step` + `override force-proceed` branch
  (auto.py:1583–1651), all three `on_escalate` modes (auto.py:1652–1693), and the `add-note`-failures
  → force-proceed escape valve (auto.py:1720–1744).
- **timeouts**: per-phase `phase_timeout`/`phase_idle_timeout` → synthesized `ExitKind.timeout`
  (auto.py:1164–1175, 1897), stall detection (auto.py:1505–1562), rework-cycle cap
  (auto.py:1477–1502), iteration cap (auto.py:2231–2249).
This suite is the acceptance gate for S2–S4: the in-process port must produce **identical**
`DriverOutcome`s for identical scripted inputs.

**S2 — Port the loop onto the executor as in-process `RuntimePolicy` hooks.** Replace `_run_phase`
(auto.py:1129) subprocess dispatch with in-process executor stage dispatch on the m1-unified
`run_pipeline` (executor.py:212, override-complete after the m1 merge). Wire the executor's
between-stage hook to consult `policy.stall`/`policy.cost`/`policy.escalate` (the pattern already
sketched in `run_pipeline_with_policy`, executor.py:367–399) **and** the now-live
`policy.context_retry`/`policy.blocked_retry`. The dead `should_retry` methods (runtime.py:115, 136)
need a uniform `phase_result`-shaped signal from each stage — today auto reads `PhaseResult.exit_kind`
off `phase_result.json` written by the subprocess (auto.py:1156, `read_phase_result`); in-process the
stage result must surface the same `exit_kind`/`blocked_tasks`/`external_error`/`deviations` shape the
loop branches on (auto.py:2060–2213). **Do not unify on `run_pipeline_with_policy` as-is** — c1 Claim 1
confirms it drops override-edge dispatch and c1 Claim 2 confirms its `"abort"` resolution is a dead
branch; m1 is responsible for merging it into the override-complete path. m3 consumes the merged result.

**S3 — Wire per-stage `ResumeCursor` persistence + self-loop disambiguation.** After each stage,
`ResumeCursor(stage=node.name, payload=...).save(plan_dir)` (resume.py:74) so a mid-pipeline crash
resumes at the right stage — the docstring's intended pattern (resume.py:16–17) that the executor never
actually does (c1 Claim 4). Carry the legacy `retry_strategy`/`batch_index` payload that auto's
`_record_lifecycle_failure` writes today (e.g. auto.py:1527, 1797, 2126) so the existing resume
contract is preserved. The cursor payload is the state needed to break gate self-loops first-match
edge dispatch cannot (c1 Claim 5).

**S4 — Reconcile resume into ONE model.** There are currently three overlapping notions:
(a) executor `_pipeline_paused` → `halt_reason="awaiting_user"` (executor.py:262–264);
(b) auto's `state.json::current_state`/`next_step`/`resume_cursor` (read via `_status`, written via
`_record_lifecycle_failure`, auto.py:741); (c) the m1-era `STATE_AWAITING_HUMAN` prep-clarification
gate + `awaiting_user.json` + the 9th override action `resume-clarify` (`_override_resume_clarify`,
override.py:848; `check_awaiting_user`, resume.py:104; u1 L84–87). Define one resume entry that:
checks `awaiting_user.json` first (human-gate), else loads `ResumeCursor` and re-enters via
`with_entry` (resume.py:90), else starts at `pipeline.entry`. The `STATE_AWAITING_HUMAN` terminal
handling in `drive` (auto.py:1307–1335, which distinguishes prep-clarification from
criteria-verification) must be preserved as a terminal `awaiting_human` outcome, not folded away.

**S5 — Re-point the cloud-supervisor coupling onto the m1 status contract.** `cloud/supervise.py:54`
SSHes `python3 -c "from megaplan.chain import _capture_sync_state, ChainState, save_chain_state,
load_chain_state; ..."` — a refactor of `chain.py` is a remote-breaking change with no static check
(EPIC #9). m3 moves auto in-process, which is adjacent to chain's `current_state` writes; re-point this
SSH coupling onto the m1-pinned `megaplan status` JSON contract instead of internal imports, so the
in-process port can't silently break the cloud supervisor. (Scope-limited to the coupling m3's changes
touch — broader cloud SSH hardening is out of scope.)

**S6 — Preserve the approval-gate semantics EXACTLY (footgun guard).** Today `_phase_command`
(auto.py:497–510) injects `--user-approved` into every execute dispatch, and `handle_execute`
(execute.py:108–116) reads `auto_approve = state["config"]["auto_approve"]`, sets
`state["meta"]["user_approved_gate"] = True` when `args.user_approved` is truthy (execute.py:109–111),
and raises `missing_approval` otherwise. This is the known auto-gate-bypass behavior
(memory `feedback_auto_gate_bypass.md`). In-process there is no subprocess argv to carry
`--user-approved`; the port MUST set the same `user_approved_gate` signal through whatever in-process
context the executor passes to `handle_execute`, with **identical** truth conditions. S1 must include an
explicit parity test: auto-driven execute injects approval; a non-auto in-process run with neither
`auto_approve` nor `--user-approved` still raises `missing_approval`.

---

## Locked decisions

- **Direction is in-process** (EPIC "validation #2"; c4 §Unknown-unknown). The per-phase subprocess
  boundary is being removed as the isolation/timeout boundary.
- **Config is still reconstituted from `state["config"]` — just in-process.** No typed config object,
  no `HandlerContext`. That is m5. (EPIC m3 anti-scope L107–108.)
- **`test_auto_drive.py` is written and green against the *current subprocess* engine FIRST**, then
  re-run unchanged against the in-process port. Parity is defined as identical `DriverOutcome`s.
- **The dispatch toggle is the cutover mechanism.** `MEGAPLAN_UNIFIED_DISPATCH`/`dispatch_path` (m1
  handoff) selects subprocess-auto vs in-process-auto. Default stays OFF until parity is proven.

## Open questions (real for this milestone — surface, don't bury)

1. **Where does the per-phase timeout/isolation boundary go once the subprocess is gone?** The
   subprocess WAS the timeout boundary (`_run_megaplan` `timeout`/`idle_timeout`, auto.py:242–243; c4
   Unknown-unknown). In-process there is no SIGKILL-able child for a wedged Codex/Shannon stream. Options:
   (a) per-stage thread + cooperative cancellation, (b) keep execute (only) as a subprocess while moving
   the orchestration in-process, (c) a watchdog thread that aborts the executor. This is the single
   biggest design unknown — see Constraints/Risk.
2. **Does the in-process stage result expose the full `PhaseResult` shape** (`exit_kind`,
   `blocked_tasks`, `external_error`, `deviations`) the loop branches on, or do we keep reading
   `phase_result.json` from disk even in-process? Reading the file in-process is lower-risk for parity
   but keeps a serialization seam; returning it in-band is cleaner but touches every handler's return.
3. **Heartbeat/liveness without a subprocess.** `_plan_liveness_mtime` + idle-timeout heartbeat
   (auto.py:300–303, 398) detect a silent child via output/mtime. In-process, what is the liveness
   signal? (Cross-ref memory `project_execute_stall_codex_silence.md`: streaming heartbeat once never
   touched state.json and false-stalled.)
4. **Concurrency / `plan_locked`.** The subprocess model tolerated two auto drivers racing via the
   `plan_locked` transient (auto.py:1991). In-process, does the executor hold the plan lock across the
   whole drive, or per stage? This changes the contention semantics.

## Constraints

- **Subprocess → in-process is the load-bearing risk (call it out explicitly).** The fresh subprocess
  per phase gave three things for free: (1) a hard, kill-able timeout/idle boundary; (2) total state
  isolation between phases (fresh argparse/handler lifecycle, auto.py:249–251); (3) crash containment —
  a phase that segfaults/OOMs/leaks doesn't take the driver down. In-process, all three must be
  re-engineered. A wedged worker now wedges the whole `megaplan auto` process. This is why m3 is
  extreme/max and why the toggle exists.
- **Approval-gate semantics are a footgun** (memory `feedback_auto_gate_bypass.md`): the in-process
  port must reproduce `--user-approved` injection + `user_approved_gate` exactly (S6). A silent change
  here lets auto execute without the gate, or blocks a legitimate `megaplan run`.
- **`save_state_merge_meta` is at 37 call sites** (u1 L35); in-process auto must not introduce a 38th
  competing writer — all writes still go through atomic `write_plan_state`/`save_state_merge_meta`.
- **The parity gate from m1 must stay green** throughout (EPIC cross-cutting invariant L156–158).

## Done criteria (testable)

- [ ] `tests/test_auto_drive.py` exists, covers every `DriverOutcome.status` exit path (S1 list), and
      is **green against the current subprocess engine** before any port lands.
- [ ] With `dispatch_path=in_process`, the **same** `test_auto_drive.py` passes unchanged — identical
      `DriverOutcome` per scripted input (the parity oracle).
- [ ] `ContextRetry.should_retry`/`BlockedRetry.should_retry` (runtime.py:115,136) have live callers in
      the executor path (grep proves they are no longer dead — closes c1 Claim 3).
- [ ] `ResumeCursor.save` is called per stage by the executor; a crash-injection test resumes at the
      correct stage (closes c1 Claim 4).
- [ ] One resume entry point handles all three resume notions (S4); explicit test for each:
      prep-clarification (`resume-clarify`), criteria-verification (`verify-human`), mid-pipeline cursor.
- [ ] Approval-gate parity test (S6) passes: auto injects approval; bare in-process run without
      approval still raises `missing_approval`.
- [ ] `cloud/supervise.py` no longer SSHes `from megaplan.chain import ...` for the path m3 touches; a
      contract test pins it to the m1 `megaplan status` JSON schema.
- [ ] m1 parity gate (`tests/test_pipeline_parity.py`) still green.

## Touchpoints

- `megaplan/auto.py` — `drive` (1065), `_run_phase` (1129), `_run_megaplan` (238), `_phase_command`
  (486), `_status` (466), `_record_lifecycle_failure` (741), `run_auto` (2410), `DriverOutcome` (132).
- `megaplan/_pipeline/executor.py` — `run_pipeline` (212, m1-merged), `run_pipeline_with_policy` (308,
  to be subsumed/merged by m1).
- `megaplan/_pipeline/runtime.py` — `RuntimePolicy` (146), `ContextRetry`/`BlockedRetry` (104–142),
  `policy_from_cli_args` (164), `pipeline_runtime_enabled` (191, the toggle precedent).
- `megaplan/_pipeline/resume.py` — `ResumeCursor` (35), `with_entry` (90), `check_awaiting_user` (104).
- `megaplan/handlers/execute.py` — approval gate (108–116).
- `megaplan/handlers/override.py` — `_override_resume_clarify` (848).
- `megaplan/cloud/supervise.py` — SSH chain-import coupling (54).
- `tests/test_auto_drive.py` (new), `tests/test_auto.py`, `tests/test_auto_pipeline_runtime.py`.

## Anti-scope

- **No config-OBJECT change.** Config is still rebuilt from `state["config"]` each phase, now
  in-process. No `HandlerContext`, no `args_to_hctx`, no typed config surface — that is m5.
- **No Realizer / EvidenceRealizer** and no `is_prose_mode` consolidation — m6.
- **No pack relocation.** Planning stays at `_BUILTIN_NAMES` (registry.py:53); not pack-ified — m4.
- **No split-brain routing collapse** (`InProcessHandlerStep._label_for`/`_gate_next_step`) — m4.
- **No new override actions / no change to the 9 existing** (override.py); m3 only reconciles resume.
- **No broad cloud SSH hardening** beyond re-pointing the coupling m3's in-process change touches (S5).

## Risk & rollback

- **Rollback = the m1 dispatch toggle.** If in-process auto regresses, flip
  `MEGAPLAN_UNIFIED_DISPATCH`/`dispatch_path` back to subprocess-auto; the legacy `drive` subprocess
  loop stays intact and shippable until parity is proven for the full exit-kind matrix. Default OFF.
- **Land in two commits behind the toggle:** (1) `test_auto_drive.py` green on the subprocess engine;
  (2) in-process port selectable only via the toggle. Do not delete the subprocess path in m3 — its
  removal is a follow-on once the in-process path has soaked.
- **Highest-likelihood regression:** a wedged worker hangs the whole `auto` process because the
  kill-able subprocess boundary is gone (Constraints #1 / Open Q1/Q3). Mitigation must ship with the
  port — an in-process timeout/watchdog with parity to `phase_timeout`/`phase_idle_timeout`.
- **Silent approval-gate change** (S6) is the second footgun; the explicit parity test is the guard.
