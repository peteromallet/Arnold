# Megaplan Decomposition & Multi-Critique Sprint — Source Plan (v2, hardened)

> v1 was a one-page wish list. v2 incorporates three parallel critiques
> (architecture, implementation-gaps, adversarial-risk) into an executable
> brief. The substantive deltas vs v1 are recorded in `## Critique deltas`
> at the end.

## Context & prior art

Megaplan is a Claude+Codex harness that drives plans from idea → execute via a
state machine (`megaplan/_core/workflow.py`), per-phase handlers
(`megaplan/handlers/`), per-mode prompt variants (`megaplan/prompts/`,
including `*_joke`, `*_creative`, `*_doc` already), per-profile model slots
(`megaplan/profiles/*.toml`, 18 profiles × 13 slots), and an auto driver
(`megaplan/auto.py`) with stall/cost/escalate policy.

The abstraction the v1 brief proposes ("primitive steps + loop types +
parent abstraction") **already exists implicitly** across these surfaces. The
real refactor is hoisting that implicit shape into a single declarative
`Pipeline` value, then proving generality by hosting one pipeline shape the
current code structurally cannot express cleanly.

Concretely, prior art:

- **State machine** — `WORKFLOW` dict at `megaplan/_core/workflow.py:41`,
  11 states with gate-condition branches (`gate_iterate`,
  `gate_tiebreaker`, `gate_escalate`, `gate_proceed_blocked`,
  `gate_proceed`).
- **Robustness overlays** — `_ROBUSTNESS_OVERRIDES` at `workflow.py:94`
  patches transitions per level.
- **Mode dispatch** — `megaplan/_core/modes.py` (`code`/`creative`/`joke`/`doc`).
- **Prompt-mode variants** — `prompts/critique.py`, `critique_joke.py`,
  `critique_creative.py`, `execute_doc.py`, `revise_creative.py`, etc.
- **Feature overlays** — `_with_prep_from_state` / `_with_feedback_from_state`
  in `workflow.py:191-258` splice phases in/out.
- **Profile slot table** — 13 keys per profile
  (`plan/prep/critique/revise/gate/finalize/execute/feedback/loop_plan/loop_execute/review/tiebreaker_researcher/tiebreaker_challenger`).
- **Auto driver** — `auto.py` is a second runtime with `resume_cursor`,
  stall detection, cost cap, context-retry, escalate-policy.

## Goal (rewritten)

Hoist the implicit pipeline-shape into a single declarative `Pipeline` value;
collapse `WORKFLOW` + `_ROBUSTNESS_OVERRIDES` + `with_prep`/`with_feedback`
overlays + mode dispatch into one source-of-truth; prove generality by
hosting a pipeline the current code can't express cleanly. The existing
planning flow must remain bit-identical at the artifact level for a fixture
input. No second abstraction layer — legacy `WORKFLOW` dict gets **deleted**,
not shadowed.

## Proof of generality (sharper than v1)

The v1 demo ("3x critique→revise loop on a doc") is expressible today via
`--mode doc --robustness robust`. Insufficient. The new demo must be
structurally novel.

**Primary demo: fan-out judge + synthesis pipeline.** Three judges (different
models or different prompt rubrics) critique the same artifact in parallel; a
synthesis stage merges verdicts; gate decides on synthesis. Current
`WORKFLOW` cannot express fan-out + barrier-join declaratively
(`parallel_critique` is hard-coded inside `handle_critique`).

**Secondary demo (only if primary lands early): two-artifact co-evolution.**
Produce spec + tests in parallel, gate on cross-consistency.

The original "doc critique" loop is kept as a third easier check that the
abstraction still expresses simple cases.

## Primitive step types (specified)

Five primitives fall out of the existing handler surface:

```python
@dataclass
class StepContext:
    plan_dir: Path
    state: PlanState
    profile: Profile
    mode: str                  # "code"|"doc"|"creative"|"joke"
    inputs: dict[str, Path]    # ArtifactRefs by name
    budget: BudgetRef

@dataclass
class StepResult:
    outputs: dict[str, Path]   # written artifacts
    verdict: Optional[Verdict] # populated for Judge/Decide
    next: NextEdge             # "always" | branch label | "halt"
    state_patch: dict[str, Any]

class Step(Protocol):
    name: str
    kind: Literal["produce","judge","decide","subloop","override"]
    prompt_key: str            # resolves prompts/<key>[_<mode>].py
    slot: str                  # profile slot key
    def run(ctx: StepContext) -> StepResult: ...
```

- **Produce** — writes a versioned artifact, advances state. (plan, prep,
  revise, finalize, execute.)
- **Judge** — reads artifact(s), emits typed verdict (flags, score). (critique,
  review.)
- **Decide** — consumes verdicts, returns labeled next-edge. (gate.)
- **Subloop** — nested pipeline returning to parent state. (tiebreaker.)
- **Override** — escape edge mutating state outside the graph. (override.)

Side-effect ownership: the harness writes artifacts (via `phase_result_guard`
+ `_write_plan_version` today), Step.run returns paths only. State.json is
written by the harness on each step boundary; `state_patch` is the only mutation
channel.

## Parent abstraction (specified)

```python
@dataclass
class Edge:
    label: str                 # "always" | "gate_iterate" | ...
    target: str                # next stage name | "halt"

@dataclass
class Stage:
    name: str
    step: Step
    edges: list[Edge]

@dataclass
class Pipeline:
    stages: dict[str, Stage]
    entry: str
    overlays: list[Overlay]    # robustness, with_prep, with_feedback, mode

@dataclass
class Overlay:
    name: str
    apply: Callable[[Pipeline], Pipeline]
```

`WORKFLOW` + `_ROBUSTNESS_OVERRIDES` collapses into one `Pipeline` instance for
each top-level mode. Robustness, `--with-prep`, `--with-feedback`, mode become
Overlays. Fan-out is a new `ParallelStage(steps=[...], join=...)`. The
declarative pipeline shape is the **only** source of truth; the auto driver
walks it.

## Loop semantics

A loop is **not** a primitive. It is a stage whose edge points backwards
under a condition. Termination is expressed by edge labels (e.g.
`gate.recommendation == ITERATE → revise → plan`). For finite-iteration
loops (e.g. "3× critique→revise"), the gate stage carries a max-iter counter
in `state_patch` and the iterate edge fires only while count < limit. No
new loop combinator needed; this matches today's gate-driven iteration.

## Leaks (acknowledged, addressed)

| Leak | Resolution |
| --- | --- |
| Gate branches read payload semantics, not just labels (`_transition_matches` `workflow.py:262`) | Verdict struct includes typed fields; gate's Decide returns labeled `NextEdge`; the executor matches on label only. |
| Review→rework loop lives in handler, not graph (`workflow.py:71-75`) | Add explicit `review_needs_rework` edge from review back to finalize. Remove handler-driven state mutation. |
| Tiebreaker is a nested pipeline with own state pair | First-class `SubloopStep` whose `Pipeline` returns into `STATE_CRITIQUED`. |
| Override mutates state outside graph | First-class `OverrideEdge` on every stage (typed escape). |
| Profile expansion, parallel critique, scope-creep, verifiability inside `handle_critique` | These are *middleware*. Modeled as `StepDecorator(step, before=..., after=...)`. Re-applied around primitive instances at pipeline-build time. |
| `auto.py` is a second runtime (stall, cost cap, context-retry, escalate) | Preserved bit-for-bit. Pipeline executor lives **inside** `auto.py` — replaces the phase loop, keeps the policy machinery. |

## Profile / state / CLI compat

- **Profile TOMLs unchanged.** Slot keys (`plan`, `prep`, `critique`, …) stay
  the same. Primitive instances bind to slots by name. New stages added for
  the fan-out demo bind to a new slot (`judge_a`/`judge_b`/`judge_c`/`synthesis`),
  optionally; if absent, fall back to the `critique` slot. No TOML rewrite.
- **`state.json` schema unchanged.** `resume_cursor.phase` continues to name
  the stage. Stages keep current phase names where they correspond 1:1
  (`plan`, `critique`, …); only the *implementation* moves to Pipeline.
- **CLI subcommands unchanged.** `megaplan plan/critique/gate/finalize/execute/...`
  remain. Each handler becomes a thin adapter that invokes the matching stage
  through the Pipeline executor with a single-stage filter.
- **`auto.py` unchanged at the CLI surface.** All `auto` flags work.
- **Tests:** the existing test suite must pass unmodified. A new
  `test_pipeline_compat.py` proves byte-identical artifacts on a fixture plan.

## Resumability contract

`resume_cursor.phase` → stage name. `_RESUME_ACTIVE_STATES`
(`workflow.py:361`) is auto-generated from the Pipeline (stages whose `kind`
is produce/judge contribute their resume-state mapping). Worked example
documented in `docs/pipeline-resume.md` (created in sprint 1).

## Isolation strategy (real, not fictional)

The system-wide `megaplan` shebang at `/Users/peteromalley/.local/bin/megaplan`
points at `/Users/peteromalley/Documents/megaplan/.venv/bin/python` and
imports from the main checkout. A worktree alone does **not** isolate.

Isolation contract:

1. **Source isolation:** `git worktree add ../megaplan-decomp decomp/main`
   off main. All edits go into the worktree. Branch `decomp/main`.
2. **Venv isolation:** `cd ../megaplan-decomp && python -m venv .venv-decomp
   && .venv-decomp/bin/pip install -e .`. All decomp work runs through
   `.venv-decomp/bin/megaplan`. The system `megaplan` binary keeps pointing at
   main.
3. **State isolation:** every decomp run sets
   `MEGAPLAN_HOME=$WORKTREE/.megaplan-home` (or `MEGAPLAN_STATE_DIR` if
   `MEGAPLAN_HOME` isn't honored — verify). Plan storage, DB blobs, tickets,
   chains, logs all rooted under that.
4. **No `pip install -e` from the worktree against the system venv.** Ever.
5. **Smoke check before any edit:** in the worktree's venv, run
   `python -c "import megaplan; print(megaplan.__file__)"` and confirm it
   resolves to the worktree path.
6. **Live processes:** if any `python -m megaplan` is running on this
   machine when sprint 1 starts, let it finish or snapshot
   `~/.megaplan/<repo-id>/` before touching shared state. Document PID(s).

## Sprint plan (re-sequenced — demo FIRST)

The v1 sequence (refactor → demo) is backwards: we only know the abstraction
is right by building the second flow. Inverted:

### Sprint 1 (weeks 1–2): primitive shape + demo spike

1. Write `megaplan/_pipeline/types.py` (Step, Stage, Pipeline, Edge,
   Overlay, StepContext, StepResult).
2. Throwaway prototype: `megaplan/_pipeline/demo_judges.py` — a fan-out
   judge + synthesis pipeline running end-to-end on a fixture document,
   using **only** the new types (no handlers).
3. Validate: prototype runs to completion, writes artifacts under
   `.megaplan/demos/judges/<run>/`, fixture-test asserts artifact shape.
4. Freeze the type interfaces. Any change to Step/Stage/Pipeline/Edge after
   this requires explicit note in `briefs/megaplan-decomposition.md`.

### Sprint 2 (weeks 3–4): port planning to the Pipeline

1. Port each handler into a Step:
   `handle_prep/plan/critique/gate/finalize/revise/execute/review/tiebreaker_run/tiebreaker_decide`.
   Handler CLI entrypoints stay; they delegate to single-stage Pipeline runs.
2. Compile `WORKFLOW` + `_ROBUSTNESS_OVERRIDES` + `with_prep` + `with_feedback`
   + mode dispatch into Overlays. Delete `WORKFLOW` and `_ROBUSTNESS_OVERRIDES`
   when overlays are proven equivalent.
3. Update `auto.py` to walk the Pipeline. Keep all stall/cost/escalate
   policy.
4. Acceptance: full test suite green; byte-identical artifacts on
   `tests/fixtures/decomp-parity-plan.md` pre/post; `megaplan auto` runs a
   sample idea end-to-end; doc-critique 3-iter demo runs; fan-out demo
   re-runs through the unified Pipeline (not the prototype runtime).

Hard scope limit: if Sprint 2 reveals the type design from Sprint 1 is
wrong, the brief gets an explicit revision note and Sprint 2 may extend by
≤1 week. Beyond that, write a follow-up brief.

### Robustness uplift

- All megaplan invocations for sprint planning: `--robustness robust`
  (NOT standard — this is kernel-invariant work).
- Profile: `all-claude`.
- The two megaplans (one per sprint) are themselves planned by megaplan.

## Falsifiable acceptance tests

These are written before coding starts; coding aims to pass them.

1. **Parity test:** `tests/test_pipeline_parity.py` runs `megaplan auto`
   on a fixture idea + fixture model recordings, asserts the resulting
   `plan_v1.md`, `critique_v1.json`, `gate.json`, `final.md`, `execution.json`,
   `review.json` are byte-identical before vs after the refactor.
2. **Compose test:** `tests/test_pipeline_compose.py` constructs a 4-stage
   pipeline `prep → 2× critique → finalize` in ≤50 lines of Python using
   only public primitives, runs it on a fixture doc, asserts artifacts land.
3. **Fan-out demo test:** `tests/test_pipeline_demo_judges.py` runs the
   fan-out judges pipeline on a fixture doc, asserts 3 judge artifacts +
   1 synthesis artifact land in expected paths.
4. **Doc-critique demo test:** `tests/test_pipeline_doc_critique.py` runs
   the 3x critique→revise loop on a fixture doc, asserts iteration count =
   3 and final doc differs from input.
5. **Resume test:** `tests/test_pipeline_resume.py` kills `megaplan auto`
   mid-run, resumes, asserts final artifacts identical to uninterrupted run.
6. **Legacy CLI test:** `tests/test_legacy_phase_cli_compat.py` exercises
   `megaplan plan/critique/gate/finalize/execute/review` standalone subcommands
   against a fixture plan dir, asserts behavior unchanged.
7. **Profile compat test:** `tests/test_legacy_profile_compat.py` loads
   every existing profile TOML and runs a stage from each slot through the
   Pipeline, asserts no slot-resolution errors.

Sprint 1 ships #2 + #3 passing on the prototype runtime. Sprint 2 ships
all seven passing through the unified Pipeline.

## Operating principles (revised)

- **No human review or approval gates.** Yes.
- **Mandatory artifact-based checkpoints** at the end of each handler-port:
  full test suite + parity fixture + commit. (Replaces "no checkpoints" —
  these are self-validating, not human gates.)
- **Blockers get overcome, not reported.** Yes — but a blocker means
  "stuck for >2 attempts" not "first error." When stuck, write a
  `BLOCKER-<n>.md` in the worktree explaining state + try; then keep going
  via a fallback path; never silently paper over schema mismatches.
- **Live megaplan must keep working.** Verified by (a) `which megaplan`
  still pointing at the system shebang, (b) the system venv's `megaplan`
  importing from `Documents/megaplan/megaplan/__init__.py` not the
  worktree, (c) a smoke `megaplan list` from outside the worktree returns
  the same plans as before.
- **The existing planning flow must produce byte-identical artifacts** on
  the parity fixture after the refactor.

## Out of scope

- Cloud orchestrator changes (`megaplan/cloud/`).
- Hermes worker / chain runtime changes (`hermes_worker.py`, `chain.py`).
- Resident scheduler changes (`megaplan/resident/`).
- Discord/Railway runner image updates.
- Profile TOML schema changes (slot names locked).
- `--vendor` / `--critic` / `--depth` flag semantics changes.

These are explicitly preserved bit-for-bit. Any change here triggers a
follow-up brief.

## Success criteria (falsifiable)

- All 7 acceptance tests above pass.
- Legacy `WORKFLOW` dict and `_ROBUSTNESS_OVERRIDES` deleted from
  `megaplan/_core/workflow.py`. Single source of pipeline shape.
- `megaplan auto` on a fresh idea runs through the unified Pipeline.
- Live `megaplan` (system shebang) keeps working on existing plans.
- A new pipeline (fan-out judges) ships in `megaplan/_pipeline/` and is
  importable.

## Critique deltas (v1 → v2)

| Critic angle | Delta applied |
| --- | --- |
| Architecture: prior art collision | Added explicit "Context & prior art" section. Rewrote Goal. |
| Architecture: leaks list | Added "Leaks" table with concrete resolutions. |
| Architecture: weak demo | Replaced "3x critique on a doc" with fan-out judge + synthesis; kept doc-critique as secondary check. |
| Architecture: WORKFLOW must be deleted not shadowed | Made deletion an explicit acceptance criterion. |
| Implementation: primitive interface absent | Added Step protocol + StepContext/StepResult dataclasses. |
| Implementation: loop semantics absent | Resolved as backwards-edge under gate condition; no new combinator. |
| Implementation: state machine fate | Explicit: WORKFLOW deleted, compiled from Pipeline; gate verdicts typed. |
| Implementation: profile slot mapping | Slot keys stay phase-named; primitives bind by name. No TOML rewrite. |
| Implementation: persistence/resume | resume_cursor.phase → stage name; auto-derived from Pipeline; worked example. |
| Implementation: doc-critique spec | Input flag, output paths, iteration count, fixture spelled out. |
| Implementation: worktree mechanics | Branch name, venv, MEGAPLAN_HOME, smoke check. |
| Implementation: sprint cut | Sprint 1 = primitive shape + demo spike; Sprint 2 = port planning. |
| Implementation: acceptance tests | 7 named tests with explicit assertions. |
| Implementation: back-compat list | CLI subcommands, profile keys, state.json, resume contract — each preserved. |
| Risk: worktree fiction | Added venv isolation + smoke check + live-process snapshot. |
| Risk: robustness too low | Bumped to `robust` for both sprints. |
| Risk: same-primitives trap | Demo inverted: prototype FIRST, then port. |
| Risk: sprint sequencing | Inverted (demo → port). |
| Risk: no questions trap | Replaced with mandatory artifact checkpoints. |
| Risk: joke mode prior art | Acknowledged in prior-art section; mode dispatch is an Overlay. |
| Risk: 18 profiles × 13 slots migration | Resolved by slot-name preservation (no migration). |
| Risk: unfalsifiable success | All criteria now have concrete tests. |
