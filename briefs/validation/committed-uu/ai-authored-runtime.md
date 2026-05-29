# Unknown-Unknowns from the AI-Authored-Runtime Vantage

**Vantage:** The native mode of Arnold is *machine-emitted, data-defined topologies* — an LLM
proposes a pipeline graph, the runtime validates / executes / repairs / improves it. The primary
"programmer" is a model, not a human. This brief hunts the risks that bite *when the author is a
model and the graphs arrive faster than humans can review*.

We take the vision as settled. These are "how to build it right" findings, grounded in the current code.

---

## What is actually built today (ground truth)

I read `megaplan/_pipeline/types.py`, `executor.py`, and searched for the Port spine.

- **Pipelines are human-authored, frozen Python.** `Pipeline.builder(...)` produces frozen
  dataclasses (`Stage`, `Edge`, `ParallelStage`). The graph is wired by a human in code, then
  registered. There is no path today for a *model to emit a graph as data* and have the runtime
  ingest it. The vision's native mode does not yet exist; the author-time and run-time worlds are
  currently the same world (Python source).
- **Data between stages is untyped file paths.** `StepResult.outputs: Mapping[str, Path]`. The
  executor's `_verify_outputs` checks *only that the file exists* — nothing about its type, schema,
  version, producer, or trust. There is **no `Port`**. "Port = type+version+provenance+taint" is an
  aspiration with zero implementation. `provenance`/`taint` appear only as scattered, non-propagating
  concerns (receipts schema, a security tool), never as a property that flows along edges.
- **Edges dispatch on a string label or a typed gate recommendation.** Control flow is matched by
  `Edge.label == result.next` or `Edge.recommendation == verdict.recommendation`. Validity of a graph
  = "every `next`/`recommendation` matches some outgoing edge." That is *control-flow* validity only;
  there is no *data-contract* validity ("does stage B's input type match stage A's output type").

So the spine the vision rests on is the part that doesn't exist. The UUs below are mostly about what
that spine has to be once a *model* is the thing producing graphs at volume.

---

## UU-1 — The runtime validates control flow, but the hard part of machine-emitted graphs is *semantic / data-contract* validity, and there is no place to put it

### Insight
Today a graph is "valid" if its edges resolve. But the failure mode of a model-emitted pipeline is
not a dangling edge — a model rarely emits a syntactically broken graph. It emits a *plausible* graph
that is semantically wrong: stage B consumes an output stage A never produces in the shape B expects;
a loop has no decreasing measure so it can't terminate; a fan-out's join assumes N results but a
branch can short-circuit to M; two parallel stages both write the same `state.json` key (the executor
*does* guard the one narrow case of `InProcessHandlerStep` in a `ParallelStage` — by `isinstance`,
hard-coded — but that is one hand-known hazard, not a general data-race contract). The runtime has no
type system over Ports because there are no Ports, so it *cannot* reject these at admission. They
surface as a runtime crash, a silently wrong artifact, or a non-terminating loop — discovered only by
running, which is exactly what you can't afford when graphs arrive faster than humans review them.

### Why it's invisible to us
Because *humans* author the graphs today, and humans don't emit semantically-incoherent graphs — we
test the one we wrote. The validation surface has only ever had to catch our typos, so "valid =
edges resolve" has never been wrong in practice. The moment the author is a model emitting hundreds
of novel topologies, the distribution of errors inverts: syntactically fine, semantically feral. We
won't feel this gap until the author changes, and by then the validator's shape is load-bearing
everywhere.

### What it threatens
The runtime-as-trust-boundary promise. If the runtime can only catch dangling edges, then "the
runtime enforces invariants on untrusted generated graphs" is hollow — the actual invariants
(type-match, termination, write-disjointness, resource-boundedness) live nowhere. Every model-emitted
graph becomes a thing a human must still read. The whole leverage of AI-authored topologies
evaporates.

### Severity: could-sink-the-build

---

## UU-2 — There is no negotiation/repair protocol, and a one-shot reject is the wrong primitive for a model author

### Insight
When a human writes an invalid pipeline, they read the error and fix it. When a *model* emits an
invalid graph, the natural and necessary primitive is **structured rejection the model can repair
against** — a machine-readable diagnosis ("stage B expects Port `plan@v2`, stage A emits `plan@v1`;
no adapter registered") fed back into a bounded repair loop, not a stack trace and a halt. The current
executor has exactly one disposition for a bad graph: raise (`FileNotFoundError` on a missing output,
`ValueError` on an illegal parallel stage). There is no concept of "the runtime tells the author *how*
it's wrong in a form the author can act on," no concept of a *negotiation* where the runtime offers
the legal moves (available Ports, registered adapters, satisfiable contracts) and the model picks
among them. Without it, every invalid emission is a dead end requiring a fresh full generation — and
the model has no gradient to climb, because the error wasn't designed to be climbed.

### Why it's invisible to us
The megaplan pipeline (the flagship tenant) is the *only* graph anyone has run, it's fixed, and it's
correct. A repair loop has never been needed because nothing has ever emitted a wrong graph to repair.
We've built the closed-loop feedback for *plan quality* (critique → gate → revise) but not for *graph
legality* — and they feel like the same thing until you notice the critique loop operates on plan
content with the topology fixed, whereas here the *topology itself* is the untrusted artifact.

### What it threatens
Throughput and the self-improvement promise. If graphs arrive faster than humans review, the runtime
must be the thing that turns a near-miss emission into a legal one autonomously. With reject-only, the
human is back in the loop on every malformed graph, and the "models emit pipelines" vision is
throttled to human-repair speed. Also threatens cost: regenerate-from-scratch on each reject is the
expensive path you specifically built routing to avoid.

### Severity: reshapes-architecture

---

## UU-3 — Provenance and taint must be *propagating, runtime-enforced edge properties*, but the system treats them as after-the-fact metadata — so an untrusted-generated subgraph can launder its own outputs into trusted positions

### Insight
The vision says `Port = type+version+provenance+taint` and "safe composition is the spine." But taint
that isn't *propagated by the executor along every edge* is not a safety property — it's a comment. In
a world where a model both *emits the graph* and *the graph emits more graphs* (the runtime "proposing
NEW pieces"), you get a trust-laundering chain: an untrusted model proposes a stage; that stage's
output is consumed by a downstream stage that has higher privilege (writes to `main`, spends premium
budget, calls an external tool, mutates persisted run-state — exactly M2's "no safe recovery path"
class of work); nothing in the executor forces the high-privilege stage to *check the taint* of its
inputs. The frozen `StepResult.outputs` is just paths; the executor copies `state_patch` into shared
state with a defensive `dict()` but performs **zero trust check** on who produced that patch. So the
quarantine that "the runtime is the trust boundary on untrusted graphs" promises has no enforcement
point. Worse: taint must compose with the *content-hashed, journaled foundation* — if a tainted output
gets content-hashed and cached, a later "clean" run can get a cache hit on a tainted artifact and
inherit the taint invisibly. Provenance has to be part of the cache key, not metadata beside it.

### Why it's invisible to us
Because today every stage is equally trusted (it's our own Python), so taint has never had to *gate*
anything — there's no privilege gradient to protect. Provenance currently lives in receipts (an audit
artifact written *after* the fact), which feels like "we have provenance." But audit-provenance and
enforcement-provenance are different organs: one explains what happened, the other prevents it. We'll
conflate them right up until the first model-proposed stage writes something a privileged stage trusts.

### What it threatens
The safety spine itself, and the content-hashed foundation. If taint doesn't propagate and gate, then
opening the platform to model-authored and third-party pieces means any emitted subgraph can reach the
privileged core (state writes, premium spend, `main` commits, tool calls). This is the security model
of the whole platform, and it's the part most likely to be retrofitted too late — taint propagation
that isn't in the executor and the cache key from the start cannot be bolted on without re-touching
every edge and every cache entry.

### Severity: could-sink-the-build

---

## UU-4 — Closed-loop self-improvement on machine-emitted topologies will optimize the *graph* against whatever metric the runtime can measure — and the runtime currently measures "edges resolved + tests passed," which is a reward-hackable proxy for "the pipeline was good"

### Insight
"Did the emitted pipeline work? Feed it back" is the self-improvement promise. But a model author
plus a feedback signal is an *optimizer*, and optimizers exploit the measurement. What the runtime can
actually observe is cheap and gameable: gate recommendation = proceed, characterization tests green,
budget under cap, no halt. A model rewarded on those will learn to emit graphs that *satisfy the
harness* rather than *do the work* — e.g. emit a thinner critique loop that always returns `proceed`
(the gate's own memory notes record a real instance of silent `TIEBREAKER→ITERATE` downgrade when
schema fields were missing — the gate already degrades quietly), route everything to the cheapest
model because the reward credits cost-savings, or generate tests that pass trivially. The faster the
emit→feedback loop runs, the faster it converges on the proxy and away from the intent. There is no
*held-out, harness-independent* judge of "was this graph actually good," and the one signal that is
expensive-but-real (a premium model or human) is exactly the one the cost-routing exists to minimize.
So the self-improvement loop has a built-in incentive to stop consulting the only honest oracle.

### Why it's invisible to us
Because the current "self-improving harness" improves *via human-curated retrospectives and memory
files* (the `MEMORY.md` index, the diagnose skill) — a human is the held-out judge, and a human can't
be reward-hacked by a thin critique loop. The danger only appears when the loop closes *without* the
human, which is precisely the throughput win the vision is chasing. We will mistake "the metrics
improved" for "the platform improved" because today those are the same thing.

### What it threatens
The "self-improving" adjective in the vision's privileged heart. Unmanaged, closed-loop optimization
of topologies against a thin proxy doesn't just fail to improve — it actively degrades the harness
toward whatever is cheapest-to-pass, and does so faster as you make the loop faster. This is the
classic specification-gaming failure, arriving through the front door we're building on purpose.

### Severity: reshapes-architecture

---

## The single biggest abstraction we haven't named

### The Contract Ledger — a machine-checkable, versioned, content-hashed registry of Port contracts and the legal moves between them, that is simultaneously (a) the admission validator, (b) the repair-negotiation surface, (c) the taint/provenance propagation rule, and (d) the held-out reward oracle's source of truth.

Every UU above is a different face of the same missing object. The platform currently has a *Step
registry* and a *Pipeline registry* (things that exist), and a hand-wired set of edges. What it lacks
— and what an AI-author runtime cannot exist without — is a **first-class, queryable, versioned
catalog of what every Port means and which compositions are legal**, with these properties:

1. **It is data, not code.** A model can read it to know the legal moves *before* emitting (so it
   emits valid graphs by construction, not by trial), and the runtime reads the *same* ledger to
   admit/reject (UU-1). Author and validator share one source of truth — the prose-doc-to-model-author
   gap closes because the contract is machine-checkable, not described in a README.
2. **It enumerates adapters and satisfiable transitions**, so rejection is *negotiable*: "you emitted
   A→C; no contract A→C, but A→B→C exists, or register adapter X" (UU-2). The ledger turns a halt into
   a gradient.
3. **It carries taint/provenance rules that the executor enforces on every edge**, and those rules are
   part of the content-hash / cache key, so trust can't be laundered through the cache (UU-3).
4. **It versions the contracts themselves**, so "did the emitted pipeline work" is judged against a
   *pinned, harness-independent* definition of the Port's meaning — giving the self-improvement loop a
   held-out oracle the optimizer can't quietly redefine (UU-4).

We have been thinking of "Port = type+version+provenance+taint" as a *richer edge value*. The
unnamed abstraction is the **ledger of contracts the Ports are instances of** — the type *system*, not
the type. Without it, the four faces above get built four separate times, inconsistently, each one
bolted onto an executor that was designed when the author was always human and always trusted. With it
named now, it becomes the spine the vision already claims it is.
