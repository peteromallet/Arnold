# Unknown-unknowns — ECONOMICS vantage

Vantage: the money reality. Unit economics of running many compositions, each a fan_out
of N model calls, across many concurrent modules/tenants. Who pays, for what, and whether
the cost *profile* of "compose lots of agent calls" is viable vs the value delivered.

Hard facts pulled from the repo (load-bearing, not speculation):

- **Cost cap is a per-run terminal abort, not a budget primitive.** `auto.py` carries
  `max_cost_usd`; when cumulative spend after a phase exceeds it, the *whole run* aborts with
  `cost_cap_exceeded`. There is no per-node, per-tenant, or cross-composition budget ledger,
  no soft-degrade, no reservation/commit. Budget is a single scalar checked at phase seams.
- **Cost reporting is explicitly single-plan.** `briefs/megaplan-cost-subcommand.md` Scope(OUT):
  "Do not build cross-plan aggregation (single plan only for now)." The whole accounting frame
  assumes one plan = one cost object.
- **The Claude backend is bound to subscription/OAuth billing via an interactive tmux session.**
  `shannon.py:1188-1190` empties `ANTHROPIC_API_KEY` so Claude Code "falls back to OAuth
  credentials" — i.e. it deliberately rides a *human's Claude subscription seat*, not metered API.
  The fan-out brief already discovered the consequence: `claude -p` headless is "technically
  feasible but economically rejected" because it forces metered API-key billing.
- **Cache tokens are tracked but not architected.** `hermes_state.py` stores
  `cache_read_tokens`/`cache_write_tokens`, but nothing in the node library treats prompt-cache
  reuse as a composition-level optimization. Caching is a measurement, not a strategy.

These four facts, taken together, point at things the epic frame structurally cannot see.

---

## UU-1 — The Claude backend's billing model does not survive becoming "a substrate other people compose on"

**Insight.** Megaplan's economic moat today is a quiet arbitrage: Shannon drives Claude
*interactively, on a subscription seat*, so the marginal dollar cost of a Claude turn is ~$0 to
the operator (it's a flat monthly seat, rate-limited by Anthropic). Every "premium" reasoning
turn in plan/critique/review effectively rides that flat-rate seat. Arnold's thesis — "other
people compose pieces, including premium model calls, into their own modules" — silently assumes
that arbitrage *transfers*. It does not. The moment a third party composes a pipeline that fans
out 8 Claude judges, one of two things must be true: (a) those calls ride the *builder's own*
single subscription seat — in which case a fan_out of N>1 Claude calls is **serialized through one
interactive tmux session and one rate-limited seat**, destroying the parallelism that makes
fan_out valuable; or (b) they switch to metered API billing — in which case the per-call cost the
operator never paid suddenly becomes real, and the "compose lots of agent calls" economics look
completely different (a fan_out panel of 8 is now 8× metered Opus calls, not 8 "free" seat turns).

**Why our process was blind to it.** Every prior pass treated the Claude-via-OAuth path as a
*driver implementation detail* ("inside the frame — don't re-audit the drivers"). The cost of a
Claude turn never appeared in any unit-economics reasoning *because in the dogfood configuration it
is genuinely near-zero at the margin*. The frame "single-repo SDK that a developer composes" hides
the fact that the dogfood operator and the imagined external builder have **fundamentally different
cost curves** for the exact same node. We costed the system we run, not the system we ship.

**If true.** The "value is composability" thesis is partly subsidized by a billing arbitrage that
external builders can't inherit. Either: (1) fan_out-over-Claude is a single-tenant, serialized
primitive (it cannot be the panel-of-N it's drawn as) and the canonical examples must be re-drawn
on cheap metered models with Claude as the rare escalation; or (2) Arnold must make the
billing-substrate (seat vs metered, whose seat) a **first-class, explicit property of every model
call**, surfaced in the node contract, because it changes both latency and cost by orders of
magnitude. The current plan exposes neither.

**Severity: would-redirect.**

---

## UU-2 — fan_out / compete have inverted unit economics: cost scales with N, value scales with diversity, and they decouple fast

**Insight.** A fan_out panel of N calls costs O(N) dollars but delivers value sub-linearly —
roughly O(log N) or worse, because LLM panels exhibit heavy *answer correlation* (same base model,
same prompt → highly correlated outputs; the 5th DeepSeek judge rarely says anything the first
three didn't). `compete` (select-one) is worse: you pay for N full runs and *discard N-1 by
construction*. The system has primitives (`fan_out`, `compete`, parallel critique, bakeoffs) whose
spend is linear in panel width but whose marginal informational return collapses after 2-3 agents.
Nothing in the node library prices this. There is no "diversity-aware" stop ("the panel has
converged, stop spawning"), no per-node cost/value telemetry, no notion that the *correct* N is a
function of observed disagreement, not a config constant. At scale across many modules each fanning
out, the dominant line item becomes **panels paying linear cost for logarithmic value** — the most
expensive possible failure mode, and the one most invisible because each individual call looks
cheap.

**Why our process was blind to it.** The hardening effort was about *correctness and composability*
of the primitives (typed Ports, realized graph, reduce semantics) — making fan_out/reduce *work*,
not making them *worth it*. "A fan_out panel = N model calls" was stated as a mechanical fact in the
vantage prompt, never as an economic liability. The frame "builders compose pieces" treats more
composition as more value; it has no concept that a composition can be net-negative EV (spend > marginal
information). Correlation-of-LLM-outputs is a statistical property no code-level audit would surface.

**If true.** Arnold needs a *value model* alongside the cost model: panel width should be adaptive
(spawn until marginal disagreement drops below a threshold), reduce/select nodes should emit a
cost-per-bit-of-information signal, and the canonical "fan out 5 judges" examples are an
anti-pattern to be replaced with "fan out 2, escalate to 3 only on disagreement." Without this, the
most-composed pipelines are the least economic, and Arnold actively teaches builders to burn money.

**Severity: would-reshape.**

---

## UU-3 — There is no economic actor model: "who pays for what" is undefined, and that dictates an architecture the epic doesn't have

**Insight.** The plan has a *trust boundary* (M6) but no *billing boundary*. In any world where
"other people compose modules" that run "across many concurrent modules/tenants," the unanswered
question is: when module A composes module B which fans out to a premium model, **whose budget,
whose API key, whose subscription seat, whose rate limit** is consumed — and who is liable when a
composed-in third-party module quietly spawns a 50-call panel? Today cost is a single scalar
(`max_cost_usd`) attached to one run on one operator's credentials. There is no per-tenant ledger,
no key/seat ownership propagation through composition, no attribution of spend to the *composer* vs
the *composed*, no quota isolation so tenant A's runaway panel can't exhaust tenant B's seat rate
limit. The hardest economic problems of a multi-tenant compositional substrate — metering,
attribution, isolation, charge-back, abuse — are simply *not in the type system*, while a great deal
of effort went into a trust boundary that governs code, not money.

**Why our process was blind to it.** The unit of the frame is "a pipeline (DAG or loop)" and the
operator is implicitly *one developer running their own thing locally / on their own Railway box*.
Single-tenant-self-hosted is the assumed deployment, so billing identity == process identity ==
the one human, and "who pays" never needs an answer. The instant you say "many concurrent
modules/tenants" (which the vantage does) that collapses, but no prior pass took the multi-tenant
deployment as real — it was always "runs where megaplan runs today." Money attribution looks like a
*business/ops* concern, which a code-and-architecture epic systematically defers.

**If true.** Arnold needs a first-class **economic principal** threaded through dispatch alongside
the trust boundary: every model call carries a (principal, key/seat, budget-account) tuple; budgets
are reservations against an account, not a terminal scalar; the policy spine gains spend-isolation
and per-principal quota; cost events become a per-tenant ledger, not a single-plan rollup. This is a
structural addition to the very layers (dispatch, state, policy spine) the epic considers nearly
done — it would reshape M3/M4 rather than bolt on later.

**Severity: would-reshape.**

---

## UU-4 — Caching is the dominant lever and it's been demoted to a metric; composition-without-cache-design can be 5-10× more expensive than necessary

**Insight.** For "compose lots of agent calls," the single biggest cost determinant is **prompt
cache hit rate** — whether the large, stable prefix (system prompt, repo context, task framing) is
re-billed at full input price on every node, or read from cache at ~10% the price. Arnold's
composition model — many small nodes each making a fresh stateless call (`run_oneshot` is the
explicit fan-out contract) — is structurally *cache-hostile*: stateless one-shots throw away the
KV-cache between calls, and a DAG of independent nodes each re-sends overlapping context. The repo
*records* `cache_read_tokens`/`cache_write_tokens` but treats caching as observability, not as an
architectural constraint on how nodes should share a prompt prefix, how a fan_out should structure
its N calls to maximize shared-prefix cache hits, or how the executor should order/batch calls to
keep caches warm. The composition pattern the SDK is *designed to make easy* (lots of small
independent agent calls) is exactly the pattern that *defeats* the cheapest available cost lever.

**Why our process was blind to it.** Caching showed up as a column in a SQLite table, so it
registered as "handled." The architectural work was about *correctness of composition* (does the
data flow through the typed Port correctly), and caching is invisible to correctness — a
cache-cold pipeline and a cache-warm pipeline produce identical outputs and pass identical oracles.
It only shows up on the invoice. A behavioral/substrate-swap oracle gated every milestone; no oracle
gates cost-per-token. The frame has no place for "produces the right answer 8× more expensively
than it should."

**If true.** Cache-prefix design becomes a first-class concern of the node library and executor:
nodes need to declare/share stable prefixes, fan_out should be a *prefix-shared* batch by default
(N calls that differ only in the variable suffix, maximizing cache reuse), the executor should
schedule for cache warmth, and the cost report should expose hit rate as the headline number. This
is a reshape of how `run_oneshot` and the reduce/fan_out nodes are specified — not a post-hoc tuning
knob.

**Severity: would-reshape.**

---

## The single biggest REFRAME

**We have been designing a *correctness substrate* and calling it a *composition substrate* — but
for "many modules composing many agent calls," the binding constraint is not whether compositions
*work*, it's whether they *pencil out*, and economics is not a layer in this system, it is the
control plane.**

The frame says: pieces compose into pipelines; success = a builder ships a module cheaply; value =
composability. But "cheaply" is doing enormous unexamined work in that sentence. The dogfood
economics are subsidized by a Claude-subscription arbitrage no external builder inherits (UU-1); the
core primitives (fan_out/compete) have cost that scales with N and value that doesn't (UU-2); there
is no actor/billing model for "who pays" once tenants are real (UU-3); and the composition style the
SDK makes idiomatic is the one that defeats the cheapest cost lever (UU-4). Each is a different face
of the same blindness: **the epic treats money as an operational afterthought (one cap, one report,
single-plan) when, for a compositional agent substrate at scale, the budget is the thing being
composed.** A pipeline is not fundamentally a DAG of typed data — it is a *DAG of spend with a value
gradient*, and the primitives that should be first-class are: a per-principal budget ledger,
adaptive panel width keyed to marginal information, billing-substrate as a property of every call,
and cache-prefix as a composition contract. The realized graph should carry dollars and expected
value on its edges, not just types. Until economics is promoted from "a `max_cost_usd` scalar" to a
co-equal control plane alongside the trust boundary, Arnold will ship a substrate that composes
correctly and bankrupts predictably — and the most heavily-composed, most-successful modules will be
the most expensive failures, because the system has no organ that can even *perceive* the problem.
