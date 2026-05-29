# Abstraction Stress-Test — Is the Arnold SDK at the Right Altitude?

**Status:** Decision input (2026-05-28). Companion to `briefs/pipeline-unification-EPIC.md`.
**Method:** Invent 5 deliberately diverse pipelines (dev / writing / image), sketch each as a
composition of a candidate domain-free primitive set, then compare each sketch against what the
EPIC plan actually ships. Source-level claims in the sketches were spot-checked against the live
codebase (`megaplan/_pipeline/*`, `megaplan/_core/state.py`, `megaplan/orchestration/execution_evidence.py`)
and confirmed accurate.

---

## TL;DR verdict

**The candidate primitive set is at roughly the right altitude. The SDK as currently planned is not —
it is shaped like one specialization (an LLM artifact under iterative revision, judged by a 4-verdict
gate) that we mistook for the general shape.** The stress test exposes the same fault line from five
independent directions: every "general" reduce/join/gate/loop/state/evidence piece in the plan has
**planning-domain vocabulary baked into its type**, which silently excludes whole classes of pipeline
(search/backtracking, economic/allocation, evolutionary/generative, empirical-oracle, co-evolutionary).
The fix is not new exotic verbs; it is **decoupling each piece's mechanism from planning's specialization**
and exposing 3–4 axes the plan currently hard-codes as assumptions.

---

## The idea inventory

| Idea | Domain | Difficulty | The one thing it stresses |
|---|---|---|---|
| Constraint-Solver w/ Backtracking | dev | hard | State has no UNDO; driver has no search frontier |
| Citation Bounty Market | writing | hard | No SELECT-one-winner; no depletable budget; no nested fan-out |
| Genetic Image Tournament | image | medium | reduce is verdict-shaped & many-to-one; no rank / select / converge |
| Bisect Detective | dev | partial | verify is a NOTARY, not an ORACLE; `loop` driver doesn't really exist |
| Red-Team / Blue-Team Hardening | dev | medium | termination = producer yield not verdict; no accumulate; survivors-as-assets |

Three of five are rated hard, the other two partial — **none composed cleanly.** That is the signal:
the diversity was real and the SDK bent the same way each time.

---

## Sketch + comparison highlights (the load-bearing findings)

### 1. Constraint-Solver — the STATE-EVOLUTION axis is missing
- The Store (`megaplan/_core/state.py`) is **forward-only**: `append_history` (append), `latest_plan_record`
  (monotonic `plan_versions[-1]`), `write_plan_state` modes are all forward mutations. **No
  `snapshot`/`restore`/`rollback` verb exists anywhere.** Confirmed by grep.
- The plan characterizes `state` only by *durability/transactionality/leasing* — "is the write safe and
  concurrent?" — and silently assumes a single **evolution model: forward-only**. Both reference apps
  (planning, resident) happen to be forward-only, so the "diversity is the menu" framing captured dispatch
  and emit diversity but **never captured state-evolution diversity**, because neither app exercises it.
- Reveal: the plan conflates **state-durability model** with **state-evolution model**. A builder SDK must
  expose evolution as an axis: `forward-only | versioned/reversible | event-sourced`. The driver set has no
  `search/tree` driver whose frontier nodes bind to restorable state versions.

### 2. Citation Bounty Market — AGGREGATION vs SELECTION conflated; no economic state
- The only aggregators are `pattern_joins.majority_vote` / `weighted_vote`, and both collapse a panel into a
  single `GateRecommendation` (the closed 4-verdict vocabulary). They **aggregate to a verdict; they never
  return `(winner, losers[])`.** There is no `select(items, rule)` peer to `vote`.
- "Tournament/bakeoff picks a winner" is true at the orchestration tier but **invisible at the node-library
  tier** — no reusable selection node.
- `SubloopStep` deliberately runs each child on a **copy** of parent state and promotes only one
  `GateRecommendation` + namespaced keys (confirmed `subloop.py`). So **shared, depletable budget cannot
  accumulate across sibling shards** — nested fan-out (claims × researchers) forces manual artifact
  round-tripping.
- Reveal: depletable-resource / economic state is a genuinely new, non-planning concern (any agent market,
  rate-limited swarm, cost-capped search wants it) → belongs in the SDK as a state/config flavor.

### 3. Genetic Image Tournament — reduce is verdict-shaped AND many-to-one
- `JoinFn = Callable[[list[StepResult], StepContext], StepResult]` and every concrete join returns a
  `GateRecommendation` (confirmed `pattern_types.py:19`, `pattern_joins.py`). So the SDK has "judge a
  fan-out and route" but **no "aggregate a fan-out into structured DATA"** (a vector of scores) and **no
  generative one-to-many reduce** (K winners → N new candidates that re-seed the next fan_out).
- `iterate_until`'s `condition` Callable is **`del`'d at topology-build time** (confirmed
  `pattern_topology.py:288`) — the predicate is documentation-only; the wrapped Step must re-derive it.
- Reveal: three distinct verbs are conflated — **ROUTE** (collapse → control decision; the only one we have),
  **AGGREGATE** (collapse → data value), **EXPAND/SELECT** (reshape a Store-held collection). Routing on a
  verdict is *one specialization* of reduce, not its definition.

### 4. Bisect Detective — verify is a NOTARY, the `loop` driver is aspirational
- `execution_evidence.py` is purely **attestation**: it compares the executor's *claimed* changed files
  against actual `git status` (confirmed). The plan's `evidence = git/audit/none` are all notary-shaped.
  Bisect needs evidence to be an **ORACLE**: run an arbitrary probe, return a measured pass/fail that
  **branches control flow**. Same verb name, opposite contract.
- `iterate_until` is **graph-edge sugar** (appends `Edge(iterate)->self` + `Edge(halt)`), executed by the
  GRAPH driver. There is **no separate loop runtime** for data-dependent step counts (~log2 range). The
  EPIC's "drivers = graph/loop/process/oneshot" **overstates what is built** — `loop` is aspirational.
- Reveal: strip the LLM to a disposable narrator and bisect still works on `loop + state + oracle`. That
  proves those three are the actually-general primitives, while `produce/critique/gate` are a
  **planning-domain genre** sitting in the shared library.

### 5. Red/Blue Hardening — termination is producer-yield, not verdict; no accumulate
- Every real iterate primitive reads a verdict/score (`_ConsensusStep` loops on `_agreement_ratio >= bar`).
  Here termination is **"the challenger produced zero survivors"** — absence-of-yield, not a judge score.
- `state.update(dict(result.state_patch))` is **last-writer-wins, not append** — a monotonically growing
  corpus must be hand-rolled (read prior list, concat, rewrite). No `accumulate` verb.
- Join library pushes builders toward **collapse-to-winner**, but here the **losers (surviving exploits)
  are the assets** and "producer came up empty" is the success condition — an inversion the macros can't
  express.

---

## (1) Abstraction verdict

The candidate **primitive set** (`produce / judge / gate / revise / fan_out / reduce / escalate /
loop_until / clarify / verify`) is close to the right altitude — it survived five wildly different domains
and most wiring landed. But it has three altitude defects, and the **SDK plan** has worse ones:

1. **`reduce`/`gate`/`vote` are typed in planning's vocabulary.** `JoinFn` returns `GateRecommendation`.
   This is **app vocabulary leaking into a supposedly general SDK piece.** No non-planning builder can use
   `vote` without inheriting megaplan's 4-verdict enum. This is the single most repeated finding.
2. **The plan models only one specialization and calls it general.** "An LLM artifact under iterative
   revision, judged by a gate, moving forward only." Every primitive is shaped to that: forward-only state,
   verdict-shaped reduce, verdict-driven termination, notary evidence, collapse-to-winner joins. Four of
   five sketches needed at least one axis that specialization hard-codes.
3. **`loop` and `evidence` are over-sold.** `loop` is graph sugar, not a runtime; `evidence` is a notary,
   not an oracle. The EPIC's driver/evidence menu describes more than is built.

Net: the **verbs** are right; the **types and the implicit assumptions baked into the pieces** are too
planning-shaped. The SDK is currently expressive enough to build *forward-only LLM-revision pipelines* and
nothing else — which is exactly the class the two reference apps already are.

## (2) Confirmed primitives (the real core — recurred across sketches)

- **`produce`** — 5/5. Universal.
- **`fan_out`** — 4/5 (all but bisect). Topology is right; the state/emit contract under it is the constraint.
- **`loop_until`** — 5/5. The loop *shape* is universal; the current *predicate plumbing* (`del condition`)
  and the verdict-only termination idiom are wrong.
- **`verify`** — 5/5, but used at **two irreconcilable altitudes** (notary vs oracle vs cheap rule-checker).
- **`clarify / gate_zero`** — 5/5. Validate-before-start landed cleanly everywhere.
- **`state` (Store as a service)** — 5/5 as a *durable map*; its evolution model is the gap.
- **`emit`** — 5/5. The least contested piece.
- **`reduce`** — 4/5, but every use revealed it is mis-typed (verdict-shaped, many-to-one only).
- **`escalate`** — 3/5 (solver, bounty, red/blue). Confirmed but secondary.

## (3) Missing primitives (ranked by how many sketches needed them)

1. **`select(items, rule) -> (winner|subset, losers, scores, cleared?)`** — a SELECTION node peer to
   `vote`, distinct from `judge`. **Needed by 4/5** (bounty auction, genetic top_k, red/blue keep-survivors,
   and implicitly the solver's "pick best untried"). The single biggest gap.
2. **Data-valued / generative `reduce`** — `Reduce[T]` returning arbitrary data, and a one-to-many reduce
   whose output is the next fan_out's input spec list. **Needed by 3/5** (genetic breed_reduce + rank_reduce,
   bounty score_bids, red/blue accumulate).
3. **A real `loop` driver with a DATA predicate + teardown** — predicate over `{state, last_fanout_results,
   budget, iteration}`, unknown-at-wiring-time step count, finally/cleanup hook. **Needed by 4/5** (bisect,
   solver, genetic, red/blue). Today `loop` is graph sugar with a verdict-shaped exit.
4. **Oracle/measurement evidence + a `run(cmd) -> {exit_code, stdout, ...}` step** — evidence as a measuring
   instrument that branches control flow. **Needed by 2/5 strongly** (bisect, red/blue execute exploits),
   relevant to the solver's constraint-checker.
5. **`accumulate` / monotonic-growth state op** (append-to-list / union-into-set surviving across loop
   iterations). **Needed by 2/5** (red/blue corpus, genetic population) and implicit in any corpus-building
   pipeline.
6. **`snapshot(store)->id` / `restore(id)` (versioned/reversible state)** — **Needed by 1/5** (solver) but
   it is a whole capability CLASS no reference app exercises; the cheapest forgotten axis.
7. **Depletable-resource / budget meter** the loop predicate and escalate hook can read. **Needed by 2/5**
   (bounty ledger, red/blue budget).
8. **A reusable stop-predicate library** (`plateau`, `max_iters`, `threshold_reached`, `no_improvement`,
   `len(survivors)==0`) — mirroring the join library. **Needed by 4/5**.

## (4) Wrong altitude (piece → fix)

- **`reduce`/join typed as `GateRecommendation`** → Split by output altitude. Keep a `route`/verdict_reduce
  family for routing; add `Reduce[T]` returning arbitrary data; allow a generative reduce returning the next
  fan_out's input. **Remove `GateRecommendation` from the general join signature** — planning maps the
  structured result to its verdicts in the app layer.
- **`gate` couples VERDICT to CONSEQUENCE** → Parameterize gate by a consequence map:
  `verdict -> {advance | revise_in_place(target) | restore_and_diverge(version) | escalate}`. Planning's
  4-verdict labels stay app-local; the consequence binding is domain-local.
- **`state` characterized only by durability** → Add **state-evolution model** as an explicit axis
  (`forward-only` default | `versioned/reversible` | `event-sourced`), all behind one Store interface — the
  exact "multiple backends behind one interface" pattern the EPIC already endorses for dispatch/emit. Add a
  two-tier distinction: durable accepted-progress (monotonic) vs transient working/exploration tier.
- **`verify`/`evidence` as one notary strategy** → Split into **attestation** (claimed-vs-actual, today's
  git/audit) and **oracle/measurement** (run a probe, return a typed signal that branches). Add `oracle` to
  the evidence menu. Split the cheap pure rule-checker out as a node-library predicate, not the evidence
  service.
- **`loop` listed as a peer driver** → It is graph sugar today. Either build a real loop runtime (DATA
  predicate, teardown hook, max-iters cap) or **re-label `iterate_until` honestly as graph sugar** so the
  driver set reflects reality. Wire the `del`'d predicate through to the driver.
- **`fan_out` implies flat-list input + serial execution** → Document input as "a schedule/spec list" (pairs,
  tuples, grid cells). Make `dynamic_fanout` actually parallel with per-spec failure isolation (today
  `[step.run(ctx) for step in steps]` is serial). Add a **fold/shared-accumulator channel** distinct from the
  per-result join, and bless **map-of-pipelines** (`fanout_per_item`) as a supported construction so
  state/emit/budget threading per shard is the SDK's job, not the builder's.

## (5) Recommendations (prioritized, concrete)

**P0 — decouple from planning vocabulary (cheap, highest leverage, unblocks 4/5):**
1. Make `JoinFn`/reduce return structured data, not `GateRecommendation`. Add `select(items, rule)` and
   `Reduce[T]`. Move the 4-verdict mapping into the planning app. *This one change touches every hard sketch.*
2. Wire `iterate_until`'s predicate through to the driver (stop `del`-ing it) and ship a stop-predicate
   library peer to the join library.

**P1 — make `loop` and `evidence` honest:**
3. Build a real `loop` driver (DATA predicate over `{state, last_fanout_results, budget, iteration}`,
   max-iters cap, teardown/finally hook) OR re-label `iterate_until` as graph sugar in the EPIC.
4. Add `run(cmd, cwd, timeout) -> {exit_code, stdout, stderr}` as a sanctioned sandbox-aware step, and add an
   **oracle** evidence strategy alongside git/audit/none.

**P2 — expose the missing axes (do behind existing-backend pattern):**
5. State-evolution axis: ship forward-only as default backend, a versioned/reversible backend (snapshot/restore)
   as a second backend behind one interface. Add a `search/tree` driver owning a restorable frontier.
6. Add `accumulate`/monotonic-Store ops; a typed depletable-budget resource + loop predicate that reads it;
   a fold channel on fan_out; `fanout_per_item` map-of-pipelines; parallel+isolated `dynamic_fanout`.
7. Parameterize gate consequence (`advance | revise_in_place | restore_and_diverge | escalate`).

**P3 — keep the axes honest with non-forward-only acceptance tests:**
8. The current acceptance tests (jokes, one example package, the two existing apps) are **ALL forward-only,
   verdict-shaped, single-producer** — they would never surface any gap above. Add at least: (a) a tiny
   reversible-search package (resolve N vars under M constraints with backtracking), (b) a select/auction or
   evolutionary toy (Store-as-population + generative reduce + convergence predicate), (c) an oracle-driven
   loop (mini-bisect: `loop + run + state`, no LLM). These are the cheapest way to keep the state-evolution,
   selection, and oracle axes from regressing into planning-shaped assumptions.

## (6) Implications for megaplan-planning as a "beautiful example"

- **Planning is a fine FIRST example but a DANGEROUS sole reference.** It is forward-only, single-producer,
  verdict-shaped, notary-evidenced — i.e. it exercises exactly one corner of the design space. Building the
  SDK "against planning + resident as the two reference apps" (M2) will *systematically* reproduce every gap
  here, because both apps share the same specialization. **The brief's own warning — "the wrong question was
  what do the two existing apps share" — is being violated in practice**, because the shared menu only
  captured dispatch and emit diversity, not state-evolution / reduce-shape / termination / evidence diversity.
- For planning to be a *beautiful* example rather than a *gravitational* one, **the planning vocabulary must
  visibly sit on top of the SDK, not inside it.** Concretely: the 4-verdict gate, the verdict-shaped join,
  the revise-in-place consequence, and the attestation evidence should all be demonstrably **planning-app
  bindings of more general SDK pieces** (a structured-result reduce, a parameterized gate consequence, an
  evidence strategy choice). If a reader can point at planning and say "ah, `iterate` is just planning's
  binding of `revise_in_place`, and a solver would bind the same gate to `restore_and_diverge`," the example
  is beautiful. If planning's verdicts ARE the SDK's only reduce output type, the example is a trap.
- **The acceptance set must include a deliberately UN-planning-like example** (one of the search / select /
  oracle toys above). A beautiful example proves *others can build a fourth thing*; the only honest proof is
  a fourth thing that is NOT shaped like the first two. Ship at least one non-forward-only, non-verdict-shaped
  acceptance package, or the "others compose these pieces to build many different things" claim is untested.

---

## Cross-cutting reveal (the single sentence)

> The plan treats **planning's specialization as the SDK's definition**: every general piece (`reduce`, `gate`,
> `loop`, `state`, `evidence`) carries a planning assumption in its type or its missing axis, so the SDK can
> currently express only forward-only, single-producer, verdict-routed, revise-in-place pipelines — the exact
> class both reference apps already are. Decouple the pieces from that specialization (data-valued reduce,
> parameterized gate consequence, state-evolution axis, oracle evidence, real loop predicate) and the same
> verbs cover search, markets, evolution, and empirical-oracle loops with no new exotic primitives.
