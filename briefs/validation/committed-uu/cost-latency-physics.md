# Cost & Latency Physics — Unknown-Unknowns for the Arnold Vision

Vantage: COST & LATENCY PHYSICS as an engineering constraint. At vision-scale, every
composed AI workflow is O(N) model calls. The dominant levers are prompt-cache hit
rate, speculative/parallel execution, cheap-capable routing, dedup, and memoization of
content-hashed piece outputs. The question is not *whether* to build — it is which
foundational decisions, made NOW, keep the cost/latency profile viable when models are
authoring topologies that the runtime executes, and what bites if we bake in a
cache-hostile, no-memoization execution model.

## What the current code already tells us (grounding)

- `megaplan/agent/run_agent.py` DOES implement Anthropic prompt caching: a deliberately
  stable system-prompt prefix (`_cached_system_prompt`, comments at lines 538, 2582–2584
  about "preserving the stable cache prefix"), a `_cache_ttl = "5m"`, and
  `apply_anthropic_cache_control`. So caching is understood — **but only on the
  conversational agent path, only for one provider's cache idiom.**
- The privileged **Plan-Execute-Verify pipeline** path (`megaplan/_pipeline/stages/`,
  `megaplan/handlers/`) builds a fresh prompt per phase. `megaplan/receipts/canonical.py`
  shows prompts embed `<PLAN_DIR>`, `<PLAN_ID>`, `<PROJECT_DIR>` substrings that are only
  stripped *for hashing* (`canonicalize_prompt`), not before the model sees them. The
  rendered prompt the model actually receives carries per-plan, per-path entropy near the
  front — exactly where a prefix cache needs stability.
- `hash_prompts()` (canonical.py:40) produces `raw_hash`/`canonical_hash` **purely for
  receipts/provenance** (`megaplan/receipts/__init__.py:52`). There is NO code path that
  says "this canonical input was computed before → return the prior output, skip the model
  call." Content-hashing is wired for blobs (`store/blob.py`) and audit receipts, NOT for
  output memoization. The single most valuable cost lever — content-hashed memoization of
  piece outputs — is **named in the vision but absent from the execution model.**
- Routing (`megaplan/agent/agent/smart_model_routing.py`) is a keyword/length heuristic
  (`_COMPLEX_KEYWORDS`, `max_simple_chars=160`) that conservatively falls back to the
  expensive primary. It is not cost/capability-aware and operates per-turn, not per-piece.
- Fan-out (`megaplan/orchestration/parallel_critique.py`, hermes fanout) launches N
  sibling model calls whose prompts differ by a single check — large shared prefix, no
  cross-sibling cache sharing or dedup.

These are not bugs; they are the seams where the vision's cost physics will either hold
or collapse once topologies are AI-authored and run wide.

---

## UU-1: Caching is a *property of the provider/protocol*, but the vision's value is *cross-provider, cross-pipeline reuse* — the two are physically incompatible without a caching abstraction we don't have.

**Insight.** Prompt caching as it exists (Anthropic ephemeral breakpoints, 5m TTL, prefix
must be byte-stable, max ~4 breakpoints, single-conversation/single-provider locality) is
a *vendor-local optimization*. The vision routes the cheapest capable model per piece —
which means a given logical piece may run on DeepSeek today, Codex tomorrow, an OpenRouter
proxy the next. Each provider has a different cache idiom (some none, some
implicit/automatic, some explicit-breakpoint, all with different TTLs and prefix-stability
rules). The moment routing moves a piece across providers, *all accumulated cache state is
worthless* and you re-pay full input cost. So the two flagship levers — cheapest-capable
routing and high cache-hit-rate — are **directly antagonistic** under the naive model:
optimizing one destroys the other. Worse, the receipt canonicalization (`<PLAN_DIR>` etc.)
proves we already inject per-run entropy into prompt prefixes, which defeats even
same-provider prefix caching at the pipeline layer.

**Why invisible to us.** Caching "works" in dev because the agent path is single-provider
and the system prompt is stable, so we see healthy cache-read tokens
(`session_cache_read_tokens`). We will conclude caching is solved. We will not see that the
*pipeline/handler* path — the actual heart — has near-zero prefix-cache hit rate, because
nobody is measuring per-phase cache-hit-rate as a first-class metric, and the cost looks
"fine" at one-plan-at-a-time scale. The antagonism with routing only manifests at scale,
when routing churn is high.

**What it threatens.** The core economic claim ("cheapest-capable routing + cache =
viable O(N)"). At vision scale this isn't a percentage tax — routing-induced cache misses
can be the difference between 10x and 100x input-token cost on long stable prefixes
(system + pipeline scaffolding + retrieved context), which is the bulk of the bytes.

**Severity: could-sink-the-build.**

---

## UU-2: Content-hashed memoization is treated as a storage feature; it must be a *scheduler-level activation gate*, and AI-authored topologies will be cache-hostile by construction.

**Insight.** The vision says "memoization of piece outputs (content-hashed!)" — but
memoization is only sound if a piece is a **pure function of a fully-captured input
closure**: prompt + model + decoding params + tool-environment state + every retrieved
byte + temperature/seed. LLM calls are (a) nondeterministic by default (temperature>0, no
seed pinning), (b) tool-effectful (the execute phase runs shell/edits — re-running it is
not free or safe), and (c) closed over hidden state (filesystem, clock, network). The
current `hash_prompts` hashes the *prompt text only* — not the model identity, not decode
params, not the tool-env. A memo keyed on that hash would return stale/wrong outputs the
moment the model or environment changed, silently. And when **models author the
topologies**, they will emit prompts stuffed with timestamps, UUIDs, run-ids, and freeform
restatements — maximally cache- and memo-hostile — unless the runtime *enforces*
input-closure normalization as an invariant on the Port boundary. Memoization at vision
scale is not a cache.get() bolt-on; it is a **purity contract enforced by the
scheduler/activation model**, deciding per-piece: pure→memoizable, effectful→never,
idempotent-effectful→memoize-result-not-effect.

**Why invisible to us.** We already have the *machinery* (content-hashed blob store,
SHA-256 receipt hashing) so it feels "ready." The gap is conceptual, not infrastructural:
nobody has had to decide *which pieces are pure* because today's runs are bespoke and
human-authored, so re-execution waste is small and invisible. The danger surfaces only
when AI emits thousands of near-identical sub-pipelines that *should* collapse to a handful
of memo hits but don't.

**What it threatens.** The "O(N) but mostly cheap because we memoize" economics, AND
correctness — a memoization layer keyed on an incomplete input closure is a *silent
correctness bug generator*, the worst kind, because it returns plausible stale results.
Reshapes how Ports, purity, and the scheduler must be defined together.

**Severity: reshapes-architecture.**

---

## UU-3: Speculative/parallel execution turns the cost model from "pay for what you needed" to "pay for everything you might have needed" — and there is no abandonment/budget primitive.

**Insight.** Latency at O(N) sequential model calls is brutal (N × seconds-to-minutes), so
the vision needs speculation: launch branches before you know which you'll keep (speculate
the next pipeline stage on the *predicted* output, fan out critiques/tiebreakers, run loop
bodies ahead). `parallel_critique.py` already fans out. But speculation inverts the cost
contract: you pay for *work you throw away*. Without a first-class **budget/abandonment
primitive** — speculative branches that can be cancelled mid-flight, with the scheduler
accounting committed vs. speculative spend and killing losers the instant the resolving
branch is known — speculation makes cost *unbounded and nondeterministic*. Emergent graphs
and loops (vision primitives!) make it worse: a loop that speculates its own next iteration
can fork-bomb spend. Model calls are also largely **non-cancellable mid-generation** at the
API layer (you pay for tokens already produced), so "abandonment" must be designed at the
scheduling layer with hard token-budget ceilings per branch, not as a hopeful `task.cancel()`.

**Why invisible to us.** Today fan-out is narrow, bounded (N checks), and human-triggered,
so wasted speculative spend is a rounding error. The primitive looks like "just run things
in parallel." The unbounded-cost failure mode only appears when topologies are
AI-authored, recursive, and the scheduler is asked to speculate deep.

**What it threatens.** Latency viability (if we *don't* speculate) traded against cost
viability (if we speculate without bounds). Without the primitive, we'll be forced to pick
one and lose the other. Also threatens predictability — a platform whose cost per run is
nondeterministic is un-budgetable for any tenant.

**Severity: reshapes-architecture.**

---

## UU-4: Cache and memo state is a *hidden global resource* that fan-out, retries, and multi-tenancy will thrash — invalidation is the unnamed time-bomb.

**Insight.** Once you have prefix-cache warmth, output memos, and content-hashed piece
results, *cache-hit-rate becomes a function of execution ORDER and CONCURRENCY*, not just
of inputs. Fan-out that launches N branches simultaneously gets zero warm-cache benefit
from each other (all cold at t=0) where serializing the first would have warmed it for the
rest — a real scheduler tradeoff (latency vs. cache amortization) nobody is currently
deciding. Retries (the harness retries blocked milestones, stalls) re-pay unless the memo
is hit, but the memo may be invalidated by the very state change that caused the retry.
And the journaled/content-hashed foundation means **invalidation** — the genuinely hard CS
problem — is unsolved: when a piece's *transitive input* changes (a shared scaffold prompt,
a model version, a retrieved doc), every downstream memo must invalidate, but the taint/
provenance graph to do that correctly doesn't exist as a runtime structure. Stale memo +
provenance taint = wrong answers that *look* journaled and trustworthy.

**Why invisible to us.** Single-tenant, single-plan, low-concurrency dev never thrashes the
cache; invalidation never fires because nothing is shared long enough to go stale. The
5m TTL hides the problem by expiring everything before staleness matters — which is *itself*
a cost bug at scale (re-warming constantly).

**What it threatens.** Both the cost claim (thrashed cache = full re-pay) and the durability/
trust claim (stale memo defeats the journaled-foundation promise). Worth designing the
provenance-taint graph for invalidation before, not after, memoization ships.

**Severity: worth-designing-for.**

---

## The single biggest abstraction we haven't named

### The **Computation Receipt** — a content-addressed, provider-portable, purity-typed memo key that binds the *full input closure* of a piece to its output and its invalidation lineage.

Today we have two halves that never meet: `hash_prompts()` (prompt-text → hash, for
*audit*) and the content-hashed blob/receipt store (for *durability*). Neither is a
**memoization key**, because neither captures the closure that makes an LLM call
reproducible: `(canonical_prompt ⊕ model_identity ⊕ decode_params ⊕ tool_env_fingerprint ⊕
retrieved_context_hashes ⊕ purity_class)`. The Computation Receipt is that key, and it is
the missing spine connecting *every* cost lever in this vantage:

- **Memoization**: same Receipt key → return stored output, skip the model call. This is
  the lever the vision names but the code lacks.
- **Routing/caching antagonism (UU-1)**: the Receipt is provider-*portable* — it
  memoizes the logical result independent of which provider produced it, so cheapest-capable
  routing no longer destroys reuse. The Receipt, not the provider's ephemeral cache, becomes
  the durable cache layer; provider prefix-caching becomes a mere fast-path under it.
- **Purity contract (UU-2)**: the Receipt carries a `purity_class` (pure / idempotent-
  effectful / impure) that the *scheduler* reads to decide whether a hit is reusable — making
  memoization a scheduler-level activation gate, not a storage afterthought.
- **Speculation accounting (UU-3)**: speculative branches are Receipts marked `committed=false`;
  the scheduler bounds spend by counting open speculative Receipts and can abandon them.
- **Invalidation (UU-4)**: each Receipt records its input-closure lineage, so a change to any
  transitive input produces a *different* key automatically — invalidation becomes
  structural (a new key is a miss) rather than a manual cache-bust. This is also exactly the
  Port's `provenance + taint` made executable.

This abstraction is the load-bearing unification of "content-hashed/journaled foundation,"
"Port = type+version+provenance+taint," and "cheapest-capable routing" into one object
whose existence makes the O(N) cost model viable and whose absence makes every lever in
this vantage fight the others. **Name it, type it, and make the scheduler/activation model
take a Computation Receipt as the unit it schedules — before the execution idiom and the
prompt-rendering layer harden around the cache-hostile, audit-only hashing we have today.**
