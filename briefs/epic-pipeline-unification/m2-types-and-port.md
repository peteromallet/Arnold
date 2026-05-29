# Megaplan brief — M2: De-planning types + THE TYPED PORT + Contract Ledger + StateDelta (CAS) + R3 taint-in-hash

**Status:** regenerated against current code 2026-05-29 (`megaplan/_pipeline/*`, `megaplan/_core/state.py`).
Tier: **apex · thorough/high** (`[T1]`, on the critical path's near-branch — M3 hard-depends on it).
Authoritative parents:
- `briefs/validation/sequencing/PROGRAM.md` **M2 entry (PROGRAM:105–123)** — delivers the Port + Contract
  Ledger (R3) + StateDelta(CAS) + taint-in-hash; depends_on **M1** (Port's `artifact` kind refs the M1 log;
  taint enters the log's hash); runs **∥ M2.5** off the M1 base; merge gate **grep=0 AND all consumers green
  together — never a partial merge** (PROGRAM:122).
- `briefs/pipeline-unification-EPIC.md` — the data model (EPIC:51–67: `Port = kind × content-type × schema`
  + the binder + open MIME-like registry) and Structural-piece #1 (EPIC:174–184, the keystone).
- `briefs/validation/committed-uu/SYNTHESIS.md` — the **Contract Ledger** organ (SYNTHESIS:267–273), the
  **Port** reshaper #3 (taint a propagating lattice INSIDE the content-hash, SYNTHESIS:360–362), UU#4
  (cache-collision-launders-taint, SYNTHESIS:72–82), UU#5 (no type system → feral graphs, SYNTHESIS:85–93).
- `briefs/validation/human-blockers/REGISTER.md` — all M2 open questions resolved to defaults (REGISTER:105).
- PRIOR DRAFT `briefs/epic-pipeline-unification/m2-deplanning-types.md` — reused/re-aimed; all code-cites
  below re-verified against current code (file:line confirmed live 2026-05-29).

> **Re-aim vs prior draft:** the prior M2 brief is correct and grounded but predates the sequenced PROGRAM,
> which lands TWO additional organs at M2: the **Contract Ledger** (the type *system* the binder reads, not
> just the Port dataclass) and **R3 taint-in-hash** (taint enters the content-hash NOW, before any untrusted
> value shares the store — UU#4 is unrecoverable retrofit). It also frames every piece under the strangler
> `{old-path default-ON, new-path default-OFF behind a flag}` discipline. This brief folds those in.

---

## Outcome

When M2 is done, behind the default-OFF flag `MEGAPLAN_TYPED_PORTS` (old string/state-dict plumbing stays
default-ON and live):

1. **The general pieces carry no planning vocabulary.** `reduce`/`JoinFn`/`PromoteFn` and the concrete joins
   return **structured data**, never `GateRecommendation`. The 4-verdict mapping
   (`proceed|iterate|tiebreaker|escalate`) lives only in a **planning-app binding**. **CI grep gate: ZERO
   `GateRecommendation` references survive in SDK-side `_pipeline` modules** — confirmed live today in **6
   modules** (`pattern_types.py`, `pattern_joins.py`, `pattern_topology.py`, `types.py`, `subloop.py`,
   `stages/tiebreaker.py`). Partial conversion is **worse than none** (SYNTHESIS:133-style, hides coupling
   behind a green gate).

2. **`select(items, rule) -> SelectionResult(winner|subset, losers, scores, cleared)`** exists as a peer to
   `vote`/`judge` — the #1 missing primitive (4/5 sketches). A data-valued **`Reduce[T]`** exists, including a
   **generative** form whose output is the next `fan_out`'s input spec list.

3. **THE TYPED PORT.** `Port = (kind ∈ {value, artifact, stream} × content-type × schema)` + envelope-ready
   `version`. **kind:** `value` = inline-in-the-M1-log; `artifact` = **by-content-hash reference** to a blob
   store, **never inlined**; `stream` reserved. **content-type** = an **OPEN, MIME-like registry**
   (`text/markdown`, `image/png`, `application/x-git-diff`, `…/verdict+json`) — a new domain registers a
   content-type; the core never changes (EPIC:53–57). **schema** = a content-hashed schema for structured
   `value`s (the Contract Ledger holds it); for `artifact`s the content-type IS the contract. The `Step`
   Protocol gains `produces`/`consumes`.

4. **THE CONTRACT LEDGER (R3) + binder.** A content-hashed registry of Port contracts + the **legal coercions**
   between them. `builder.build()` runs the binder: it resolves every `consumes`↔upstream `produces` **at
   build time** (structural + content-type + legal-coercion match) and **fails admission LOUDLY with a
   machine-readable repair gradient** ("B wants X, A emits Y; legal moves: …") — replacing the
   never-validated `_input_refs` (`builder.py:146,178`) and **killing the `step_helpers.py:104` silent `v1.md`
   fallback**: a missing/typo'd/mistyped dep is a loud `build()` failure, not a guessed path.

5. **R3 — TAINT ENTERS THE CONTENT-HASH.** Taint is a propagating lattice that lives **inside** the Port's
   content-hash (not beside the value), seeded as a no-op-propagating field NOW (SYNTHESIS:360–362, principle
   #4). Two identical-byte values with different taint hash **differently**, so dedup cannot launder a tainted
   copy into a trusted slot (UU#4, SYNTHESIS:72–82). This is the un-retrofittable seed; M2 is the last cheap
   moment — once an untrusted value shares the store it is unrecoverable.

6. **StateDelta (CAS).** `StateDelta = (replace | accumulate | deep-merge) + version stamp`, **compare-and-set
   not last-writer-wins** — replacing `executor_owned_keys` flat-key LWW (`executor.py:258–260,363–365`;
   `state.py:361–373` `executor-key-merge`). `accumulate` gives growth (corpus/population) the LWW merge
   cannot express.

7. **`iterate_until`'s predicate is wired through** (no longer `del`'d at `pattern_topology.py:288`) and a
   **stop-predicate library** ships (`plateau`, `max_iters`, `threshold_reached`, `no_improvement`).
   `last_fanout_results` becomes a **typed `value`-kind Port the fan-out join writes** (exists nowhere today —
   confirmed empty grep).

**The load-bearing proof (acceptance):** a deliberately **NON-planning select-tournament** built entirely on
these pieces — (i) **NO hand-rolled inter-step plumbing — every cross-step datum crosses a declared Port** (no
`state["specs"]` string channel, no `plan_dir`/`v1.md` path convention); (ii) **NO `GateRecommendation` /
4-verdict reference anywhere in it**. If the tournament can be written only by hand-wiring a string channel,
the Port failed and M2 failed.

---

## Scope (work items, each tied to current file:line)

### Part A — De-planning the value types (under the grep gate)

**W1 — `JoinFn`/reduce return structured DATA.** `JoinFn = Callable[[list[StepResult], StepContext],
StepResult]` (`pattern_types.py:19`) and both concrete joins build `PipelineVerdict(score=1.0,
recommendation=chosen)` + `next=chosen` (`pattern_joins.py:40–41` `majority_vote` :17, `weighted_vote` :46),
with `chosen="tiebreaker"` hard-coded as the no-quorum fallback (`pattern_joins.py:32,37,73,77`). Introduce a
structured `ReduceResult`/`Aggregate[T]` (value `T` + per-input scores/tally + provenance) surfaced via a Port
(W6), NOT via `verdict.recommendation`. `PromoteFn` (`pattern_types.py:16`, returns `GateRecommendation`)
loses its return type.

**W2 — `select(items, rule) -> SelectionResult`.** No selection node exists. Add `SelectionResult =
(winner|subset, losers[], scores, cleared: bool)`; `rule` selects top-1 / top-k / threshold. `cleared`
distinguishes "a winner met the bar" from "nobody qualified." Distinct from `judge` (scores one) and `vote`
(collapse-to-one-label).

**W3 — Data-valued + generative `Reduce[T]`.** Add `Reduce[T]` (aggregate → arbitrary data) AND a generative
reduce (K winners → N child specs). Today `pattern_dynamic._extract_specs_from_result:52` reads `specs` off
`result.state_patch["specs"]` (`:56–57`) or `outputs["specs"]` (`:62`). Wire the generative reduce to emit
into that channel **via a typed Port (W6)**, NOT the untyped `state_patch["specs"]` key that erases `T`.

**W4 — Wire the dropped loop predicate + stop-predicate library.** `iterate_until` (`pattern_topology.py:269`)
does `del condition, max_iterations` at `:288` — the predicate (params `:272–273`) is doc-only. Thread it so
the loop evaluates a real DATA predicate over `{state, last_fanout_results, iteration}`. (Note `consensus_loop`
`:174` similarly `del`s `until_condition`; thread there too.) Graph-driver loop only — the standalone loop
runtime is **M3**. Ship `megaplan/_pipeline/pattern_stops.py`: `plateau`, `max_iters`, `threshold_reached`,
`no_improvement`, each a pure `Callable[[LoopState], bool]`.

**W5 — Move the 4-verdict mapping OUT of general types, INTO the planning app.** Add a thin planning binding
`planning_reduce(aggregate) -> GateRecommendation` co-located with `planning.py`; `planning.py`'s gate stage
consumes it; `subloop.py` `_DEFAULT_PROMOTE` and `stages/tiebreaker.py` stay planning-local but **de-typed off
the shared alias**. `GateRecommendation` stays defined in `types.py:76` ONLY for the `kind="gate"` executor
edge-dispatch (`types.py:45`) — the grep-gate allow-list.

### Part B — THE TYPED PORT + Contract Ledger + StateDelta + taint-in-hash

**W6 — The typed Port + `produces`/`consumes` on the Step Protocol.** The `Step` Protocol (`types.py:168–183`)
carries `name`, `kind`, `prompt_key`, `run` — **nothing about consume/produce**. The DSL `inputs=[...]` is
stashed as `_input_refs` (`builder.py:146,178` on `AgentStep`/`PanelReviewerStep`) and **never validated**.
Define `Port = (name, kind: value|artifact|stream, content-type, schema, cardinality, version)`; extend the
Protocol additively with `produces: tuple[Port,...]` / `consumes: tuple[PortRef,...]`. `value` = inline in the
M1 log; `artifact` = by-content-hash ref (never inlined); the **content-type registry is open** (a small dict
the core never edits to add a domain). `StepResult.outputs` (`types.py:161`, a `Mapping[str,Path]`) and the
`Reduce[T]`/`SelectionResult` values surface as named Ports.

**W7 — The Contract Ledger + build-time `consumes`↔`produces` resolution (the checked DAG).** Land a
content-hashed **Contract Ledger** = Port-contract registry + a **legal-coercions** table (the type *system*,
SYNTHESIS:267–273). `builder.build()` (`builder.py:400`) runs the binder against it: resolves every `consumes`
to an upstream `produces` (structural + content-type + coercion match) and **fails `build()`** on missing /
typo'd / mistyped / cardinality-wrong deps, returning a **machine-readable repair gradient** (not a bare
raise) so an LLM author can climb it — replacing `_input_refs`.

**W8 — Runtime port binding (kills `v1.md`) + R3 taint-in-hash + StateDelta CAS.** `_verify_outputs`
(`executor.py:137–139`) is existence-only (`if not Path(path).exists()`), called at `:255` and `:361`; inputs
resolve by path convention with a **silent fallback** `step_helpers.py:104` `resolved[ref] = ctx.plan_dir /
ref / "v1.md"`. (a) The executor **binds** each step's `consumes` Ports at runtime from resolved upstream
`produces`; an unresolved/mistyped port is a **loud bind-time error**, not a guessed `v1.md`. (b) **Taint
enters the content-hash:** the Port's content-hash includes its taint lattice value; propagation is a no-op
join hook seeded now (every produced Port carries the lattice-join of its consumed Ports' taint). (c) Replace
the flat-key LWW merge — `state.update(patch); executor_owned_keys.update(patch.keys())` (`executor.py:258–260,
363–365`) feeding `write_plan_state(mode="executor-key-merge")` which blind-overwrites each owned key
(`state.py:361–373`) — with a **StateDelta** (`replace|accumulate|deep-merge` + version, CAS).

**W9 — `last_fanout_results` as a typed Port the fan-out join writes.** It exists nowhere (confirmed empty
grep). The fan-out join writes a typed `value`-kind Port named `last_fanout_results`; W4's wired predicate
reads it as a Port — the concrete proof the Port carries fan-out results across the loop boundary with no
hand-rolled channel.

---

## Locked decisions

- `reduce`/`JoinFn`/`PromoteFn` return **structured data**; MUST NOT name `GateRecommendation`. 4-verdict
  mapping = a **planning-app binding**. **CI grep gate: ZERO `GateRecommendation` in SDK-side `_pipeline`
  modules** (6 confirmed live; allow-list = `types.py` edge-dispatch + the planning binding only).
- `select` is a first-class peer to `vote`/`judge`, returning `(winner|subset, losers, scores, cleared)`.
- `Reduce[T]` includes a generative form whose output rides a typed Port, not `state["specs"]`.
- **The Port + Contract Ledger + binder + StateDelta land in M2** — the one cheap moment to type `T` across
  the boundary (EPIC:184). Port `version` field + StateDelta revision stamp **reserved now** (SYNTHESIS:366).
- **content-type is an OPEN, MIME-like registry** (EPIC:53–57); meaning lives in the rubric/prompt, never the
  type; the type system is "just-strong-enough for machine-authorship admission + repair + taint/cache keys."
- **Taint enters the content-hash NOW** (R3, no-op propagation seed) — the un-retrofittable UU#4 seed.
- Build-time binding **fails `build()`** with a **repair gradient** on bad deps; the executor binds at runtime;
  the `step_helpers.py:104` `v1.md` fallback is **removed** (not softened).
- `StateDelta` (CAS + `replace|accumulate|deep-merge`) replaces `executor_owned_keys` LWW. CAS conflict =
  **fail loud in-process** (the leased/transactional Store is M4; M2's CAS is single-process optimistic
  versioning).
- **Strangler discipline:** all of B lands behind default-OFF `MEGAPLAN_TYPED_PORTS`; the old string/state-dict
  path stays default-ON; **no old-path deletion in this PR** (the `v1.md` removal rides behind the flag, with
  the old resolver retained on the flag-OFF branch and retired only after ≥1 dual-green milestone).

## Open questions (each RESOLVED to its default — zero human blockers, REGISTER:105)

1. **Biggest unknown — how far does build-time resolution reach without M3's realized graph?** Robustness
   levels rewrite nodes/edges (`_ROBUSTNESS_OVERRIDES`), so the DAG `build()` checks at one level isn't the DAG
   that runs at another. **DEFAULT:** check `consumes`↔`produces` **against the fully-rewritten graph per
   robustness level the parity gate exercises**; defer mid-run re-realization to M3; the runtime bind (W8)
   catches any rewrite-induced gap loudly. (REGISTER:105 "check vs fully-rewritten graph per parity-gate level,
   defer re-realization to M3.")
2. **Aggregate type shape** (`ReduceResult` vs `Aggregate[T]`; new dataclass vs `StepResult.outputs`).
   **DEFAULT:** a new **frozen `ReduceResult` dataclass surfaced as a typed Port** (REGISTER:105).
3. **CAS conflict policy on a real LWW collision.** **DEFAULT:** **fail loud in-process** (REGISTER:105 DC#6).
4. **`select.rule` enum vs Callable.** **DEFAULT:** a **Callable with `top_1`/`top_k`/`threshold` named
   constructors** (REGISTER:105).
5. **content-type registry shape / where it lives.** **DEFAULT:** an open module-level dict in `types.py`
   seeded with the four EPIC examples; adding a content-type is a one-line code change, never a core edit.
6. **`GateRecommendation` allow-list scope.** **DEFAULT:** `types.py` edge-dispatch + the planning binding
   only, enforced by the grep gate (REGISTER:105 DC#1).

## Constraints

- **No planning behavior change.** The parity gate (`tests/test_pipeline_parity.py`) MUST stay green: the
  planning binding produces byte-identical decisions to today's in-line verdict mapping; the binder produces
  the same artifacts on the planning happy path.
- **The parity gate is structurally blind to the substrate swap** (it is a SHA256 happy-path gate; the Port +
  CAS + taint-in-hash change the *channel*). It is **NOT** the retirement authority. Add **direct unit
  assertions on the binder** (unresolved/mistyped port fails build with a repair gradient; CAS conflict caught;
  differently-tainted identical bytes hash differently) — never rely on parity to prove the Port/taint works.
- **Frozen-types discipline:** every new shared dataclass (`Port`, `ReduceResult`, `SelectionResult`,
  `StateDelta`) is **additive** + a revision note; `StepResult`/`PipelineVerdict` fields not removed. Extend the
  `Step` Protocol additively so `AgentStep`/`PanelReviewerStep` satisfy `produces`/`consumes` via defaults.
- **Back-compat shims:** `JoinFn`/`PromoteFn` are public aliases consumed by `pattern_topology.py`,
  `pattern_dynamic.py`, `subloop.py`, `planning.py`, tests — update all in lockstep; no half-typed alias.
- Don't dogfood off an editable install — run on M0's pinned engine (EPIC:178; MEMORY dogfood-engine-shadow).

## Done criteria (testable, incl. the milestone's oracle gate)

1. `grep -rn GateRecommendation megaplan/_pipeline/` returns hits **only** in `types.py` (edge-dispatch) + the
   planning binding; the CI grep-gate test enforces ZERO elsewhere. `majority_vote`/`weighted_vote` return a
   structured tally + winning label as DATA (test asserts no `verdict.recommendation` set).
2. `select(items, rule)` returns `SelectionResult(winner|subset, losers, scores, cleared)`; a test covers
   top-1, top-k, and `cleared=False` (nobody qualified).
3. A data-`Reduce[T]` returns a non-verdict value; a generative reduce produces a spec list `dynamic_fanout`
   consumes **through a typed Port** (round-trip; assert `T` survives, not erased through `state["specs"]`).
4. **Port build-time resolution:** `build()` **raises with a machine-readable repair gradient** on a `consumes`
   with no matching `produces`, a typo'd name, a schema/content-type mismatch, a cardinality mismatch — one
   test per failure mode; a correctly-wired pipeline builds clean.
5. **Runtime binding + no `v1.md`:** `grep -n 'v1.md' megaplan/_pipeline/step_helpers.py` shows the fallback is
   **gone** (behind the flag); a test proves a step's `consumes` Port is bound from upstream `produces` (not a
   guessed path); an unbindable port errors loudly.
6. **R3 taint-in-hash:** a test feeds two byte-identical Port values with different taint and asserts they
   **hash differently** (dedup cannot launder); a produced Port's taint is the lattice-join of its consumed
   Ports' taint.
7. **StateDelta CAS:** two writers hit the same key — LWW loses an update, `accumulate` does not; a
   stale-version write is **rejected** (CAS), replacing `executor_owned_keys` behavior (`executor.py:258–260`,
   `state.py:361–373`).
8. `iterate_until`/`consensus_loop` no longer `del` `condition`; a loop **terminates on the data predicate over
   `last_fanout_results` (a Port)**. `pattern_stops.py` ships `plateau`/`max_iters`/`threshold_reached`/
   `no_improvement`, each unit-tested as a pure data callable.
9. The 4-verdict mapping is a planning binding; `planning.py`'s gate consumes it; **the parity gate stays
   green** (decision + artifact parity unchanged).
10. **THE acceptance / oracle gate — the non-planning `select`-tournament toy** (`demos/tournament.py` +
    `tests/_pipeline/test_tournament_toy.py`): rounds fan-out matchups, a data-`reduce` scores them, `select`
    advances winners / drops losers, a stop predicate ends it → a champion. Asserts (a) **zero
    `GateRecommendation`/4-verdict references** in the toy (grep) and it imports nothing from the planning
    binding; (b) **NO hand-wired inter-step data — every cross-step datum crosses a declared Port** (no
    `state_patch["..."]` string-channel, no `plan_dir`/`v1.md` convention; grep + a binder audit).
11. **Strangler oracle / merge gate:** the milestone merges **only when grep-gate=0 AND every consumer is green
    together** (never a partial merge, PROGRAM:122); the old string/state-dict path still drives a throwaway
    planning-shaped plan flag-OFF (OLD-alive), and the typed-Port path drives the tournament + a planning-shaped
    throwaway flag-ON matching recorded traces (NEW-alive); red auto-halts/reverts or runs the bounded ladder
    (retry ×2 → bump one tier → `stop_chain` + auto-ticket) — never parks on a human (REGISTER §2-4).

## Touchpoints (files to change)

- `megaplan/_pipeline/pattern_types.py` (`PromoteFn` :16, `JoinFn` :19 — drop `GateRecommendation` :14).
- `megaplan/_pipeline/pattern_joins.py` (`majority_vote` :17, `weighted_vote` :46 — structured data; drop
  `GateRecommendation`/`PipelineVerdict` :10–11).
- `megaplan/_pipeline/types.py` — additive `Port`, `ReduceResult`, `SelectionResult`, `StateDelta`, the open
  content-type registry, the taint-lattice field; `produces`/`consumes` on the `Step` Protocol (:168–183);
  keep `GateRecommendation` (:76) for the gate edge-dispatch (:45) only.
- `megaplan/_pipeline/builder.py` (`_input_refs` :146,:178 → resolved/checked `consumes`; `build()` :400 runs
  the Contract-Ledger binder).
- NEW `megaplan/_pipeline/contracts.py` (the Contract Ledger: Port-contract registry + legal-coercions +
  repair-gradient builder).
- `megaplan/_pipeline/executor.py` (`_verify_outputs` :137 + call sites :255/:361 — add port binding;
  :258–260/:363–365 — replace `executor_owned_keys` LWW with `StateDelta` CAS; thread taint into the hash).
- `megaplan/_pipeline/step_helpers.py` (:104 — **remove** the `v1.md` fallback behind the flag).
- `megaplan/_core/state.py` (`write_plan_state` :329, `executor-key-merge` :361–373 — `StateDelta`-backed CAS).
- `megaplan/_pipeline/pattern_topology.py` (`iterate_until` :269/:288, `consensus_loop` :174 — thread predicate).
- `megaplan/_pipeline/pattern_dynamic.py` (`_extract_specs_from_result` :52, `dynamic_fanout` — generative
  reduce → typed Port; `last_fanout_results` Port written by the fan-out join).
- NEW `megaplan/_pipeline/pattern_select.py`, `megaplan/_pipeline/pattern_stops.py`,
  `megaplan/_pipeline/demos/tournament.py`.
- `megaplan/_pipeline/planning.py` (gate stage) + NEW planning verdict-mapping binding; `subloop.py`
  (`_DEFAULT_PROMOTE`) + `stages/tiebreaker.py` — de-typed off the shared alias, stay planning-local.
- Tests: extend `tests/_pipeline/test_patterns.py`, `test_dynamic_primitives.py`; NEW binder tests (DC#4–7),
  taint-hash test (DC#6), tournament-toy test (DC#10), CI grep-gate test (DC#1).

## Anti-scope

NO real `loop` runtime/driver — M2 wires the predicate through the existing graph-sugar `iterate_until`; the
standalone loop driver + **realized graph / topology-realizer** are **M3** (PROGRAM:141). NO mid-run
re-realization (M2 resolves per handed robustness level). NO `run(cmd)`/oracle evidence, NO `snapshot`/
`restore`/state-evolution axis (M2 ships CAS + `accumulate`, NOT reversibility), NO `budget`/depletable
resource, NO gate-consequence parameterization, NO **Conveyance/Work-Envelope** (the Port's temporal half —
M3 sub-PR, PROGRAM:159–164) — taint here is the spatial seed only. NO **policy spine** / RecoveryPolicy /
budget authority / observability contract — **M4**. NO `dispatch`/`emit`/`evidence`/`config` services — **M4**.
NO **Effect Ledger** (act-idempotency) — **M4**. NO run-outcome / control vocabulary, NO `STATE_*` eviction —
**M5c**. NO pack relocation / `_BUILTIN_NAMES` removal / manifest-first discovery / the R1 authority flip —
**M3/M6**. NO change to planning's verdict vocabulary or its observable decisions. NO old-path deletion in any
M2 PR (the swap of the only system-flipping deletion is M6).
