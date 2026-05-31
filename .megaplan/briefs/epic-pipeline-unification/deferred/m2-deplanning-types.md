# Megaplan brief — M2: De-planning the types + the typed Port (THE KEYSTONE)

**Status:** regenerated against current code 2026-05-29 (`megaplan/_pipeline/*`, `megaplan/_core/state.py`).
Parent: `.megaplan/briefs/pipeline-unification-EPIC.md` (M2 entry EPIC:138–141; **Structural pieces #1 — the Port,
EPIC:95–101 — the keystone**; "Primitive contract — evidence-backed" EPIC:56–77 — all authoritative).
Evidence sources: `.megaplan/briefs/validation/decision/abstraction-stress-test.md` (verdict: verbs are at the right
altitude, the **types** are planning-shaped) and `.megaplan/briefs/validation/interrogation/SYNTHESIS.md` (**Theme A —
the #1 / highest-convergence finding: there is no typed data contract between composed pieces**; missing
abstraction **#1** — the typed Port + binder + StateDelta). Tier: apex · thorough/high.

> This brief was promoted to **keystone**. Two bodies of work land together in M2: (a) the original
> de-planning type work (de-verdict `reduce`/`JoinFn`, add `select`/`Reduce[T]`, wire the dropped loop
> predicate) and (b) **the typed Port + binder + StateDelta** — missing-abstraction #1, the noun every other
> named gap is a verb about (SYNTHESIS:139–149). M2 is the **one cheap moment** to make the data type `T`
> typed *across the composition boundary* instead of erased into `state["specs"]`: M2 already rewrites every
> join/reduce signature, so it touches the same surface the Port retypes (SYNTHESIS:297–299). Arriving with
> the Port in M5/M6 makes it a rewrite of code those milestones just shipped.

---

## Outcome

When M2 is done:

1. **The general pieces carry no planning vocabulary.** `reduce`/`JoinFn`/`PromoteFn` and the concrete joins
   return **structured data**, never `GateRecommendation`. The 4-verdict mapping
   (`proceed|iterate|tiebreaker|escalate`) lives only in a **planning-app binding**. **CI grep gate: ZERO
   `GateRecommendation` references survive in SDK-side `_pipeline` modules** — confirmed live today in **6
   modules** (`pattern_types.py`, `pattern_joins.py`, `pattern_topology.py`, `types.py`, `subloop.py`,
   `stages/tiebreaker.py`). Partial conversion is **worse than none** — it hides coupling behind a green gate
   (SYNTHESIS:133, 352–354).

2. **`select(items, rule) -> SelectionResult(winner|subset, losers, scores, cleared)`** exists as a peer to
   `vote`/`judge` — the #1 missing primitive (4/5 sketches, stress-test §136). A data-valued **`Reduce[T]`**
   exists, including a **generative** form whose output is the next `fan_out`'s input spec list.

3. **THE KEYSTONE — the typed Port + binder + StateDelta.** A `Port = (name, kind: artifact|value|stream,
   schema, cardinality, version)`; the `Step` Protocol gains `produces`/`consumes`; `builder.build()`
   resolves every `consumes` against an upstream `produces` **at build time** and **fails the build** on a
   missing / typo'd / mistyped dependency (replacing the never-validated `_input_refs`); the executor **binds**
   ports at runtime from resolved upstream outputs (killing the `step_helpers.py:104` `v1.md` silent
   fallback); a **`StateDelta`** (`replace|accumulate|deep-merge` + version, **CAS not flat-key LWW** —
   replacing `executor_owned_keys`) carries cross-step state. `last_fanout_results` becomes a **typed Port the
   fan-out join writes** (it exists nowhere today — confirmed empty grep).

4. **`iterate_until`'s predicate is wired through** (no longer `del`'d at `pattern_topology.py:288`) and a
   **stop-predicate library** ships (`plateau`, `max_iters`, `threshold_reached`, `no_improvement`).

**The load-bearing proof (acceptance #1, EPIC:79–88; SYNTHESIS:249–252, 357–358):** a deliberately
**NON-planning toy** — a `select`-tournament — built entirely on these pieces, with two acceptance checks:
(i) **NO toy hand-rolls inter-step plumbing — all data crosses a declared Port** (no `state["specs"]`-style
string channel, no `plan_dir`/`v1.md` path convention); (ii) **NO `GateRecommendation` / 4-verdict reference
anywhere in it**. If the tournament can be written only by hand-wiring a string channel, the Port failed and
M2 failed.

---

## Scope (work items, each tied to current file:line evidence)

### Part A — De-planning the value types

**W1 — `JoinFn`/reduce return structured DATA (de-verdict the join surface).**
- Today `JoinFn = Callable[[list[StepResult], StepContext], StepResult]` (`pattern_types.py:19`) and BOTH
  concrete joins build `PipelineVerdict(score=1.0, recommendation=<GateRecommendation>)` + `next=<verdict>`
  (`pattern_joins.py:40–41, 83–84`) — they collapse a panel into the closed 4-verdict vocabulary, with
  `chosen="tiebreaker"` hard-coded as the no-quorum fallback (`pattern_joins.py:31–39, 71–82`).
- Introduce a structured result the join writes instead of a verdict-shaped `StepResult`: a `ReduceResult` /
  `Aggregate[T]` carrying `value: T` + per-input `scores`/tally + provenance, surfaced via a **Port**
  (W6), NOT via `verdict.recommendation`. `majority_vote`/`weighted_vote` return the tally + the winning
  *label as data*; `PromoteFn` (`pattern_types.py:16`, returns `GateRecommendation`) loses its return type.

**W2 — `select(items, rule) -> SelectionResult`.**
- No selection node exists today; the only aggregators are `majority_vote`/`weighted_vote`, both
  collapse-to-one and verdict-typed. Stress-test ranks this the **single biggest gap (4/5)** (§136 #1).
- Add `SelectionResult = (winner|subset, losers[], scores, cleared: bool)` and `select(items, rule)` where
  `rule` selects top-1, top-k, or threshold-clears. `cleared` distinguishes "a winner met the bar" from
  "nobody qualified" (red/blue zero-survivors, bounty no-bid-cleared). Distinct from `judge` (scores one
  artifact) and `vote` (collapse-to-one-label).

**W3 — Data-valued + generative `Reduce[T]`.**
- Add `Reduce[T]`: aggregate `list[StepResult]` → arbitrary data, distinct from the verdict-route family.
  AND a **generative** reduce (one-to-many; K winners → N children). Today
  `pattern_dynamic._extract_specs_from_result` + `dynamic_fanout` read a spec list off a `StepResult` — wire
  the generative reduce to emit into that channel **via a typed Port (W6)**, NOT the untyped
  `state_patch["specs"]` key that erases `T` the instant it crosses the boundary (SYNTHESIS:38–41).

**W4 — Wire the dropped loop predicate + ship a stop-predicate library.**
- `iterate_until` (`pattern_topology.py:269`) does `del condition, max_iterations` at `:288` — the predicate
  is documentation-only (docstring `:279`); the wrapped Step must re-derive it. **Stop discarding it:**
  thread `condition` + `max_iterations` so the loop evaluates a real DATA predicate over
  `{state, last_fanout_results, iteration}` (now a typed Port, W6). This is the **graph-driver** loop only;
  the standalone loop **runtime/driver is M3** (EPIC:144).
- Ship `megaplan/_pipeline/pattern_stops.py` peer to `pattern_joins.py`: `plateau`, `max_iters`,
  `threshold_reached`, `no_improvement` (stress-test §156 #8). Each a pure `Callable[[LoopState], bool]`.

**W5 — Move the 4-verdict mapping OUT of general types, INTO the planning app.**
- After W1, the joins return data. Add a thin **planning binding** (e.g.
  `planning_reduce(aggregate) -> GateRecommendation`) co-located with `planning.py` mapping a structured tally
  → `proceed|iterate|tiebreaker|escalate`. `planning.py`'s gate stage consumes it; `subloop.py`'s
  `_DEFAULT_PROMOTE` and `stages/tiebreaker.py` stay planning-local but **de-typed off the shared alias**.
  `GateRecommendation` stays defined in `types.py` only for the `kind="gate"` executor **edge dispatch**
  (gate is a confirmed core primitive, EPIC:65) — but ZERO references survive in the SDK-side join/reduce/
  topology surface (W1's CI gate).

### Part B — THE KEYSTONE: typed Port + binder + StateDelta

**W6 — The typed Port + `produces`/`consumes` on the Step Protocol.**
- The `Step` Protocol (`types.py:167–183`) carries `name`, `kind`, `prompt_key`, `slot`, `run` — and
  **nothing about what a node consumes or produces** (SYNTHESIS:35–37). The advertised wiring DSL
  (`builder.py` `inputs=[...]`) is stashed as `_input_refs` (`builder.py:146, 178`) and **never validated**.
- Define `Port = (name, kind: artifact|value|stream, schema: type|ContentType, cardinality, version)` and
  extend the `Step` Protocol with `produces: tuple[Port, ...]` / `consumes: tuple[PortRef, ...]`. **Reserve
  the `version` field on the Port now** (SYNTHESIS:366) so the epic can keep reshaping provisional types
  while versioning is not a later retrofit. `StepResult.outputs` (a `Mapping[str, Path]`, `types.py:161`) and
  the `Reduce[T]`/`SelectionResult` values are surfaced as named Ports.

**W7 — Build-time `consumes`↔`produces` resolution (the checked DAG).**
- `builder.build()` resolves every `consumes` against an upstream `produces`, building a checked DAG, and
  **fails `build()`** on a missing dep, a typo'd name, a mistyped/incompatible schema, or a cardinality
  mismatch — replacing the silently-stashed-and-ignored `_input_refs` (`builder.py:146, 178`). This is the
  build-time half that turns "composition is a filesystem convention" into a real contract (SYNTHESIS:139–144).

**W8 — Runtime port binding (kills the `v1.md` fallback) + `StateDelta` CAS merge.**
- The executor today never binds a step's inputs from a predecessor's outputs — `_verify_outputs`
  (`executor.py:137`) is **existence-only** (`if not Path(path).exists()`), called at `:255` and `:361`;
  inputs are resolved by path convention with a **silent fallback**: `step_helpers.py:104`
  `resolved[ref] = ctx.plan_dir / ref / "v1.md"` — to a file that may not exist (named `v1.md` literally; the
  fallback the SYNTHESIS calls the smoking gun of Theme A).
- The executor **binds** each step's `consumes` Ports at runtime from resolved upstream `produces` outputs;
  an unresolved/mistyped port is a **loud bind-time error** (it cannot reach the build-clean DAG, but the
  runtime bind still asserts), NOT a guessed `v1.md` path.
- Replace the flat-key LWW merge — today `state.update(patch); executor_owned_keys.update(patch.keys())`
  (`executor.py:257–259`) feeding `write_plan_state(mode="executor-key-merge", executor_owned_keys=...)`
  which blind-overwrites each owned key (`state.py:364–373`) — with a **`StateDelta`**
  (`replace | accumulate | deep-merge` + version stamp, **compare-and-set** not last-writer-wins). This is
  the same Port abstraction on the state side (SYNTHESIS:148–149); `accumulate` also gives the red/blue
  corpus / genetic population growth the LWW merge cannot express (stress-test §94).

**W9 — `last_fanout_results` as a typed Port the fan-out join writes.**
- `last_fanout_results` **exists nowhere in the codebase** (confirmed: grep returns only brief lines /
  SYNTHESIS:41). It is the promised in-memory channel the (M3) loop predicate reads. In M2 the **fan-out
  join writes a typed `value`-kind Port** named `last_fanout_results`; W4's wired `iterate_until` predicate
  reads it as a Port (not a string key). This is the concrete proof the Port carries fan-out results across
  the loop boundary without a hand-rolled channel.

---

## Locked decisions

- `reduce`/`JoinFn`/`PromoteFn` return **structured data** (`ReduceResult`/`Aggregate[T]`); they MUST NOT
  name `GateRecommendation`. The 4-verdict mapping is a **planning-app binding** (EPIC:96, 138–139;
  stress-test §158, §188). **CI grep gate: ZERO `GateRecommendation` in SDK-side `_pipeline` modules**
  (6 modules confirmed live); partial conversion is worse than none (SYNTHESIS:133, 352).
- `select` is a **first-class peer** to `vote`/`judge`, returning `(winner|subset, losers, scores, cleared)`.
- `Reduce[T]` includes a **generative** form whose output rides a **typed Port**, not `state["specs"]`.
- **The typed Port + binder + StateDelta lands in M2**, alongside `Reduce[T]`/`select` — it is the one cheap
  moment to type `T` across the boundary (EPIC:101; SYNTHESIS:297–299). The Port's `version` field and the
  `StateDelta` revision stamp are **reserved now** (SYNTHESIS:366).
- Build-time resolution **fails `build()`** on missing/typo'd/mistyped/cardinality-wrong deps; the executor
  **binds** at runtime; the `step_helpers.py:104` `v1.md` fallback is **removed** (not softened).
- `StateDelta` replaces `executor_owned_keys` flat-key LWW with **CAS + (replace|accumulate|deep-merge)**.
- `iterate_until`'s predicate is **threaded through** (stop `del`-ing it); stop predicates are pure data
  callables in a new `pattern_stops.py`. The Port-aware predicate reads `last_fanout_results` as a Port.
- **Anti-scope (M3+):** the real `loop` runtime/driver, the topology-realizer, `run(cmd)`/oracle evidence,
  `snapshot`/`restore`/state-evolution axis, gate-consequence parameterization, the policy spine /
  RecoveryPolicy / budget authority, the 2-axis driver model. M2 = P0 + missing-abstraction #1 only.

## Open questions

1. **Biggest blocking unknown — how far does the Port's build-time resolution reach into the runtime bind
   without M3's realized graph?** Robustness levels do node/edge **rewriting** (`_ROBUSTNESS_OVERRIDES` adds/
   deletes critique+gate nodes; SYNTHESIS:48–55), so the DAG `build()` checks at one robustness level may not
   be the DAG that actually runs at another. The realized-graph layer is explicitly M3 (EPIC:143). M2 must
   resolve `consumes`↔`produces` **per realized robustness level it is handed**, or scope build-time checking
   to the static pre-rewrite graph and rely on the runtime bind to catch rewrite-induced gaps loudly. **Lean:
   check against the fully-rewritten graph for each level exercised by the parity gate; defer mid-run
   re-realization to M3.** This is the seam most likely to force a redesign — resolve before building W7.
2. Exact name/shape of the aggregate type (`ReduceResult` vs `Aggregate[T]`) and whether the Port value rides
   a new frozen dataclass in `types.py` vs `StepResult.outputs`. Lean: a new frozen `ReduceResult` surfaced as
   a typed Port so the data path is visible, not smuggled through the verdict-shaped `StepResult`.
3. `StateDelta` CAS conflict policy on a real LWW collision today — fail loud vs last-write-wins-with-warn.
   Lean: fail loud in-process (the lost-update class a2 found, SYNTHESIS:41–44); the leased/transactional
   Store is M4, so M2's CAS is single-process optimistic versioning.
4. Whether `select`'s `rule` is an enum (`top_1|top_k|threshold`) or a `Callable`. Lean: a callable with the
   three as named constructors, mirroring the join factories.

## Constraints

- **No planning behavior change.** The parity gate (`tests/test_pipeline_parity.py`, EPIC:137) MUST stay
  green through M2 — the planning binding produces byte-identical decisions to today's in-line verdict
  mapping; the Port binder produces the same artifacts on the planning happy path.
- **Parity gate is structurally blind to the substrate swap** (SYNTHESIS:126–133, Theme G). The Port + CAS
  StateDelta change the *channel*, which the SHA256 happy-path gate cannot see. Add a **direct unit assertion
  on the binder** (an unresolved/mistyped port fails build; a CAS conflict is caught) — do NOT rely on the
  parity gate to prove the Port works.
- Frozen-types discipline: `types.py` shapes were frozen end of Sprint 1; any new shared dataclass (`Port`,
  `ReduceResult`, `SelectionResult`, `StateDelta`) is **additive** + documented as a revision note. Existing
  `StepResult`/`PipelineVerdict` fields are not removed.
- Back-compat shims: `JoinFn`/`PromoteFn` are public aliases consumed by `pattern_topology.py`,
  `pattern_dynamic.py`, `subloop.py`, `planning.py`, and tests — update all consumers in lockstep; no
  half-typed alias. Extend the `Step` Protocol additively so existing steps (`AgentStep`, `PanelReviewerStep`)
  satisfy `produces`/`consumes` with sane defaults during migration.
- Don't dogfood off an editable install (EPIC:178); pin the engine.

## Done criteria (testable)

1. `grep -rn GateRecommendation megaplan/_pipeline/{pattern_joins,pattern_types,pattern_topology,subloop}.py`
   (+ `pattern_stops.py`, `pattern_select.py`) returns **zero hits**; the CI grep gate enforces ZERO in all
   SDK-side `_pipeline` modules (allow-list: `types.py` edge-dispatch + the planning binding only).
   `majority_vote`/`weighted_vote` return a structured tally + winning label as DATA (unit test asserts no
   `verdict.recommendation` is set).
2. `select(items, rule)` returns `SelectionResult(winner|subset, losers, scores, cleared)`; a unit test
   covers top-1, top-k, and the `cleared=False` (nobody qualified) case.
3. A `Reduce[T]` data-reduce returns a non-verdict value; a **generative** reduce produces a spec list that
   `dynamic_fanout` consumes **through a typed Port** (round-trip test; assert `T` survives — not erased
   through `state["specs"]`).
4. **Port build-time resolution:** `build()` **raises** on a `consumes` with no matching upstream `produces`,
   on a typo'd port name, on a schema/cardinality mismatch — one test per failure mode. A correctly-wired
   pipeline builds clean.
5. **Runtime binding + no `v1.md` fallback:** `grep -n 'v1.md' megaplan/_pipeline/step_helpers.py` shows the
   fallback is **gone**; a test proves a step's `consumes` Port is bound from the upstream `produces` output
   (not a guessed path), and an unbindable port errors loudly.
6. **`StateDelta` CAS:** a test drives two writers to the same key; LWW would lose an update, the
   `accumulate` delta does not; a stale-version write is rejected (CAS), replacing `executor_owned_keys`
   behavior (`executor.py:257–259`, `state.py:364–373`).
7. `iterate_until` no longer `del`s `condition`/`max_iterations`; a test drives a loop that **terminates on
   the data predicate over `last_fanout_results` (a Port)**, not a re-derived verdict. `pattern_stops.py`
   ships `plateau`, `max_iters`, `threshold_reached`, `no_improvement`, each unit-tested as a pure data
   callable.
8. The 4-verdict mapping is a planning-app binding; `planning.py`'s gate consumes it; the parity gate stays
   green (decision + artifact parity unchanged).
9. **THE acceptance test — the non-planning `select`-tournament toy** (e.g.
   `megaplan/_pipeline/demos/tournament.py` + `tests/_pipeline/test_tournament_toy.py`): each round fan-outs
   matchups, a data-`reduce` scores them, `select` advances winners / drops losers, a stop predicate
   (`no_improvement` or `len(remaining)==1`) ends it, producing a champion. The test asserts:
   (a) **zero `GateRecommendation`/4-verdict references** in the toy's source (grep), and it imports nothing
   from the planning binding;
   (b) **NO inter-step data is hand-wired — every cross-step datum crosses a declared Port** (assert no
   `state_patch["..."]` string-channel and no `plan_dir`/`v1.md` path convention in the toy; grep + a binder
   audit). This is the load-bearing proof both that the vocabulary is de-planned AND that composition is real
   (EPIC:141; SYNTHESIS:249–252, 357–358).

## Touchpoints (files to change)

- `megaplan/_pipeline/pattern_types.py` (`JoinFn` :19, `PromoteFn` :16 — drop `GateRecommendation`).
- `megaplan/_pipeline/pattern_joins.py` (`majority_vote` :17, `weighted_vote` :46 — return structured data).
- `megaplan/_pipeline/types.py` — additive `Port`, `ReduceResult`, `SelectionResult`, `StateDelta` + the
  `produces`/`consumes` extension to the `Step` Protocol (:167–183); revision note; keep `GateRecommendation`
  (:~76) for the gate edge-dispatch only.
- `megaplan/_pipeline/builder.py` (:146, :178 — `_input_refs` becomes resolved/checked `consumes`; `build()`
  performs DAG resolution).
- `megaplan/_pipeline/executor.py` (`_verify_outputs` :137 + call sites :255/:361 — add port binding;
  :257–259 — replace `executor_owned_keys` LWW with `StateDelta` CAS).
- `megaplan/_pipeline/step_helpers.py` (:104 — **remove** the `v1.md` fallback; resolution moves to the binder).
- `megaplan/_core/state.py` (write_plan_state `:330–373` — `StateDelta`-backed CAS path replacing
  `executor-key-merge`/`executor_owned_keys`).
- `megaplan/_pipeline/pattern_topology.py` (`iterate_until` :269/:288 — thread predicate; consensus loop :174).
- `megaplan/_pipeline/pattern_dynamic.py` (`_extract_specs_from_result` :52, `dynamic_fanout` :148 —
  generative reduce → typed Port channel; `last_fanout_results` Port written by the fan-out join).
- NEW `megaplan/_pipeline/pattern_select.py` (the `select` node), `megaplan/_pipeline/pattern_stops.py`
  (stop-predicate library), `megaplan/_pipeline/demos/tournament.py` (the toy).
- `megaplan/_pipeline/planning.py` (gate :68–71/:113–116) + NEW planning verdict-mapping binding;
  `megaplan/_pipeline/subloop.py` (`_DEFAULT_PROMOTE` :48,:68) + `stages/tiebreaker.py` — de-typed off the
  shared alias, stay planning-local.
- Tests: extend `tests/_pipeline/test_patterns.py`, `test_dynamic_primitives.py`; NEW binder tests (DC #4–6),
  tournament-toy test (DC #9), CI grep-gate test (DC #1).

## Anti-scope

NO real `loop` runtime/driver — M2 wires the predicate through the existing graph-sugar `iterate_until`; the
standalone loop driver is **M3** (EPIC:144). NO **topology-realizer / realized graph** — M2 resolves the
Port DAG per handed robustness level and defers mid-run re-realization to M3 (EPIC:143; the realized-graph
layer is missing-abstraction #2). NO `run(cmd)`/oracle evidence, NO `snapshot`/`restore`/state-evolution
axis (M2 ships `StateDelta` CAS + `accumulate`, NOT reversibility), NO `budget`/depletable resource, NO
gate-consequence parameterization (`advance|revise_in_place|restore_and_diverge|escalate`) — all **M3**
(EPIC:143–145). NO **policy spine** (`RecoveryPolicy`, the single budget authority, the observability
contract) — **M4** (EPIC:146–149; missing-abstraction #3). NO `dispatch`/`emit`/`config` service work — **M4**.
NO run-outcome / control vocabulary, NO eviction of planning's `STATE_*` from the control plane — **M5c/M6**
(missing-abstraction #4). NO pack relocation / `_BUILTIN_NAMES` removal / manifest-first discovery — **M6**.
NO change to planning's verdict vocabulary or its observable decisions.
