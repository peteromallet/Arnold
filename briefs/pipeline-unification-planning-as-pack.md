# Brief: Unify planning into the pipeline-pack model

**Status:** design — consolidated 2026-05-23 (after three investigation waves:
5-agent architecture sense-check, 5-agent implementation-landmine pass, 4-agent capability
inventory + a 3-model jury on execution).
**Authors:** Claude + DeepSeek/Kimi investigation; decisions by Peter.

**Goal.** Make the canonical planning flow *be* a pipeline like `creative`/`doc`, not just *look*
like one. End state: a **single execution path** — every flow, planning included, is a discovered
pipeline pack run through `run_pipeline` / `run_pipeline_with_policy`. The legacy per-phase
`COMMAND_HANDLERS` dispatch and `auto.py`'s subprocess shelling are retired.

**Two settled decisions (driving everything below):**
1. **End state = full pack-ification.** Planning relocates to `megaplan/pipelines/planning/` and
   drops its `_BUILTIN_NAMES` entry — discovered like any pack. (The alternative, keeping it a
   privileged built-in, was considered and declined; symmetry is the goal. The one real risk this
   creates — silent discovery failure of the core flow — is mitigated by a discovery-integrity
   guard, below.)
2. **Mechanism = shared-core, NOT absorb-into-`run()`.** Replace the ~25-field `argparse.Namespace`
   config bus with a typed `HandlerContext`; make `handle_*` pure-ish functions of
   `(root, state, hctx)`; both the CLI and the planning Steps become thin callers. ~20% the cost of
   rewriting handler bodies into `Step.run()`, no ~1,500-LOC rewrite.

---

## 1. The problem: two parallel descriptions of planning

Today the planning flow exists twice, and production uses the *non-pipeline* one:

- **Legacy path (production).** `megaplan plan/prep/critique/gate/revise/finalize/execute/review`
  dispatch through `COMMAND_HANDLERS` (`cli.py:4454-4491`) → `handler(root, args)` (`cli.py:5170`),
  calling `handle_*` **directly**. No registry, no `Pipeline`, no executor. `megaplan auto`
  (`auto.py`) drives this by **shelling out** to `megaplan <phase>` subprocesses (`auto.py:158-183`).
- **Pipeline path.** `megaplan run <name>` → `run_cli.cli_run` → `registry.get_pipeline` →
  `run_pipeline(...)`. This is what `creative`/`doc`/`judges` use. It is also the *only* path that
  materialises planning's `Pipeline` (`_pipeline/planning.py`) — whose stages are thin
  `InProcessHandlerStep` wrappers that just re-call the same `handle_*` the legacy CLI calls.

Consequences: planning is special-cased in `_BUILTIN_NAMES` (`registry.py:53`, builders `:415-440`)
instead of discovered; and `auto.py` reimplements orchestration the executor already has.

**Scoping the "drift" motivation (corrected after claim-verification, see §13).** The Steps *do*
call the same `handle_*` the CLI calls, so the phase *logic* isn't duplicated. But "it's just a
wrapper of itself, only topology can drift" was an over-simplification: there are **real divergence
vectors** between the two paths. (a) `InProcessHandlerStep` carries its **own routing table**
(`_label_for`/`_gate_next_step`, `inprocess_step.py:130-189`) — a second, independent encoding of
next-step routing that can drift from the `Pipeline` edges. (b) `ExecuteStep` injects
`user_approved=True` (`stages/execute.py:17-18,34`), logic that lives in the Step, not the handler.
(c) The legacy/`auto` path doesn't use `InProcessHandlerStep` at all — it shells out and reads
`phase_result.json`, an entirely different result-interpretation path. (d) `TiebreakerStep` is a
`SubloopStep` running a nested pipeline, structurally unlike the legacy two-call tiebreaker. So drift
is a **genuine** (if bounded) risk, and the §7 parity gate is doing real work, not testing a function
against itself. The full-unification justification still rests primarily on retiring the *dual
dispatch surface* + unlocking the platform model (§2) — but "drift is trivial" is **not** an accurate
reason to downscope. Keep this in view when deciding scope (see §12, §13).

**What's already true (don't re-solve):** planning's full *topology* — critique→revise→gate loop,
four-way verdict dispatch, tiebreaker subloop, phase-zero gate, escalate — **already compiles to a
`Pipeline` with existing frozen types**. The `subloop`/`override` edge kinds were reserved in
advance for exactly this (`types.py:16-20,78`). Pack-ification needs **zero new types and zero new
registry features**. The weight is **not topology (~40%) — it's handler logic (~60%)**: the work
hides inside `handle_*` (the gate flag-reprompt + auto-downgrade two-pass loop `gate.py:466-521`;
the tiebreaker downgrade cascade reading `state["meta"]` counters `gate.py:327-392`; iteration
threading; version-chain diffing in `inprocess_step.py`; the approval check `execute.py:108-116`).

---

## 2. Target architecture (the north star)

The investigation reframed this from "relocate planning" into a coherent platform model. Three
principles:

### 2.1 One contract + graded capabilities (not two tiers)
Every pack — shallow (`creative`, ~5 small files) or deep (`planning`) — exposes exactly
`build_pipeline(**kwargs) -> Pipeline`. No base class, no ceremony. Shallow packs import nothing
from `patterns.py` and return a linear `Pipeline`; deep packs compose `critique_revise_gate_loop`,
`phase_zero_gate`, subloops, etc. **Depth = how many capabilities you compose, not which tier you're
in.** A two-tier "core flow vs pluggable pack" split was rejected — it just re-creates the
asymmetry we're removing.

Add one declarative metadata key the registry reads alongside the existing ones
(`registry.py:343-357`):

```python
capabilities: tuple[str, ...]
# creative=()                          doc=("fanout",)
# writing_panel_strict=("fanout","human_gate")
# planning=("gating","subloops","fanout","human_gate","override","robustness","policy")
```

Declarative, **not mixins** — nothing inherited. It lets the CLI/observability/resume adapt:
approval UX only for `human_gate` packs, override UX only for `override` packs, stall/cost guards
only for `policy` packs. **`patterns.py` already is the capability library** — formalise it; no new
abstraction needed. `_BUILTIN_NAMES` dies.

**Boundary rule:** if a Step's `run()` branches on domain config (`robustness`,
`max_tasks_per_batch`) it's pack-local; if it's pure topology (`critique_revise_gate_loop`,
`panel_parallel`) it's an engine pattern.

### 2.2 Promote the mechanism, keep the policy
The rule for deciding what generalises into the engine vs stays planning-local (§4 has the full map):
the **mechanism** is usually general (gate dispatch, a findings ledger, a deadlock-resolver subloop,
a rigour dial); the **policy/content** is usually planning-specific (the 4-verdict vocabulary, the
tiebreaker's flag wiring, the bare/light/full levels).

### 2.3 Execution is one realizer among many
Code execution is **one backend**, not the universal one — and the code half-shows it: ~12
`is_prose_mode` branches across `execute/core.py` + `execute/execute.py` (e.g. `core.py:575-658`,
plus two `required_fields` tuples in `_merge_batch_results`), and **doc/prose mode already piggybacks
the planning execute path** (`assemble_doc` at `execute.py:179`, verified). *Calibrated claim (per
§13):* this is **not** "two realizers cohabiting a 1,770-LOC function" — `core.py` is a 1,770-line
*file* of ~15 functions, and prose mode is ~5–6 mode-guarded skips/field-swaps reusing the same
worker/batch/merge machinery, not a second strategy object. So the realizer abstraction is a
*legitimate refactor of an inline-branch pattern*, not the rescue of a monolith. §5 specifies the
`Realizer` extraction.

---

## 3. The pack contract & capability manifest

### 3.1 The discovered-pack contract
A pack under `megaplan/pipelines/<name>/`:
- `__init__.py` exposes **`build_pipeline() -> Pipeline`** (REQUIRED; defaulted kwargs OK). Optional
  metadata constants: `description`, `default_profile`, `supported_modes`, `recommended_profiles`,
  and the new `capabilities` (§2.1) — read by `_module_metadata` (`registry.py:343-357`).
- `steps.py` — `@dataclass(frozen=True)` classes satisfying the `Step` protocol
  (`types.py:167-183`): `name`, `kind`, `prompt_key`, `slot`, `run(ctx) -> StepResult`. No subclassing.
- `prompts/__init__.py` — `register_pipeline_prompt(pipeline, key, renderer, *, mode=None)` side
  effects, imported for effect from `__init__.py`.
- `SKILL.md` — human docs, resolved by `registry.read_skill_md()`.
- Discovery: `discover_python_pipelines` scans `megaplan/pipelines/` + `~/.megaplan/pipelines/`;
  CLI name = stem with `_`→`-` (`registry.py:360-407`).

### 3.2 Planning is a HEAVY pack — the bill of materials
Planning is not a thin pack. Its full manifest:

**Ships INSIDE `pipelines/planning/`:**
| Component | Source today | Notes |
|---|---|---|
| 8 phase steps + topology | `_pipeline/stages/*`, `_pipeline/planning.py` | compiles with existing types |
| tiebreaker | `handlers/tiebreaker.py`, `stages/tiebreaker.py` | researcher/challenger subloop |
| override (8 actions) | `handlers/override.py:388-763` | force-proceed/abort/replan/add-note/recover-blocked/set-robustness/-profile/-model (override *edges* stay in engine, `types.py:16-20`) |
| finalize | `handlers/finalize.py` (~597 LOC) | task decomposition + validation + coverage |
| execute/ | `handlers/execute.py`, `execute/core.py`+`quality.py` (**~1,770 LOC**) | batch + auto-loop + quality gate |
| `SKILL.md` | **author it** | phase semantics, gate verdicts, robustness tiers, tiebreaker/escalate |
| `prompts/__init__.py` | **~40 LOC bridge** | planning has ZERO pipeline-scoped prompt registrations today; the Step `prompt_key` fields are **decorative dead code** (bypassed by `InProcessHandlerStep`). Wrap existing builders (`megaplan/prompts/planning.py` etc.) via `register_pipeline_prompt("planning", …)` |
| config schema (14 pack-local keys) | scattered in `types.py:44-58` `PlanConfig`, `handlers/init.py` | `robustness`(behaviour), `auto_approve`, `strict_notes`, `max_tasks_per_batch`, `allow_tiebreaker`, `max_tiebreakers_per_plan`, `tiebreaker_blocklist`, `tiebreaker_{token,time}_budget*`, `with_prep`, `with_feedback`, `prep_direction`, `phase_model` + metadata |

**Stays ENGINE / SHARED (planning calls into, doesn't own):** `FaultRegistry`
(`_pipeline/faults.py`, generic); `receipts/` (generic audit, currently unused); `tickets/`
(repo-level); `resume` — `HumanGateStep`+`ResumeCursor` are engine primitives, `handle_resume` is
shared CLI dispatch; `status`/`doctor`/`introspect`; the profile-resolution system (`profiles/`,
~1,453 LOC — note `VALID_PHASE_KEYS` is hardcoded to planning phases, a legacy quirk to clean up but
not move); `mode` helpers (`_core/modes.py`). **Subtle:** robustness *values/normalization* are
engine constants; robustness *semantics* are a planning-pack contract.

**Does NOT move in — the user-facing skills.** `megaplan`, `megaplan-decision`, `-epic`, `-observe`,
`-bakeoff`, `-tickets`, `-cloud` are orchestration skills that drive/observe planning *from above*;
they encode the consumer contract, not planning internals. They stay as repo/user skills and consume
the pack's `SKILL.md`.

### 3.3 The pack's PUBLIC API (what every wrapper binds to)
- **In-process:** `build_pipeline() -> Pipeline` **and** `run_planning(plan, policy, cwd) ->
  PlanningOutcome` (the in-process replacement for `auto.drive()`'s subprocess loop; `PlanningPolicy`
  carries ESCALATE/stall/cost/retry/timeout; `PlanningOutcome` mirrors `DriverOutcome`). `auto` and
  `chain` rebind to this.
- **Sanctioned mutation:** export **`mark_plan_executed(plan, cwd)`** so `chain.py:1512`
  (`_mark_blocked_execute_as_executed`) stops writing `current_state` directly (see §6 hazard 3).
- **Irreducible CLI/JSON boundary (cloud-over-SSH):** `megaplan status --plan` (`{state, next_step,
  valid_next, active_step, progress}`), `megaplan init` stdout (`{plan}`), `phase_result.json`
  (`{phase, exit_kind, blocked_tasks?}`), `DriverOutcome`/`--outcome-file`, `chain_state.json`.
  Must stay version-stable. `bakeoff` keeps its subprocess isolation.
- Planning must be **worktree-agnostic** — callers (bakeoff/cloud) own the worktree lifecycle.

---

## 4. Generalisation map (promote vs keep)

| Capability | Call | Shape |
|---|---|---|
| Typed-gate dispatch (`Edge.kind=="gate"`+`recommendation`) | **PROMOTE mechanism / KEEP taxonomy** | engine already dispatches; demote the 4-verdict `proceed/iterate/tiebreaker/escalate` literal (`types.py:76`) from an engine type to pack policy — other packs want `accept/revise/reject`, `publish/discard/requeue` |
| `FaultRegistry` (`faults.py`) | **PROMOTE core / strip 1 method** | most reusable structure in planning; move `addressed_then_reopened_count` (the tiebreaker trigger) into the pack as a derived helper |
| Tiebreaker researcher/challenger | **PROMOTE pattern / KEEP impl** | promote a generic `DeadlockResolver` SubloopStep (two opposing agents + human decide); planning ships a `FlagDeadlockResolver` wired to flag IDs/fuzzy groups |
| Override actions (8) | **PROMOTE 3 / KEEP 5** | promote `abort`/`force-proceed`/`add-note` (`OverrideAction` already lists 4); keep `replan`/`recover-blocked`/`set-robustness`/`set-profile`/`set-model` |
| Robustness | **PROMOTE dial+normalization / KEEP levels** | engine accepts a `str` intensity + canonical-name/alias normalization; packs declare their own levels & semantics |
| Receipts | **PROMOTE schema / KEEP resolver** | `Receipt` schema + `build_receipt` general; pack supplies `upstream_artifact_hashes` (hardcodes planning phases today) |
| Human gates, RuntimePolicy | **already ENGINE** | correctly placed |
| Versioned-artifact naming | **PROMOTE helper / KEEP naming** | engine `versioned_artifact_path(...)`; pack owns the `plan_v{n}.md` prefix map |
| Finalize task-decomposition | **KEEP core / SPLIT execution (§5)** | DAG/sense-checks/validation generalise; the code-specific injection moves to `CodeRealizer` |
| Execute batch loop | **SPLIT (§5)** | DAG-runner → engine; code specifics → `CodeRealizer` |

Highest-leverage promotions: typed-gate-dispatch-as-policy, `FaultRegistry`, `DeadlockResolver`, the
intensity dial. Irreducibly planning: finalize's task-DAG content, the 4-verdict gate vocabulary.

---

## 5. Execution as pluggable realizers

Split `execute/` along the seam the `is_prose_mode` branches already trace:

- **Universal → engine "DAG-runner":** task-graph batching + `depends_on` prereqs, the merge/track
  loop, `blocked/partial/success`, deviation reporting, `phase_result.json` emission, tier routing.
- **Code-specific → `CodeRealizer`:** git-as-evidence-substrate (`quality.py:369-429`),
  `files_changed`/`commands_run` evidence currency, LOC scope-drift, pytest baseline + the
  auto-injected verification task (`finalize.py:295,475`).

```python
class Realizer(Protocol):
    backend_id: str  # "code" | "prose" | "doc" | "data" | "infra" | "research"
    def realize(self, ctx: RealizeContext) -> RealizerResult: ...   # artifacts + evidence + blocked/deviations
    def evidence_contract(self, unit) -> EvidenceSpec: ...          # files+cmds | sections | rows | citations
    def quality_gate(self, batch, observed) -> list[Deviation]: ... # per-backend; deviation→blocked plumbing shared
    def assemble(self, units, out) -> ArtifactRef | None: ...       # run tests (code) | concat (doc)
```

**Reshape planning:** `finalize` becomes a mode-agnostic decomposer; `execute` becomes a realizer
dispatch (`Realizer.for_mode(mode)`). Topology stays `…→finalize→[realizer]→review`; the realizer is
selectable. Planning ships `CodeRealizer` as **first among equals, not the hardwired default**.
Creative/doc *gain* the DAG + quality gate they currently lack; ~200 LOC of `is_prose_mode`
conditionals disappear.

---

## 6. Critical hazards & prerequisites

These are confirmed in code and must be addressed as explicit gates, not discovered mid-implementation.

**1. State-write ownership (real, but narrower than first stated — corrected per §13).** Handlers
persist `state` to disk themselves via `save_state_merge_meta` (`shared.py:355` and ~29 other
scattered call sites — **30 total**, only ONE of which is in `_finish_step`); the executor expects a
`state_patch` return (`types.py:26-28`). The bridge (`inprocess_step.py:85-88`) diffs only an
**allowlist** (`current_state`, `iteration`, `last_gate`). **Correction:** mutations to other keys do
NOT silently vanish from disk — the handler writes the full state to `state.json`, and the executor's
`_merge_state_to_disk` uses *split ownership* (executor wins for the 3 allowlist keys; on-disk handler
values win for everything else), so `history`/`meta`/`plan_versions`/`sessions` **survive on disk**.
The real bug is narrower: the executor's **in-memory** `state` is stale for non-allowlist keys, so
**policy hooks** (`runtime.py` StallDetector/CostTracker reading `state`) and any hermetic Step see
stale data — handler-backed Steps re-read disk and are fine. So this is a *correctness bug in the
in-memory bridge + a model mismatch to clean up when unifying*, not a latent disk-corruption
time-bomb. Still worth fixing (pick one write model: handlers return a full delta, both callers own
the write) — and the 30 scattered persist sites make it bigger than "fix `_finish_step`."

**2. Observability is load-bearing — but `auto` does NOT route on it (corrected per §13).**
Correction to the earlier framing: `auto.drive()` picks the **next phase** from `state.json` via
`megaplan status` (`next_step`/`valid_next`), **not** from `phase_result.json`. `phase_result.json`
(written by `_emit_phase_result`, `shared.py:374`) feeds *secondary* routing only — timeout /
context-exhaustion / blocked-by-prereq|quality handling. There IS a fallback that synthesizes
`success` when the file is missing on a clean exit (`auto.py:763-771`, verified), but its blast
radius is smaller than "blunders forward on broken state": a genuinely failed phase leaves
`state.json` unadvanced and stall-detection kills the loop after ~5 iterations. Still: the emission
surface (`phase_result` + receipts + history + events) is what `status`/`chain`/cloud/`introspect`/
`doctor` consume, and the executor emits none of it on its own. **Guard rail (unchanged):** a single
shared **post-step emission hook** invoked by both callers — so the unified path keeps emitting what
the operability tools read. Just don't justify it with the (incorrect) "auto synthesizes success for
every phase" claim.

**3. External state writers — THREE, not one (corrected per §13).** Direct `current_state` writes
outside the handler/executor system: (a) `chain.py:_mark_blocked_execute_as_executed` (`:1517`,
sets `STATE_EXECUTED`, pops `active_step`/`latest_failure`/`resume_cursor`); (b)
`_core/workflow.py:352` `resume_plan()` (bumps `current_state` on resume from failed/blocked); (c)
`store/plan_repository.py:392` `record_lifecycle_failure()` (called from `auto.py:563`). An
executor-owned write model must account for **all three** bypass paths (the doc earlier named only
chain). Fix via a sanctioned `mark_plan_executed()` / state-mutation API (§3.3). Also: (d)
`megaplan/__init__.py` + `megaplan/handlers/__init__.py` export `handle_*` in `__all__` — a public
Python API; signature change needs deprecation shims. (e) Cloud providers shell `megaplan status`
over SSH — pin the status JSON as a stable contract against version skew.

**4. `auto_approve` bypass (must reproduce deliberately).** `auto.py:316-335` always injects
`--user-approved --confirm-destructive` for execute; `handle_execute` gates on `auto_approve` OR
`--user-approved` (`execute.py:108-116`). An in-process rewrite that drops this signal makes
`auto_approve=False` plans **halt at execute**. `HandlerContext` must carry it explicitly.

**5. State/resume incompatibility — partial (corrected per §13).** The pipeline path reads
`_pipeline_paused_stage` (`run_cli.py:261`; `:307` is the decision site, not the read); legacy
`handle_resume` reads `current_state`/`next_step`/`resume_cursor`. These differ for **blocked/failure
pauses** — those legacy plans need a migration shim. But **human-gate pauses already converge**: both
paths read `awaiting_user.json::stage`, so they're mutually resumable today. So the shim is needed for
blocked/failure pauses, not universally.

**6. `auto.py` ≠ `RuntimePolicy`.** auto also does ESCALATE→force-proceed policy, context-exhaustion
retry (`--fresh`), blocked-task retries, per-phase timeouts. These must be ported deliberately, not
assumed present.

**7. Handlers are not pure.** `handle_gate` runs an in-function reprompt loop (`gate.py:466-521`);
`handle_execute` runs an auto-loop (`execute.py:140-166`). So the shared-core buys **one handler
surface with two thin callers**, not literally "one execution path" until the CLI/auto rewire.
`HandlerContext` must **separate config (~17 stable fields) from runtime services**
(`progress_emitter`, event sink, a `worker_runner` callable the gate reprompt needs) or it just
re-becomes the grab bag it replaced.

**8. Reversibility.** A **`MEGAPLAN_UNIFIED_DISPATCH`** toggle (the repo already uses `MEGAPLAN_*`
toggles, e.g. `MEGAPLAN_MOCK_WORKERS`) would let the legacy and unified paths coexist behind a flag,
keeping `main` releasable while the migration is in progress (~15 LOC). **Caveat (important):** the
toggle only routes *dispatch* — it does NOT shield changes to the shared `handle_*` themselves
(both paths call them). To make the handler-signature migration reversible, the legacy dispatch
needs an `args_to_hctx` adapter so the toggle selects old- vs new-signature invocation (see §10
Body 1b). And the toggle must be resolved at **plan-init time** and stamped into `state.json`
(`dispatch_path`), not read per-invocation — otherwise flipping it mid-plan resumes a plan under the
other path and (given hazard 9) silently corrupts its state.

**9. State migration safety: no `schema_version` (severity downgraded per §13).** `state.json` has
**no version marker** (unlike `bakeoff/state.py`, `receipts/schema.py`, `agent/hermes_state.py`).
*Correction:* the earlier "silently loses meta/sessions/plan_versions → zombie state" claim was
overstated — it rested on the allowlist misreading corrected in hazard 1; on-disk state is preserved
by the split-ownership merge, so resume does not silently drop those keys. The real residual issue is
modest: there's no clean way to tell legacy vs unified state shape, and the in-memory staleness
(hazard 1) plus a mid-plan dispatch flip could still desync. **Fix (good hygiene, lower urgency):**
introduce `schema_version` (stamped by the emission hook in §10 Body
1a); on load, a plan with `schema_version` absent/`<2` runs the *full* migration shim (all keys, not
the allowlist) and re-saves. For safe rollback the unified path should **dual-write** legacy keys
(`current_state`/`next_step`/`resume_cursor`) alongside the pipeline keys until the legacy path is
removed. Cloud version-skew (new-local + old-remote shelling `megaplan status` over SSH) has no
compat-window enforcement today — the pinned status-JSON contract (hazard 3c) is the only guard;
keep the `state` field stable.

---

## 7. The parity gate (the correctness oracle)

Load-bearing for the whole migration. It is **achievable, not aspirational**: the
`MEGAPLAN_MOCK_WORKERS`/`MOCK_ENV_VAR` stub (`conftest.py:113`, `_impl.py:1749`) makes every phase a
deterministic function of `(step, iteration, config)`, so everything downstream of the worker is
pure Python.

**Design:** deep-copy the plan dir; run legacy `handle_*` on the original and the new Step on the
copy; diff `extract_decision_fields()` — state transitions, gate recommendation, downgrade
decisions, next-step labels, artifact filenames — while stripping prose/cost/timing.

**Caveat:** the default mock payloads never exercise the reprompt / auto-downgrade / tiebreaker
branches; the harness needs per-test `mock_overrides` (via `conftest.make_worker_sequence`,
`conftest.py:268`) to cover the full decision surface — otherwise it only proves the happy path.
**Keep the gate permanently** (post-cutover it becomes golden-state regression armor against the
very drift §1 describes).

---

## 8. Discovery-integrity guard

Because pack-ification drops planning's `_BUILTIN_NAMES` safety net, add a startup/CI assertion that
the `planning` pipeline is discoverable and `build_pipeline()` compiles — **fail loud, never
silently absent**. Creative/doc may be missing; planning must not be.

---

## 9. Shared infrastructure that already needs no change
`profiles/`, `resume.py`, `preflight.py`, `runtime.py`/`RuntimePolicy`, `_core/modes.py` are already
shared by `run_cli.py` for every pipeline. `HumanGateStep`/`ResumeCursor` are engine primitives.
`patterns.py` already hosts `critique_revise_gate_loop`/`phase_zero_gate`/panel/vote/debate/
`dynamic_fanout`.

---

## 10. Sequencing

Reconciled from two independent sequencing passes (Claude + DeepSeek) that converged on the critical
path. The serial spine is **state-write → emission hook → HandlerContext → handler migration →
pack-ify → CLI rewire → auto rewrite**; generalisations come last and parallelize. Two findings
that corrected the first-draft instinct: pack-ify planning *early* (it's the dispatch-rewire target,
not a final "move files" step), and rewire the CLI *before* `auto` (auto must rebind onto an
already-working unified path, not lead it).

### Phase 0 — Scaffolding (all parallel; no production impact)
- **Parity gate (§7)** — `extract_decision_fields()` diff harness with `make_worker_sequence`
  overrides covering the reprompt/downgrade/tiebreaker branches (not just the happy path).
- **Discovery-integrity guard (§8).**
- **`MEGAPLAN_UNIFIED_DISPATCH` toggle (hazard 8).**

Ships immediately; first value delivered is **drift detection**, before any behaviour changes.

### Body 1 — Foundation (the three deepest hazards; ~30% of the LOC but the bulk of the risk)
**The toggle does NOT protect this body** — `MEGAPLAN_UNIFIED_DISPATCH` routes *dispatch*, but both
paths call the *same* `handle_*`, so any handler-signature/state-model change hits both paths at
once. So Body 1 is split to keep each step independently reversible:

- **1a — State-write + emission + schema marker (additive, reversible).** Handlers stop
  self-persisting inside `_finish_step` (`shared.py:355`) and return a full state delta; the
  executor and the legacy CLI dispatch *both* apply the delta and invoke the single shared
  **emission hook** (phase_result + receipt + history + events, hazard 2); widen the
  `inprocess_step.py:85-88` allowlist to the full delta; stamp `schema_version` on every write
  (hazard 9). This is signature-compatible — the legacy path keeps working — so it ships safely.
- **1b — HandlerContext behind a legacy adapter.** Migrate `handle_*` to `(root, state, hctx)` with
  config (~17 fields) separated from runtime services (`worker_runner` for the gate reprompt,
  emitter, event sink), carrying `auto_approve`/`user_approved` explicitly (hazards 4, 7). Build an
  `args_to_hctx` adapter in the legacy CLI dispatch so the **toggle selects old- vs new-signature
  invocation** — only this makes the migration toggle-reversible. Add deprecation shims for the two
  public `__all__` blocks (`megaplan/__init__.py`, `megaplan/handlers/__init__.py`, hazard 3b).

**← Cut point.** Validate behind the toggle, parity gate green. *Note the genuine one-way doors* (the
state-write contract, the public-API signature): the adapter and shims make rollback practical, not
free.

### Body 2 — Unification (mostly mechanical against the green gate)
4. **Pack-ify planning (§3).** Create `pipelines/planning/`; Steps become thin callers of the new
   handler signature (retire `InProcessHandlerStep`); move topology + stages + tiebreaker + override
   + finalize + execute; author `SKILL.md`; write the `prompts/__init__.py` bridge (make the dead
   `prompt_key` fields live); declare the 14-key config schema; export `run_planning()` +
   `mark_plan_executed()`; rewire `chain.py:1512` off its direct `current_state` write (hazard 3a);
   add the resume-migration shim (hazard 5); drop `planning` from `_BUILTIN_NAMES` (the discovery
   guard is now load-bearing).
5. **CLI rewire.** Behind the toggle, route the phase subcommands through the executor instead of
   `COMMAND_HANDLERS`; preserve argparse surface + exit codes. **First point the single path runs in
   production.**
6. **`auto.py` in-process rewrite (hazard 6) — the most undersized item in this plan.** `auto.py`
   is ~1,846 LOC with **zero direct tests**, and its subprocess boundary is also the *isolation*
   boundary (per-phase timeouts, stall/idle detection, context-exhaustion) that must be
   reimplemented in-process. Treat this as a ~600-LOC orchestration port, not "replace with
   `run_planning()`". **Write `test_auto_drive.py` FIRST** (driving `drive()` against
   `make_worker_sequence`/`make_fake_phase_result` for every exit kind: success / blocked_by_prereq
   / blocked_by_quality / timeout / escalate / external_error) so it becomes the parity oracle for
   this boundary. Then port ESCALATE→force-proceed, `--fresh` retry, blocked-task retries, timeouts,
   cost/stall caps; pin the `megaplan status` JSON contract (hazard 3c). **← single execution path
   delivered: the goal.**
7. **Cleanup.** Flip the toggle default on; after one release, remove the toggle and the dead
   `COMMAND_HANDLERS` planning entries; the parity gate becomes permanent regression CI.

### Body 3 — Platform generalisation (after Body 2; lower urgency, parallelizable)
- `capabilities` metadata (§2.1) + formalise `patterns.py` as the capability library.
- Extract the engine DAG-runner + the `Realizer` interface; refactor `execute/` into `CodeRealizer`;
  make `finalize` mode-agnostic (§5).
- Promotions (§4): `FaultRegistry`, `DeadlockResolver`, the intensity dial, the receipt schema, the
  versioned-artifact helper; demote the 4-verdict gate taxonomy to pack policy.

### Critical path, parallelism, checkpoints
- **Strictly serial spine:** state-write → emission → HandlerContext → handler migration → pack-ify
  → CLI rewire → auto rewrite → toggle removal. Everything else hangs off it.
- **Parallel:** all of Phase 0; the `mark_plan_executed()` export and resume shim alongside (4); all
  of Body 3 (independent capability libraries — they touch `patterns.py`/`faults.py`/`execute/`, not
  the dispatch seam) can run concurrently once the pack exists.
- **Shippable / releasable after:** Phase 0 (drift detection); Body 1 (state model + HandlerContext,
  legacy path still default behind toggle); Phase 4 (pack discovered, toggle still off); Phase 6
  (single path live — the goal). Keep the parity gate forever.
- **Where to split:** three distinct bodies. The hard cut is after Body 1 (deepest hazards landed
  and validated); Body 3 is a separate, lower-urgency effort that delivers no planning-behaviour
  change (it buys creative/doc the DAG+quality gate and removes duplication) and depends on Body 2's
  green gate but not vice versa.

---

## 11. Evidence index
- **Dual dispatch:** `cli.py:4454-4491`, `:5072`, `:5170`; `auto.py:158-183`.
- **Pipeline path:** `run_cli.cli_run`; `registry.get_pipeline`; `executor.run_pipeline` /
  `run_pipeline_with_policy` (`executor.py:204`, `:303`).
- **Planning compiler / stages:** `_pipeline/planning.py:24`; `_pipeline/stages/*`; bridge
  `inprocess_step.py` (allowlist diff `:85-88`).
- **Handler bindings:** prep→`handle_prep`, plan→`handle_plan`, critique→`handle_critique`,
  gate→`handle_gate`, revise→`handle_revise`, finalize→`handle_finalize`, execute→`handle_execute`,
  review→`handle_review`, tiebreaker→`handle_tiebreaker_run`/`_decide`.
- **Handler logic hot spots:** gate reprompt/downgrade `gate.py:466-521`, tiebreaker cascade
  `gate.py:327-392`, approval check `execute.py:108-116`, `is_prose_mode` branches
  `execute/core.py:575-658`, `assemble_doc` `execute.py:179`, finalize verification-task injection
  `finalize.py:295,475`.
- **State/persistence:** `_finish_step`+`save_state_merge_meta` `shared.py:355`; `phase_result.json`
  `shared.py:374` consumed at `auto.py:732`, success-synthesis fallback `auto.py:763-771`;
  resume key `_pipeline_paused_stage` `run_cli.py:307`.
- **auto_approve bypass:** `auto.py:316-335` vs `execute.py:108-116`.
- **Cross-system consumers:** `chain.py:1512` direct `current_state` write; `megaplan/__init__.py:25-34`
  `__all__`; `cloud/providers/{ssh,railway,local}.py`.
- **Pack contract / discovery:** `registry.py:343-407`; `_BUILTIN_NAMES` `:53`, builders `:415-440`;
  other built-ins `_pipeline/demos/doc_critique.py`, `_pipeline/demo_judges.py`. Examples:
  `pipelines/creative/{__init__,steps}.py`, `pipelines/doc/`, `pipelines/writing_panel_strict.py`.
- **Capability manifest sources:** `handlers/{tiebreaker,override,finalize,execute}.py`,
  `execute/{core,quality}.py`, `_pipeline/faults.py`, `receipts/`, `tickets/`,
  `_pipeline/steps/human_gate.py`, `profiles/` (`VALID_PHASE_KEYS`), `_core/modes.py`,
  config keys `types.py:44-58`.
- **Parity gate:** mock stub `conftest.py:113`, `_impl.py:1749`; `make_worker_sequence`
  `conftest.py:268`; `test_pipeline_parity.py` already dual-runs `handle_*` vs `InProcessHandlerStep`.

---

## 12. Scope dissent & sizing (decision input)

**Sizing (one senior engineer): ~2–3 months total.** Phase 0 ~1 week; Body 1 ~1 month (the
deepest risk — `save_state_merge_meta` is called at ~30 sites across the handlers; `args.` is read
at ~47 sites and threads through `_finish_step`→`build_receipt`→`_run_worker`→`resolve_agent_mode`
and ~20 other helpers, so HandlerContext is a call-graph refactor, not a dataclass); Body 2 ~2–3
weeks (the `auto.py` rewrite alone is ~600 LOC and the riskiest single item); Body 3 ~2–3 weeks
(parallelizable). Long-tail not yet costed: ~300–500 LOC of test updates, the two `__all__` shims,
`VALID_PHASE_KEYS` generalisation (named in §3.2 but in no body), `SKILL.md` authoring, cloud
contract tests.

**Skeptic dissent (independent Kimi + Claude verdicts, both unprompted-aligned).** Both argued the
full scope is disproportionate to the stated pain and recommend: ship the **parity gate as permanent
CI** (kills the drift risk — see §1's honest re-scoping) + the **state-write/emission fix** (a real
latent-corruption bug worth fixing on its own merits, hazards 1, 9) + the **in-process `auto.py`
rewrite** (genuine perf/robustness win, decoupled from pack-ification) — and **defer**
pack-ification, the CLI rewire, the `Realizer` extraction, `capabilities` metadata, and the
gate-vocabulary demotion as "tidiness/symmetry/speculative generality." Claude's sharpest point:
demoting `_BUILTIN_NAMES` and then re-adding a discovery-integrity guard (§8) to compensate is
deleting a privilege and rebuilding it as an assertion.

**Decision (reaffirmed 2026-05-23, dissent weighed):** **full scope holds.** The goal is the
platform model in §2 (one contract + capabilities + pluggable realizers) — a maintainability and
extensibility bet, not a drift fix — and that bet is taken deliberately at the ~2–3-month price the
dissent honestly surfaced. The skeptics' minimum subset (parity-gate-as-CI + state-write/emission
fix + in-process `auto`) is **not** an alternative to full scope here — it is precisely the **first
shippable increment** of it (Phase 0 + Body 1a + the decoupled `auto` win), so building it first
loses nothing and de-risks the rest. Sequence accordingly: deliver the subset as the first
releasable milestone, then continue through Body 1b → Body 2 → Body 3 per §10.

---

## 13. Claim-verification ledger (10 independent DeepSeek agents, falsification-first, 2026-05-23)

Each load-bearing code claim was re-checked by an agent told to investigate the code first and try to
*refute* the claim. Cited line numbers held up well; several *interpretations* were overstated and
are corrected above. **Score: 3 clean, 1 supported-but-overstated, 5 partial, 1 contradicted.**

| # | Claim | Verdict | Correction folded in |
|---|---|---|---|
| 1 | Legacy dual-dispatch (`COMMAND_HANDLERS` → `handler(root,args)`, no executor; `run` uses registry) | **SUPPORTED** | cited lines correct |
| 2 | "Drift overstated — Steps are wrappers of the same handlers, only topology drifts" | **CONTRADICTED** | §1 fixed: real divergence vectors exist (own routing table `inprocess_step.py:130-189`; ExecuteStep `user_approved` injection; legacy/auto path is entirely separate; tiebreaker is a SubloopStep). Drift is genuine. |
| 3 | 3-key allowlist → handler mutations "silently vanish" → zombie state | **PARTIAL** | hazard 1 fixed: allowlist real (3 keys, cited right) but disk state is preserved by split-ownership merge; real bug = stale **in-memory** state for policy hooks, not disk corruption |
| 4 | Handlers self-persist via `save_state_merge_meta` "inside `_finish_step`", ~30 sites | **PARTIAL** | count is exactly **30** (correct!), but only 1 is in `_finish_step` — the other 29 are scattered (override 9, execute 7, …). Refactor is bigger/more dispersed than implied |
| 5 | `phase_result.json` is THE signal auto reads to pick next phase; missing → synth `success` → blunders forward | **SUPPORTED but overstated** | hazard 2 fixed: auto routes next phase from `state.json`/`next_step` via `megaplan status`; phase_result is *secondary*; success-synth exists but stall-detection backstops |
| 6 | `auto_approve` bypass on the auto path | **SUPPORTED** | cited ranges slightly imprecise; conclusion holds |
| 7 | `chain.py` writes `current_state` directly (one forgotten consumer) | **PARTIAL** | hazard 3 fixed: **three** external writers (chain `:1517`, `workflow.py:352`, `plan_repository.py:392`), not one |
| 8 | planning is a `_BUILTIN_NAMES` special case, not discovered | **SUPPORTED** | all cited lines correct |
| 9 | Legacy vs pipeline resume keys differ → won't resume without shim | **PARTIAL** | hazard 5 fixed: true for blocked/failure pauses; **human-gate pauses already converge** on `awaiting_user.json::stage`. Read site is `run_cli.py:261` not `:307` |
| 10 | `is_prose_mode` branches = strategy-pattern-in-duct-tape; "two realizers cohabit one 1,770-LOC function" | **PARTIAL** | §2.3/§5 fixed: `core.py` is a 1,770-line *file* (~15 functions), not one function; ~12 branches / ~5-6 prose skips, not two cohabiting realizers. Refactor still valid, oversold |

**Net read:** the *structural* claims (dual dispatch, built-in special-casing, auto_approve bypass)
are solid; the *severity/danger framings* I'd folded in were repeatedly too strong — most notably the
"deepest hazard" (state-write → zombie plans) is a narrower in-memory-staleness bug because disk
persistence already preserves the data. This *strengthens* the skeptics' case (§12) that the
state-write fix is real-but-bounded, not a corruption emergency — though full scope still holds for
the platform reasons, now on more honest footing.
