# Arnold SDK — composable pieces for building pipelines & agents

> 🚀 **FULL VISION — category bet, NO demand gate (decided 2026-05-29).** This is a category-creating
> platform built from conviction, not gated on current demand. The unknown-unknowns swarm's demand/business
> findings (N=0 builders, founder-portfolio, "sell an MVP first") are consciously **set aside** — "no
> builders yet" is what *before the category exists* looks like; you build the world, the builders come.
> BUT going all the way means building it *right*, so the swarm's **architectural** findings
> (`validation/unknown-unknowns/SYNTHESIS.md`) are taken as REDIRECTS that make the vision bigger, not
> smaller. The plan below is being re-aimed to these five:
> 1. **Keep the soul.** The self-improving Plan-Execute-Verify harness + cheapest-capable-model routing
>    calibration is the privileged HEART, not stripped to "example #3." Decouple "technically a discovered
>    module" from "no special status." (Reverses the M6/M7 "grep-prove zero planning vocabulary" overshoot.)
> 2. **Right foundation.** Durable, content-hashed, journaled execution — NOT the single-writer `.megaplan`
>    substrate every durable-execution engine abandoned. Multi-day/multi-tenant/resumable is core, not later.
> 3. **Right primitive.** A pluggable scheduler / activation model spanning standing & interactive processes
>    (no terminal state) and *emergent* graphs — not just DAG/loop. (The select+reduce gap was one level too
>    shallow.)
> 4. **Built for AI-authored topologies.** Workflow-as-data the model emits; the runtime's durable value is
>    the invariants it enforces on machine-emitted graphs, not a verb library for human coders.
> 5. **Safe-composition as the spine.** `Port = (type, version, provenance, taint)` decided at M2 — an OS,
>    not a plugin folder.

## The architecture — the organs the vision implies (committed-UU swarm, 2026-05-29 · `validation/committed-uu/SYNTHESIS.md`)
Built right, this is an **event-sourced, content-addressed, ledger architecture** — a runtime/OS for
autonomous work — NOT a DAG-walker with a `state.json`. Eleven first-class organs the vision implies (today
built 0-to-N times as ad-hoc side-channels); naming them now is the highest-leverage move, because each
unnamed one is otherwise built 3-5× inconsistently:
- **Activation** — the real scheduler primitive: persisted+supervised record of a node firing with a
  *pluggable readiness rule* (DAG=upstream-done · fixpoint=changed-not-converged · standing=mailbox · market=
  fire-N-select-K · emergent=producer-declared) + lifecycle. Subsumes Port+scheduler+`state.json`.
- **Conveyance / Work-Envelope** — conserved run-context on every edge (identity+lineage+taint-lattice+cost+
  deadline+cancellation+error-class+retry-budget). Port's temporal half. *Nothing crosses a seam naked.*
- **Governor + Capacity-Lease** — dynamics safety: tree-scoped recursion/cost budget + linearizable
  cross-tenant arbiter (fencing tokens). Stops AI-emitted recursive graphs fork-bombing shared keys/wallet.
- **Effect Ledger** — typed world-acts: replay-class (pure|idempotent-keyed|at-most-once|pivot) + external
  idempotency-key ≠ content-hash + declared compensation.
- **Contract Ledger** — the type *system*: admission validator + machine repair-negotiation (halt→gradient) +
  taint-propagation-in-cache-key + optimizer-can't-redefine pinned meaning.
- **Calibration Ledger** — CapabilityClaims + decay/churn + exploration budget + taint-aware aggregation; the
  1-5 score & `tier_models` become projections; routing = a query.
- **Evaluand + one Ledger** — versioned attributable judgments in ONE content-addressed log every surface
  reads and nothing recomputes; "is the new version better?" = a join, not a vibe. For a self-improving heart
  this IS the spine.
- **Behavioral Identity Manifest** (genome) — hash the behavioral *closure* (topology+step-code+prompt-bodies+
  routing-taken+ABI+dep-closure), not the output file. Resume/reproduce/diamond/semver = a manifest-diff.
- **Replayable Capsule** — portable unit of exchange (Definition+Contract+Lineage+Evidence); registry/
  inspector/fork-with-back-edge are operations on it.
- **Warrant** — outward atom: signed authority + verified-work + decision-time rationale, *shape-independent*
  (one-shot action and a 200-turn emergent graph yield identical Warrants — keeps 2030 from foreclosing us).

**The data model — how typed data flows across node types (the conclusion the Port/Conveyance/Contract
organs lead to; was implicit).** A Port is `(kind × content-type × schema)` + the envelope. **kind** = `value`
(inline, lives in the event log) | `artifact` (by **content-hash reference** to a blob store, never inlined) |
`stream`. **content-type** = a MIME-like **OPEN registry** (`text/markdown`, `image/png`,
`application/x-git-diff`, `…/verdict+json`) — a new domain (audio/3D/video) registers a content-type; the core
never changes. **schema** = a content-hashed schema in the Contract Ledger for structured values; for
artifacts the content-type IS the contract. **Each node declares `produces`/`consumes` Ports** (that's a node
"encoding its format"); the binder resolves `consumes`↔`produces` at build/emit time via the Contract Ledger
(structural + content-type + legal-coercion match) and **fails admission with a machine-readable repair
gradient** ("B wants X, A emits Y; legal moves: …") an LLM author climbs. **Generic nodes are polymorphic over
content-type; domain *meaning* lives in the rubric/prompt/realizer (app content), never in the type** — so the
same `produce/judge/gate/select/reduce` serve dev (x-git-diff) / writing (markdown) / image (png), differing
only by content-type (which selects the evidence realizer) and rubric. Taint/provenance ride the Conveyance on
every value *regardless of format*. Guardrails against overcorrection: **open** (not nominal/closed) types;
meaning **out** of the type; the type system is for **machine-authorship admission + repair + taint/cache
keys, just-strong-enough**, not a human-ergonomic static type theory. Minimal organs (Port = dataclass +
binder + coercion table; Ledger = append-only log), designed toward the whole, each at its thinnest slice.

**Seven architecture-reshapers (foundational, NOT retrofittable):** (1) **state = deterministic fold over an
append-only, effect-typed, taint-carrying event log** (WAL authoritative; `state.json` a cache) — *Reshaper
#1, everything stands on it*; (2) the **Activation** (not graph shape) is the scheduler primitive; (3) **Port
runtime-enforced**, taint a propagating lattice in the hash + a typed declassification edge; (4) a
**tree-scoped Governor + Capacity-Lease** under the scheduler / over the key pool; (5) **one Ledger**,
recorded-into never recomputed-from; (6) the **Manifest** is what the content-hash points at; (7)
**model-identity is a hash-pinned provenance fact**.

**Tensions to design for (not solve away):** self-improvement vs durable replay (the model IS the control
flow); cheapest-routing vs prompt-caching (physically antagonistic — ~10× vs ~100× input cost); taint/privacy
vs the cross-tenant calibration flywheel (data gravity = the real moat); the routing monoculture attractor;
the eval-ruler-as-unversioned-float (Goodhart); the calibration loop's censored co-degradation.

**Consequence:** the milestone program below predates this and gestures at only a few organs (Port, realized
graph, policy spine). It is being **re-derived onto Reshaper #1 (the event-sourced ledger foundation)** with
the organs as the abstraction set — together with the zero-human-blocker pass.

**Status:** Design of record (consolidated 2026-05-28). This is the SINGLE source of truth; it supersedes
all prior versions of this doc. Investigation evidence (append-only record, do not rewrite):
`briefs/validation/{c1-c7, s1-s4, u1, u2}.md`, `briefs/validation/premortem/{p1-p8, SYNTHESIS}.md`,
`briefs/validation/confidence/{k-arnold-reconciliation, a2-a7, d1-d4, SYNTHESIS}.md`,
`briefs/validation/decision/{resident-shape, migration-fit, interface-feasibility}.md`.

## The goal (Peter)
> **Other people build on the same pieces to CREATE new things.**

Arnold is a **builder SDK**: a set of reusable pieces a developer composes to make a new pipeline or
agent without reinventing dispatch, state, emission, evidence, or orchestration. **Megaplan-planning and
the resident agent are the first two apps built on it** — and the source of the initial backends. Success
= a *third* builder ships a *fourth* thing cheaply.

## The framing that took us a while to reach
The wrong question was "what do planning and resident *share*?" — it leads to a thin waist. The right
question is "what does a *new builder* need?" The diversity between the two existing apps (subprocess vs
async dispatch; last-writer-wins JSON vs transactional/leased Store; graph vs event-loop) is **not a
conflict to resolve — it is the menu of backends/drivers the SDK offers.** resident bringing its own
runner is the symptom the SDK exists to cure: a builder had to reinvent dispatch because the piece didn't
exist yet.

## Discipline (the principle)
The SDK offers **general capabilities**; **domain specifics stay in the app/package.** Test each piece:
*would an unrelated builder want this?* Yes → SDK. Planning-only → stays in the planning package.

| SDK piece (general, builder-facing) | App/domain-local (stays put) |
|---|---|
| `dispatch` interface + backends: `subprocess-cli` (from planning), `async-api` (from resident); handles key-pool, cost, stall/liveness | the 4-verdict gate vocabulary; planning's prompts |
| `state` = the **Store** (durable, transactional, leased) — the canonical state piece for new builders | planning's specific state schema/contents |
| `emit` = an `EventSink.emit(kind, payload, scope)` verb + backends (`events.ndjson`, Store `EpicEvent`) | — |
| `evidence` = injected strategy: `git` / `audit` / `none` | how planning specifically judges code diffs |
| **node library** = `patterns.py` (critique_revise_gate_loop, fanout, panel, vote, gate, …) — already real | planning's specific node wiring |
| **drivers** = `graph` / `loop` / `process` / `oneshot` runtimes a package plugs into | robustness levels; the execute task-DAG |
| **package contract** = manifest + **SKILL.md** + driver choice + domain code; discovery makes external packages first-class | the 9 override actions; chain/epic/bakeoff orchestration |
| (general) human-gate / pause-resume hook; cloud-hosting; parameterize-by-config | planning's specific robustness presets & override semantics |

Feasibility note (from `interface-feasibility.md`): the pieces are interfaces **with multiple backends**,
NOT one forced mechanism — you do not unify planning's subprocess dispatch and resident's async runner
into one engine; you offer both as backends behind one `dispatch` interface. Same for `state`/`emit`.

## What this means for planning — it becomes a module like any other
**Full extraction. No privilege, no exit, no "opportunistic adoption."** Every planning feature is pulled
into a general SDK piece + a thin planning-app binding (see the feature→form table above), and planning is
then re-expressed as a *composition* of those pieces — discovered identically to jokes/doc (manifest +
driver + domain bindings + SKILL.md), with no `_BUILTIN_NAMES` and no special execution path. The
migration-fit gaps are NOT deferred as "planning domain logic" — they become real SDK pieces *because
other builders need them too*: process isolation → a `process` driver; the control/override plane → a
control / pause-resume service; robustness reshaping the graph → parameterize-graph-by-config; chain /
epic / bakeoff → a supervisor tier. Planning keeps only its *content* — prompts, rubrics, the 4 verdict
labels, its tier map, its robustness presets — as the thinnest possible bindings. The bar: planning reads
as a composition, and a fourth, non-planning tool ships on the identical parts.

## Primitive contract — evidence-backed (abstraction stress-test 2026-05-28)
Stress-tested by sketching 5 deliberately-divergent pipelines (constraint solver, bounty market, genetic
tournament, git-bisect, red/blue) as compositions and comparing vs this plan. Full report:
`briefs/validation/decision/abstraction-stress-test.md`. Verdict: **the verbs are at the right altitude;
the TYPES are too planning-shaped.** All 5 domains bent the SDK the same way. The SDK as first drafted only
expresses *forward-only, single-producer, verdict-routed, revise-in-place* pipelines — i.e. planning's own
shape. Fix = decoupling, not new verbs.
- **Smoking gun:** `JoinFn` returns `GateRecommendation` (`pattern_types.py:19`) → no non-planning builder
  can use `vote`/`reduce` without inheriting the 4-verdict enum. App vocab leaking into a general piece (4/5).
- **Confirmed primitives (core):** produce, judge, gate, revise, fan_out, escalate, clarify, verify, loop_until (shape), state, emit.
- **Missing primitives (ranked by sketches needing them):** `select(items, rule)→(winner, losers, scores)`
  — selection ≠ judge (**4/5, biggest gap**); data-valued/generative `reduce` (3/5); a **real loop driver**
  with a data predicate + teardown — today `iterate_until` drops its predicate (`pattern_topology.py:288`),
  it's graph sugar (4/5); a stop-predicate library (4/5); oracle evidence + `run(cmd)→{exit,stdout,stderr}`
  (2/5); reversible state (`snapshot`/`restore`), `accumulate`, depletable `budget` (a capability class).
- **Wrong-altitude fixes:** reduce/join → structured data (4-verdict mapping moves to the planning app);
  parameterize `gate` consequence (`advance | revise_in_place | restore_and_diverge | escalate`);
  state-evolution as an axis (forward-only | versioned/reversible | event-sourced) behind one Store;
  split `verify` into attestation (notary) vs oracle (measuring instrument that branches control flow).
- **Priority:** P0 = structured `reduce` + `select` + move 4-verdict to the app + wire the dropped predicate
  (touches every hard sketch). P1 = real loop driver / `run(cmd)` / oracle evidence. P2 = state-evolution
  axis + gate-consequence param. These are decouplings + a few additions, not a rewrite.

## Proof of success (acceptance tests — build these, don't just assert)
1. **A non-planning-shaped package** (the load-bearing test): one deliberately un-planning-like tool — a
   `select`-based tournament, a `snapshot/restore` search, or a `run(cmd)`-oracle bisect — built on the SDK.
   jokes + the two existing apps are ALL forward-only/verdict-shaped and would never surface the gaps; the
   only honest proof "others can build a fourth thing" is a fourth thing not shaped like the first two.
2. **A new, simple pipeline is cheap** — upgrade `jokes` from a stub to a real SDK-built pipeline (~50
   lines of domain code + "I'm a `graph` driver, I need `dispatch`+`emit`").
3. **Planning reads as composition, not as the SDK** — a reader can point at planning and say "`iterate` is
   just planning's binding of `revise_in_place`." If planning's verdicts ARE the SDK's only reduce output,
   the example is a trap, not a teacher.
4. The two existing apps can each name which SDK pieces they'd adopt without a rewrite.

## Structural pieces the SDK must ADD (interrogation 2026-05-29 — `interrogation/SYNTHESIS.md`)
Ten adversarial lenses (ambition fixed) converged on ~4 deep missing nouns + 2 edge pieces. Without these
the SDK "composition" is a filesystem convention and the acceptance toys pass green by hand-wiring the very
reinvention the SDK exists to abolish. These are first-class, not refinements:
1. **Typed Port + binder + StateDelta** (the keystone — every other gap is a verb about it). `Port =
   (name, kind: artifact|value|stream, schema, cardinality, version)`; `Step` gains `produces`/`consumes`;
   the builder resolves `consumes`↔upstream `produces` at **build time** (fails `build()` on missing/
   typo'd/mistyped dep); the executor **binds** ports at runtime from upstream outputs — killing the
   `step_helpers.py:104` `v1.md` silent fallback. State side = `StateDelta` (replace|accumulate|deep-merge
   + version, **CAS not flat-key LWW** — replaces `executor_owned_keys`). `last_fanout_results` becomes a
   typed Port the fan-out join writes. (Lands in M2, alongside the type work — arriving later rewrites code.)
2. **Realized-graph / topology-realizer**: `build_topology(run_config) -> Graph` — an ordered rewrite fold
   matching `_ROBUSTNESS_WORKFLOW_LEVELS`, re-invocable mid-run (set-robustness mutates it live). The SINGLE
   source both `next_step` projection and reverse-recovery maps query (recovery = `predecessors(stage)` on
   demand, no persisted 4th copy). Root cause of "3 encodings" is *no realized graph to project from*.
3. **Driver policy spine**: an injected `RecoveryPolicy` (`classify(error)→{retry_fresh|retry_transient|
   escalate|halt(kind)}` + per-class budgets — auto.py's brain, "retry" ×104, never extracted); ONE live
   budget/cost authority folding across fan-out shards (natural home = the key/rate broker — rate & spend
   are one shared-depletable-resource problem); a backend-agnostic **composition-observability** event
   contract (re-home introspect/doctor/trace/cost onto it); an N-layer **config-precedence resolver**.
4. **Run-outcome / control vocabulary**: `{succeeded, failed, escalated, blocked, awaiting_human}` +
   `valid_targets(state)`/`recover_targets(state)`; the control interface is a `(read_valid_targets,
   apply_transition, synthesize_artifacts)` trio the binding IMPLEMENTS. **Evict planning's `STATE_*` from
   the control plane & supervisor** exactly as we evicted the 4-verdict enum from `JoinFn`.
5. **Discovery trust boundary**: manifest-first, **non-executing** discovery (read name/driver/entrypoint/
   capabilities/SKILL/`arnold_api_version` WITHOUT importing); defer `exec_module` to selected-to-run, gated
   on operator trust (in-tree/blessed/quarantined); SDK-assigned `tenant_id` + per-package quota sub-budget.
   Re-open `a5` with the IMPORT seam in scope before M6.
6. **Contract checker + diagnostic discovery + scaffold**: `pipelines check` (statically prove a composition
   is wired — every `consumes` resolves, every edge targets a real stage, gate verdicts have edges),
   `pipelines doctor` (per-path discovered✓/rejected+traceback/skipped — kills silent vanish), `pipelines new`.

**Resolved over-builds / contradictions (in writing):** the `driver` enum is 2 orthogonal axes — **substrate
(`in_process`|`subprocess_isolated`) × topology (graph, loop-control as a node)**; `oneshot` is a phantom —
delete it or give it a real contract. **Collapse the 3 routing concepts to ONE** (a Step emits a routing
key; a binding maps key→consequence; edges declared by key) — `restore_and_diverge` is ONE new `kind='restore'`
edge, not a parallel map. **State-evolution = two honest values now** (forward-only; reversible = forward +
`snapshot`/`restore` with an explicit `restorable_boundary` that fails LOUD under process/fan-out);
**event-sourced is a SEPARATE backend with its own contract** — this resolves the EPIC "one Store" vs the
M4 "irreconcilable" contradiction toward interfaces-with-backends. **"Planning keeps only content" is false
for the control plane / supervisor / execute-classification — they implement the control interface; say so.**

## The EDGES (boundaries) — full map: `../validation/edges/edges-map.md`
12 edges, none fully crisp today: namespace · command · **SDK-surface-vs-app (the most-violated — planning's
`STATE_*`/`GateRecommendation` leaking through general pieces)** · data (Port) · state (Store) · trust (the
import seam = ACE) · substrate · version/stability · + the implied control / policy-spine / routing /
realized-graph / strangler edges. The three most under-served are made crisp by: **M5c** (the SDK-vs-app
`STATE_*` eviction), **M2** (the Port), **M6** (the trust/import seam, with `a5` re-opened on the import path).
The outward surface — builder docs and the command-edge migration — is owned by **M7** / **M6**
(`builder-docs.md`, `cli-migration.md`).

## ⚠️ PRE-LAUNCH — launch-clean status (verification 2026-05-29 · `validation/prelaunch/SYNTHESIS.md`)
A pre-launch sense-check found the triple was spec-valid but not autonomously runnable. The in-repo blockers
are now **CLEARED** (engine patch landed + chain.yaml/brief corrections); only the operator pre-step remains.
Status of each original launch-blocker:
- **The autonomy ladder — CLEARED.** The engine-readiness patch landed on `main`: `FailurePolicy.from_yaml`
  parses `retry:/escalate:/abort:`; `bump_profile`/`bump_robustness` are implemented; `_handle_outcome` walks a
  **bounded** per-milestone retry counter (cap 2, capped to 1 for apex/extreme — cannot loop); `require_clean_base`
  is parsed + enforced (`_assert_clean_base`); ladder-exhaustion auto-files a megaplan ticket. `chain.yaml` now
  declares the real ladder (`on_failure: {retry, escalate, abort}`, `on_escalate: {escalate, abort}`).
- **M0 bootstrap paradox — CLEARED.** Chain milestone #1 is now `m0-harness-floor` (the in-repo harness subset:
  report-only schema validator + dual-run rig + oracle/replay harnesses + corpus). The pinned-engine/venv/launch
  part is the operator pre-step below, not a milestone.
- **`merge_policy: auto` oracle gate — REMAINS OPERATOR.** `gh pr merge --auto` defers to GitHub branch
  protection and falls back to an unconditional squash merge. Oracle-gated merge is real ONLY if the
  parity/strangler/grep gates are wired as **base-branch REQUIRED CHECKS** — this is a LAUNCH PRECONDITION
  (operator pre-step step 2). `chain.yaml`'s `merge_policy` block documents this loudly; keep `auto` only after
  the checks are wired, else set `review`.
- **`∥`/`depends_on` — CLEARED (as documented serial order).** `MilestoneSpec` has no dependency field; the
  chain is a single serial cursor that runs milestones in listed order — which IS the correct topological sort.
  `chain.yaml` now states explicitly that ordering is enforced by linear list order + each milestone's strangler
  gate, and every `∥` is a topological-sort assertion, not runtime concurrency. The non-negotiable M5-eval→M5-cal
  edge holds because m5-eval is listed before m5-cal. (A harness-enforced `depends_on`/gate field is a possible
  M1 hardening; serial-in-correct-order is acceptable for launch.)
- **Brief seam mismatches — CLEARED.** M2 defines `RoutingKey`; M5b names the `BatchReduceResult` handoff type +
  M5c carries the `{success,blocked_by_quality,blocked_by_prereq,timeout}→{succeeded,failed,escalated,blocked,
  awaiting_human}` mapping table; M5d owns the auto-merge-on-green actor (M5c F6 is halt-only); M5-cal's
  EvaluandRef re-targets M5-eval's taint-bearing record; M2.5 fixes `_pipeline_paused_stage`'s home
  (`run_cli.py:267` read / `human_gate.py:94` write / `cli/__init__.py:951` pop) + four-way resume
  (`awaiting_user.json`); M4 "kill the vendor classifier" → "stop the *new* path reading it; old stays live,
  retired at M6"; M5c control method aligned (`read_valid_targets` interface / `valid_targets` binding).

## ⚠️ PRE-LAUNCH — operator pre-step (the ONLY remaining human work before `chain start`)
The engine patch + all in-repo artifacts are launch-clean. The human performs these (none is a chain milestone)
then runs the single authorizing `megaplan chain start`:
1. **Build the frozen pinned engine.** Create a venv and install megaplan from `main@t0-sha` (the engine that
   DRIVES the chain — old W1). Verify `megaplan.__file__` resolves to the pinned copy, not the worktree
   (defeats p3 H3 / MEMORY dogfood-shadow). This is the operator pre-step, NOT `m0-harness-floor` (a milestone
   cannot pin the engine running it).
2. **Wire the gate CI checks as base-branch REQUIRED CHECKS** on `main` (parity / strangler / grep gates). This
   is what makes `merge_policy: auto` safe — without it, auto-merge falls back to an unconditional squash. If you
   cannot wire them, set `merge_policy: review` in `chain.yaml` instead. **LAUNCH PRECONDITION.**
3. **Set an external wallet / budget ceiling** for the whole run (~$500–$1,200, budget the upper band). The
   in-band Governor/Capacity-Lease is built mid-run by M3; the chain has no spend-cap field, so the ceiling is
   external (provider budget cap).
4. **Launch** `megaplan chain start --spec briefs/epic-pipeline-unification/chain.yaml --no-git-refresh` from the
   pinned interpreter against the worktree as target. This single human `chain start` IS the authorization —
   there is no auto-arm (the M1/W8 lint is M1's own output and cannot gate the run that produces it).

## Sequenced build program — FINAL (sequencing panel, 2026-05-29 · `validation/sequencing/PROGRAM.md`)
Three architects (dependency-DAG / strangler-keep-alive / risk-value) reconciled into one order: DAG edges are
forced; the **strangler envelope is the binding constraint** (adopted wholesale); risk-value reshapes only
within it. **Reshaper #1 (event-sourced foundation) is the floor.** This supersedes the milestone shape below.

**Critical path (the spine):**
- **M0 — Keep-alive floor:** a PINNED external megaplan engine in its own venv drives the epic against the
  worktree (`--no-git-refresh`, so the executing code never changes mid-flight) + schema validator report-only +
  the standing dual-run rig + behavioral-replay/substrate-swap oracle skeleton. *(Solves rebuild-while-flying.)*
- **M1 — Foundation / hygiene / contract-checker + R1 shadow-WAL seed** (+ seeded R7/Effect skeleton).
- **M2.5 — auto.py characterization spike + single-resume-model decision** (de-risks M3; runs ∥ M2).
- **M3 — THE HINGE:** the **Activation** primitive + realized-graph + 2-axis drivers + the **Conveyance**
  envelope + **the R1 authority-flip** (event log authoritative; `state.json` a cache) + **Governor/Capacity-Lease.**
- **M4 — Services + spine:** dispatch/emit/evidence + **Effect Ledger** (enforced) + **RecoveryPolicy** + the
  **one Ledger** (R5) + Evaluand scaffold.
- **M5b — execute realm** (complexity-tiering → task-DAG scheduler).
- **M5-eval — Evaluand + the one Ledger** (versioned attributable judgments — *the spine*; **gates Calibration**).
- **M5-cal — Calibration Ledger** (CapabilityClaims + decay/exploration; routing = a query). *M5-eval→M5-cal is
  non-negotiable: routing before the versioned ruler = Goodhart on an unversioned float.*
- **M5c — control plane** (run-outcome vocabulary; evict planning's `STATE_*`).
- **M6 — THE STRANGLER SWAP:** megaplan-as-module + `arnold` namespace + trust boundary + journal unification +
  R7 load-bearing; **atomic, oracle-gated cutover — the LAST load-bearing node**, so no multi-week broken window.
- **M5d — supervisor tier** (after M6; canary-epic acceptance). **M7 sinks** (Capsule ∥ Warrant ∥ docs) project off the Manifest+Ledgers.

**Parallel tracks:** M1∥M2 · M2∥M2.5 · M5a∥M5b∥M5-eval (off the M4 base) · M6∥M5d · M7 sinks.
**Strangler discipline (machine-gated every milestone):** OLD engine still self-hosts the build (pinned/frozen,
report-only schema, flag-off) AND a planning-shaped throwaway runs on the new organs behind a default-OFF flag;
the **behavioral-replay + substrate-swap oracle is the SOLE retirement authority** (never the substrate-blind
happy-path parity gate). No organ-swap and its old-path deletion share a PR; M6 is the single atomic flip.
**Top risks:** (1) M3 R1 authority-flip = max danger (last version-isolation seam, longest rope) — mitigated by
the M2.5 pre-merged oracle + fold-equivalence vs a recovery/**blocked** corpus + default-OFF flag; (2) R1
seed-early/enforce-late must validate against real recovery/blocked traces; (3) M5-eval→M5-cal non-negotiable;
(4) Governor's Capacity-Lease built before a 2nd tenant (synthetic-adversary oracles); (5) M6 atomic swap is
irreversible (gated on a full discovered-planning dual-run milestone + `megaplan` aliases fallback).

## (SUPERSEDED by the sequenced program above) earlier milestone shape — FULL EXTRACTION, interrogation-hardened
- **M1 — Foundation, hygiene & the contract-checker** (standalone PRs): CI marker-switch; executor-merge
  superset; state back-compat (`extra="ignore"` + fixture corpus); pin status/chain contracts;
  discovery-integrity guard; sandbox fail-*open* fix; **`pipelines check`/`doctor` graph linter** (every later
  milestone adds edges to mis-wire); a **chain.yaml↔EPIC↔briefs lint** so the executable artifact can't drift.
- **M2 — De-planning types + the Port**: `reduce`/`JoinFn`→structured data with a **CI grep gate: ZERO
  `GateRecommendation` in SDK modules** (partial conversion is worse than none); `select()`/`Reduce[T]`;
  the **typed Port + binder + StateDelta (CAS)**; wire the dropped `iterate_until` predicate + stop-predicate
  library. Acceptance #1 + the check "**no toy hand-rolls inter-step plumbing**."
- **M3 — Drivers + realized-graph + state-evolution**: the **2-axis driver** model; the **topology-realizer**
  with the `{5 robustness}×{prep,feedback}×{states}×{verdicts}` parity test as an **M3 GATE** (the collapse is
  unsafe until the projection is proven faithful); loop-control as a node; state-evolution = two honest values
  + `restorable_boundary`; the cloud `_phase_command` shim born here with the process driver.
- **M4 — Services + the policy spine**: `dispatch` (2 backends), `emit` (one contract), `evidence`
  (attestation + oracle/`run(cmd)`), `config`-precedence resolver, and the **driver policy spine**
  (`RecoveryPolicy` + ONE budget authority + composition-observability contract). Re-home introspect/doctor/
  trace/cost onto the observability contract.
- **M5a — node library** (F1/F3/F9): formalize `patterns` as the composition vocabulary (provisional tier).
- **M5b — execute realm** (F4→F5): the task-DAG scheduler; F5's reducer returns **app-defined outcomes**.
- **M5c — control plane** (F6→F7, last/hardest): the run-outcome vocabulary + control interface; planning's
  `STATE_*` binds onto it. F7 ships separately, last.
- **M5d — supervisor tier** (F8, depends on M6 + the process driver): general cross-run orchestration invoking
  general control ops (not "force-proceed" by name); its only honest acceptance is a **throwaway canary epic**.
- **M6 — Megaplan as a discovered module + `arnold` namespace + trust boundary**: relocate planning, drop
  `_BUILTIN_NAMES`, manifest + driver + bindings + SKILL.md; **manifest-first non-executing discovery + trust
  tier + `arnold_api_version`**; collapse the next-step encodings (now safe — M3 proved the projection);
  resident adopts the pieces. Proof: planning reads as composition; a fourth non-planning tool ships on the
  same parts; **no binding carries `STATE_*` as mechanism**. The CLI/namespace migration (the command edge —
  `../validation/edges/cli-migration.md`) lands here: introduce `arnold <verb>` (umbrella) + `arnold <module>
  <verb>` (e.g. `arnold planning gate`, `arnold run planning`); move the per-run inspectors up (gated on M5c
  de-planning their payloads); split `auto`/`override` along the control/planning seam; back-compat aliases
  keep `megaplan <x>` resolving until the rename trigger.
- **M7 — Builder documentation & onboarding** (gated on M6): the `docs/arnold/` set — authoring guide +
  **generated-from-types reference** (CI drift-gated) + package-contract + worked examples (jokes / the
  non-planning tournament / planning-as-composition) + tooling docs. Acceptance: an external builder ships
  the `select`-tournament from docs + scaffold ALONE, with a grep proving **zero planning vocabulary**.
  Design: `../validation/edges/builder-docs.md`.
- **Standing (gated EVERY milestone, not a milestone):** a **strangler boundary** — OLD engine still boots +
  drives a throwaway plan AND a planning-shaped plan runs on the NEW pieces; a program-level **behavioral-
  replay oracle** (recorded real-run traces vs each PR) + **substrate-swap oracles** (resume-across-versions,
  crash-isolation, version-skew) gated where the swap happens; freeze list includes the chain supervisor +
  override plane for the whole epic.

## Deferred (genuinely not needed yet)
The symmetric 5-method Realizer Protocol (the mode-keyed evidence seam suffices); full `HandlerContext`
"pure handlers" + 81-field typing (the `config` piece + bindings cover it); PR#43 re-home (only if a
CodeRealizer is ever built). (`deferred/` holds v1 drafts.)

## Cross-cutting / guardrails (every milestone)
Back-compat (`extra="ignore"`, name aliases, keep planning phase names valid in profiles, `handle_*`
`__all__` shims, preserve 26 `MEGAPLAN_*`); the missing surface (the 2 other subprocess drivers
`workflow.py::resume_plan` + `loop/engine.py`, the 3rd next-step encoding `workflow_next`, the 2nd
cloud→auto coupling `cloud/cli.py::_phase_command`, raw `state.json` readers, 63 raw `state["config"]`
reads); SKILL.md becomes a required package element; don't dogfood off an editable install (pinned engine,
schema report-only till last); parity gate stays green & honestly labelled (control-flow/artifact parity
on the happy path, not "drift provably zero").
