# m5 — Extract planning's features into pieces + thin bindings (the big extraction)

**Epic:** Pipeline Unification (`.megaplan/briefs/pipeline-unification-EPIC.md`, m5 §106–109; Discipline table §29–38).
**Tier/robustness:** premium · thorough/high. **This is the largest milestone in the program** — flag the
sub-features below that are sub-milestone-sized (§"Sub-milestone candidates").
**Depends on:** m2 (4-verdict enum already moved into the planning app; `select`/`Reduce[T]` exist; the
`iterate_until` predicate is wired), m3 (a real `loop` driver + the `process` driver + gate-consequence
param + state-evolution axis), m4 (`dispatch`/`emit`/`evidence`/`config` are real services with backends).
**Grounded:** 2026-05-28/29 against current main. **Findings:** `.megaplan/briefs/validation/decision/migration-fit.md`
(full feature surface + the (e1–e7) no-home gaps these pieces fill), `.megaplan/briefs/validation/confidence/a3-human-recovery.md`
(the control/override plane + `workflow_next` projection contract), `.megaplan/briefs/pipeline-unification-EPIC.md`
§56–77 (abstraction stress-test: keep verbs, de-planning-ize types).

> **Locked framing.** For EACH planning feature below, m5 produces a `{general SDK piece + thin planning
> binding}` pair. The piece is builder-facing and must pass the discipline test ("would an unrelated builder
> want this?"). The binding is planning's *content only* — prompts, rubrics, the 4 verdict labels, the 1–5
> tier map, the robustness presets, the 9 override-action semantics. Planning keeps NO mechanism. After m5
> the node library is formalized and planning reads as a composition of pieces, not as the SDK.

---

## Outcome

Eight planning features that today live as bespoke planning code become reusable SDK pieces, each with a
thin planning binding carrying only domain content:

1. **`critique_revise_gate_loop` macro** — the canonical judge→gate→revise cycle is a formalized,
   parameterized node-library macro (gate consequence injected, verdict labels supplied by the app), not a
   hard-wired planning topology.
2. **`fan_out` / `panel`** — scatter→invoke→reduce as ONE general read+write fan-out primitive, unifying
   prep research fan-out, parallel critique, and the panel pattern. Planning supplies lens/area content.
3. **`escalate` / deadlock (tiebreaker→general)** — the escape-hatch + subpipeline-as-tiebreaker becomes a
   general `escalate`/deadlock-breaker node; planning's researcher→challenger→synthesis child is a binding.
4. **complexity-tiering** — a general dispatch slot/tier-resolution capability; planning's 1–5 map +
   justification hard-reject is a binding.
5. **the execute task-DAG** — a general `produce`+`process`-driver scheduler (batch/dependency walk over a
   work list); planning's task decomposition + batch sizing is the binding.
6. **`clarify` / human-gate** — a general clarify node + a pause/resume hook on the driver; planning's
   prep-clarification + `awaiting_human` semantics are bindings.
7. **the control/override plane** — a general control service (out-of-band, state-mutating operations over a
   running driver); planning's 9 override actions are bindings.
8. **the chain/epic/bakeoff SUPERVISOR TIER** — a general cross-run orchestration tier (sequence/parallel
   runs, dependency/failure semantics, blind-compare/merge); planning's milestone-chain + bakeoff are
   bindings.

**Handoff:** the node library is the public composition vocabulary; planning's pipeline is re-expressible as
calls into it + content; a non-planning tool can compose the same eight pieces (acceptance #1/#3, EPIC §79–89).

---

## Scope (a sub-section per feature: piece + binding + current code)

### F1 — `critique_revise_gate_loop` macro

- **Current code.** `_pipeline/pattern_topology.py:47` `critique_revise_gate_loop(critique_step, gate_step,
  revise_step, *, on_proceed, on_iterate, on_tiebreaker, on_escalate, …)` already returns
  `{"critique","gate","revise"}` Stages and emits **exactly four `kind="gate"` recommendation edges**
  (`pattern_topology.py:78–83`). The production wiring of those steps + the gate's verdict logic lives in
  `handlers/gate.py` (`_resolve_revise_transition` rejects revise unless `recommendation=="ITERATE"`,
  `gate.py:152–154`; the four labels are hard-coded `iterate/proceed/tiebreaker/escalate`).
- **Piece (general).** Formalize the macro so its four edges are **not** the 4-verdict enum baked in — the
  caller supplies `verdict_labels` + per-label target/consequence (m2 already moved the enum to the app; m3
  added gate-consequence param `advance|revise_in_place|restore_and_diverge|escalate`). The macro becomes
  "judge → gate(consequence-per-verdict) → revise(loop-back-target)", N verdicts not 4.
- **Binding (planning).** Planning passes its 4 labels + the ITERATE→revise / TIEBREAKER→deadlock /
  ESCALATE→halt mapping and its critique/gate/revise prompts. The `ITERATE`-only revise guard
  (`gate.py:152`) becomes a binding-supplied consequence, not macro logic.

### F2 — `fan_out` / `panel` (scatter→invoke→reduce)

- **Current code.** THREE near-parallel implementations: (a) `panel_parallel` (`pattern_topology.py:100`) →
  a `ParallelStage` whose join collates `{reviewer_id}.{label}`; (b) prep research fan-out via
  `_core/hermes_fanout.scatter_gather` driven by `orchestration/prep_research.py` (`scatter_gather` import
  at `prep_research.py:17–19`, `GenericScatterResult` reduce at `prep_research.py:301`); (c)
  `orchestration/parallel_critique.py` `run_parallel_critique` (`parallel_critique.py:165`) which scatters
  one Hermes worker per check via `scatter_gather_checks` (`:206`) and reduces to `verified/disputed` flag
  IDs. Also `pattern_dynamic.dynamic_fanout` / `panel_from_artifact` (runtime-sized fan-out).
- **Piece (general).** ONE `fan_out(items, invoke, reduce)` primitive: scatter a work-list → invoke a Step
  per item (read OR write; prep is read-only Hermes, critique is read-only, but the primitive must not
  assume read-only) → `reduce` to a structured value (m2 made `Reduce[T]` structured, not a
  `GateRecommendation`). `panel` = `fan_out` with a fixed item-list (reviewers); `dynamic_fanout` = runtime
  item-list. Concurrency cap + per-item failure/sentinel handling (`prep_research.research_sentinel`,
  `:118`) belong to the primitive.
- **Binding (planning).** Lens/area selection content (the critique lens list, `prep_area_cap`,
  `:113`), the write-capable-provider rejection for prep (`_reject_write_capable_prep_provider`, `:209`) as
  a binding policy, and the reduce shapes (flag-IDs for critique; research findings for prep).
- ⚠ The three impls have **different dispatch substrates** (panel = in-process ParallelStage threads; prep
  = process-isolated Hermes; critique = thread-pool Hermes). Unifying them rides on m4's `dispatch` service
  having both backends — the primitive picks a backend, it does not re-implement either.

### F3 — `escalate` / deadlock (tiebreaker → general)

- **Current code.** `pattern_topology.py:301` `escalate_if(condition, escalation_handler) → (Step, Edge)`
  (escape edge, `kind="gate"`, `recommendation="escalate"`). The deadlock-breaker is the **tiebreaker
  subpipeline**: `orchestration/tiebreaker.py::_run_tiebreaker` (`:50`) runs researcher→challenger→synthesis
  as three sequential workers (`tiebreaker.py:67/86/100`); `subpipeline_call` (`pattern_topology.py:193`)
  wraps a child `Pipeline` in a `SubloopStep` with a `promote` fn mapping child terminal state → parent
  verdict. Gate routes to it on `recommendation=="TIEBREAKER"`.
- **Piece (general).** A general `escalate`/deadlock node = "when a gate cannot resolve, run a
  deadlock-breaker subpipeline and `promote` its result back to a verdict." This is `escalate_if` +
  `subpipeline_call` formalized into one node-library entry with the consequence param from m3
  (`restore_and_diverge` for the divergent-subpipeline case).
- **Binding (planning).** The researcher→challenger→synthesis child pipeline + its three prompts
  (`prompts/tiebreaker_*`) + the `promote` that maps synthesis → PROCEED/ITERATE. These are pure content.

### F4 — complexity-tiering

- **Current code.** Two coupled halves: (a) **adjudication** in `handlers/finalize.py:264–274` — every task
  must carry an integer `complexity` in 1..5 **with** a non-empty `complexity_justification`, hard-`_reject`
  otherwise (`finalize.py:223`). (b) **tier→model resolution** in `profiles/__init__.py` (`tier_models.*`
  nested `{phase:{tier:spec}}`, `_extract_tier_models` `:297`, validation `:172–176`) and at execute time
  `execute/batch.py:79` `_resolve_tier_spec` + `compute_batch_complexity` (`batch.py:18`) maps a batch's
  tier → an agent spec.
- **Piece (general).** A general **dispatch slot/tier resolution** capability: a profile declares
  `tier_models[slot][tier] → spec`, and the scheduler resolves "this unit of work, scored at tier T, runs on
  spec S." Tier is an opaque ordinal to the SDK. (Rides on m4 `dispatch` + `config`.)
- **Binding (planning).** The 1–5 scale, the rubric, the justification-required hard-reject
  (`finalize.py:265`), and the "rater≥dispatchee" guarantee live as planning content. (NB the project memory
  `project_complexity_adjudication.md` flags cheap-finalize profiles still lack that guarantee — fix or
  carry as a known gap; do not let the *general* piece encode the 1–5 scale.)

### F5 — the execute task-DAG

- **Current code.** `execute/batch.py` (1,529 LOC) is the scheduler: `compute_task_batches` /
  `compute_global_batches` / `split_oversized_batches` (`batch.py:18–32`) decompose finalize's task list
  into dependency-respecting batches sized by `max_tasks_per_batch` (`_resolve_max_tasks_per_batch`,
  `:144`); `handle_execute_one_batch` (`:432`) runs a batch, `_run_and_merge_batch` (`:264`) dispatches +
  merges + classifies blocked/deviation; `_merge_batch_results` in `execute/merge.py`. m4 already named
  `compute_task_batches` as the shared pure scheduler.
- **Piece (general).** A general `produce`+`process`-driver scheduler: `produce` yields a work-list with
  dependencies; the driver schedules it into batches and `process`-es each (the m3 `process` driver gives
  per-unit OS isolation; the batch walk is the general scheduling policy). Blocked/deviation classification
  is a general `process`-result reducer.
- **Binding (planning).** The decomposition rule (finalize tasks → batches), `max_tasks_per_batch` default
  (`get_effective("execution","max_tasks_per_batch")`, `batch.py:139`), per-batch tier→model (F4), and the
  sense-check / verification-task content.

### F6 — `clarify` / human-gate

- **Current code.** `phase_zero_gate` (`pattern_topology.py:326`) is the in-graph objective gate. The
  human-pause surface is the `STATE_AWAITING_HUMAN` family: prep emits a clarification (`clarification.source
  == "prep"`, consumed by `override resume-clarify`, `handlers/override.py:857`); `verify-human` requires
  `STATE_AWAITING_HUMAN_VERIFY → STATE_DONE` reading `success_criteria` from `plan_v1.meta.json`
  (`handlers/verifiability.py`). migration-fit (e3) + a3 name this as an out-of-band pause that the
  in-graph `HumanDecisionStep` cannot express alone.
- **Piece (general).** Two pieces: (i) a general `clarify` node (ask → block → resume on answer); (ii) a
  **pause/resume hook on the driver** — a driver-level "halt for external input, persist a resume cursor,
  resume from cursor" capability (the m3 loop/process drivers grow this hook). Distinct from F7: F6 is the
  *halt-and-wait*; F7 is the *operator action that mutates and un-halts*.
- **Binding (planning).** prep's clarification content + `clarification.source` discrimination; the criteria-
  verification gate content (`success_criteria` from `plan_v1.meta.json`); state names `STATE_AWAITING_HUMAN`
  / `STATE_AWAITING_HUMAN_VERIFY` as planning's vocabulary mapped onto the general pause states.

### F7 — the control/override plane (the 9 actions)

- **Current code.** `handlers/override.py` — `_OVERRIDE_ACTIONS` (`:898`) maps **9 actions**:
  `add-note`, `abort`, `force-proceed`, `replan`, `recover-blocked`, `resume-clarify`, `set-robustness`,
  `set-profile`, `set-model`. Each is an out-of-band, state-mutating operation injected *between* phase
  subprocesses: `force-proceed` manufactures a PROCEED gate artifact + writes `gate.json` + flips
  `STATE_CRITIQUED/BLOCKED → STATE_GATED` (`:242–349`); `recover-blocked` owns a private phase→recovered-
  state map `_BLOCKED_RECOVERY_STATES` (`:399`) — a *second copy* of the workflow's reverse edges (a3 §1
  flags `_RESUME_ACTIVE_STATES` in `workflow.py:326` as a third copy); `set-robustness`/`set-profile`/
  `set-model` mutate `state.config` to take effect next phase.
- **Piece (general).** A **control service**: a typed set of out-of-band operations over a running driver
  (`force-advance`, `re-route`, `recover-from-stuck`, `reconfigure`, `annotate`, `abort`) that mutate
  persisted run state + emit a control event, independent of the in-graph flow. It must compose with the m3
  state-evolution axis (mutations are versioned events) and with F6 (resume after a halt). a3's locked
  constraint: it consumes `workflow_next`'s **dynamic, state-derived projection** for valid-next hints — it
  does NOT read static graph edges (would print wrong recovery commands on reduced-robustness plans).
- **Binding (planning).** All 9 actions as planning bindings of the general operations: the
  STATE-name vocabulary, the manufactured-gate-artifact mechanics, the reverse-edge recovery maps (derive
  the THREE copies from one graph-edge relation per a3 §4.3, exposed as a queryable API), the strict-notes
  invariant (`:218`), the 1–5/profile/model reconfiguration semantics. **This is the densest planning-
  vocabulary coupling in the codebase** (a3 §1) — see Open questions.

### F8 — chain / epic / bakeoff SUPERVISOR TIER

- **Current code.** `chain/__init__.py` (1,820 LOC): `MilestoneSpec` (`:171`) / `ChainSpec` (`:291`) drive N
  milestone plans, each via `auto_drive` (imported `:73`), with git branch/worktree ops (`chain/git_ops.py`,
  `_init_plan` `:796`, `_drive_plan` `:909`), dependency ordering, `on_failure`/`on_escalate` semantics
  (`:347–348`, `ESCALATE_ACTIONS` `:396`), `.chains/` progress state (`ChainState` `:425`). `bakeoff/`
  (orchestrator/judge/comparison/merge/worktree) spins multiple worktrees, runs the same plan under
  different profiles, blind-judges + merges a winner. migration-fit (e4/e6) names both as a **meta-driver /
  supervisor tier** with no slot in the 4-layer model. Cloud (e5) wraps `auto`/`chain` as a process — out of
  m5 scope (it sits above the supervisor tier; carry as anti-scope).
- **Piece (general).** A **supervisor tier** above a single run: orchestrate a *graph of runs* with
  dependency ordering, per-run failure/escalate policy, and persisted progress — plus a parallel/compare
  variant (run-the-same-work-N-ways → blind-reduce → select-a-winner, which is m2's `select` at the
  run granularity). Chain = sequential dependency DAG of runs; bakeoff = parallel runs + `select` + merge.
- **Binding (planning).** The milestone-chain YAML schema + `auto_drive` integration, the git/worktree
  isolation policy, the escalate-action vocabulary (`force-proceed` default `:308`), and bakeoff's
  profile-matrix + blind-judge rubric. The supervisor tier itself knows nothing about planning phases.

### F9 — Formalize the node library (cross-cutting deliverable)

`patterns.py` is already a compatibility facade (`patterns.py:1–58`) re-exporting from `pattern_topology` /
`pattern_dynamic` / `pattern_joins` / `pattern_types`. m5's terminal step: declare this the **public,
documented composition vocabulary** — every macro above (F1–F3) is a node-library entry with a stable
signature, app-vocab-free types (m2), and a SKILL-discoverable manifest. Planning's pipeline becomes a file
that calls these and supplies content; no planning mechanism remains in `_pipeline/`.

---

## Locked decisions

- One `{piece + binding}` pair per feature; planning keeps **only content** (prompts, rubrics, 4 verdict
  labels, 1–5 tier map, robustness presets, 9-action semantics). No planning mechanism survives in the SDK.
- Verbs are at the right altitude (EPIC §61); m5 does **decoupling + formalization**, not new verbs. The
  4-verdict enum is ALREADY in the app (m2) — no piece below may re-introduce it.
- F7 (control plane) consumes `workflow_next`'s dynamic projection, NOT static edges (a3 verdict). The three
  phase↔state maps (`_BLOCKED_RECOVERY_STATES`, `_RESUME_ACTIVE_STATES`, forward transitions) are derived
  from one graph-edge relation but remain a queryable API for the recovery handlers (a3 §4.3).
- `fan_out`/`panel` (F2) ride m4's `dispatch` backends; the primitive selects a backend, it does not unify
  the subprocess/async/thread substrates itself.
- Cloud is NOT in m5 (it wraps the supervisor tier; see Anti-scope). Bakeoff IS (it's a supervisor-tier
  binding alongside chain).
- Back-compat constraints from the EPIC apply: `extra="ignore"`, name aliases, `handle_*` `__all__` shims,
  preserve 26 `MEGAPLAN_*`, keep planning phase names valid in profiles.

## Open questions (biggest blocking unknowns)

1. **F7 control plane is the hardest clean split.** The 9 override actions are written in the planning
   state-machine's *private vocabulary*: hard-coded `STATE_*` literals, manufactured gate artifacts,
   gate-verdict predicates (`force-proceed` reads `last_gate.recommendation`, depends on the
   `gate_proceed_agent_availability_blocked` predicate, `override.py:63`), robustness-conditional valid-next
   hints. Where exactly is the seam between "general control operation" and "planning's transition
   semantics"? a3 proves the *forward-progress* half maps to general transitions but `recover-blocked` /
   `resume_plan` are reverse projections with no forward edge. **This is the single biggest unknown and most
   likely to need its own sub-milestone.**
2. **Does F8's supervisor tier subsume cloud's operator loop, or stay strictly below it?** migration-fit
   (e5) couples cloud to auto+chain. m5 must define the boundary or cloud breaks in m6.
3. **F2 reduce-shape generality.** Prep reduces to research findings; critique to flag-ID sets; panel to
   `{reviewer}.{label}` paths. m2 gave `Reduce[T]` — is one structured reduce type enough, or does each
   binding need its own reducer the primitive merely invokes? (Lean: primitive invokes binding-supplied
   reducer.)
4. **F5 dependency semantics.** Does the general scheduler need a real DAG (arbitrary deps) or is planning's
   batch-with-ordering sufficient as the general contract? Over-generalizing here risks gold-plating.

## Constraints

- Parity gate stays green and honestly labelled (control-flow/artifact parity on the happy path). Add the
  a3 §4.4 parity test: `workflow_next` over the new graph-backed projection equals the legacy dict-backed
  impl across {5 robustness} × {with_prep,with_feedback} × {all states} × {all gate recommendations}.
- Don't dogfood off an editable install (pinned engine); schema report-only until the last step
  (`project_dogfood_engine_shadow_and_openrouter.md`).
- Preserve what `auto.py`'s subprocess loop buys (context-exhaustion retry, per-phase idle-timeout kill,
  worktree isolation) — these are the m3 `process` driver's job; m5 must not regress them while extracting.
- No silent gate auto-downgrade regressions (`project_gate_tiebreaker_downgrade.md`,
  `project_complexity_adjudication.md`): F1/F4 must keep the hard-reject + verdict-fidelity guarantees.

## Done criteria

- [ ] F1–F8 each land as `{general piece committed to the node library / SDK} + {planning binding carrying
      only content}`; no planning mechanism remains in `_pipeline/patterns*` or the shared pieces.
- [ ] `patterns.py` is a documented, app-vocab-free public node-library surface (F9); `JoinFn`/`Reduce`
      return structured data, never `GateRecommendation`.
- [ ] Planning's pipeline is re-expressible as composition + content; a reader can point at `iterate` and
      say "that's planning's binding of `revise_in_place`" (acceptance #3, EPIC §86).
- [ ] The a3 `workflow_next` parity test is green; the three phase↔state maps derive from one relation.
- [ ] At least one piece (candidate: F2 `fan_out` or F8 `select`-at-run-granularity) is exercised by the
      non-planning acceptance toy (#1) to prove generality.
- [ ] All 9 override actions behave identically post-extraction (characterization tests for `override.py`).

## Touchpoints

`_pipeline/pattern_topology.py` (F1/F3/F6), `_pipeline/pattern_dynamic.py` + `pattern_joins.py` +
`pattern_types.py` (F2/F9), `_pipeline/subloop.py` (F3), `orchestration/{prep_research,parallel_critique,
tiebreaker}.py` + `_core/hermes_fanout.py` (F2/F3), `handlers/{gate,finalize,override,verifiability}.py`
(F1/F4/F6/F7), `profiles/__init__.py` (F4), `execute/{batch,merge,aggregation}.py` (F5), `_core/workflow.py`
+ `workflow_data.py` (F6/F7 projection), `chain/__init__.py` + `chain/git_ops.py` + `bakeoff/*` (F8).
Tests: `tests/test_override_strict_notes.py`, the characterization import-surface test, parity suite.

## Anti-scope

- **Cloud** (`cloud/`, `mp-supervise`, `supervise.py`) — wraps the supervisor tier as a long-lived process;
  it's an m6/separate concern (migration-fit e5). m5 defines the boundary, does not port it.
- **The m6 relocation** (planning → `pipelines/planning/`, drop `_BUILTIN_NAMES`, manifest+SKILL.md,
  umbrella discovery) — m5 makes planning *composable*; m6 makes it *discovered*.
- **New verbs** — EPIC §62 is explicit: decoupling, not new primitives. No speculative driver shapes.
- **Pure handlers / 81-field HandlerContext** — deferred (EPIC §117); m4's RunConfig+services is the ceiling.
- **Re-tuning planning's prompts/rubrics** — content moves verbatim into bindings; quality tuning is not m5.

---

## Sub-milestone candidates (this is the largest milestone — split if it slips)

Ranked hardest-to-cleanly-split first:

1. **F7 — control/override plane (STRONGEST candidate).** Densest planning-vocabulary coupling (a3 §1);
   reverse-edge maps + manufactured artifacts + verdict predicates; the seam between general control and
   planning transitions is genuinely unresolved. Own sub-milestone, likely sequenced last in m5.
2. **F8 — supervisor tier.** 1,820-LOC chain + the entire `bakeoff/` package + git/worktree orchestration; a
   whole new architectural tier. Natural standalone sub-milestone.
3. **F5 — execute task-DAG.** 1,529-LOC `batch.py`; the produce/process/DAG split is mechanically large but
   conceptually cleaner than F7/F8. Sub-milestone if F7+F8 are already split out.
4. **F2 — fan_out/panel.** Three substrates to unify behind m4 dispatch; clean *interface* but touches three
   orchestration modules. Could pair with F3 (both are dispatch-fan-out shaped) in one sub-milestone.

F1, F3, F4, F6, F9 are tractable as a single "node-library formalization" sub-milestone (they're mostly
already-extracted topology + content-binding work).
