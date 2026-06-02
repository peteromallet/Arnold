# M10a: suspendable pipeline executor (generic awaiting → checkpoint → resume)

## Outcome

`run_pipeline` (`arnold/pipeline/executor.py`) gains a **generic suspend/resume
capability**: when any step signals "awaiting", the executor checkpoints the run
(suspended stage + working state + resume cursor), **returns a structured
outcome** instead of terminating, and a later resume re-enters the graph **at the
suspended stage** with the awaited input available. This completes the runtime
contract m2a already declared (`AdvanceOutcome(kind="awaiting")`) but left unwired.
It is the substrate the m10b `human_review` primitive (and any future
external-signal step) builds on — suspension is a generic executor capability,
not a human-review-specific feature.

## Context (why / what exists)

- **m2a declared the seam but nothing honors it.** `AdvanceOutcome(kind="awaiting")`
  exists in the `StepwiseDriver` protocol (`arnold/runtime/driver.py:53-61`) and
  `StepwiseDriver.resume()` is defined (`driver.py:135-140`) — but the graph
  executor (`arnold/pipeline/executor.py`, ~`run_pipeline` at line 29) is a
  synchronous `while` loop that only terminates on `"halt"`, returns a bare
  `RuntimeEnvelope`, and discards its local `state`/`current_name`. So every
  milestone from m2b on ships an executor that *cannot express the awaiting
  contract it advertises*. (Verified: the executor has no driver integration and
  no `awaiting` return path.)
- **Proven prior art exists — port it, don't invent it.** The pre-Arnold
  `megaplan/_pipeline` already implements this exact loop with **exit-and-restart
  semantics**: `executor.py:483` returns
  `{"halt_reason": "awaiting_user", "final_stage": …, "state": …, "envelope": …}`;
  `resume.py:104 check_awaiting_user(plan_dir)` detects a pause file;
  `run_cli.py:260-297` reloads `awaiting_user.json` + prior state and re-enters at
  the recorded stage on `--resume-choice`; `steps/human_gate.py` writes the pause
  file and returns `halt`. m10a lifts this proven mechanism into the neutral
  Arnold executor/runtime, generalized beyond the human case.
- **Subprocess reality forces exit-and-restart, not in-process yield.** Pipeline
  stages run inside forked worker subprocesses (`megaplan/workers/_impl.py`). You
  cannot "park" a live subprocess and keep a parent waiting indefinitely — the
  process must **exit cleanly, persist the checkpoint, and be re-spawned** on
  resume. The design is exit-and-restart, exactly as the prior art does.

## Scope

In:
- **Suspend signal on `StepResult`.** Add an optional `kind: str` field to
  `StepResult` (`arnold/pipeline/types.py`, default `"advanced"`) so a step can
  return `kind="awaiting"` *without importing driver types*. (Steps return
  `StepResult`; the driver speaks `AdvanceOutcome` — this is the bridge. Do NOT
  overload the `next` label string.)
- **Structured executor outcome.** `run_pipeline` returns a `PipelineOutcome`
  dataclass `{kind: str, envelope, suspended_stage: str | None, cursor: dict}`
  instead of a bare `RuntimeEnvelope` (keep a thin compat accessor for the
  envelope so existing callers don't all churn at once).
- **Checkpoint on suspend.** When a step returns `kind="awaiting"`, the executor:
  (1) serializes `suspended_stage` + a deep copy of working `state` into
  `resume_cursor.cursor` (`arnold/runtime/resume.py` — the cursor's opaque dict is
  the right home); (2) returns `PipelineOutcome(kind="awaiting", …)`. The working
  state/cursor must round-trip through JSON losslessly.
- **Resume re-entry.** Add `resume_at: str | None` and a restored-`state` path to
  `run_pipeline` so resume re-enters the graph **at the suspended stage** with the
  prior working state, rather than restarting at `pipeline.entry`. Wire
  `StepwiseDriver.resume()` to: load envelope + cursor, then call
  `run_pipeline(…, resume_at=cursor["stage"], state=cursor["state"])`. (Clarify in
  the brief that the driver does state restoration; the executor is the graph
  re-entrant — m2a conflated these.)
- **Liveness on suspend.** On suspend, the executor touches a liveness marker the
  watchdog recognizes (co-designed with m9) so an awaiting run is a *non-stalled*
  state, and **releases the plan lock** (`_core/state.py` `plan_lock`) before
  returning — otherwise the resume CLI can't acquire it.

Out / anti-scope:
- No `human_review` step, no human-answer semantics, no CLI — that's m10b. m10a
  ships the generic mechanism + a trivial test step that returns `kind="awaiting"`.
- Do NOT add `OperationKind.HUMAN_REVIEW` or any new `OperationKind` member —
  awaiting is an executor/`StepResult` concern, not a dispatched operation.
- Do NOT add fields to the frozen `RuntimeEnvelope` for working data — the
  checkpoint lives in `resume_cursor.cursor`.
- Don't touch Megaplan's plan-level `awaiting_human_verify` path.

## Locked Decisions

- Suspend is signaled by `StepResult.kind == "awaiting"`; the executor maps it to
  `AdvanceOutcome(kind="awaiting")` at the driver boundary. **Exit-and-restart**
  semantics (process exits, checkpoint persists, re-spawn on resume) — not
  in-process yield.
- The checkpoint (suspended stage + working state) lives in
  `RuntimeEnvelope.resume_cursor.cursor` (JSON), **not** as new fields on the
  frozen envelope and **not** in ad-hoc files.
- `run_pipeline` returns a structured `PipelineOutcome`, not a bare envelope.

## Constraints

- Suspend/resume round-trips through JSON with no loss; resuming a serialized run
  restarts at the suspended stage with prior working state intact.
- An awaiting run must NOT false-trigger the idle/stall watchdog (co-design the
  liveness marker with m9's liveness channel — awaiting is explicitly non-stalled).
- Plan lock released on suspend, re-acquired on resume.
- No Megaplan vocabulary in the neutral carriers (`PipelineOutcome`, cursor keys).

## Done Criteria

- A pipeline `step → awaiting-step → step` **suspends** at the awaiting step:
  `run_pipeline` returns `PipelineOutcome(kind="awaiting", suspended_stage=…)`, the
  envelope+cursor serialize to JSON, the process can exit.
- Re-invoking `run_pipeline(…, resume_at=…, state=<restored>)` (via
  `StepwiseDriver.resume`) **re-enters at the suspended stage** and runs to
  completion — including after a simulated process restart (load envelope from
  disk → resume), proving crash-recovery.
- The awaiting state does not trip the stall watchdog in a test that advances the
  clock past the idle threshold.
- Boundary tests confirm no Megaplan vocabulary leaks into `PipelineOutcome`/cursor.

## Touchpoints

- `arnold/pipeline/executor.py` (suspendable `run_pipeline`, `PipelineOutcome`),
  `arnold/pipeline/types.py` (`StepResult.kind`)
- `arnold/runtime/driver.py` (`StepwiseDriver.resume` re-entry wiring),
  `arnold/runtime/resume.py` (cursor carries stage + state)
- `megaplan/_core/state.py` (plan-lock release/re-acquire across suspend)
- Reference (port from, do not modify): `megaplan/_pipeline/executor.py:483`,
  `resume.py:104`, `run_cli.py:260`, `steps/human_gate.py`

## Dependencies

- m2a (run envelope / `StepwiseDriver` `awaiting` seam / resume cursor).
- m9 (liveness/persistence decoupling) — **hard dependency**: the awaiting-is-not-
  stalled liveness marker must use m9's liveness channel. Sequenced after m9.
