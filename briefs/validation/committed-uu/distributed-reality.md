# Distributed / Multi-Tenant Reality — Unknown-Unknowns for the Full Arnold Vision

Vantage: the full vision is *many agents, many users, many concurrent runs sharing
models / keys / state / compute*. Arnold started single-process. This brief hunts the
distributed-systems hazards that will bite a platform that grew from one process, grounded
in the actual code as it exists today.

## What the code actually is today (ground truth)

1. **The key pool is a process-global singleton keyed on `time.monotonic()`.**
   `megaplan/runtime/key_pool.py` ends with `_pool = KeyPool()` — one in-memory object per
   Python process. `acquire(provider)` picks `min(eligible, key=last_used)` under a
   `threading.Lock`. Cooldowns (`report_429`) set `cooldown_until = now + cooldown_secs`
   where `now = time.monotonic()`. Monotonic clocks are **per-process, non-comparable across
   processes or hosts**, and reset on restart. The pool's notion of "which key is least
   recently used" and "which key is cooling down" is private to one process.

2. **Fan-out is in-process Thread/ProcessPool, but every worker reaches the same global pool.**
   `megaplan/_core/hermes_fanout.py` uses `ThreadPoolExecutor` (scatter_gather) and
   `ProcessPoolExecutor` (process-isolated variant). The thread variant shares the one
   `_pool`; the process variant gets a *fresh* `_pool` per child — so the two fan-out paths
   have *different* rate-limit-coordination semantics for the same keys.

3. **Two stores, two consistency models, both wall-clock leases.**
   `MultiStore` (megaplan/store/multi.py) federates a `FileStore` and a `DBStore`.
   - DBStore leases: `DELETE ... WHERE expires_at <= now(); INSERT ...` with `FOR UPDATE`
     elsewhere — server-side wall clock, real row locks.
   - FileStore leases (`_file/operations.py::acquire_execution_lease`): **read-then-write**
     (`get_active_lease()` then `_save_model()`), no atomic CAS, `expires_at` computed from
     the *caller's* `datetime.now(UTC)`.
   - Optimistic concurrency exists (`expected_revision` → `OptimisticLockError`) but only
     within a single store's update path.

4. **Idempotency keys are deterministic SHA-256 slugs of caller-supplied parts**
   (`store/base.py::deterministic_idempotency_key`). Dedup correctness depends entirely on
   callers feeding the *same* parts; there is no global sequencer.

---

## Unknown-Unknown #1 — The key pool is a hidden shared scheduler with no global state

**Insight.** `KeyPool` is not "config plumbing" — it is a *scheduler for a contended global
resource* (provider rate-limit budget) that happens to be written as a process-local
singleton with a monotonic clock. The moment two runs share a key (same `ZHIPU_API_KEY`,
same OpenRouter account), the *real* rate limit lives at the provider, but each process
believes it owns the whole budget. Cooldowns set by process A after a 429 are invisible to
process B, which immediately hammers the same cooling key. There is no token bucket, no
fair-share, no cross-process backpressure — just N processes independently rediscovering the
same 429 wall. Worse: the LRU `min(last_used)` selection means *every* fresh process picks
the *same* "least recently used" key first (its own `last_used` starts at 0.0 for all keys),
so a fan-out of 20 workers stampedes key #1 in lockstep. This is a thundering-herd /
synchronized-retry pattern that gets *worse* with scale, and it is completely invisible in
single-process testing where the one pool genuinely does own the budget.

**Why invisible to us.** Single-process dogfooding (the entire current dev loop) is the one
regime where the abstraction is *correct*. The bug only manifests with concurrency we don't
yet run. The code even *looks* careful — there's a lock, cooldowns, failed-marking — which
disguises that the whole thing is the wrong scope (process, not fleet).

**What it threatens.** Cheapest-capable-model routing — the privileged heart. Routing's
entire premise is "pick the cheapest key/model that can do the job." Under multi-tenant load
the router is optimizing against a *fictional* private budget; real behavior is correlated
429 storms, unfair starvation of small tenants by large ones, and cost/latency blowups that
look like provider flakiness. It silently invalidates the routing telemetry the
self-improving harness learns from.

**Severity: could-sink-the-build** (it directly corrupts the heart's core promise at scale).

---

## Unknown-Unknown #2 — Wall-clock leases over a shared filesystem are not mutual exclusion

**Insight.** The FileStore lease path is `get_active_lease()` → branch → `_save_model()`.
That is a textbook check-then-act race: two workers on two hosts mounting the same file root
(the obvious "scale out cheaply: just share the volume" move — and `megaplan cloud` already
has a *persistent workspace volume* shared across chains) both read "no active lease," both
write their own lease file, both believe they hold it. Even if writes were atomic,
`expires_at` is computed from each host's `datetime.now(UTC)`; a host whose clock is 90s fast
will treat a live lease as expired and steal it; a slow host will hold a lease the system
thinks is dead. Heartbeats don't fix this — they *re-derive* TTL from the same skewed clock.
The execution lease is the thing that guarantees *exactly one worker drives a plan's
Plan-Execute-Verify loop*. If it can be double-held, two workers run `execute` on the same
plan against the same git worktree concurrently — and the worktree-carry / dirty-state bugs
already in MEMORY.md become *corruption*, not just false-positive reviews.

**Why invisible to us.** Leases are tested against the DBStore (real `FOR UPDATE`, server
clock) where they're correct, OR against a single-process FileStore where there's no second
contender. Nobody has run two hosts against one shared file root *and* induced clock skew —
yet "share the volume" is the cheapest path to the multi-run vision and is already half-built
in cloud. The MultiStore even silently *picks* which backend owns leases per-epic, so the
guarantee differs by epic without anyone choosing it.

**What it threatens.** The durable, content-hashed, journaled foundation's central safety
property: single-writer-per-plan. Double execution means divergent journals, conflicting
content hashes for the "same" transaction, and unreplayable history.

**Severity: could-sink-the-build.**

---

## Unknown-Unknown #3 — The federation has no global time order, so the journal isn't globally replayable

**Insight.** Events carry `pre_state_sha256` / `post_state_sha256` (content-hash chaining)
and `occurred_at`. `_event_sort_key` orders by `(occurred_at, id)` — i.e. **wall-clock
timestamps generated independently on each writer**. With two backends (file + db) and many
hosts, there is no single source of monotonic ordering. The content-hash chain gives you
*integrity within one writer's lineage* but not a *total order* across the federation:
`events_by_transaction` literally merges results from both backends and re-sorts by time.
Under skew, replay can produce an order in which a `post_state_sha256` of one event doesn't
match the `pre_state_sha256` of its "successor" — the chain looks broken even though no data
was lost, because *there was never a real edge between them*. CAP bites here: the system is
implicitly AP (two backends, eventual reconciliation) but the replay/revert machinery assumes
CP (one linearizable log). Emergent graphs and loops — where the topology is data-defined and
a node's output feeds another's input across runs — make this far worse: the "happens-before"
relation the scheduler needs is exactly the thing the timestamps can't provide.

**Why invisible to us.** Today most work is one epic, one backend, one writer, where
`occurred_at` *is* a faithful total order. The hash chain passes its tests because nothing
forks the lineage. The gap only appears when concurrent writers interleave under skew — and
when someone tries to *replay across the federation boundary*, which the MultiStore comments
admit is hand-waved ("transaction ids are globally unique... the single DB lookup is
sufficient").

**What it threatens.** The journaled foundation's promise that any state is *reconstructible
and revertible*. If replay can't establish a deterministic order, `revert` and
`get_epic_at_time` are unsound under concurrency, and the self-improving harness loses its
ground truth for "what actually happened."

**Severity: reshapes-architecture.**

---

## Unknown-Unknown #4 — Backpressure and fairness have no home; the unit of isolation is undefined

**Insight.** Across the whole vision there is no place that answers "tenant X is allowed N
concurrent model calls / M dollars / K worktrees right now, and tenant Y is starving — slow
X down." Fan-out concurrency is a per-call `max_concurrent` int read from config; there is no
*global* admission control. When models *emit pipelines* (AI-authored topologies), a single
emitted graph can fan out unboundedly — a loop node that spawns sub-plans that each fan out
critique 20-wide is a fork bomb against shared keys and shared compute, authored by a model,
with no governor. The scheduler primitive (DAGs / loops / standing / emergent) is described
as the platform's defining primitive, but scheduling *is* resource arbitration, and right now
arbitration is scattered across: the KeyPool (keys), `max_concurrent` (fan-out width),
leases (plan exclusivity), and nothing at all (dollars, worktrees, CPU, tenant fairness).
There is no named entity that owns "who gets to run next, and how much."

**Why invisible to us.** At single-tenant scale the operator *is* the governor — Peter
decides what runs. The MEMORY notes ("don't shrink scope, burn the money") encode that the
human absorbs backpressure today. Nothing in the code needs a quota because there's one will
behind every run. The vision removes that human — agents and other tenants author and launch
runs — but the governor was never built because it was always a person.

**What it threatens.** The pluggable-scheduler primitive itself, plus basic survivability:
one greedy or buggy AI-authored topology can exhaust shared keys/compute and take down every
tenant. Fairness, isolation, and cost-safety are all downstream of an arbiter that doesn't
exist.

**Severity: reshapes-architecture.**

---

## The single biggest UNNAMED ABSTRACTION this vantage reveals

**A first-class, distributed RESOURCE GOVERNOR (a "Capacity Lease" / global admission +
fair-share scheduler) — the cross-tenant arbiter of every contended resource.**

Today, arbitration of contended resources is *smeared across four unrelated mechanisms at
the wrong scope*: the process-local `KeyPool` (provider budget), a per-call `max_concurrent`
int (fan-out width), wall-clock file/DB leases (plan exclusivity), and a human (dollars,
compute, fairness). The full vision needs one named primitive that sits *under* the scheduler
and *over* the key pool: it issues **capacity leases** — "you may make N calls to provider P /
spend $D / hold W worktrees, until time T, fairly shared against all other tenants" — backed
by a single linearizable source of truth (the DB, with real time and real locks), with the
provider rate limit, the dollar budget, the worktree pool, and plan-exclusivity all expressed
as the *same* kind of lease. The KeyPool becomes a thin local cache of grants from the
governor, not an authority. Leases get a real fencing token (monotonic sequence, not wall
clock) so a stolen/expired lease *fails its next write* instead of silently double-running.
The scheduler asks the governor "may this node run now?" and the governor enforces fairness,
backpressure, and cost ceilings — including against pipelines models authored themselves.

Name it now, give it the linearizable backbone, and #1–#4 collapse into one solved problem.
Leave it unnamed and each will be discovered separately, in production, as a different
mysterious outage.
