# Arnold-SDK plan — full-ambition interrogation: SYNTHESIS

**Posture:** We WILL do all of it. Planning becomes a module like any other; pieces are composed,
discovered identically, no privilege, no special path. Nothing below argues to scale that down.
Everything below is what the plan must **ADD, fix, re-sequence, or abstract differently** to make
full ambition actually hold instead of shipping green while the disease survives.

Ten adversarial lenses each drew blood. The striking result is **convergence**: the same handful of
missing nouns reappear under nearly every lens wearing different costumes. That convergence is the
signal — it means these are not ten problems, they are ~4 structural holes seen from ten angles. The
plan has the right **verbs** (the stress-test was correct) and is now hardening the **value types**
(M2's `Reduce[T]`, `select`, `SelectionResult`). But it leaves the **channels between pieces, the
graph the driver actually walks, the policy spine that sequences pieces, and the trust/version
boundary at the package edge** unnamed. Those four absences are where full ambition bites.

---

## CROSS-CUTTING THEMES (where ≥2 lenses converged)

### Theme A — There is no typed data CONTRACT between composed pieces. "Composition" is a filesystem convention. (7 lenses)
`missing-abstraction`, `composition-DX`, `state-dataflow`, `over-simplification`, `success-second-order`,
`sequencing`, and `planning-resists` all land on the same nerve from different sides.

The executor **never binds a step's `ctx.inputs` from a predecessor's `StepResult.outputs`**
(executor.py only `_verify_outputs` existence-checks at :255/:361; inputs are frozen at pipeline
entry). Downstream data dependencies resolve by **path convention** with a **silent fallback** —
`step_helpers.py:104`: `resolved[ref] = ctx.plan_dir / ref / "v1.md"` — to a file that may not exist.
M2 introduces a typed `Reduce[T]` but immediately launders `T` back through the hard-coded untyped
key `state_patch["specs"]` (`pattern_dynamic.py`), so the type is erased the instant it crosses the
composition boundary. The advertised wiring DSL (`builder.py` docstrings: `inputs=["draft"]`,
`inputs=["panel_review.*"]`) is **stashed as `_input_refs` and never validated** — the `Step` Protocol
(types.py:167-183) carries nothing about what a node consumes or produces. `NextEdge = str`,
`outputs: Mapping[str, Path]`, `state_patch: Mapping[str, Any]` — the most-used inter-step interface is
a bag of strings checked only at runtime (`LookupError` at executor.py:299/:401, after dispatch + LLM
cost). `last_fanout_results` — the typed in-memory channel the M3 loop predicate is promised — **exists
nowhere in the codebase** (confirmed: grep returns only brief lines). The cross-transport bridge is a
**flat-key last-writer-wins merge** (`executor_owned_keys`, state.py:337/364-373) with no revision, no
nesting — the same lost-update class a2 found, now on the core composition path.

**The convergent verdict:** the "composition layer" the SDK sells is a fiction. Pieces connect only by
sharing a `plan_dir` convention. Every acceptance toy will be written by an author who controls BOTH
ends, so they hand-wire `state["specs"]`-style channels and path conventions and **still pass green** —
masking the exact reinvention the SDK exists to eliminate (EPIC:20-23). This is the single highest-
convergence finding.

### Theme B — There is no REALIZED graph; the driver walks a static map planning never uses statically. (4 lenses, both criticals in `planning-resists`)
`planning-resists`, `over-simplification`, `over-complication`, `sequencing` converge on: the plan
treats "collapse onto the graph as single source of truth" (M6 §3) as deletion-of-duplication, but the
three next-step encodings are at **different altitudes and not redundant**. `_ROBUSTNESS_OVERRIDES`
(workflow_data.py:91) does true **node/edge REWRITING**, not parameter binding — `bare` deletes the
critique+gate nodes, `light` collapses critique→gate, `with_feedback` rewires execute→review→feedback;
levels fold cumulatively via `_ROBUSTNESS_WORKFLOW_LEVELS` (confirmed). A "preset" that adds/removes
nodes is **graph-construction policy**, which migration-fit e1 already declared "has no home." EPIC §51's
"parameterize-graph-by-config" **names a parameter where the real thing is a rewrite FUNCTION.**
`workflow_next` must fold the robustness stack, evaluate 7 gate predicates, AND manufacture a synthetic
`step` target **that exists in no edge** — a thin edge-projection cannot manufacture that. `_gate_next_step`
routes escalate INTO the F7 control plane — the graph already points out of itself. You cannot collapse
"onto the graph" when (a) there is no realized graph to collapse onto and (b) the graph dereferences out
to the control plane.

**The convergent verdict:** the root cause of the "3 encodings" problem is **not 3 encodings — it is the
absence of a realized graph to project from.** And no acceptance toy reshapes its own topology, so the
epic can ship green without ever proving the graph driver can host planning's defining trick.

### Theme C — The driver has MECHANISM but no POLICY SPINE; auto.py's brain is never extracted. (4 lenses)
`cross-cutting`, `over-simplification` (F5/F8 leaks), `state-dataflow` (budget across shards),
`missing-abstraction` (fat dispatch request) converge. The plan extracts auto.py's **mechanism**
(subprocess loop → M3 process driver) and its **features** (M5) but **never extracts its policy spine**.
auto.py is the run's recovery state machine: `ExitKind` taxonomy, a 14-value status taxonomy, THREE
distinct retry loops with separate caps (context-exhaustion `retry_fresh`, targeted transient gated by
`_is_retryable_external_error`, blocked-task `max_blocked_retries`); "retry" appears **104×** (confirmed).
M3 builds loop/process drivers with a teardown hook + max-iters cap and says **nothing** about retry
classification, budgets, or error→consequence mapping. Money is **three uncoordinated ledgers** (M4
post-hoc attribution journal; M3 per-run loop budget that is explicitly "not a quota broker"; live
`CostTracker` cap reading only `state.meta.total_cost_usd`) with **no single live authority** that can
stop spend when the WHOLE composition exceeds budget — both briefs flag it and punt to each other.
Because no policy owner exists, the M4 dispatch **request becomes a god-object**: liveness/run_id + cost
context (tenant_id/dispatch_id) + key/rate brokers + prompt_override/shim all ride the request — the
exact "fat request" the M4 "thin altitude" principle is trying to avoid.

**The convergent verdict:** a fourth tool hitting transient errors / context exhaustion / budget overrun
must reach into planning's retry logic (forbidden privilege), reinvent it (the symptom the SDK cures), or
get none. The thing that sequences the pieces was given mechanism but **no horizontal responsibility.**

### Theme D — "Binding = content" is FALSE for the four hardest features; the binding is mechanism in planning's private state vocabulary. (4 lenses)
`over-simplification` (lead lens), `planning-resists`, `cross-cutting`, `sequencing` converge. EPIC §52-54
asserts "planning keeps only content." But for **F7 control plane**, **e1 robustness**, **F8 supervisor**,
and **F5 execute classification**, the binding is **behavior**, not passive content. The override plane:
39 `STATE_*` references (confirmed), `build_gate_artifact` synthesizing a domain artifact (override.py:297),
a debt registry, and `_BLOCKED_RECOVERY_STATES` (override.py:399) — a reverse-edge map with **no forward
edge** (the graph returns `[]` for blocked). a3 proved only the forward-progress half maps to general
transitions. The F8 supervisor claims to "know nothing about planning phases" yet branches on planning's
terminal `STATE_*` and invokes "force-proceed" by name — **the JoinFn→GateRecommendation enum leak
recurring at RUN granularity, one tier up where the stress-test never looked.** F5 calls blocked/deviation
classification a "general process-result reducer," but `blocked` is a planning verdict coupled to
`STATE_BLOCKED` → recover-blocked.

**The convergent verdict:** the EPIC evicted the 4-verdict enum from `JoinFn` (§63) but **never evicted
planning's `STATE_*` enum** from the control plane or the supervisor. The disease the stress-test cured
one layer down is **untreated one layer up.**

### Theme E — Discovery imports untrusted code, pins unversioned types, with no diagnostics and no contract checker. (3 lenses)
`composition-DX`, `success-second-order`, `sequencing` converge on the package edge. Discovery does
`spec.loader.exec_module` then `except Exception: return None` (registry.py:339-342, `# noqa: BLE001`
confirmed) — so on M6 success "drop a community package in `~/.megaplan/pipelines`" = **arbitrary code
execution** of the author's top-level imports on the next `megaplan` command (discovery is eager: list/
status/profile resolution all funnel through it). a5 reasoned only about the runtime DISPATCH sandbox and
concluded "low risk" — it **never examined the import seam.** Same path: any import error / typo'd
entrypoint / (post-M6) missing SKILL.md makes a package **vanish with no error, warning, or log.** And M5
declares `patterns.py` the "public, documented composition vocabulary with stable signatures" while the
EPIC's whole purpose is to keep reshaping those types — with **no `arnold_api_version`, no SemVer, no
deprecation window.** Fixing `JoinFn`-returns-`GateRecommendation` is a free refactor today; post-success
it's an ecosystem-breaking change with no version gate to even detect the break.

### Theme F — chain.yaml is the territory and it points at the wrong map. (3 lenses)
`sequencing`, `bootstrapping`, and the EPIC's own §91 converge. **The executable artifact lies.**
chain.yaml:11-30 still encodes the **stale May-28 4-milestone v1** (m1-foundation, m2-dispatch-service,
m3-planning-as-pack, m4-shared-substrate) — confirmed verbatim — while the brief dir holds BOTH
generations side by side (m2-deplanning-types.md AND m2-dispatch-service.md, etc.). The harness runs
chain.yaml, not the EPIC prose. Running it executes "**planning as a discovered pack" at M3 — three
milestones early, before the drivers/state/services it must compose exist, and before M6's deliberate
last-place sequencing of dropping `_BUILTIN_NAMES`** (confirmed `frozenset({"planning"})` still live).
This is the single most likely program-staller and the cheapest to fix.

### Theme G — Every guardrail-by-gate is a HAPPY-PATH gate guarding a SUBSTRATE swap. (3 lenses)
`bootstrapping`, `sequencing`, `state-dataflow` converge. The parity gate SHA256-compares ~10 deliverable
artifacts on ONE happy path while the thing being swapped is the **substrate** (subprocess→in-process,
LWW JSON→leased Store, ndjson→EpicEvent, dispatch backend). The gate stays **green while the engine
underneath is entirely replaced**, because identical happy-path artifacts say nothing about concurrency,
crash-isolation, resume-after-merge, or version-skew. Same shape recurs: M2's GateRecommendation removal,
M3's reversible-snapshot toy (pure in-memory rollback never touches the world side-effects), M5's
fan_out reduce (garbage shard absorbed silently) — all pass green precisely on the path that hides the
gap. Partial conversion is **worse than none** because it hides coupling behind a green gate.

---

## CONFIRMED MISSING ABSTRACTIONS

1. **A typed, revision-bearing PORT / inter-step data contract + a binder the driver runs between steps.**
   `Port = (name, kind: artifact|value|stream, schema: type|ContentType, cardinality, version)`; extend
   the `Step` Protocol with `produces`/`consumes`. The builder resolves `consumes` against upstream
   `produces` at **build time** (turning `builder.py`'s aspirational `inputs=[...]` into a checked DAG
   that fails `build()` on missing/typo'd/mistyped dep); the executor **binds ports at runtime** from
   resolved upstream outputs — replacing `resolve_inputs` path-guessing and killing the `v1.md` fallback.
   This Port is the **noun all the other named gaps are verbs about**: versioning = a field on the Port;
   dependency declaration = `consumes` IS the declaration; typed failure-propagation = a Port error variant
   (today the per-binding `research_sentinel` hack); `last_fanout_results` = the fan-out join writes a
   typed Port the loop driver reads. The cross-transport `StateDelta` (replace|accumulate|deep-merge +
   version stamp, CAS not flat-key LWW) is the same abstraction on the state side.

2. **A REALIZED-GRAPH / topology-realizer layer** between the static package-declared `Pipeline` and the
   driver's edge-walk: `realize(graph, run_config) -> graph`, an ordered rewrite fold matching
   `_ROBUSTNESS_WORKFLOW_LEVELS`, run at init AND **re-invocable mid-flight** (set-robustness mutates it
   live). It is the SINGLE source both the `next_step` projection and the reverse-recovery maps query —
   which **kills the 3-copies problem at its real root** (the root is "no realized graph to project from,"
   not "3 encodings"). Reverse-recovery maps become `predecessors(stage)` computed on demand, **not a
   persisted fourth copy that drifts** after a mid-run reconfigure.

3. **A driver-level POLICY SPINE** owned by the driver tier and consulted by graph/loop/process uniformly:
   an injected `RecoveryPolicy` (`classify(error) -> {retry_fresh, retry_transient, escalate, halt(kind)}`
   + per-class budgets); a **single live budget/cost authority** consulted before each dispatch (folding
   across fan-out shards); a **composition-observability event contract** (the driver emits step boundary
   / decision+rationale / retry+class / budget delta / piece identity, carried by BOTH emit backends and
   consumed by a backend-agnostic introspector); and an **N-layer config-precedence resolver** generalizing
   `get_effective` + `setting_is_explicit` (env > args > state.config(override) > profile > robustness >
   DEFAULTS), through which F7's runtime mutation writes instead of blind-poking `state.config`.

4. **A general RUN-OUTCOME / control-target vocabulary** — `{succeeded, failed, escalated, blocked,
   awaiting_human}` + queryable `valid_targets(state)` / `recover_targets(state)` projections — that BOTH
   F7 (control plane) and F8 (supervisor) branch on, with every run-type (planning included) mapping its
   private `STATE_*` onto it via a binding. The control interface is a `(read_valid_targets,
   apply_transition, synthesize_artifacts)` trio the binding **IMPLEMENTS**; the SDK owns only invocation,
   event emission, versioned-mutation envelope, and the projection. **Stop calling F7/F8/F5/e1 "content."**

5. **A package-trust / capability TIER on the manifest, evaluated at DISCOVERY/LOAD time** — distinct from
   the runtime dispatch sandbox. Manifest-first discovery reads a **static, non-executing manifest**
   (name/driver/entrypoint/declared-capabilities/SKILL path + `arnold_api_version`) WITHOUT importing,
   deferring `exec_module` until selected-to-run and gating it on an operator trust decision
   (in-tree/blessed/quarantined). This tier is the common root of three `success-second-order` bites:
   checked before `exec_module`, before broker access (per-package quota sub-budget + SDK-assigned
   `tenant_id`, not self-declared), and used to gate which surface versions a package may pin.

6. **A package CONTRACT CHECKER + diagnostic discovery + scaffold** — `validate(pipeline) -> Diagnostics` /
   `megaplan pipelines check`: a type-checker for the graph that statically proves a composition is wired
   (every `next`→edge resolves, every `Edge.target`→stage-or-halt, no unreachable stage, no `halt` edge
   label, gate verdicts have matching edges, declared `out_labels` exact), discoverable, and contract-
   complete — plus `pipelines doctor` (per-path discovered✓ / rejected+traceback / skipped) and
   `pipelines new` scaffold emitting a minimal green package. Every Theme-A and Theme-E bite is a facet
   of this one hole.

---

## CONFIRMED OVER-COMPLICATIONS

- **The flat 4-value `driver` enum.** The honest count is **2 substrates (`in_process` | `subprocess_isolated`)
  × a graph topology with loop-control as a composable node.** `graph` = today's `run_pipeline`; `oneshot`
  is a **phantom** (named twice in briefs, zero spec/acceptance/user); `loop` is, by m3's own admission,
  graph-self-edge + a data predicate sharing one interpreter. Selling 4 co-equal drivers forces a 4-way
  manifest enum, a 4-way discovery surface, and the M6 "one driver or compose process+graph?" open
  question — which **only exists because the taxonomy flattened an isolation axis and a topology axis into
  one list.** Name the two orthogonal axes and the open question disappears.

- **The dispatch request as god-object.** Symptom of missing-abstraction #3, not an independent flaw: with
  a RecoveryPolicy / budget-authority / observability-contract owned by the driver, liveness/cost/rate are
  consulted via those owners rather than smuggled per-request through both dispatch backends.

- **Three routing concepts for one gate.** `Edge.label`+`StepResult.next` (normal) vs
  `Edge.recommendation`+`verdict.recommendation` (gate), now compounded by M3's separate
  consequence map (advance|revise_in_place|restore_and_diverge|escalate) — matched in a priority order
  documented only in prose. Collapse to ONE model: a Step emits a routing key; the gate-consequence binding
  maps key→consequence; edges are declared by key. Of the 4 consequences, **three already exist as graph
  edges today** (advance = next-stage edge, revise_in_place = revise edge, escalate = policy path); only
  `restore_and_diverge` is genuinely new — add it as ONE new `kind='restore'` edge peer, not a parallel
  routing vocabulary.

- **A persisted reverse-recovery map.** Given missing-abstraction #2, the recovery map is `predecessors(stage)`
  on the realized graph, computed on demand — persisting it (even "derived from one relation") reintroduces
  a fourth copy that drifts after mid-run set-robustness. The plan over-builds here out of back-compat
  caution the realized-graph layer makes unnecessary.

- **The cross-process key/rate broker built for "two tenants" before per-package isolation exists.** The
  flock'd wall-clock ledger + global quota is real a2 engineering, but its value only materializes with
  mutually-distrusting external co-tenants — exactly the case it does NOT defend. It is half a solution;
  the hard part (per-package partitioning/accounting) is unscoped. (NOT "do less" — finish it.)

---

## CONFIRMED OVER-SIMPLIFICATIONS

- **"Planning keeps ONLY content."** False for F7/F8/F5/e1 (Theme D). Replace the word "content" with an
  explicit binding-implements-interface contract for these four.

- **"State-evolution axis behind ONE Store."** Three different mutation contracts papered into one
  interface, then the hardest value (event-sourced) shipped scaffold-only. forward-only ⊆ reversible is an
  honest superset; **event-sourced (write = append(event), read = projection) is a fundamentally different
  contract** — M4:39 itself says LWW state.json and a revisioned/event Store are "irreconcilable as one
  mutating contract," directly contradicting the EPIC table. Ship two honest values now (forward-only;
  reversible = forward + snapshot/restore); treat event-sourced as a SEPARATE backend with its own
  contract. Resolve the EPIC §36 vs M4:39 contradiction **in writing.**

- **"snapshot = copy the whole state.json blob."** Treats reversibility as bookkeeping-only. The M3
  acceptance toys (backtracking solver, mini-bisect) are valuable precisely because they mutate a world
  OUTSIDE the blob (file edits, git checkout); whole-blob restore rolls back the RECORD but not the WORLD,
  and M3 defers oracle/`run(cmd)` (the only undo mechanism) to M4. The reversible toy can only exercise
  pure in-memory rollback — the one case that never surfaces the gap. M3 must declare the snapshot
  BOUNDARY explicitly and add a `restorable_boundary` to the evolution axis that fails LOUD when composed
  with process/fan-out.

- **The acceptance toys as sufficient proof.** Every toy is written by an author who controls both ends and
  will hand-wire string channels and still pass green. Add an explicit acceptance check that **NO toy
  hand-rolls inter-step data plumbing** (all data crosses a declared Port) and **NO non-planning binding
  carries planning's `STATE_*` as mechanism.**

- **a5's "low risk" trust verdict** carried into M6 unchanged — correct for shared dispatch, dangerously
  wrong as the SOLE trust analysis once external packages are first-class (Theme E).

- **The parity gate as the epic's behavior guardrail** — structurally blind to the substrate swap it is
  asked to guard (Theme G).

---

## TOP RISKS (ranked)

1. **chain.yaml runs the wrong decomposition** → harness silently relocates planning to a pack at M3,
   before its substrate exists, inverting the deliberately-last `_BUILTIN_NAMES` drop. Highest
   probability × cheapest fix. (Theme F)
2. **No Port contract → "composition" is a filesystem fiction**; acceptance toys pass green while hand-
   wiring the exact reinvention the SDK exists to cure. Highest blast radius; retrofit touches executor,
   builder, step_helpers, subloop, and every M5 binding. (Theme A)
3. **No realized-graph layer → "collapse onto the graph" deletes the robustness projection and the `step`
   hatch**, printing wrong recovery commands to a stuck operator; the defining planning trick is never
   proven. (Theme B)
4. **No policy spine → retry/budget/observability/config smear**; fourth tool reaches back into planning or
   gets none; money has no single live authority across fan-out. (Theme C)
5. **"Binding = content" is false for F7/F8/F5/e1** → the two hardest features carry planning's full state
   vocabulary as mechanism; the disease survives one layer up. (Theme D)
6. **Discovery executes untrusted code with no diagnostics; public types pinned with no version gate** →
   ACE on the first community package + an unevolvable API on success. (Theme E)
7. **Happy-path gates guard substrate swaps** → concurrency/crash/resume/version-skew regressions ship
   green and surface at M6, the worst place. (Theme G)
8. **M5 as one ~9350-LOC all-or-nothing milestone** entangles the unresolved F7 seam with mechanically-
   clean F1/F4/F5; the whole milestone stalls on its hardest sub-part. (sequencing)
9. **Cloud recoupling (cloud/cli.py → auto.py::_phase_command) has no owner** between M5 (anti-scope) and
   M6 (silent) → 1432+775 LOC breaks at M6 with no parity oracle. (sequencing)
10. **The driving loop is extracted while in use** (M5 rebuilds chain/epic supervisor + override plane —
    the operator's own recovery levers); a frozen engine means F8's supervisor is never self-hosted, so
    its strongest dogfood test is structurally unreachable. (bootstrapping)

---

## CONCRETE CHANGES THE PLAN MUST MAKE (add / fix / re-sequence / reserve)

### Re-sequence (do these FIRST, they gate everything)
- **Regenerate chain.yaml to the 6 May-29 briefs** and archive the stale May-28 set BEFORE any run. Add a
  lint asserting chain.yaml idea-paths + milestone count match the EPIC. Treat **EPIC doc + brief set +
  chain.yaml as one artifact triple regenerated together.**
- **Land the Port contract in M2**, alongside `Reduce[T]`/`select` — M2 already rewrites every join/reduce
  signature; it is the ONE cheap moment to make `T` typed across the boundary instead of erased into
  `state["specs"]`. Arriving in M5/M6 makes it a rewrite of code M5 just shipped.
- **Land the graph linter / contract checker in M1/M2** — every later milestone adds more edges to mis-wire.
- **Make the realized-graph rewrite a first-class DESIGNED M3 piece** (`build_topology(config) -> Graph`),
  with the a3 §4.4 parity test ({5 robustness} × {with_prep, with_feedback} × {states} × {verdicts})
  landing as an **M3 GATE, not implicitly in M6** — the single-source collapse is unsafe until the dynamic
  projection is proven faithful (the gate→TIEBREAKER→ITERATE silent downgrade is this class already biting).
- **Re-decompose M5 into ordered sub-milestones** with their own chain entries + parity oracles:
  M5a node-lib (F1/F3/F9) → M5b F4 then F5 → M5c F6 then F7 (last, hardest seam) → M5d F8 supervisor
  (after M3's process driver settles). State the **back-edge explicitly: F8 depends on M6; F7 depends on F6
  + the realized-graph layer.**
- **Assign cloud-recoupling explicitly** — a guarded `_phase_command` shim landed in M3 when the process
  driver is born, plus a cloud smoke oracle wired into the chain. Not implicit in the M5/M6 seam.
- **Promote F7 to "ships separately, last"** and make **F8 explicitly DEPEND on F7** (today they are peers).

### Add (new abstractions / owners — the four nouns above, plus tooling)
- **Port + binder + StateDelta** (missing-abstraction #1): build-time DAG resolution; runtime port binding;
  revision-aware CAS merge replacing flat-key LWW BEFORE the process driver and versioned Store land.
- **Topology realizer** (missing-abstraction #2): the realized graph is the single source for `next_step`
  AND recovery; recovery maps computed on demand; re-invocable mid-run with a still-valid resume cursor.
- **Driver policy spine** (missing-abstraction #3): injected `RecoveryPolicy`; ONE live budget authority
  (natural home = the a2 key_broker/rate_broker — rate and spend are the same shared-depletable-resource-
  across-concurrent-pieces problem; the plan gives rate a flock'd ledger but spend three uncoordinated
  counters); a backend-agnostic **composition-observability contract** the driver emits by default and onto
  which introspect/doctor/trace/cost are re-homed (today hardwired to ndjson + planning payloads); an
  N-layer **config-precedence resolver** with a characterization test.
- **Run-outcome vocabulary** (missing-abstraction #4): the `(read_valid_targets, apply_transition,
  synthesize_artifacts)` trio F7 implements; the supervisor's failure policy invokes general control ops,
  not "force-proceed" by name; F5's reducer returns app-defined outcomes (apply m5 Open-Q#3's "primitive
  invokes binding reducer" lean to F5, not just F2).
- **Discovery trust boundary + manifest-first, non-executing discovery** (missing-abstraction #5): defer
  `exec_module` to selected-to-run, gated on operator trust tier; SDK-assigned `tenant_id`; per-package
  quota sub-budgets reserved in the ledger schema NOW; `arnold_api_version` on the manifest checked at
  discovery. **Re-open a5 with the import seam in scope before M6.**
- **Contract checker + diagnostic discovery + scaffold** (missing-abstraction #6): `pipelines check` /
  `pipelines doctor` / `pipelines new`, with the acceptance test "feed it a deliberately mis-wired package
  and assert it names the exact defect" — the mirror of the fourth-tool happy-path test.
- **Split the driver contract into orthogonal axes** (substrate × topology); delete `oneshot` from EPIC:36/m3
  or give it a real distinct contract+user; bind loop-predicate+teardown+max-iters as control on the walk.
- **Make state-evolution TWO honest values + event-sourced as a separate backend**; add `restorable_boundary`;
  amend EPIC §36 to M4's interfaces-with-backends framing in writing.
- **An always-on, program-level behavioral oracle that survives across milestones**: a standing
  characterization-replay harness (recorded real-run traces replayed against each milestone PR + against
  main nightly) PLUS substrate-swap oracles gated where the swap happens — (a) resume-across-versions,
  (b) crash-isolation (process driver contains a mid-run kill; in-process loop does NOT — elevate m3
  done-criteria #2 to an epic gate), (c) a planning-SHAPED self-host smoke test running beside the frozen
  epic engine every milestone.
- **A named old-engine/new-engine strangler boundary with an epic-level liveness invariant**: "OLD engine
  still boots + drives a 1-milestone throwaway plan AND a planning-shaped plan runs on the NEW pieces" —
  gated every milestone. Add a named throwaway **canary epic** as F8's only honest acceptance (the real
  epic can't self-host its own supervisor). Extend the freeze list to explicitly include the chain
  supervisor loop and the override plane for the whole epic.

### Fix (splits / contradictions stated in writing)
- **M2 done-criteria: ZERO `GateRecommendation` references survive in SDK-side modules** via a CI grep gate
  (confirmed live in 6 _pipeline modules), and re-type `PromoteFn`/`JoinFn`/`Reduce[T]` to structured data
  in the SAME milestone. **Partial conversion is worse than none** — it hides coupling behind a green gate.
- **Collapse routing to ONE model**; add `restore_and_diverge` as one new edge kind, not a parallel map.
- **Resolve EPIC §36 "one Store" vs M4:39 "irreconcilable" in writing**; pick interfaces-with-backends.
- **Add acceptance checks** that no toy hand-rolls inter-step plumbing and no binding carries `STATE_*` as
  mechanism — the two checks that turn the fourth-tool test from a happy-path toy into honest proof.

### Reserve room (decisions cheap now, migrations later)
- `arnold_api_version` + per-node-library stability tier (`stable|provisional|internal`) + deprecation/alias
  policy mirroring planning's name-alias policy — reserved NOW so the epic can keep reshaping provisional
  types while stable ones carry a contract.
- Per-tenant sub-budget schema in the broker ledger — retrofitting into a flat `time.time()` ledger is a
  migration.
- `version` field on the Port and `restorable_boundary` on the Store axis — reserved at M2/M3 so versioning
  and reversibility-composability are not retrofits.

---

## The one-sentence indictment
The plan got the **verbs** right and is correctly hardening the **value types**, but it ships an SDK whose
**channels (Port), graph (realized topology), brain (policy spine), control vocabulary (run-outcome), and
edge (trust + version + contract-checker) are all still planning-shaped or simply unnamed** — so at full
ambition the acceptance toys pass green by hand-wiring exactly the reinvention the SDK exists to abolish,
and the disease the stress-test cured one layer down survives, untreated, one layer up.
