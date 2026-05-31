# Pre-launch verification — M0/M1 executability dry-check

**Vantage:** Can M0 (pinned-engine rig + dual-run + oracle skeleton + report-only schema) and
M1 (foundation + contract-checker + R1 shadow-WAL seed) actually be EXECUTED as briefed against
v0.23.0 by a `megaplan chain` run, after a single t0 "go"?

**Triple:** `.megaplan/briefs/epic-pipeline-unification/{chain.yaml, m0-keepalive-floor.md, m1-foundation.md}`,
`.megaplan/briefs/validation/sequencing/PROGRAM.md`, `.megaplan/briefs/validation/human-blockers/REGISTER.md`.

**Verdict: NOT first-PR ready. M0 cannot be a chain milestone as briefed — it is a bootstrap
paradox (the chain would have to be running the pinned engine in order to build the pinned
engine). M1's touchpoints are real and largely executable, but M1 inherits M0's broken
autonomy ladder and a self-host that doesn't exist yet.**

---

## F1 (BLOCKS LAUNCH) — M0 is a bootstrap paradox: the pinned-engine rig cannot be built BY the chain it is supposed to pin

The chain launches every phase and sub-command via the *current* interpreter:
- `megaplan/chain/__init__.py:761` `subprocess.run([sys.executable, "-m", "megaplan", "status", ...])`
- `megaplan/chain/__init__.py:835` `args = [sys.executable, "-m", "megaplan", "init", ...]`
- `megaplan/auto.py:266,287` phase seam `[sys.executable, "-m", "megaplan", *args]`

There is **no `--engine` / venv / interpreter-selection flag anywhere** in the chain harness, auto.py,
or the parser (`grep` for `engine_python|--engine|MEGAPLAN_ENGINE|interpreter` returns nothing in
`megaplan/chain/`, `auto.py`, `cli/parser.py`). The engine that drives the chain is simply *whichever
`python` invoked `megaplan chain`* — it is a property of the **invocation environment, fixed before
the chain starts.** The chain cannot install a frozen venv and re-exec itself into it.

M0's W1 done-criterion (m0 §141) requires "a phase subprocess launched by the harness asserts
`megaplan.__file__` resolves under the **pinned venv**, not the editable target tree." But if M0 is
chain milestone #1 (`chain.yaml:21`), M0 is driven by the *unpinned* `sys.executable` — i.e. the
editable target tree it is mutating. The deliverable (pinned engine) is exactly the precondition for
running the milestone that builds it. PROGRAM.md states this plainly: M0 is "**A harness milestone
(M0) [that] precedes even R1**" and "the true floor is M0" (`PROGRAM.md:43-56`) — but a *floor* that
the chain stands on must be erected **before** the chain, not as the chain's first step.

**Evidence the brief half-knows this:** m0 Open-Q "Pin by git-sha or PyPI tag? → git-sha of current
`main` HEAD **at t0**, installed into a venv" (m0 §108-110). That install is a t0 act, not an M1-driven
PR. And W1's text says it "wires `--no-git-refresh` ON for the epic and adds the missing *verification*"
— verification is a milestone-shaped deliverable, but the *installation + re-launch under the pinned
venv* is not.

**Fix:** Split M0. The actual pinning (build frozen venv from `main`@t0-sha; launch `megaplan chain`
from that interpreter with `--no-git-refresh`) is a **manual / scripted t0 PRE-STEP**, not a chain
milestone. What *can* be a chain milestone (call it M0') is the buildable, in-repo subset: the
report-only schema validator (W2), the dual-run/oracle/replay harnesses + corpus (W3-W5), and the
strangler-gate entrypoint (W6) — all of which are ordinary code+tests a milestone can produce. The
launcher script (W1) ships as a `tools/`-level artifact but is *executed by the operator at t0*, and
its "is the engine pinned?" probe runs as a CI test, not as proof the running chain is pinned. The
EPIC/PROGRAM/REGISTER and chain.yaml must be updated so the t0 "go" includes "operator runs
`tools/launch_pinned_engine.sh`," and chain.yaml's first milestone is M0' (harness-code only).

---

## F2 (BLOCKS LAUNCH) — the autonomy ladder M0/M1 depend on is silently dropped by the harness (the confirmed exemplar, now load-bearing on M0/M1)

`chain.yaml:101-118` configures `on_failure: {retry: retry_milestone, escalate: bump_profile,
abort: stop_chain}` and `on_escalate: {escalate: bump_robustness, abort: stop_chain}`. The parser
reads **only** `block.get("abort", default)`:

- `megaplan/chain/__init__.py:339` `value = block.get("abort", default)` inside `_action(...)`
- `:347-348` `on_failure = _action("on_failure", "stop_chain")` / `on_escalate = _action(..., "stop_chain")`
- `:89` `VALID_FAILURE_ACTIONS = ("stop_chain", "skip_milestone", "retry_milestone")` — `bump_profile`
  and `bump_robustness` are **not valid actions** (grep: zero implementation anywhere).
- consumer `:1227-1234`: a failed/stalled/cap milestone → `policy = spec.on_failure` → `stop_chain`
  → returns `"stop"` → **chain halts and waits for a human.**

So the `retry:`/`escalate:` ladder keys are **silently ignored**; both `on_failure` and `on_escalate`
collapse to `stop_chain`. REGISTER.md §3 lines 91-92 ("→ **ladder**: retry×2 → bump_profile → abort")
and lines 57-58 of the runtime-gate table describe machinery that **does not exist in v0.23.0.** This
directly defeats the "zero human blockers after one t0 go" guarantee — and it is *most* dangerous on
M0/M1: M0's done-criteria §8 and §162, and m0 Open-Q "What happens on a red strangler gate? → the
REGISTER ladder" (m0 §122), all assume the ladder fires. The very first red gate during M0 or M1
parks on a person, contradicting m0 §164 / m1 §10 ("machine-gate, no human wait").

**Fix:** Either (a) implement `retry_milestone`-with-count + `bump_profile`/`bump_robustness` as real
`VALID_FAILURE_ACTIONS` and have `_action` parse the `retry:`/`escalate:` sub-keys (a real code
change — but note this is *itself* harness work the epic is supposed to deliver, see F3), or (b)
honestly downgrade REGISTER/EPIC to state that until the ladder exists, a red gate = `stop_chain` =
human halt, and accept M0/M1 are NOT zero-human. As briefed, the docs assert a capability the engine
lacks. (Pre-confirmed; restated because it is load-bearing for M0/M1, not just downstream.)

---

## F3 (MUST-FIX-IN-M0/M1) — bootstrapping circularity: M0/M1 assume autonomy/gate machinery that later milestones are supposed to BUILD

The autonomy the chain needs *to run M0 and M1 unattended* is the autonomy M3-M5d are scheduled to
build. REGISTER's own table sources its "replacements" from future milestones: the RecoveryPolicy
spine is **M4** (REGISTER:64), the run-OUTCOME vocabulary that the escalate ladder branches on is
**M5c** (REGISTER:74-75), the auto-merge-on-green supervisor is **M5d/M5c** (REGISTER:73). Yet
chain.yaml sets `merge_policy: auto` and the no-human ladder **from milestone 0**. The pinned frozen
engine is `main`@t0 — which by construction does **not** contain M3/M4/M5c/M5d, because
`--no-git-refresh` is ON for the whole epic (m0 §126) and the engine is re-launched "deliberately,
never stomped" (m0 §128). So the engine driving M0-M5 is frozen at a commit that lacks the ladder,
RecoveryPolicy, and run-outcome machinery those milestones produce — the autonomy can never reach the
driver during the epic. **M0/M1 run on exactly today's autonomy semantics: `stop_chain` on any
red/escalate.**

**Fix:** Accept and document that the *driving* engine's autonomy is frozen at t0 == today's
behavior (F2's reality), and that the epic's machine-gates are advisory-until-merged-and-relaunched.
If true unattended drive is required for M0/M1, the t0 pinned engine must be cut from a branch that
*already* contains a minimal retry/bump ladder — i.e. a small "M-minus-1" autonomy patch must land on
`main` and be included in the t0 pin BEFORE the chain starts. This is a real prerequisite the triple
does not name.

---

## F4 (FIX-BEFORE-ITS-MILESTONE) — M1 touchpoint line numbers have drifted; symbols exist but the brief's `file:line` citations are stale

M1 cites symbols that are real but at shifted lines (v0.23.0):
- `load_plan_from_dir` briefed at `state.py:93` → actually `:127`; `save_state` briefed `:210` →
  actually `:245`; `_apply_legacy_state_migration` briefed `:293` → actually `:328`; atomic replace
  briefed `:346,436` → `transaction`/replace path at `:381,471`.
- `Plan` is at `schemas/sprint1.py:215` (correct); `StorageModel.model_config = ConfigDict(extra=
  "forbid", ...)` is at `schemas/base.py:37` (correct).
- `executor.py` `run_pipeline:212`, `find_override_edge` import `:273,278`, `run_pipeline_with_policy
  :308` — all correct.
- `registry.py` `_BUILTIN_NAMES:53`, `discover_python_pipelines:360`, `build_pipeline` getattr `:399`
  — correct; silent-skip path confirmed.
- `events.py` `EventKind:31`, `STATE_TRANSITION:42`, `EventWriter:126`, `emit:154` under
  `flock`+`fsync` (`:201,213,219`), `read_events:298` — all confirmed real (W9's shadow-WAL substrate
  exists). No `fold_events`/`assert_fold_equiv` yet (correctly new work).
- `cli/parser.py` has no `pipelines` command *group* — only the `list pipelines` choice at `:331`
  (W7 correctly adds a new group; brief's "sibling of `list pipelines`" is accurate).

None of these block M1 — the symbols are all present and W1-W11 are buildable code+test work — but
the stale line numbers will mislead the executing agent and should be re-pinned (W8's chain↔EPIC↔
briefs lint does NOT check brief `file:line` accuracy, so nothing catches this automatically).

**Fix:** Re-verify and update M1's `file:line` citations against v0.23.0 before the milestone runs,
or instruct the executor to grep-by-symbol rather than trust line numbers.

---

## F5 (MUST-FIX-IN-M0/M1) — M0/M1 each carry an "ORACLE GATE" done-criterion the harness has no way to enforce as a chain gate

m0 §154-162 ("THE MILESTONE ORACLE GATE", W6 strangler gate "consumable by the chain's per-milestone
gate ... red auto-halts/auto-reverts or enters the bounded escalation ladder") and m1 §192-197 ("THE
M1 ORACLE GATE ... A divergence auto-fails CI (machine-gate, no human wait)") both assume the chain
can run a custom per-milestone gate that, on red, *auto-reverts or climbs the ladder*. The chain's
per-milestone gating is the auto.drive gate (`auto.py:1829-1933`) whose only escalate outcomes are
`force-proceed` / `abort` / `fail→human_required` — plus the `on_failure`/`on_escalate` collapse from
F2. There is no hook by which a `tools/`-level "strangler gate green/red verdict" feeds the chain's
advance/halt decision; the closest is CI (a PR check), which gates *merge*, not the chain's
per-milestone progression. So "the chain auto-runs OLD-alive AND NEW-alive AND replay-MATCH at every
milestone boundary" (m0 §83) has no implementation surface.

**Fix:** Decide the enforcement venue. Realistic path: the oracle/strangler gate runs as a **CI
required check** on each milestone PR (gating auto-merge under `merge_policy: auto`), NOT as an
in-chain per-step gate — and the .megaplan/briefs/REGISTER should say so. If in-chain enforcement is truly
wanted, it is new harness work (a milestone-gate plugin hook) that must precede M1 and be in the t0
pin (see F3).

---

## Summary

- **M1's code surface is real and buildable** (W1-W11 map to live symbols; events.ndjson shadow-WAL
  substrate, executor superset, schema back-compat, discovery guard, `pipelines` group, grep-gates
  are all ordinary milestone work). Stale line numbers (F4) are a nuisance, not a blocker.
- **M0 as a chain milestone is the blocker.** The pinned-engine deliverable is the chain's own
  precondition (F1) — it must be a scripted t0 pre-step, with only the schema-validator/oracle/harness
  code remaining as a milestone.
- **The autonomy the whole epic rests on (the ladder, RecoveryPolicy, run-outcome vocab, auto-merge)
  does not exist at t0 and is frozen out of the driving engine by `--no-git-refresh`** (F2, F3). So
  M0/M1 will, on the first red gate or escalate, halt and wait for a human — directly contradicting
  the "zero human blockers after one go" promise the triple asserts.
- **The per-milestone oracle gates have no in-chain enforcement surface** (F5).

The first launch will not run unattended through M0; it will either stall at M0's pinning paradox or,
if the operator hand-pins at t0, halt for a human at the first non-green gate.
