# Adjacent-Field Transplant — Unknown-Unknowns for Arnold

**Vantage:** four masters of adjacent fields look at "a runtime that composes, schedules, and
self-improves graphs of AI computations" and name the solved problem we're reinventing or the
failure mode their field has a word for. Lenses: OS designer, programming-language designer,
control-theory/cybernetics, gene-regulatory/metabolic-network biologist.

**Grounding (what actually exists today, read from the repo):**
- A graph executor (`_pipeline/executor.py`) walking frozen `Stage`/`Edge`/`PipelineVerdict`
  types; edge dispatch is override > gate > label. Subloop edges run child pipelines.
- State is an **accreted `state.json`** — no `schema_version`, ~30 `save_state_merge_meta`
  sites, a 3-key allowlist bridge, split-ownership disk merge (per `docs/foundation-audit/`).
- An **append-only `events.ndjson` journal** is *proposed* (`observability-and-introspection-design.md`),
  not yet the source of truth — state is still a clobbered snapshot.
- Discovery is a **best-effort plugin loader** (`registry.py`), prompt registration is
  "import for effect," silent-skip on bad packs is a named risk.
- `auto.py` (~1846 LOC) uses the **subprocess boundary AS the isolation boundary** — OS
  process groups, signals, timeouts, kill-grandchildren give crash containment for free.
- The router is a single scalar: `finalize` scores each task **difficulty 1–5**, that score
  drives cheapest-capable-model dispatch.
- **Port = type+version+provenance+taint** and "emergent graphs / models emit pipelines"
  are *vision-aspirational*. No taint type, no provenance lattice, no port contract exists yet.

---

## Lens 1 — OS DESIGNER

**What they see:** Arnold is an operating system whose processes are LLM calls, whose syscalls
are tool invocations, whose scheduler is the pipeline executor, and whose kernel state is
`state.json`. Every hard-won OS abstraction has a counterpart here — and we have built almost
none of them.

- **The journal IS a write-ahead log, but state.json is not a page cache over it.** An OS
  designer's first reflex: in a journaled FS, the journal is *authoritative* and the live
  structures are a derived, rebuildable cache. Arnold has it backwards — `state.json` is the
  truth (clobbered, racy, ~30 writers) and `events.ndjson` is a *parallel best-effort log*.
  This is the single most dangerous inversion: a crash mid-write corrupts the authority while
  the journal that *could* have rebuilt it is treated as optional telemetry. The fix the OS
  field names: **state must be a fold (left-reduce) over the event log**, not a separately
  maintained mutable file. Then resume = replay, and the corruption class disappears.
- **Subprocess-as-isolation is process isolation without a process model.** auto.py gets
  crash containment, memory-blowup containment, and runaway-kill *as accidental gifts of the
  OS*. The unification brief proposes porting auto in-process (~600 LOC). An OS designer
  screams: you are about to **collapse address-space isolation into a shared heap with no
  fault domain.** One agent's OOM, infinite loop, or fd leak now takes down the scheduler.
  The named abstraction we're missing is a **fault domain / supervision boundary** that is
  *explicit and reified*, independent of whether the unit happens to be a subprocess.
- **There is no resource accounting kernel.** Cost is tracked, but tokens, context-window
  occupancy, rate-limit budget, and concurrency slots are not first-class **quotas charged
  against a principal**. Fan-out (the multi-agent primitive) will spawn N children with no
  cgroup-equivalent; a runaway emergent graph can exhaust provider rate limits for the whole
  host. OS calls this the **resource principal / cgroup** abstraction. We have a cost meter,
  not a kernel.

## Lens 2 — PROGRAMMING-LANGUAGE DESIGNER

**What they see:** "Port = type+version+provenance+taint" is a **type-and-effect system for a
language whose values flow between non-deterministic functions (LLM calls).** "Models emit
pipelines; the runtime enforces invariants" means **the runtime is a compiler/typechecker for
AI-authored programs.** This is the deepest under-named part of the whole vision.

- **Taint is an effect, not a tag — and effects don't compose by union.** The fan-out brief
  already discovered (lens 1 of its own review) that "WORKTREE+flag-union is nonsense" and that
  read-merge (commutative/combine-all) and write-merge (select-one/competing) are *different
  algebras*. A PL designer recognizes this instantly: **provenance and taint form a lattice,
  and composition is a lattice join, not a set union.** "Came from an unverified model" ⊔
  "came from a trusted source" must have *defined* join semantics, and operations must declare
  how they transform taint (a verifier *lowers* taint; a generation *preserves or raises* it).
  Without a declared taint-transfer function per Step, taint propagation will be silently wrong
  at every join — and silently-wrong taint is worse than no taint, because it confers false trust.
- **AI-authored topologies need a typechecker, but the type system doesn't exist yet.** If
  models emit pipelines, the runtime *must* reject ill-typed graphs *before* execution — a Port
  of type `Plan@v2` cannot feed a stage expecting `Plan@v1`. Today edges match on a **string
  label or a recommendation enum** — that is *dynamic dispatch on a stringly-typed value*, the
  weakest possible contract. An adversarial or merely-confused model will emit graphs that
  typecheck-as-strings but are semantically incoherent. The missing abstraction is a **static
  graph validator over Port types** that runs at pipeline-construction time, not runtime.
- **Self-improvement is the runtime rewriting its own programs — that is a metacircular
  evaluator, and it has a soundness obligation.** A PL designer asks the question nobody in the
  repo has asked: when the harness improves a pipeline, **what proves the improved pipeline is
  observationally equivalent or strictly better, rather than subtly broken?** There is no
  semantics against which "improvement" is checked. Without a **refinement relation** (a formal
  "P' refines P iff every invariant P guarantees, P' also guarantees"), self-improvement is
  unconstrained self-modification — the program-synthesis field's oldest trap.

## Lens 3 — CONTROL THEORY / CYBERNETICS

**What they see:** A "self-improving Plan-Execute-Verify harness" is a **closed-loop adaptive
controller with a learning meta-loop.** Control theory has named, proven theorems about exactly
the failure modes a self-improving multi-loop system hits — and they are invisible to software
people because they live in the *dynamics*, not the code.

- **Ashby's Law of Requisite Variety bounds what the router CAN do.** The router compresses
  every task to a **scalar 1–5 difficulty**. Control theory: *a regulator can only regulate
  the variety it can sense.* A 5-state controller cannot correctly regulate a task space with
  more than 5 distinguishable failure modes — the difficulty scalar **structurally cannot
  distinguish "hard because long/mechanical" from "hard because subtle/unrecoverable"** (the
  M2-store-integrity case the intro doc had to pin all-premium *by hand* because the router
  couldn't see it). The scalar is a low-variety sensor on a high-variety plant. Routing errors
  here are not bugs to fix; they are a **modeling-capacity limit** until the sensor's variety
  matches the plant's.
- **Stacked feedback loops with mismatched time constants oscillate or lock.** Arnold has a
  critique→gate→revise loop *inside* a phase, an escalate/retry loop *around* phases, a chain
  loop across an epic, and a self-improvement loop *across runs*. Control theory: **nested
  loops are only stable if inner loops settle much faster than outer ones** (time-scale
  separation). If the self-improvement loop adjusts policy faster than runs accumulate signal,
  or the gate's auto-downgrade (TIEBREAKER→ITERATE, per MEMORY) fires on the same timescale as
  the thing it's reacting to, you get **limit cycles** — the system thrashes between policies,
  never converging. Nobody is checking loop gain or phase margin.
- **Self-improvement with the verifier inside the loop is a recipe for reward hacking /
  integral windup.** If the harness optimizes a metric the verifier produces, and the verifier
  is itself improvable, the loop will **drive the metric, not the goal** — Goodhart's law,
  which control theory frames as the controller learning to fool its own sensor. The named
  defense is a **reference signal that lives outside the adaptive loop** (an unimprovable,
  human-anchored ground truth the meta-loop is forbidden to touch).

## Lens 4 — GENE-REGULATORY / METABOLIC-NETWORK BIOLOGIST

**What they see:** "Emergent graphs" + "data-defined topologies" + "self-improving" is a
**developmental gene-regulatory network (GRN)** — a system where the network *grows and rewires
itself* from a genome (the packs/pipelines) reacting to signals (Ports/data). Biology has spent
3 billion years solving the control problems of self-constructing networks, and names failure
modes software has no vocabulary for.

- **Canalization: robust developmental networks need buffering that HIDES variation — and that
  hiding accumulates silent debt.** GRNs are robust because they *canalize* — many inputs funnel
  to the same stable phenotype, masking underlying mutations. Arnold's fail-loud work, gates,
  and characterization tests are exactly this buffering. The biologist's warning: **canalization
  hides cryptic variation that releases catastrophically under stress** (de-canalization). Every
  silenced `except`, every gate auto-downgrade, every "safe fallback empty set" is masked
  variation. When an emergent/AI-authored graph pushes the system off its well-trodden path
  (the "stress"), all that accumulated hidden brittleness **releases at once**, far from its
  cause. The missing abstraction: **a measure of how much hidden variation the buffers are
  masking** — canalization is a debt account, currently unmeasured.
- **Feedback motifs determine global behavior, and emergent graphs will assemble pathological
  motifs nobody designed.** GRN biology classifies network *motifs*: feed-forward loops (filter
  noise), negative feedback (homeostasis), **positive feedback (bistable switches/runaway)**.
  When models emit topologies, they will inevitably wire **unintended positive-feedback loops**
  — e.g., a pipeline that improves itself by spawning a critique that recommends spawning more
  critique. Software has no static analysis for "does this emergent graph contain an
  amplifying cycle?" Biology does (motif detection). The missing abstraction: **topological
  invariant checking on AI-authored graphs — detect runaway/bistable motifs before they run.**
- **Metabolic networks have a fixed conserved currency (ATP) that bounds every reaction; Arnold
  has no conserved quantity, so emergent graphs have no thermodynamic stop.** Every metabolic
  reaction is gated by a globally-conserved budget. A self-constructing graph with **no
  conservation law cannot self-limit** — it will expand until it hits an external wall (rate
  limit, wallet, crash) rather than reaching homeostasis. Tokens/cost are *consumed* but not
  *conserved against a fixed pool charged per emergent subgraph*. This is the same gap the OS
  lens names as "no resource principal" — biology reframes it as **the absence of a conserved
  currency is why the system can't reach steady state, only collapse.**

---

## THE SINGLE BIGGEST ABSTRACTION WE HAVEN'T NAMED

All four lenses converge on the same hole from different sides:

> **The "Reduction" — a single, authoritative, replayable substrate where state is a
> deterministic FOLD over an effect-typed, taint-carrying event log, and every adaptive
> decision is charged against a conserved budget held by a named principal.**

Four masters point at one missing thing:
- **OS:** state must be a fold over the WAL (journal is authority), inside an explicit fault
  domain with a resource-principal/cgroup.
- **PL:** the values flowing through that log carry an **effect/taint lattice**, composed by
  *join* with declared per-Step transfer functions, typechecked before execution.
- **Control theory:** the adaptive loop needs a **reference signal outside itself** and
  time-scale separation so the fold-state evolves stably.
- **Biology:** the self-constructing graph needs a **conserved currency** (so it reaches
  homeostasis not collapse) and **motif/canalization invariants** on the folded history.

Arnold today has the *pieces in embryo* — an event journal (proposed), a Port concept
(aspirational), a cost meter (consumed-not-conserved), nested loops (uncoordinated). What it
lacks is the **unifying substrate that makes state a function of a typed, conserved, journaled
history** rather than a clobbered mutable file with telemetry bolted alongside. Name it, build
it first, and the corruption class, the taint-composition bugs, the loop-instability, and the
runaway-emergent-graph class **all collapse into one solved problem.** Build it last, and we'll
discover each independently, expensively, in production — which is precisely the
unknown-unknown.
