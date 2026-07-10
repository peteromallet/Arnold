# M4 — Collapse Eval Modules + Unify Diagnostics

## Outcome
One eval-node code path (the half-done migration is finished or reverted, decisively),
and one diagnostics system with a shared diagnostic data model. No dead modules, no
two-systems-for-the-same-job.

## Problem (audit lenses 5 & 6)
**Eval triplication — a half-executed migration:**
- `vibecomfy/runtime/eval.py` (437 LOC) is the **live** path: the CLI
  (`commands/runtime.py:53 _cmd_runtime_eval_node`) uses `eval.compile_eval_subgraph`
  plus its own inline `_queue_embedded`/`_queue_server` helpers.
- `vibecomfy/runtime/eval_plan.py` (187 LOC, newer, richer) and
  `vibecomfy/runtime/eval_prompt.py` (145 LOC, wraps eval_plan) have **zero production
  callers** (verified) — only tests touch them.
- Two competing output-type detectors: `eval._detect_output_type` vs
  `eval_plan._classify_outputs` → `preview_plan_for_type`.

**Queue/wait logic triplicated:** the `queue_prompt → _wait_for_server_history →
_outputs_from_server_history` sequence appears in `run.py:84-92`,
`session.py:505-530` (`ServerSession._run_untracked`), and `eval_prompt.py:55-58`.

**Diagnostics duplication:** `vibecomfy/environment_diagnostics.py`
(`metadata_environment_warnings() -> list[str]`) vs the richer
`vibecomfy/diagnostics/` package (`SubcheckFinding`/`SubcheckResult`/`HealthReport`,
with `run_doctor_readiness` duplicating some doctor checks in a different data model).
Three diagnostic dataclasses with no shared base: `EmissionDiagnostic`
(`porting/emitter.py:52`), `PortIssue` (`porting/report.py:19`), `LintDiagnostic`
(`porting/lint.py:17`).

## Scope
1. **Decide eval direction and execute it:** EITHER promote the `eval_plan`/`eval_prompt`
   design to be the live path (wire the CLI to it, delete `eval.py`'s superseded parts),
   OR delete `eval_plan.py`+`eval_prompt.py` and keep `eval.py`. Pick based on which
   design is better; justify in the plan. End state: **one** eval path, one output-type
   classifier, no dead module.
2. **Extract the shared queue/wait/outputs sequence** into one helper used by `run.py`,
   `ServerSession._run_untracked`, and the eval path. Eliminate the ~80%-identical
   `run.run()` / `ServerSession._run_untracked` duplication.
3. **Unify diagnostics:** one diagnostics system. Fold
   `environment_diagnostics.metadata_environment_warnings` into the `diagnostics/`
   package's structured model (or vice versa), with one output schema. Reconcile
   `run_doctor_readiness` so doctor checks aren't defined twice.
4. **Shared diagnostic dataclass base/protocol** for `EmissionDiagnostic`, `PortIssue`,
   `LintDiagnostic` (they all carry `code`/`message`/`severity`/`node_id`/`class_type`/
   `detail`). Remove the manual `EmissionDiagnostic → PortIssue` remapping in
   `convert.py:241`.

## Locked decisions
- Build on M2 shared utils.
- Behavior-preserving for the CLI surfaces (`runtime eval-node`, `doctor`). The eval
  *output shape* may change only if you promote the richer design — if so, pin it with
  tests and note it for M6's release notes.

## Done criteria
- Exactly one eval module/path; no `NotImplementedError` dead branches; no
  zero-caller eval module remains.
- One queue/wait/outputs helper; `run.py` and `ServerSession` delegate to it.
- One diagnostics system; one diagnostic dataclass base.
- Full `pytest` green; `runtime eval-node` and `doctor` CLI smoke pass.

## Touchpoints
`vibecomfy/runtime/{eval,eval_plan,eval_prompt,run,session,client,server}.py`,
`vibecomfy/commands/runtime.py`, `vibecomfy/environment_diagnostics.py`,
`vibecomfy/diagnostics/`, `vibecomfy/porting/{emitter,report,lint,convert}.py`.

## Anti-scope
Do not split `emitter.py`/`session.py` here (M5) beyond the targeted dedup above. Do
not touch validation (M3, already done). Do not edit docs (M6).
