# P4 — The parity-gate illusion (pre-mortem, parity-gate adequacy lens)

**Frame:** 6 months out. The epic's load-bearing safety claim — "the m1 parity gate proves
handler-vs-pipeline drift is provably zero" (EPIC L71, L80; m1 L16, L134) — stayed GREEN the whole
epic, yet production planning regressed badly. The gate was an illusion. This document works backward
from that outcome and argues, hard, what mock-worker parity structurally CANNOT catch.

## What the gate actually is (ground truth from code)

- **Interception point.** The mock is injected at the *bottom* of the worker layer:
  `run_codex_step` (`_impl.py:1705`) and `run_shannon_step` (`:2187`) early-return
  `mock_worker_output(...)` when `MEGAPLAN_MOCK_WORKERS=1`. Routing/availability is *bypassed*
  (`:2390` skips the availability check for shannon under mock). So everything ABOVE the worker call
  (handler logic, gate math, state writes, emission) is real; everything that IS the worker (the
  model, the subprocess, the stream, timing, cost) is fake.
- **The mock is a pure deterministic function of `(step, state, plan_dir)`** — `_build_mock_payload`
  (`_mock_payloads.py:454`). Critically:
  - Gate verdict is hard-coded: `recommendation = "ITERATE" if state["iteration"] == 1 else "PROCEED"`
    (`:244`). The gate branch is a function of the *iteration counter*, not of plan content, critique
    flags, weighted scores, or any model judgment.
  - Critique flags iteration 1 with two fixed FLAG-001/FLAG-002, then clears them on iteration 2
    (`:140`). Revise always claims it addressed both (`:233`).
  - Execute always writes one file and marks T1/T2 done (`:335`); review always returns `approved`
    (`:395`). `cost_usd=0.0`, `duration_ms=1` (`make_gate_worker_result`, conftest `:298`).
- **The single live parity test** (`test_pipeline_parity.py:162`) drives ONE happy path
  (`_run_direct` :81 vs `_run_pipeline` :100) and SHA256-compares 10 *deliverable* artifacts
  (`_PARITY_ARTIFACTS` :41). It explicitly **excludes** `state.json`, `*.meta.json`, `step_receipt_*`,
  `phase_result.json`, `faults.json`, `execution_audit.json` from byte comparison (docstring L14–16).
  `extract_decision_fields` — the thing that would diff *decisions* — is **ABSENT** (s3 row 4; m1 W1).
  Branch coverage (reprompt/downgrade/tiebreaker) is **not built** (s3 row 3 = PARTIAL).

So today the "gate" is: one mock-driven happy path, two in-process drivers, 10 SHA256s. Even the m1
*planned* gate only adds decision-field diffing + three gate branches under the same deterministic
mock. **Both versions share the same blind spot: they compare two in-process executions of fake
workers and call the result "drift is zero."**

## Why the gate stays GREEN while reality DIVERGES — ranked

### 1. The subprocess→in-process boundary (m3) is the whole regression surface, and the gate runs ENTIRELY in-process on BOTH arms — so it can never see it. (Highest.)
m3 is "THE HINGE" (m3 title): it deletes the per-phase subprocess and moves auto's ~2,500-LOC driving
loop in-process. The brief itself says the subprocess gave **three things for free** that "must be
re-engineered" (m3 Constraints L140–145): (1) a hard, SIGKILL-able timeout/idle boundary, (2) total
state isolation between phases (fresh argparse/handler lifecycle), (3) crash containment — a phase
that OOMs/segfaults/leaks no longer takes the driver down. A wedged worker now wedges the whole
`megaplan auto` process (open question #1, "the single biggest design unknown").

The parity test's `_run_direct` and `_run_pipeline` are **both** in-process loops in the *same* test
process. There is no subprocess in either arm. Therefore:
  - The timeout/idle boundary that the subprocess used to enforce (`_run_megaplan` `timeout`/
    `idle_timeout`, auto.py:242–243) is **not exercised at all** — mocks return in 1ms.
  - Module-level / interpreter state leakage *between* phases (config caches, lru_cache, global
    singletons, monkeypatched module attrs) is a real in-process hazard the subprocess masked. The
    parity test can't surface it because it never compares against a subprocess baseline.
  - Crash containment: a real worker that segfaults kills in-process auto; the mock never crashes.
The gate's own done-criteria even *admit* this gap exists elsewhere: parity for m3 is delegated to a
**separate** oracle, `test_auto_drive.py` (m3 S1, done-criteria L155–158), which monkeypatches
`_run_megaplan`/`_status` with scripted sequences — i.e. the m1 mock-artifact gate was never the m3
oracle. If anyone treated "m1 gate green" as covering m3, that is the illusion in one sentence.

### 2. Real worker nondeterminism — the gate compares two runs of the SAME deterministic stub, so it tests reproducibility of a fake, not equivalence of two real paths. (Very high.)
SHA256-comparing artifacts only proves the two code paths feed identical *inputs* to an identical
*pure function*. It says nothing about whether, under a real model, the handler path and the pipeline
path would (a) build the same prompt, (b) parse the same response, (c) take the same branch. Real
models are nondeterministic; the gate has zero signal on whether divergent prompt assembly or
divergent response handling between the two paths would *amplify* under real output. The gate proves
"same fixture in → same bytes out," which is true of any two callers of a deterministic function and
is **not** the safety property claimed.

### 3. The gate branch is driven by a counter, not by judgment — so the entire decision surface the epic touches is untested. (High.)
Production "planning behavior" IS the gate/critique/finalize decision logic: when does gate say
ITERATE vs PROCEED vs TIEBREAKER, how are weighted scores computed, when does a flag downgrade,
complexity-tier adjudication (memory `project_complexity_adjudication.md`), tiebreaker→iterate silent
downgrade (memory `project_gate_tiebreaker_downgrade.md`). The mock gate is `iteration==1 ? ITERATE :
PROCEED`. It **never** drives a TIEBREAKER, never computes a real weighted score, never exercises
`find_override_edge`, never hits the downgrade path. m1 W6 merges the executor's override dispatch —
the canonical claim is "override-complete" — yet the only parity artifact that would reveal a dropped
override branch is `gate.json`, and under the mock the override edge is never taken. **A regression
that silently drops the override/tiebreaker branch in the merged executor leaves all 10 SHA256s
identical.** The planned branch coverage (reprompt/downgrade/tiebreaker via `make_worker_sequence`)
helps *only if* those sequences are hand-scripted to force each branch — and even then it tests the
handler's branch *selection* under fed verdicts, not the model's verdict *production*.

### 4. resolve_agent_mode / routing / profiles are bypassed entirely (m2 surface). (High.)
The mock skips availability (`:2390`) and is reached the same way regardless of which agent/model
routing resolved (the early-return at `:1705`/`:2187` happens after `agent`/`model` are resolved but
the *output* is identical for any agent). m2 changes profile pack-agnosticism and `resolve_agent_mode`;
the gate cannot tell whether a profile change routed a phase to the wrong agent, changed effort tier,
or broke per-vendor prompt selection — the mock output is agent-invariant. Memory
`project_adaptive_critique_codex_silent_break.md` is the canonical proof this class regresses silently:
the critique evaluator fell back to static on **every codex-chain milestone** via a KeyError, and a
mock-artifact gate would not have flinched because the mock doesn't route by vendor.

### 5. Timeouts / stalls / heartbeats / liveness — structurally invisible. (High, overlaps #1.)
`duration_ms=1`, no streaming, no idle. The heartbeat/liveness signal (auto.py:300–303, 398;
`_plan_liveness_mtime`) and the documented false-stall bugs (memory
`project_execute_stall_codex_silence.md`: streaming heartbeat never touched state.json → silent
false-stall; `project_shannon_stream_stall_refactor.md`: 900s idle cap false-killed big turns) are
exactly the regressions that recur in this codebase, and the gate exercises **none** of the timing
machinery. m3 open-question #3 ("heartbeat/liveness without a subprocess") is wholly unmodeled.

### 6. The auto.py recovery / retry / escalate matrix is untested by m1's gate. (High.)
m3 S1 enumerates ~16 `DriverOutcome` exit kinds (stalled/escalated/cost_cap_exceeded/
context_retry_exhausted/worker_blocked/tiebreaker_pending/...). The m1 parity test drives a clean
linear happy path — it never blocks, never retries, never escalates, never exhausts a cap, never hits
`_recover_execute_callback_failure_state`. Memory `project_chain_blocked_retry_and_resume.md`
(hardcoded max_blocked_retries killed milestones) is precisely a recovery-path regression a happy-path
artifact gate cannot see. The approval-gate footgun (memory `feedback_auto_gate_bypass.md`; m3 S6) —
auto injects `--user-approved`; in-process there's no argv to carry it — is a planning-behavior
regression (auto executes without the gate) that the m1 gate, which runs execute with
`user_approved=True` always, structurally cannot detect.

### 7. Cost / token accounting — zeroed. (Medium-high.)
`cost_usd=0.0` everywhere. Cost-cap escalation, the cost command, token-budget routing, and the
"don't shrink scope" cost discipline (memory `feedback_burn_money.md`) all read real numbers. The gate
proves nothing about cost accounting parity between paths, and a cost-cap regression (e.g. policy
hooks dropped in the executor merge — c1 Claim 2's dead `"abort"` return) is invisible.

### 8. Emission side-effects diverge by design and are EXCLUDED from comparison. (Medium-high.)
C3 establishes emission is duplicated across three `_emit_phase_result` sites + two receipt sites, and
that execute/review hand-roll outcome→exit_kind + receipt-with-drift while `_finish_step` does it
generically and *excludes* execute/review. The parity test **excludes** `phase_result.json`,
`step_receipt_*`, `faults.json`, `execution_audit.json` from byte comparison (docstring L14). So the
single richest divergence surface — the emission contract the epic consolidates — is the one the gate
deliberately does not compare. C3's named silent-breakage ((a) phase_result degrading to plain
success/error, (b) `set_active_step` dropped → emission no-ops with only a warning) would leave the 10
compared artifacts byte-identical. The mock even *deletes* its own `critique_output.json`/
`review_output.json` side effects (`_impl.py:1597`), further flattening the side-effect surface.

### 9. Prompt content is not compared. (Medium.)
The mock sets `rendered_prompt = create_hermes_prompt(...)` (`:1596`) but the parity test hashes
*output* artifacts, not prompts. Two paths could assemble *different* prompts and still produce
identical mock output (because the mock ignores the prompt except for the execute batch-id regex at
`:325`). Prompt drift (wrong template, missing context, dropped brief — memory
`project_init_brief_snapshot_gap.md`) is a top planning-quality regression and is uncompared. The
brief content gap (init stores brief as PATH; clean-worktree drops untracked briefs) would not move a
single SHA256.

### 10. Filesystem / git state, worktree carry-in. (Medium.)
Memories `project_worktree_carry_review_falsepositive.md` and
`project_worktree_carry_breaks_pr_isolation.md`: MAIN's dirty state forks into the worktree and review
flags inherited noise as scope violations. The parity test uses fresh `tmp_path` roots with an empty
`.git` dir (`test_pipeline_parity.py:172`) — no real git, no worktree, no carry-in. Real
git/worktree/FS interactions are entirely outside the gate.

## Is "drift is provably zero" a true promise?

**No.** The claim is false as stated, in two distinct ways:

1. **Scope false.** SHA256-comparing 10 deliverable artifacts from two *in-process* runs of a *pure
   deterministic stub* proves only: "given identical fixture inputs, the handler loop and the pipeline
   loop call the same pure function in the same order." That is a real but narrow property — it pins
   *control-flow ordering and artifact-write parity for the happy path under fixtures*. It is NOT
   "behavioral drift is zero." The behaviors the epic actually changes — subprocess→in-process
   isolation (m3), routing/profiles (m2), timeout/liveness, recovery/retry/escalate, cost, emission,
   prompts, git/FS — are each either bypassed, zeroed, excluded, or never branched. The gate is GREEN
   in a space orthogonal to where the epic's risk lives.

2. **Word "provably" is the dangerous part.** "Provably zero" invites treating green-gate as a
   *license to skip* the per-milestone behavioral oracles (m3's `test_auto_drive.py`, an m2 routing
   test, a cost test). The cross-cutting invariant (EPIC L156–158) says any behavior-changing
   milestone must "update the gate's golden expectations deliberately" — but a mock-artifact gate has
   almost no golden expectations to update for in-process isolation, timing, routing, cost, or
   emission, so the invariant creates *false comfort*: a milestone can change real behavior and the
   gate has nothing to update because it never measured that dimension. The gate going green is
   consistent with both "no drift" and "catastrophic drift the gate can't see" — so green carries near
   zero information about the failure modes that matter.

The honest framing: the m1 gate is a **control-flow / artifact-ordering regression detector for the
fixtured happy path**. That is worth having. It is **not** a proof of behavioral parity and must not
be marketed as the epic's safety story. The real safety story is the *per-milestone* oracle
(`test_auto_drive.py` for m3, etc.), and m1's gate is necessary-but-wildly-insufficient.

## Concrete additions the gate needs to be REAL

To make the safety claim defensible, the gate must stop being a single in-process happy-path
artifact-diff and grow these (ranked by how much illusion they remove):

1. **A subprocess-vs-in-process parity arm (closes #1).** Run the SAME scripted mock sequence through
   (a) the real subprocess engine (`auto drive` shelling `_run_megaplan`) and (b) the in-process
   executor, and assert identical `DriverOutcome` + identical state.json/phase_result.json. This is
   `test_auto_drive.py` (m3 S1) — but it must be **promoted into the m1 CI gate set and declared part
   of the safety claim**, not deferred to m3, because without it "drift is zero" is meaningless the
   moment m3 lands. Until it exists, the safety claim should read "for the in-process path only."
2. **Decision-field + branch coverage with FORCED branches (closes #3).** Implement
   `extract_decision_fields` (m1 W1) and use `make_worker_sequence` to script gate verdicts that force
   ITERATE, PROCEED, TIEBREAKER, override-edge, downgrade, and reprompt — diffing the *decision tuple*
   (recommendation, override edge, next_step/valid_next, last_gate, iteration) between paths, per
   branch. The deterministic counter-based mock gate must be replaced by *injected* verdicts so the
   branch is the test variable, not iteration count.
3. **An emission/side-effect parity arm (closes #8).** STOP excluding phase_result.json,
   step_receipt_*, faults.json from comparison; compare their *structural* fields (exit_kind, drift,
   blocked_tasks, invocation presence) between paths. Add a test that drops `set_active_step` and
   asserts the gate *fails* (proving it would catch C3's silent no-op).
4. **A recovery/retry/escalate/approval matrix (closes #6).** Script blocked tasks, context
   exhaustion, cost cap, escalate modes, and the auto approval-gate injection; assert outcome parity.
   Include the `feedback_auto_gate_bypass.md` case explicitly: bare in-process run without approval
   must raise `missing_approval`.
5. **A routing/profile parity check (closes #4).** Assert that under a given profile, each phase
   resolves to the expected agent/model/effort on BOTH paths, and that vendor-keyed prompt/evaluator
   selection (the `critique_evaluator` KeyError class) is identical — without bypassing
   `resolve_agent_mode` via the mock early-return.
6. **At least one non-mock smoke arm in CI (closes #2, #5, #7, #9).** A small, cheap *real-worker*
   (or recorded-cassette) run of a single trivial idea through both paths, comparing decision fields
   and cost-accounting *shape* — to catch prompt-assembly drift, timing/liveness, and cost-accounting
   divergence that no deterministic stub can model. Recorded-response cassettes are the cheap
   compromise: deterministic in CI, but exercising real prompt assembly + response parsing + cost
   fields rather than a hand-written payload.
7. **Re-label the claim.** Change EPIC L71/L80 and m1 L16/L134 from "drift is provably zero" to
   "control-flow/artifact parity on the fixtured happy path; behavioral parity is proven per-milestone
   by the named oracles (m3 test_auto_drive, m2 routing test, emission/recovery suites)." Words matter
   here — "provably zero" is the load-bearing overstatement.

**Bottom line:** the gate as built (and as m1 plans it) constrains a narrow, real, useful property and
nothing more. The epic's headline safety claim attributes to it a property it structurally cannot
have. If the team relies on "m1 gate green" as the epic's risk control, the regression in this
pre-mortem is not a tail risk — it is the expected outcome.
