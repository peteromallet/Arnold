# M5b — Execute realm: F4 complexity-tiering → F5 task-DAG scheduler

**Epic:** Pipeline Unification (`.megaplan/briefs/pipeline-unification-EPIC.md` §240/§278: "M5b — execute realm
(F4→F5): the task-DAG scheduler; F5's reducer returns **app-defined outcomes**").
**Program slot:** `PROGRAM.md` §216–226 — `[T2]`, **parallel with M5-eval** (both fan out off the M4
service base; `M5a ∥ M5b ∥ M5-eval`, §354). Critical-path hop `M4 → M5b → M5-eval` (§340).
**Tier/robustness:** premium · thorough/high — mechanically large, conceptually clean; the topo-sort is
already pure (the ~80%-there piece).
**Delivers (PROGRAM §216–226):** F4 tier-resolution capability; F5 batch/task-DAG scheduler whose reducer
returns app-defined typed outcomes (`Reduce[T]`, binding maps to `phase_outcome`); merge stays mechanical,
classification moves to the reducer. **Hard internal edge F4-before-F5** (F5's per-batch tier→model
resolution consumes F4's capability — `execute/batch.py:528–533`).
**Depends_on:** M5a (the formalized node library this realm plugs into — `PROGRAM §201`), M3 (the
`process` driver = per-unit OS isolation + the state-evolution axis — `PROGRAM §141`), M4 (the Governor
bounds task fan-out; the service `dispatch` — `PROGRAM §179`). Transitively M2 (Ports + `Reduce[T]`/
`select`, the 4-verdict enum already evicted to the app — `PROGRAM §105`).
**Grounded:** 2026-05-29 against current main (`execute/batch.py` = 1531 LOC; cites re-verified below).

> **Locked framing (the SDK discipline, EPIC §108–120).** Each feature ships a `{general SDK piece +
> thin planning binding}` pair. Planning keeps its *content* (rubric, 1–5 scale, batch defaults) AND —
> per EPIC §214 — the *behavior* that is mechanism in its private `STATE_*`/outcome vocabulary, expressed
> as a **binding that IMPLEMENTS an interface**, never baked into the general piece. For F5 this is
> load-bearing: the scheduler's result reducer MUST NOT return planning's `blocked`/`STATE_BLOCKED`
> verdict. This is the `JoinFn → GateRecommendation` eviction (EPIC §146) repeated for the scheduler.

---

## Outcome

The execute realm — today a 1531-LOC bespoke planning scheduler (`execute/batch.py`) — becomes two
reusable SDK pieces, each with a thin planning binding, landed under the strangler envelope (old path
default-ON, new path default-OFF behind `MEGAPLAN_UNIFIED_EXECUTE`):

1. **F4 — a general dispatch slot/tier-resolution capability.** A profile declares
   `tier_models[slot][tier] → spec`; the scheduler resolves "this unit of work, scored at tier T, runs on
   spec S." **Tier is an opaque ordinal to the SDK.** Planning's 1–5 scale, the rubric, and the
   justification-required hard-reject are the binding. (Per SYNTHESIS §283, the 1–5 score and `tier_models`
   ultimately become *projections* of the Calibration Ledger — but that is M5-cal; M5b lands F4 as the
   neutral resolution piece routing queries through, never owning the scale.)
2. **F5 — a general `produce`+`process`-driver scheduler.** `produce` yields a work-list with
   `depends_on`; the driver batches it (`compute_task_batches`, already a pure topo-sort) and `process`-es
   each batch on the **M3 `process` driver** (per-unit OS isolation). The **process-result reducer returns
   app-defined outcomes** — the primitive **invokes a binding-supplied reducer** (REGISTER §109, Open-Q#3
   lean), it does not own `success`/`blocked_by_quality`. Planning maps results→its verdicts in its binding.

**Handoff (the acceptance bar, EPIC §163).** The scheduler + tier-resolution are node-library/SDK pieces a
non-planning tool can drive over an arbitrary work-list (a `produce`-a-task-list / `process`-each batch job)
without inheriting any planning outcome name. Planning's execute phase then reads as a composition:
`produce`(finalize tasks) → schedule → `process` → reduce→verdict.

---

## Scope (file:line — verified against current main 2026-05-29)

### F4 — complexity-tiering (do this FIRST; F5's tier→spec input)

- **Current code, two coupled halves.**
  - *Adjudication* — `handlers/finalize.py:264–275`: every task must carry an integer `complexity` in
    1..5 (`:264–269`, `_reject` defined `:223`) **with** a non-empty `complexity_justification`
    (`:270–275`), hard-reject otherwise. Post-injection safety net `_normalize_task_complexity`
    (`finalize.py:559`, called `:608`) defaults injected tasks to a tier.
  - *Tier→spec resolution* — `execute/batch.py:79` `_resolve_tier_spec(...) → (agent, mode, model)`;
    `compute_batch_complexity` (imported `batch.py:18`, from `_core/io.py`) scores a batch;
    `_resolve_max_tasks_per_batch` (`batch.py:144`, default via `_default_max_tasks_per_batch` `:137` →
    `get_effective("execution","max_tasks_per_batch")` `:139`). Profile side: `profiles/__init__.py`
    `tier_models.*` nested `{slot:{tier:spec}}`.
- **Piece (general).** Dispatch slot/tier-resolution: a profile declares `tier_models[slot][tier] → spec`;
  the scheduler resolves a tier-scored unit to a dispatch spec. Tier is an **opaque ordinal**. Rides M2
  Ports + M4 `dispatch`/`config`. **No `1`/`5`/rubric literals in the general piece.**
- **Binding (planning).** The 1–5 scale, the rubric, the justification hard-reject (`finalize.py:264–275`),
  the "rater≥dispatchee" guarantee. **Known gap (carry, do not block — REGISTER §109):** cheap-finalize
  profiles still lack the rater≥dispatchee guarantee (MEMORY `project_complexity_adjudication.md`) — record
  it as a logged KNOWN GAP (log → continue → surface in report), do not gold-plate it shut here. The
  general piece must not encode 1–5.

### F5 — the execute task-DAG (the bulk; depends on F4 landing)

- **Current code.** `execute/batch.py` (1531 LOC) is the scheduler.
  - *Scheduling (the reusable core):* `compute_task_batches` (`_core/io.py:58`) is **already a pure
    topo-sort** — normalizes `depends_on`, raises on unknown dep (`io.py:83`) and on cycles (`io.py:99`),
    returns dependency-respecting batches; `compute_global_batches` (`io.py:128`)/`split_oversized_batches`
    (`io.py:107`) re-export through `batch.py:18`; `_resolve_max_tasks_per_batch` (`batch.py:144`) sizes them.
  - *Per-batch run/merge/classify:* `handle_execute_one_batch` (`batch.py:432`) resolves tier→spec per
    batch (`batch.py:528–533`, F4), runs `_run_and_merge_batch` (`batch.py:264`) which merges via
    `execute/merge.py::_merge_batch_results` (`merge.py:354`) and accumulates `deviations`.
  - **The leak (F5's whole point):** `_PHASE_OUTCOMES = {"success","blocked_by_quality",
    "blocked_by_prereq","timeout"}` (`batch.py:104–106`) is **planning's outcome vocabulary baked into the
    scheduler**; `phase_outcome = "blocked_by_quality" if blocked else "success"` (`batch.py:779`); `blocked`
    is derived from `blocking_reasons` (built `batch.py:603`, `:662`) sourced from `batch_blocked_ids`
    (worker `status=="blocked"`, `batch.py:616`) + `_blocked_task_reason` (`batch.py:249`). `merge.py`
    auto-downgrades a task to `status="blocked"` on a blocking deviation (`merge.py:152`,
    `_is_blocking_deviation` `:74`) — classification leaking into the merge step.
- **Piece (general).** A `produce`+`process`-driver scheduler: `produce` yields a work-list with
  `depends_on`; the driver batches via the pure topo-sort + a max-batch-size policy, `process`-es each batch
  on the M3 `process` driver (per-unit OS isolation), and runs a **process-result reducer that returns
  app-defined outcomes** — the primitive **invokes a binding-supplied reducer**, it does not own
  `success`/`blocked_by_quality`. `_PHASE_OUTCOMES`, the `blocked`→`STATE_BLOCKED` chain, and the
  `_is_blocking_deviation` downgrade move into the planning reducer.
- **Binding (planning).** The decomposition rule (finalize tasks → work-list), the `max_tasks_per_batch`
  default (`batch.py:139`), per-batch tier→spec (F4), the deviation/blocked classification + its mapping
  result → `{success, blocked_by_quality, blocked_by_prereq, timeout}` → planning's `STATE_*`, and the
  sense-check / verification-task content.

---

## Locked decisions

- **F4 before F5.** Tier-resolution is F5's binding input (`batch.py:528–533`); land it first as a clean
  piece, then build the scheduler on top.
- **F5's reducer returns app-defined outcomes, NOT planning's `blocked`/`STATE_BLOCKED`** (EPIC §278;
  SYNTHESIS missing-abstraction #4 / EPIC §194). The 4 `_PHASE_OUTCOMES` literals (`batch.py:104`) belong to
  the planning reducer, mapped onto M5c's run-outcome vocabulary later — never owned by the general scheduler.
- **Primitive invokes a binding-supplied reducer** (REGISTER §109, Open-Q#3 lean). The scheduler owns
  scatter/batch/`process`/collect; the binding owns "what does this result mean."
- **F5 returns a typed `Reduce[T]` (M2), NAMED `BatchReduceResult = Reduce[BatchOutcome]`** — a frozen
  per-batch result type M5b defines; the planning binding maps it to `phase_outcome`; **M5c's binding consumes
  `BatchReduceResult` and applies its 4→5 mapping table** (REGISTER §109). M5b never re-imports `STATE_BLOCKED`.
- **Keep the arbitrary-deps DAG** (`io.py:58`) — it is already pure and app-vocab-free; F5 extracts the
  *scheduling policy + process loop* around it, not the topo-sort itself. Don't gold-plate beyond what's
  already pure (REGISTER §109).
- **`_is_blocking_deviation` (`merge.py:152`): merge stays mechanical (validate+merge fields); the
  classification (deviation→outcome) moves to the reducer** (REGISTER §109). Fidelity moved, not weakened.
- **Tier is an opaque ordinal to the SDK** (F4); the 1–5 scale lives only in the planning binding.
- **Strangler envelope (PROGRAM §361–379).** Both pieces land as `{old-path default-ON, new-path
  default-OFF behind `MEGAPLAN_UNIFIED_EXECUTE`}`. The old `handle_execute_one_batch` /
  `handle_execute_auto_loop` stay live and authoritative; the new scheduler soaks on THROWAWAY work-lists.
  **No organ-swap + old-path deletion in one PR; the old execute path is retired only after ≥1 dual-green
  milestone AND its behavioral-replay oracle is green — the parity gate is NOT the retirement authority.**
  The new path's old root deletion belongs to the M6 atomic swap, not here.
- **Back-compat (EPIC §172):** `extra="ignore"`; `handle_execute_one_batch`/`handle_execute_auto_loop` keep
  their `__all__` import surface (shims); preserve `MEGAPLAN_*`; planning phase names stay valid.

## Open questions (each RESOLVED to its default — zero human blockers, REGISTER §109)

1. **F5 dependency semantics (real DAG vs batch-with-ordering)?** → **RESOLVED: keep the arbitrary-deps
   DAG** (`io.py:58` already supports arbitrary `depends_on`); don't gold-plate beyond what's already pure.
2. **Where does the app-defined-outcome reducer hand off to M5c?** → **RESOLVED: F5 returns a typed
   `Reduce[T]` instantiated as the NAMED type `BatchReduceResult` (a frozen `Reduce[BatchOutcome]`); the
   planning binding (in M5b) maps it to `phase_outcome`; M5c re-homes `STATE_*` later.** M5b defines this
   return type (`BatchReduceResult = Reduce[BatchOutcome]`, where `BatchOutcome` is the planning binding's
   `{success, blocked_by_quality, blocked_by_prereq, timeout}` enum) so M5c consumes a real named symbol
   without F5 re-importing `STATE_BLOCKED`. **M5c's `read_valid_targets`/`apply_transition` binding consumes
   `BatchReduceResult` and applies the 4→5 mapping table defined in M5c.**
3. **Does `_is_blocking_deviation` (`merge.py:152`) stay in merge or move to the reducer?** → **RESOLVED:
   merge stays mechanical; classification (deviation→outcome) moves to the reducer.**
4. **rater≥dispatchee gap on cheap-finalize profiles?** → **RESOLVED: carry as a recorded KNOWN GAP** (log →
   continue → surface in report); do not block M5b on closing it.

## Constraints

- **No silent gate/status auto-downgrade regressions** (MEMORY `project_gate_tiebreaker_downgrade.md`,
  `project_complexity_adjudication.md`): F4 keeps the complexity hard-reject (`finalize.py:264–275`); F5
  keeps the blocking-deviation→blocked fidelity (`merge.py:148–152`) — **moved into the reducer, not
  weakened.**
- **Preserve what the subprocess execute loop buys** (per-batch idle-timeout kill, context-exhaustion
  retry, worktree isolation): these are the **M3 `process` driver's** job; M5b wires the scheduler onto it
  and must not regress them. MEMORY `project_execute_stall_codex_silence.md`,
  `project_shannon_stream_stall_refactor.md` (idle backstop 1800 / batch=1 for big mechanical tasks) — keep
  these as binding/driver config, not hardcoded in the general piece.
- **Parity gate stays green & honestly labelled** (happy-path control-flow/artifact parity — NOT
  drift-provably-zero; PROGRAM §381). It is never the retirement gate.
- **Don't dogfood off an editable install** (MEMORY `project_dogfood_engine_shadow_and_openrouter.md`);
  schema validation report-only (PROGRAM §369). The epic driving the build runs `MEGAPLAN_UNIFIED_EXECUTE`
  OFF on the frozen pinned old engine.
- **Autonomy (REGISTER §149):** every gate machine-gated; red → bounded ladder (retry ×2 → bump
  profile/robustness one tier → `stop_chain` + auto-ticket), never parks on a human.

## Done criteria (testable; includes the milestone oracle gate)

- [ ] **F4** lands as `{general tier-resolution piece} + {planning binding}`, default-OFF behind
      `MEGAPLAN_UNIFIED_EXECUTE`; the 1–5 scale + justification hard-reject (`finalize.py:264–275`) live only
      in the binding; the general piece treats tier as an opaque ordinal.
- [ ] **F5** lands as `{general produce+process scheduler over the pure topo-sort} + {planning binding}`,
      default-OFF; the scheduler `process`-es on the M3 driver and invokes a binding-supplied reducer
      returning a typed `Reduce[T]`.
- [ ] **CI grep gate: the general scheduler/reducer modules contain ZERO of the 4 `_PHASE_OUTCOMES` literals
      (`batch.py:104`) and ZERO `STATE_BLOCKED` references** (mirrors M2's `GateRecommendation` grep gate,
      EPIC §146; REGISTER §119). Partial conversion merges only when grep-gate=0 AND all consumers green.
- [ ] The planning reducer maps results → `{success, blocked_by_quality, blocked_by_prereq, timeout}` and
      behaves identically to today — a **characterization test** over `handle_execute_one_batch` outcomes
      across success / blocked / timeout / deviation paths (new test, added to CI).
- [ ] **Non-planning exercise (the load-bearing proof, EPIC §163):** at least one non-planning tool drives
      the scheduler over an arbitrary `produce`d work-list and gets back a *different* outcome vocabulary —
      proving the reducer is binding-supplied, not baked.
- [ ] **ORACLE GATE (the sole retirement authority, PROGRAM §381):** subprocess-loop guarantees (idle kill,
      retry, worktree isolation) preserved via the M3 driver — **no regression vs the recorded execute
      traces (behavioral-replay oracle, PROGRAM §161/§372), including a recorded blocked-retry-then-resume
      trace**, NOT just happy-path parity. The old execute path is retired only after this oracle is green
      across ≥1 dual-green milestone.

## Touchpoints

`execute/batch.py` (F4 `_resolve_tier_spec` `:79`, F5 scheduler `handle_execute_one_batch` `:432` /
`_run_and_merge_batch` `:264` / `_PHASE_OUTCOMES` `:104` / `phase_outcome` `:779`), `execute/merge.py`
(`_merge_batch_results` `:354`, `_is_blocking_deviation` `:74`, downgrade `:152`), `_core/io.py`
(`compute_task_batches` `:58`, `split_oversized_batches` `:107`, `compute_global_batches` `:128` — the kept
pure core), `handlers/finalize.py` (F4 adjudication `:264–275`, `_normalize_task_complexity` `:559`),
`profiles/__init__.py` (`tier_models`, F4). Tests: `tests/test_pipeline_run_cli.py`, the characterization
import-surface test (`tests/characterization/test_import_surface.py`), the parity suite, a new
execute-outcome characterization test, the non-planning-scheduler exercise, the M3 behavioral-replay oracle.

## Anti-scope

- **The control plane / override (M5c → F6/F7).** `handlers/override.py`'s `recover-blocked` /
  `_BLOCKED_RECOVERY_STATES` consume F5's `blocked` outcome but are M5c's problem; M5b only emits the
  app-defined outcome + the planning binding's `STATE_*` mapping. The run-outcome vocabulary itself
  (`{succeeded, failed, escalated, blocked, awaiting_human}`, EPIC §194) is **defined in M5c**; M5b's
  reducer just returns a typed result M5c can map.
- **The Calibration Ledger / routing-as-a-query (M5-cal, SYNTHESIS §283).** F4 lands as opaque-ordinal
  resolution; `tier_models` becoming a *projection* of the Calibration Ledger is M5-cal, hard-gated on
  M5-eval (the versioned ruler). M5b does NOT touch calibration, decay, or exploration budget.
- **The supervisor tier (M5d → F8).** Chain/epic/bakeoff at run granularity.
- **New verbs / new driver shapes** (EPIC §145) — decoupling + formalization only; the `process` driver
  itself is M3.
- **M6 relocation / discovery / old-path deletion** — M5b makes the execute realm *composable*, not
  *discovered*; the old execute path's deletion is the M6 atomic swap, never here.
- **Re-tuning planning's complexity rubric or batch-sizing defaults** — content moves verbatim into the
  binding.
