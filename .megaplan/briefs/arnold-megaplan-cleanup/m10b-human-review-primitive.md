# M10b: human_review pipeline primitive (ask the human → resume with the answer)

## Outcome

A neutral, first-class **`human_review`** pipeline step: based on prior steps'
outputs it **poses a question and suspends the run** (via m10a's generic awaiting
mechanism), and on the human's answer **resumes**, feeding that answer to
downstream stages. It is the human-facing consumer of m10a's suspendable executor,
plus the operator surface (a neutral `arnold human answer` CLI, status surfacing,
and a headless policy). It is opt-in per pipeline — never auto-inserted.

## Context (why / what exists)

- **m10a did the hard part.** After m10a, any step can return
  `StepResult(kind="awaiting")`, the executor checkpoints `(suspended_stage,
  working_state)` into the resume cursor and returns `PipelineOutcome("awaiting")`,
  and `StepwiseDriver.resume()` re-enters at the suspended stage. m10b is a
  *consumer* of that: a `human_review` step that poses a question on suspend and
  reads the answer on resume.
- **Proven prior art for the whole UX loop.** `megaplan/_pipeline` already ships
  the human-facing version end-to-end: `steps/human_gate.py` writes
  `awaiting_user.json` and returns `halt`; `resume.py:104 check_awaiting_user`;
  `run_cli.py:89` `--resume-choice` reloads the pause file + prior state;
  `builder.py:230 .human_gate(...)` is the authoring API. m10b ports this human
  loop onto the neutral Arnold runtime (built on m10a), generalized from a
  fixed-choice gate to a free-form question/answer.
- **`human_review` is a `Step.kind` string, not an OperationKind.** `Step.kind` is
  a plain `str` at the neutral boundary (`arnold/pipeline/types.py`) — no enum
  narrowing. `OperationKind` (`arnold/runtime/operations.py:40`) is a *plugin-
  dispatch* enum (run_phase, status_projection, …); `human_review` is not a
  dispatched operation. (Verified.) No new `OperationKind`, no new Protocol.

## Scope

In:
- **`human_review` step.** A `Step` with `kind="human_review"` whose `run()` reads
  prior outputs from `ctx`, formulates a question, writes it into the awaiting
  checkpoint, and returns `StepResult(kind="awaiting")`. On resume it reads the
  human answer from working state and emits it as an output for downstream stages.
- **Answer channel — keyed by stage, in working state + cursor.** The question and
  answer live in the working `state` dict (persisted via `state_patch` / the m10a
  resume cursor), **keyed by stage name**
  (`state["human_reviews"][stage] = {question, answer, answered_at, answered_by}`)
  so multiple `human_review` stages in one run don't collide. The question is also
  surfaced on `PipelineOutcome.payload` for the CLI/status to read without loading
  working state. NOT on the frozen `RuntimeEnvelope`.
- **Project the awaiting state up to Megaplan so existing infra sees it.** When a
  `human_review` suspends inside a milestone phase, set the plan's
  `current_state = STATE_AWAITING_HUMAN` (`awaiting_human_verify`) and write the
  question into `state["clarification"]`. This is the single move that makes the
  **auto-driver stop cleanly**, the **cloud supervisor** (`cloud/supervise.py:308`,
  which only knows `awaiting_human_verify`) recognize it instead of re-triggering,
  and **`megaplan status` / `chain status`** surface the question — all via the
  existing plan-level seam. (Reuse the boundary; don't reinvent per-surface.)
- **Neutral resume CLI.** `arnold human answer --run <id> --response "…"` (new
  `arnold/cli/human.py`), modeled on `verify-human`/`resume-clarify`: atomically
  writes the answer into the checkpoint AND sets a `resume_requested` flag (so a
  crash between write and resume is recoverable/idempotent), then triggers
  `StepwiseDriver.resume`. Plus `arnold human answer --list` / a
  `--pending-human` scan so an operator can find which suspended runs await input.
- **Headless policy (locked, see below).** A `--headless-policy {block|fail|skip|
  default:<value>}` flag wired through `auto.py` and the arnold run CLI; default
  `fail`-fast so CI/cloud never block forever silently.
- **Observability.** Emit a `PIPELINE_AWAITING_HUMAN` event
  (`observability/events.py`) on suspend and on resume so monitoring distinguishes
  awaiting from a stall.
- **Chain composition.** A `human_review` inside a milestone must let the **chain**
  stop and later **re-enter the suspended milestone** with the answer — not destroy
  the milestone's plan name and re-init from scratch. Touch `chain/__init__.py`
  (the `awaiting_human` → stop mapping at ~`:886`/`:1322`) and
  `supervisor/chain_runner.py` so resume re-enters the paused milestone.
- **Authoring (m8a) API.** `p.human_review(question=…, reads=[…], …)` constructor;
  `arnold pipeline check` flags a `human_review` whose answer no downstream stage
  `reads` (no dangling human answer). (m10b is the first extension of m8a's API —
  documented as such; reserve the name in m8a if cheap.)
- **m8b scaffold.** Make the listed "human pause/resume" example use the real
  primitive.

Out / anti-scope:
- Do NOT rework Megaplan's plan-level `awaiting_human_verify`/`verify-human` — reuse
  the pattern and project onto it; keep that path intact.
- No GUI/web UI; CLI + status surfacing only. No webhook/push-notification infra.
- No bakeoff composition: a `human_review` inside a bakeoff profile is explicitly
  out of scope (bakeoff runs parallel profiles as subprocesses; per-profile suspend
  is a separate problem). `pipeline check` may warn if a human_review pipeline is
  handed to bakeoff.
- Do NOT make `human_review` mandatory or auto-inserted; opt-in per pipeline.
- No Megaplan vocabulary (`GateRecommendation`, `OverrideAction`, phase names) in
  the neutral step/carrier/CLI.

## Locked Decisions

- `human_review` is a `Step` with `kind="human_review"` built on m10a's
  `StepResult(kind="awaiting")`. No new `OperationKind`, no new Protocol.
- Question/answer live in working state + resume cursor, **keyed by stage name**;
  question mirrored on `PipelineOutcome.payload`. Not on the frozen envelope.
- The awaiting state is **projected to Megaplan `state.json`**
  (`current_state=awaiting_human_verify` + `clarification`) so existing
  auto-driver / cloud-supervisor / status / stall paths recognize it unchanged.
- Resume is an explicit human action via the neutral CLI (atomic answer +
  `resume_requested`), not auto-timeout.
- **Headless contract (resolves the former open question):** default
  `--headless-policy fail` (no human ⇒ fail fast with the question in the error);
  `block`, `skip`, `default:<value>` are opt-in. This is a *locked decision*, not
  an open question — it has a defined, testable behavior.

## Constraints

- Suspend/resume round-trips through JSON; the downstream stage sees the answer.
- An awaiting run is NOT a stalled run (inherits m10a's liveness marker; the
  Megaplan projection keeps the auto-driver/cloud from killing or re-triggering it).
- Multiple `human_review` stages in one run never collide (keyed by stage).
- Stale-answer safety: an answer written after the run already resumed (timeout /
  another answerer) must not silently corrupt state — at minimum guard with the
  `resume_requested` flag; a generation/nonce check is a nice-to-have, not required
  for v1.
- Cross-version-safe with the existing plan-level `awaiting_human` (don't break it).

## Done Criteria

- A pipeline `agent → human_review → agent` **suspends** at `human_review`, the run
  reports `awaiting_human` (not failed/stalled), the question is visible via
  `arnold human answer --list` and `megaplan status`, `arnold human answer …`
  supplies a response, the run **resumes**, and the downstream stage **sees the
  answer**.
- **Crash-recovery:** a run suspended at `human_review`, after a simulated process
  restart, resumes via `arnold human answer --run <id>` and the answer reaches the
  downstream stage.
- **Chain composition:** a `human_review` inside a milestone stops the chain
  cleanly and resume re-enters the *same* milestone (plan name preserved) with the
  answer, not a from-scratch re-init.
- Headless policy honored: `--headless-policy fail` (default) fails fast with the
  question; `block`/`skip`/`default:<v>` behave as specified — each tested.
- `arnold pipeline check` flags a `human_review` whose answer no downstream stage
  reads; `arnold run --dry-run` shows the suspend point.
- Boundary tests confirm no Megaplan vocabulary leaks into the neutral carriers/CLI.

## Touchpoints

- new `arnold/pipeline/steps/human_review` step; `arnold/cli/human.py` (+ status,
  `--list`/`--pending-human`)
- `megaplan/auto.py` (project pipeline awaiting → `awaiting_human`; `--headless-policy`)
- `megaplan/cloud/supervise.py` (recognize the projected state — verify, likely no
  change needed once projected), `observability/events.py`
  (`PIPELINE_AWAITING_HUMAN`)
- `megaplan/chain/__init__.py` + `megaplan/supervisor/chain_runner.py` (stop →
  re-enter the suspended milestone with the answer)
- m8a authoring API (`p.human_review`), m8b scaffold example
- Reference (port the human loop from): `megaplan/_pipeline/steps/human_gate.py`,
  `builder.py:230`, `run_cli.py:89`, `resume.py:104`

## Dependencies

- **m10a (suspendable executor)** — hard dependency; m10b is its human consumer.
- m3c (dataflow: `ctx.inputs`/`ctx.state` from upstream outputs — how the answer
  reaches downstream), m8a (authoring API). m9 transitively via m10a.
- Sequenced last in the epic, immediately after m10a.
