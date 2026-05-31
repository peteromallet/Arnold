# The Computational Primitive — Unknown-Unknowns (committed-vision validation)

**Vantage:** the pluggable scheduler/activation model that must subsume DAG + loop +
standing/interactive process + market/fixpoint/selection + emergent graph WITHOUT becoming a mush.
**Posture:** we ARE building the full vision. This brief is about *how to build it right* and *what
will bite*, not whether to build it.

---

## What the code actually is today (the grounding)

I read the real primitive, not the prose. The current `megaplan/_pipeline` is:

- A **frozen, statically-declared, single-entry DAG**. `Pipeline = {stages: Mapping[name, Stage|ParallelStage], entry, overlays}`, all `@dataclass(frozen=True)`. Topology is fixed at build time.
- Executed by a **sequential graph walker** (`executor.run_pipeline`): dispatch a Step, verify its declared output files exist, apply a `state_patch` to working state, follow the one matching edge, repeat until `target == "halt"`.
- **Loops are edges back to an earlier stage** (`critique_revise_gate_loop` wires `revise → "critique"`). This is the textbook "souped-up DAG" — the convenient choice the vantage explicitly warns about.
- **Concurrency is a barrier-join thread pool** (`ParallelStage` + `_run_parallel_stage`). Crucially, the executor *forbids* any step that touches shared `state.json` from running in parallel (`InProcessHandlerStep` is rejected with `ValueError`). Parallelism is allowed only for hermetic steps.
- **State is a single, destructively-overwritten `state.json` snapshot.** `write_plan_state` does an "executor-key-merge" between executor-owned keys and on-disk handler-written keys — i.e. last-writer-wins reconciliation between two writers of one mutable document. The `events.ndjson` journal (observability design doc) is being added as a **reader overlay on top of** this mutable snapshot, NOT as the source of truth.
- **Ports do not exist.** A Step's output contract is `outputs: Mapping[str, Path]` and the *only* invariant the executor enforces is `Path.exists()`. There is no type, no version, no provenance, no taint anywhere in the edge or output model. The "Port = type+version+provenance+taint" spine is 100% aspirational; the runtime currently enforces "the file is on disk."
- `subloop` / `override` Step kinds and an `Overlay` (`Pipeline → Pipeline`) transform exist as **reserved-but-inert** forward-compat stubs. Dynamic topology (`pattern_dynamic`) can only *specialize/fan-out an already-declared shape* from a JSON spec — it cannot grow new stages or new edges at runtime.

So the engine today is a **deterministic, statically-typed-topology, single-mutable-state DAG walker**. The vision asks it to also host loops-with-fixpoints, standing/interactive processes, markets/selection, and **AI-emitted (data-defined) emergent graphs**. The gap between those two things is where the unknown-unknowns live.

---

## UU-1 — The activation model, not the graph shape, is the thing we haven't chosen

**Insight.** We keep arguing about *graph shapes* (DAG vs loop vs emergent graph) when the real
primitive is the **activation rule**: *what makes a node eligible to fire, and what happens to the
rest of the graph when it does?* A DAG walker has exactly one activation rule — "the single edge
whose label/recommendation matched, fire its target next" — and a single program counter. Every
other model in the vision has a *fundamentally different* activation rule:

- **Loop/fixpoint** fires a node *repeatedly until a value stops changing* — activation is
  data-convergence, not edge-following. (Today's critique loop fakes this with a `max_blocked_retries`
  counter and a back-edge; there is no fixpoint detection — MEMORY records a real bug where a
  hardcoded `max_blocked_retries=1` killed legitimate rework. That bug *is* the missing fixpoint
  semantics surfacing.)
- **Standing/interactive process** is *always eligible* and is driven by *external events arriving*
  (a human reply, a file change, a webhook), not by an upstream node completing. It has no "next
  edge"; it has a mailbox.
- **Market/selection** fires *N candidates concurrently and lets a rule pick a winner after a
  barrier* — activation is competitive, and the losers must be *cancelled*, not just ignored.
- **Emergent graph** has *no statically-known node set at all* — nodes are created by the firing of
  other nodes.

A single sequential walker with one program counter cannot host these as peers. You get there by
bolting each one on as a special Step kind (`subloop`, `override`, `compete`, "standing-process
step that blocks the walker") — and the walker quietly becomes a **mush**: a switch statement over
incompatible activation semantics, each with its own ad-hoc state, retry counter, and cancellation
story. That is the exact failure the vantage names, and the reserved-inert `subloop`/`override`
kinds are the **first two pegs of that mush already hammered in.**

**Why invisible to us.** Because the DAG walker *works today* and every new requirement can be
expressed as "just add another Step kind / another edge kind." Each addition is locally reasonable;
the mush is only visible in aggregate, and only after the walker has accreted 5–6 incompatible
firing rules. We are measuring success by "the planning pipeline runs," which a souped-up DAG
satisfies indefinitely — right up until a tenant needs a standing process or a real fixpoint and
discovers the engine has no concept of either.

**What it threatens.** The privileged HEART (self-improving Plan-Execute-Verify) and the claim that
the primitive "spans DAGs, loops, standing/interactive processes, and emergent graphs." If the
activation model is wrong, *every* tenant inherits a planning-shaped DAG and the platform is "a DAG
runner with extra Step kinds," not a category-creating substrate.

**Severity:** reshapes-architecture (arguably could-sink-the-build, because it's the literal heart).

---

## UU-2 — Mutable single-document state is incompatible with the durable/journaled foundation AND with concurrency, and we're papering over it by *forbidding* concurrency

**Insight.** The vision says "durable, content-hashed, journaled foundation" and "emergent graphs"
and "fan-out." The implementation says: **one mutable `state.json`, last-writer-wins merge between
two writers, and a hard ban on concurrent state mutation.** These are not the same system with
different polish — they are *opposite* commitments. A journaled/content-hashed foundation means
**state is the fold of an append-only event log**; the current `events.ndjson` is being added as a
*read-only narration beside* a mutable file that remains the source of truth. The moment the journal
and the snapshot disagree (crash mid-write, concurrent writer, resume), the snapshot wins and the
journal is decorative. You cannot get durability or replay or content-addressed reproducibility from
a system whose truth is a destructively-overwritten JSON blob — no matter how good the journal beside
it is.

The concurrency tell is sharper still: the executor **rejects** any parallel stage containing a
state-touching step. The platform's answer to "concurrent activation is hard" is currently "don't do
concurrent activation where state is involved." But the vision *requires* concurrent activation
(markets, fan-out, emergent graphs, standing processes that all read/write shared world-state). The
hermeticity ban is a load-bearing assumption that **the full vision must violate**, and the merge
logic (`executor-key-merge`, `faults.json` last-write-wins folds noted in the fan-out brief) is
already the early symptom of trying to reconcile concurrent writers without a concurrency-sound
state model.

**Why invisible to us.** Because today there is effectively one writer at a time (the sequential
walker), so last-writer-wins is *always correct by construction*. The data model's unsoundness is
invisible precisely as long as concurrency is banned — and concurrency is banned precisely because
the data model is unsound. It's a self-concealing pair. The journal feels like it *is* the durable
foundation, when architecturally it's a reader, so we'll believe the foundation requirement is "in
progress" when the actual substrate has not been built.

**What it threatens.** "Durable, content-hashed, journaled foundation" (a settled pillar of the
vision) and every concurrent activation mode (market/selection/emergent/standing). Retrofitting an
event-sourced or content-addressed state core *after* tenants depend on `state.json` semantics is the
kind of migration that eats a quarter and silently corrupts in-flight runs (MEMORY already has
multiple `state.json` corruption / resume bugs — those are the foundation telling you it isn't one).

**Severity:** could-sink-the-build.

---

## UU-3 — Without Ports as a *runtime-enforced* type, AI-emitted topologies are unverifiable, and "the runtime enforces invariants" is a promise the engine can't keep

**Insight.** The spine of the vision is "models emit pipelines; the runtime enforces invariants" and
"safe composition (Port = type+version+provenance+taint)." But the runtime's *only* output invariant
today is `Path.exists()`. There is no type to check a producer against a consumer, no version to
detect a stale artifact, no provenance to trace which model/step/run produced a value, and no taint
to stop an untrusted/low-tier output from flowing into a high-trust step. When a *human* authors the
DAG, this is survivable — the author holds the type discipline in their head and wires
compatible stages. When a **model emits the topology** (the explicit future), there is no head
holding the discipline, and the runtime cannot reject an ill-typed wiring because it has no notion of
type. The engine will happily run a model-emitted graph that feeds a critique-flag artifact into a
slot expecting an execution-plan, discovering the mismatch only as a downstream parse error or, worse,
a plausible-but-wrong result. "The runtime enforces invariants" is, today, false — it enforces one
invariant (file presence), and the most important class of invariant (compositional type/provenance/
taint safety) does not exist.

The taint axis is the sleeper. The whole economic thesis is **cheapest-capable-model routing** — i.e.
deliberately mixing high-trust (frontier) and low-trust (cheap) outputs in one graph. Without taint
as a Port property, there is *nothing in the runtime* that prevents a DeepSeek-produced artifact from
silently flowing into a slot whose correctness the routing logic assumed a frontier model guaranteed.
The routing decision and the trust boundary are made in completely different places, and only the
Port could connect them. (MEMORY's "rater≥dispatchee guarantee" gap and the gate auto-downgrade bug
are this exact hole leaking through the planning tenant already.)

**Why invisible to us.** Because Port is named in the *vision prose* and feels designed, but it's
unimplemented — and the planning tenant doesn't expose the gap because its topology is hand-authored
and hand-typed by us. We will only feel this when the *second* tenant or the *first AI-emitted graph*
arrives, at which point the absence of a type/provenance/taint layer is a foundational retrofit, not
a feature.

**What it threatens.** Two settled pillars at once: "safe composition is the spine" and "built for
AI-authored, data-defined topologies; the runtime enforces invariants." Also the routing thesis's
safety story (taint). Without Ports as runtime-enforced, the platform's central differentiator —
*safe* AI-authored composition — is unbacked.

**Severity:** reshapes-architecture.

---

## UU-4 — Cancellation, supervision, and partial failure have no primitive — barrier-join hides it

**Insight.** Every model beyond a pure DAG needs an answer to *"a node is firing, and now we must
stop it / it died / we no longer want its result"*: markets cancel losing candidates; standing
processes must be supervised and restarted; fixpoint loops must be abortable; emergent graphs spawn
work that must be reaped. Today the only concurrency construct is a `ThreadPoolExecutor` barrier-join
that **waits for all N to finish** and collects results in declaration order. There is no
cancellation, no supervision tree, no "kill the losers," no "restart the crashed standing process,"
no timeout-and-reap. MEMORY is dense with the symptom: tmux sessions that *survive their launcher's
death and silently strand finished work*, idle-backstop timers tuned by hand (900s→1800s) because
there's no real liveness/supervision primitive, orphan janitors bolted on after the fact. These are
all manifestations of *the missing supervision/cancellation primitive* — each patched locally
because the engine has no concept of a supervised, cancellable activation.

A barrier-join makes this invisible because in the happy path everything finishes and the absence of
cancellation never bites. It bites exactly in the modes the vision is *built around* (compete/select,
standing processes, long emergent fan-outs) — the modes where "wait for all N" is the wrong
semantics and "kill, restart, reap, supervise" is the right one.

**Why invisible to us.** The thread-pool barrier is the *correct and complete* primitive for the one
pattern we run today (hermetic fan-out of critique/review checks that all must complete). Its
incompleteness is only visible under failure and under non-barrier activation modes, both of which
are rare in the planning tenant. We will keep hand-patching liveness timers and orphan janitors,
each looking like an isolated bug, never seeing that they are one missing abstraction.

**Why it belongs in the primitive, not ops.** BEAM/OTP's core insight is that supervision *is* part
of the activation model, not a layer above it — "let it crash + a supervisor decides the restart
policy" is a *computational* primitive. If we treat cancellation/supervision as ops glue (timers,
janitors), we will have re-derived a worse OTP by accretion.

**What it threatens.** Standing/interactive processes and market/selection (two of the five activation
modes the primitive must subsume), the reliability of any long-running or cloud run, and the
self-improving loop itself (a self-improving harness *is* a standing process that must be supervised).

**Severity:** reshapes-architecture.

---

## The single biggest abstraction we haven't named

### The **Activation** — a first-class, persisted, supervised record of "a node firing," with a pluggable *readiness rule* and a *lifecycle*.

Everything above is one missing noun. Today "a step running" is an *implicit, transient* thing: the
walker's program counter plus a thread in a pool. It has no identity, no persisted lifecycle, no
readiness rule beyond "the previous edge matched," and no supervisor. **Name it. Make it the atom of
the engine.**

An **Activation** is a durable record:

- **identity** — content-addressed over (node, input Port values, profile) → this is also the
  cache/replay key, the dedup key, and the provenance anchor. (Subsumes "content-hashed foundation.")
- **readiness rule** — a *pluggable predicate* over available Port values that decides when this
  activation may fire. *This single pluggable field is what subsumes DAG + loop + standing + market +
  emergent without a mush*: DAG = "all input Ports present"; loop/fixpoint = "input changed since last
  fire AND not yet converged"; standing process = "an external event landed in my mailbox"; market =
  "fire N now, a selector activation fires when K finish"; emergent = "a producing activation declared
  me." The graph topology stops being the primitive — the **readiness predicate** is the primitive,
  and the graph is just the common case where readiness = "upstream done."
- **lifecycle + supervisor** — `pending → running → {done | failed | cancelled | superseded}`, with a
  supervision policy (restart/escalate/abandon) owned by the engine, not by ops timers. (Subsumes
  UU-4.)
- **Port-typed I/O** — inputs and outputs are Ports (type+version+provenance+taint), so readiness can
  be type-checked and an AI-emitted activation can be *rejected at wiring time*. (Subsumes UU-3.)
- **journal-native** — an Activation's state transitions ARE the events in the append-only log; the
  "current state" is the fold of its activation records, never a destructively-overwritten snapshot.
  (Subsumes UU-2 — state.json becomes a derived cache, not the truth.)

The closest priors are the **actor with a mailbox + supervisor (BEAM/OTP)** for lifecycle and the
**tuple-space/blackboard "fire when matching tuples are present"** for the pluggable readiness rule —
fused, and made *durable and content-addressed*. A souped-up DAG is what you build if you never name
the Activation; you then spend years re-deriving its pieces as Step kinds, retry counters, orphan
janitors, idle timers, and merge reconcilers — which is precisely the trajectory the MEMORY log
already shows in miniature.

**The bet:** model the Activation as the engine's atom now, while the only tenant is planning and the
only readiness rule is "upstream done." Retrofit it after the second tenant or first AI-emitted graph,
and it's a foundation-replacement under load.
