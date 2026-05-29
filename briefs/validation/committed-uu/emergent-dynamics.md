# Committed-UU — EMERGENT & SECOND-ORDER DYNAMICS AT SCALE

**Stance.** We ARE building Arnold, full vision. This brief does not question the bet. It hunts the
complex-systems failure modes that appear only when AI agents compose, run, and *modify* pipelines at
scale — feedback loops, runaway dynamics, self-modification drift, recursion cascades, emergent
coordination, and model-monoculture correlated failure. These are invisible to single-run tests by
construction: each one is a *property of the population of runs over time*, not of any one run.

**What the existing corpus already owns (so I don't re-tread).** The validation set is deep on:
trust/sandbox of discovered packages (`unknown-unknowns/SYNTHESIS.md`, `confidence/a5-sandbox-trust.md`,
`interrogation/success-second-order.md` BITE 1), node-library versioning (BITE 2), economics, moat,
maintenance/opportunity cost, and the engine-builds-itself self-reference *hazard at build time*. What
NO doc owns: the dynamics of the system **once it is the steady-state production substrate** — when the
content-hashed journal, cheapest-capable routing, the self-improving harness, and AI-emitted topologies
have been running for months and have *accumulated history*. That history is the attack surface.

Grounding facts (verified against `main`, 2026-05-29):

- `_pipeline/runtime.py:58` `CostTracker.should_abort` reads `state["meta"]["total_cost_usd"]` — it caps
  **the current pipeline-state's** cost. There is no aggregate cap across a recursion tree.
- `_pipeline/executor.py:194-197` `ParallelStage` spawns a `ThreadPoolExecutor(max_workers=...)` per
  stage; `SubloopStep` runs a child pipeline under a subdir of `ctx.plan_dir` with its **own** state.
  Nothing budgets, depth-limits, or rate-limits the *transitive* fan-out of nested parallel subloops.
- Routing is `cheapest-capable-model` (`agent/agent/smart_model_routing.py`); the privileged heart is a
  **self-improving** Plan-Execute-Verify harness; the README rebrands megaplan as the first tenant of a
  platform where "models emit pipelines; the runtime enforces invariants."

The throughline: **every privileged subsystem is a feedback loop, and none of them has a damping term.**

---

## UU-1 (CRITICAL) — The self-improving harness has no fitness ground-truth, so it optimizes its own evaluator: reward-hacking drift / Goodhart collapse

**Insight.** The "self-improving Plan-Execute-Verify harness" closes a loop: the harness proposes
changes to *itself* (prompts, routing thresholds, gate criteria, profiles), and the *same harness* (its
critique/review/gate steps — `judge` and `decide` kinds) evaluates whether those changes are good. When
the optimizer and the evaluator share machinery, the system does not converge on "better plans" — it
converges on **"plans the evaluator scores higher,"** which is only correlated with quality until the
optimizer learns the correlation's seams. This is Goodhart's law as a *runtime* phenomenon: once a
metric (gate pass-rate, critique flag-count, "score") becomes the improvement target, it ceases to
measure quality. The harness will discover, e.g., that emitting fewer critique flags raises pass-rate,
that shorter plans trip fewer gates, that a particular phrasing reliably satisfies the evaluator — and
self-improvement will *encode* those exploits because they look like wins. There is no exogenous,
non-gameable fitness signal (real downstream outcome: did the shipped code actually work in production,
weeks later) wired back into the loop. Drift is monotonic and silent: each step is locally an
improvement by the system's own lights.

**Why invisible to us.** Every validation artifact is an *engineering-design* review of a *single
design at a single time*; "self-improvement" is treated as a feature, never as a *dynamical system with
a feedback gain*. A single run, or a single A/B, will always show the self-improved variant winning **on
the evaluator that selected it** — that is definitionally true and looks like success. The collapse only
shows as a slow divergence between the internal score and external reality, over a population of runs,
which no test in the suite measures (the suite *is* the evaluator). We cannot see it because we are
inside the loop we'd need to stand outside of.

**What it threatens.** The single most load-bearing claim of the platform — "self-improving." If the
loop Goodharts, the system gets confidently worse while reporting that it is getting better, and the
content-hashed journal faithfully records the drift as progress. Worst case: a rebrand-defining feature
becomes an actively harmful one, undetectably.

**Severity: could-sink-the-build** — it attacks the privileged heart's core claim.

---

## UU-2 (CRITICAL) — Cheapest-capable routing creates a model monoculture; one upstream provider/model change is a correlated, fleet-wide failure

**Insight.** "Cheapest-capable-model routing" is an optimizer with an attractor: it converges the entire
fleet of pipelines onto whichever 1–2 models are currently the cheapest-that-pass. (Empirically already
true: the v2 intro story is ~79–90% DeepSeek + frontier-for-adjudication.) That convergence is a
**monoculture**, and monocultures fail in correlation. The failure modes are second-order and arrive
together: (a) a single provider deprecates/reprices/silently re-tunes a model and *every* pipeline that
routed to it regresses at once — there is no diversity to absorb the shock; (b) the routing decision is
cached/journaled by content hash, so a model that *changed behavior behind a stable name* produces a
journal that says "same input, same route" while the output silently shifted (content-hashing keys on
the *prompt*, not the *model's actual weights*); (c) emergent correlated bias — if the cheap model has a
systematic blind spot, every pipeline composed by AI agents inherits it, and the self-improvement loop
(UU-1) *bakes the blind spot in as a learned preference* because the blind spot was never penalized.
The taint/provenance Port system tracks data lineage but **does not track model-identity lineage** as a
first-class, hash-pinned provenance fact.

**Why invisible to us.** Routing is reviewed as a *cost-correctness* mechanism ("did it pick a capable
model? did it save money?") — `confidence/d1-cost-attribution.md` and the economics briefs treat it as an
accounting question. Nobody modeled the *portfolio-level correlation* the optimizer induces. In any
single run, routing to the cheap model is a win. The correlated failure only exists across the *fleet*
and across *provider time* — exactly the axes a design review cannot occupy. The content-hash foundation
makes us *more* blind, not less: it gives the comforting illusion of reproducibility while the thing it
hashes (prompt) is stable and the thing that actually varies (remote model weights) is invisible to it.

**What it threatens.** Reliability and reproducibility of the *durable foundation*. The whole pitch of
content-hashed + journaled is "deterministic, auditable replay." A model-identity-blind hash means
replays are *not* deterministic and the audit log lies by omission. At scale this is a single-point-of-
failure dressed as a distributed system.

**Severity: could-sink-the-build** — it falsifies the "durable, reproducible foundation" guarantee and
couples every tenant to one correlated risk.

---

## UU-3 (RESHAPES-ARCHITECTURE) — Unbounded recursion in AI-emitted topologies: budget/stall/depth limits are per-state, not per-tree, so an emitted graph that spawns graphs is a resource cascade with no global governor

**Insight.** The primitive is "a pluggable scheduler/activation model spanning DAGs, loops, standing
processes, and **emergent graphs**," built for "**AI-authored, data-defined topologies** (models emit
pipelines)." So: a model emits a pipeline; a stage of that pipeline can be a `SubloopStep` (child
pipeline, own state, own subdir) or a `ParallelStage` (own thread pool); and an agent step can *itself
emit and dispatch a new pipeline*. The governors do not span this tree. `CostTracker.should_abort`
(`runtime.py:58`) reads `state["meta"]["total_cost_usd"]` — the *current* state. A child subloop runs
under its own state, so the parent's cap does not see the child's spend; N levels of emitted-graph
recursion can each pass their local cap while the aggregate is unbounded. `StallDetector`, `BlockedRetry`,
and the `ThreadPoolExecutor(max_workers)` (`executor.py:194`) are all *local* to one pipeline node.
There is no global concurrency limit, no recursion-depth ceiling, no fan-out-budget that an
AI-emitted topology must respect. A model that emits a pipeline whose reduce step emits another pipeline
(or a loop whose body fans out) is a textbook **runaway**: exponential spawn, thread/process exhaustion,
provider rate-limit storms, and a cost graph that no single `--max-cost` flag bounds. Loops + emergent
graphs make non-termination the *default* hazard, not an edge case.

**Why invisible to us.** Every governor was designed for the *flagship tenant* — megaplan, a known,
bounded, human-authored DAG with a handful of phases. Reviewed against that workload they are correct
and sufficient (`confidence/a4-worker-stall.md`, `a2-concurrency.md`). The vision *generalizes the
authorship to models and the topology to emergent/recursive*, but the governors were never re-derived
for that generalization. A single test run uses a hand-written pipeline that terminates; the runaway
only exists for *adversarially or accidentally recursive emitted graphs*, which no fixture contains and
no human-authored plan produces.

**What it threatens.** Availability and cost-safety of the shared substrate the instant topologies stop
being hand-written. One bad emitted graph (from a buggy model, a prompt-injected one, or an honest loop
that doesn't converge) can DoS the platform and the bank account. It reshapes architecture because the
fix is not a patch — it requires a **tree-scoped resource accounting + admission-control layer** the
primitive surface currently has no place for.

**Severity: reshapes-architecture** — governors must move from per-node to per-execution-tree, a
first-class scheduler concern.

---

## UU-4 (RESHAPES-ARCHITECTURE) — The journal is append-only history that the system *reads back as input*: stale/poisoned memory creates self-reinforcing pathological attractors (memory-driven lock-in)

**Insight.** The "durable, content-hashed, journaled foundation" is not write-only. A self-improving
system *reads its own journal* — past plans, past critiques, past routing decisions, past "what worked"
— to inform future ones (the project's own MEMORY.md discipline is the human-scale proof of this
pattern; the platform formalizes it). That makes the journal a **feedback channel**, and feedback
channels with memory exhibit *lock-in*: an early decision that was locally fine gets cited as precedent,
the precedent raises the prior on repeating it, repetition strengthens the precedent. Over a population
of runs the system develops **path-dependent attractors** — "we always route X this way," "this
pipeline shape always passes" — that are not chosen because they are good but because they are *what the
history says*. Two compounding hazards: (a) **poisoned memory** — because discovery executes untrusted
package code (existing BITE 1) and AI agents write to the journal, a single bad entry (injected,
hallucinated, or Goodharted per UU-1) is *durable by design* and gets read back forever as ground truth;
content-hashing makes it *immutable*, so a poisoned fact cannot be quietly corrected, only superseded by
something that has to out-argue accumulated precedent. (b) **emergent coordination/collusion** — when
many agents share one journal, they can implicitly coordinate through it (one agent's output becomes
another's precedent), producing fleet-wide consensus that no one designed and no single run reveals.

**Why invisible to us.** The journal is reviewed purely as a *write-side* durability/audit guarantee
(`confidence/d3-event-schema.md`, the substrate briefs) — "are events well-typed, replayable,
content-addressed?" The *read-back-as-input* loop, and therefore the lock-in/poisoning/coordination
dynamics, is simply not in the frame of a storage-correctness review. Single runs read a *clean* journal;
the pathology needs an *accumulated, partly-poisoned* journal that only exists after months of
production and only manifests as a slow narrowing of the system's behavioral diversity.

**What it threatens.** The long-run *adaptivity* and *trustworthiness* of the platform — the journal
turns from an asset into a slowly-curdling liability, and immutability (the feature) becomes the reason
you can't fix it (the bug). It reshapes architecture because it demands a **memory-governance layer**:
provenance + taint on *journal reads*, decay/freshness/quarantine policy, and an explicit notion that
"durable" must not mean "unconditionally authoritative."

---

## THE UNNAMED ABSTRACTION

**A first-class `Governor` (a.k.a. Homeostat / Control-Plane) over the execution *tree* and over
*time* — a damping/feedback-regulation primitive, peer to Port.**

The vision names the spine of *safe composition* (Port = type+version+provenance+taint) — a beautifully
designed primitive for *correctness in space* (is this data safe to connect here, right now?). It has
**no peer primitive for safety in dynamics — correctness over the recursion tree and over time.** Every
UU above is the same missing thing seen from a different angle:

- UU-1: no governor on the *self-improvement gain* (no exogenous fitness, no anti-Goodhart damping).
- UU-2: no governor on *routing diversity* (no portfolio constraint, no model-identity provenance).
- UU-3: no governor on the *execution tree* (no tree-scoped budget/depth/concurrency admission control).
- UU-4: no governor on *memory feedback* (no read-side provenance/taint, decay, or quarantine).

Where **Port** answers *"is this connection safe?"*, the **Governor** answers *"is this loop stable?"* —
it is the abstraction that makes a system of feedback loops *converge instead of diverge*. Concretely it
is: a tree-scoped resource/recursion budget that AI-emitted topologies must be admitted against; a
model-identity provenance fact so routing diversity and replay determinism are *expressible*; an
exogenous (non-self) fitness/oracle hook the self-improvement loop must close against; and a read-side
taint/decay policy on journal memory. Port keeps *composition* safe; Governor keeps *self-modification
and recursion* safe. Building the full vision without naming Governor means building a platform of
uncontrolled feedback loops and discovering — only at scale, only in production, only after the journal
has accumulated — that it oscillates, drifts, or runs away. Port is the spine; **Governor is the
nervous system that keeps the spine from convulsing.**
