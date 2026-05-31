# Committed Unknown-Unknowns — Vantage: THE FOUNDATION (durable, content-hashed, journaled execution)

**Stance:** We ARE building Arnold's durable, content-hashed, journaled execution core. This brief is not about
whether — it is about the brutal, decade-learned, $100M-tuition constraints that Temporal / Restate / DBOS /
Inngest / Dagster hit when getting durable execution *right*, mapped onto Arnold's specific shape: a
self-improving Plan-Execute-Verify harness, AI-authored data-defined topologies, and side effects that are
**git merges, LLM calls, and money-spending model invocations** — i.e. the worst possible kind of side effect
for a replay-based engine.

---

## The frame that makes the risks visible

Every mature durable engine splits the world into two halves with a hard, load-bearing membrane between them:

1. **The orchestration / control-flow half** — must be *perfectly deterministic*. On crash, the engine
   re-executes this code from the top and it MUST make the identical sequence of decisions, or the engine
   fails the workflow with a non-determinism error. (Temporal, Restate, DBOS all enforce this.)
2. **The side-effect half** — explicitly non-deterministic, wrapped (Temporal Activity / Restate `ctx.run` /
   DBOS step), journaled on first execution, and *never re-run on replay* — its first result is memoized and
   replayed.

Jack Vanlightly's "Demystifying Determinism" (2025-11) names the silent killer precisely: determinism applies
to **decision-making logic, not to the operations**. His canonical bug — a promo-date `if` that evaluates
true on first run and false on replay because wall-clock time moved — *double-charges the customer*. The
control flow branched on un-journaled external state.

**Arnold's problem:** in an AI-authored, Plan-Execute-Verify harness, *the LLM is the control flow.* The model
decides the branch. And the model's output is the single most non-deterministic thing in computing. Every
naive durable-execution mental model assumes "control flow is cheap deterministic code, side effects are the
expensive non-deterministic part." Arnold inverts this: the expensive non-deterministic part (the model) is
*authoring the control flow.* This is the root of nearly every UU below.

---

## UNKNOWN-UNKNOWN 1 — The determinism membrane runs straight through the model, not around it

**Insight.** In Temporal/Restate/DBOS, the deterministic skeleton is hand-written code; the non-deterministic
parts are clearly fenced into journaled steps. Arnold's pitch is the opposite: *models emit pipelines and make
routing decisions at runtime.* That means the thing producing the control-flow graph is itself
non-deterministic. You cannot put the model "inside a journaled step" and also let it "be the orchestrator" —
those are contradictory placements. If a planning/routing model output is treated as a journaled side effect
(memoized, replayed), then **the harness can never re-plan on replay** — it is frozen to its first decision,
which defeats "self-improving." If instead the model output drives live branching that isn't journaled, then
**any resume/replay re-invokes the model, gets a different plan, and the journal no longer matches reality** —
a non-determinism fault, except Arnold won't even detect it because it has no recorded command history to
diff against (the way Temporal diffs replayed commands vs event history).

**Why it's invisible to us now.** We're importing the durable-execution vocabulary ("journaled," "replay,"
"exactly-once") without importing the *constraint that earned it*: those guarantees exist precisely because
the orchestration code is frozen and deterministic. We have a privileged self-improving harness whose entire
value is that the orchestration *changes its mind*. We will reach for "just make it durable like Temporal" and
discover the two requirements are in direct tension at the primitive level.

**What it threatens.** The core value prop. "Self-improving harness" + "durable journaled replay" cannot both
be naive. Without a designed answer, every crash-resume either (a) silently replays a stale plan as if it were
authoritative, or (b) silently re-plans and diverges from the journal — both produce *plausible-looking wrong
results*, the worst failure class. This is the megaplan-equivalent of the double-charge bug, at the level of
"which milestones even exist."

**Severity: could-sink-the-build.**

---

## UNKNOWN-UNKNOWN 2 — Git merges, model spend, and PR creation are non-replayable, non-idempotent, pivot-class side effects with no natural idempotency key

**Insight.** DBOS is brutally honest about the boundary: it gives true exactly-once *only when the step writes
to the same Postgres that stores workflow state* (the checkpoint piggybacks on the same transaction).
"The moment your step calls an external service, you are back to at-least-once plus idempotency." Temporal
says the same: the engine guarantees the *workflow* runs to completion once, but each *side effect* is
at-least-once unless you supply an idempotency key the downstream system honors.

Arnold's marquee side effects are *exactly the ones with no clean idempotency key and no clean compensation*:
- **`git merge` / commit / push** — not idempotent (re-running after a partial failure can double-apply, or
  hit a now-changed tree and conflict), not cleanly compensable (a revert is a *new* commit, not a rollback;
  and a pushed merge that others branched from is a Saga *pivot transaction* — the point of no return).
- **Spending money on a model call** — the call already cost money before the journal write; a crash between
  "API returned" and "journal committed" means you pay again on replay with no dedup key the provider honors.
- **Creating a PR / triggering CI / posting a review** — emits visible external state. Saga literature is blunt:
  emails sent, audit records written, external API calls with side effects "can only be acknowledged and
  mitigated" — you compensate a sent email with an apology email, not an un-send.

**Why it's invisible to us now.** Content-hashing lulls us. "Everything is content-addressed and journaled"
*feels* like it confers idempotency — but content-addressing makes *reads/derivations* idempotent (same inputs
→ same hash → cache hit). It does nothing for *effects on the outside world*. A git push of content-hash `abc`
is still a mutation of a remote whose state we don't content-address. We will conflate "the artifact is
content-addressed" with "performing the act is idempotent," and only discover the gap when a resumed run
double-pushes or double-bills.

**What it threatens.** Correctness and trust of the whole "durable, resume-anywhere" promise — *especially*
for the cloud / long-running tenant where resume-after-crash is the entire selling point. Also money (double
model spend on replay) and repo integrity (double-applied merges). Memory entries already record adjacent
real pain — `worktree_carry_breaks_pr_isolation`, `execute_stall_codex_silence` — these are the *foreshocks*
of an un-modeled effect/compensation layer.

**Severity: could-sink-the-build.**

---

## UNKNOWN-UNKNOWN 3 — "Resume into a changed-code universe" is unbounded for us, because the code AND the pipeline definitions are AI-authored and constantly rewritten

**Insight.** Temporal's hardest-won, most expensive lesson is *workflow versioning*. When workflow code changes
while executions are mid-flight, replay of the old event history against new code throws non-determinism
errors. Their two mitigations both carry a long tail: the **Patched/GetVersion** API litters code with
permanent `if version >= N` branches that can essentially never be deleted; **Worker Versioning** pins
in-flight runs to the exact old binary, which means **old code paths must be retained and runnable for as long
as any pinned execution survives.** Encrypted payloads make it worse — you can't even replay-test against
production histories without decrypt access. This is the tax a self-improving system pays *continuously.*

Arnold multiplies this along *two* axes Temporal only has one of:
- **Engine code changes** (the harness improves itself — memory note
  `dogfood_engine_shadow_and_openrouter` shows we already run the *worktree's* megaplan as the engine; the
  engine mutating under in-flight runs is not hypothetical, it's our default dogfood loop).
- **Pipeline *definitions* change** — the topologies are data, AI-emitted, and the platform's premise is that
  models keep emitting better ones. A resumed run may need to replay against a pipeline graph that *no longer
  exists in the form it was journaled under.*

**Why it's invisible to us now.** We think of "content-hashed" as the *answer* to versioning — pin the hash,
get the exact graph back. But content-hashing pins the *definition*; it does not pin the *interpreter*. The
scheduler/activation semantics, the Port type-coercion rules, the taint-propagation logic — the *runtime that
walks the graph* — are code, and that code self-improves. A journaled run carries the graph hash but not a
runtime-semantics hash, so replay silently uses *new* interpreter semantics over an *old* graph. That's a
non-determinism fault Temporal would catch and we won't, because we haven't built the command-history diff
that makes it catchable.

**What it threatens.** Every long-lived execution (the durable/cloud tenant), and the self-improvement loop
itself — the faster Arnold improves, the more divergent the universe a paused run wakes into. Worst case: the
platform's core differentiator (self-improvement) is throttled by an unbudgeted requirement to keep N old
interpreter versions runnable forever, or to forbid resume across an engine change.

**Severity: reshapes-architecture.**

---

## UNKNOWN-UNKNOWN 4 — Journal/history growth is unbounded for emergent + standing + interactive topologies, and the cheap escape hatch (Continue-As-New) breaks our determinism story

**Insight.** Temporal's hard ceilings are *physical, non-negotiable* lessons: event history caps at
**51,200 events / 50 MB** (warns at 10K / 10MB), single payload max **2 MB** (warns at 256 KB), transaction
size **4 MB**, max ~**2,000** incomplete child ops per execution. Long-running workflows survive only via
**Continue-As-New**: atomically end the run and start a fresh run with empty history, carrying forward a
*small summarized state*. Large payloads must be offloaded to a blob store via the claim-check pattern (which
is exactly what content-hashing should enable — store the hash, not the blob).

Arnold's primitive *explicitly* includes "loops, standing/interactive processes, and emergent graphs."
Standing and emergent processes have **no natural completion boundary** — they're the workloads that blow past
51K events fastest, and Continue-As-New's whole trick depends on being able to **summarize forward into a
small deterministic seed**. But an *emergent* graph's relevant state may not be summarizable — its history
*is* its meaning. And every Continue-As-New boundary is a fresh determinism contract: the carried-forward seed
must deterministically reconstruct identical control flow, which collides head-on with UU#1 (the model is the
control flow).

**Why it's invisible to us now.** "Content-hashed + journaled" sounds *inherently* scalable — dedup by hash,
append-only log, done. But content-hashing dedups *storage*; it does nothing about the *length of the causal
chain the engine must walk to replay.* A 200-turn agent loop is 200 journal entries to replay *even if every
artifact is a cache hit*. We'll hit replay-cost and history-bloat walls precisely on the topologies
(standing/emergent) that are our most differentiated, and the standard escape hatch carries a determinism
contract we haven't designed for.

**What it threatens.** The scheduler/activation primitive's most novel modes (standing, emergent, loops) — the
ones that aren't just "Temporal again." Replay cost grows with chain length; cold-resume latency and engine
memory balloon; the differentiated topologies are the first to become operationally infeasible.

**Severity: reshapes-architecture.**

---

## THE ABSTRACTION WE HAVEN'T NAMED

### The **Effect Ledger** — a typed, provenance-carrying record of *acts upon the outside world*, distinct from the artifact journal, with declared replay-class and compensation.

We have named the **artifact** side beautifully: content-hashed, journaled, Ports carrying type+version+
provenance+taint. That machinery makes *derivations* (pure input→output) durable and idempotent for free.

We have **not** named the **effect** side: the irreversible, money-spending, repo-mutating, world-visible
*acts* — git merge/push, model invocation, PR creation, CI trigger, message send. Every mature durable engine
learned, expensively, that this is a *separate first-class concern* from data flow, because it obeys different
laws: at-least-once not exactly-once, idempotency-key not content-hash, compensation not rollback,
pivot-points not free-undo.

The Effect Ledger is the named primitive that makes UU#1–#4 designable instead of fatal. Every act against the
outside world is a typed Effect carrying:

- **replay-class** — `pure` (re-derivable, content-hash dedup), `idempotent-keyed` (carries a key the external
  system honors; safe to retry), `at-most-once` (must be journaled *before* execution and never replayed —
  e.g. model spend), or `pivot` (irreversible point-of-no-return — e.g. pushed merge; downstream compensable
  steps are voided once it commits).
- **idempotency key** — explicit, external-system-honored, *not* the content hash (the hash dedups the
  artifact; the key dedups the act).
- **compensation** — a declared semantic-inverse Effect (refund/void/release/revert-commit/apology), or an
  explicit `noncompensable` marker that forces the planner to treat the step as a pivot and route around
  needing to undo it.
- **provenance + taint** — same spine as Ports, so the model that *authored* an effect, and any taint on its
  inputs, is carried into the act itself (critical when the model is the control flow — UU#1).

This abstraction is the missing dual of the Port. The **Port** governs *safe composition of data* (type +
version + provenance + taint). The **Effect** governs *safe composition of acts* (replay-class + idempotency
key + compensation + provenance + taint). Without it, the durable foundation guarantees durability for the
half of the system that didn't need much help (pure derivations) and stays silent about the half that will
actually double-charge, double-push, and resume into a universe that no longer matches — the half that sank
the budgets of everyone who learned this before us.

---

## Sources

- [Demystifying Determinism in Durable Execution — Jack Vanlightly (2025-11)](https://jack-vanlightly.com/blog/2025/11/24/demystifying-determinism-in-durable-execution)
- [What is Durable Execution? — Restate](https://www.restate.dev/what-is-durable-execution)
- [Durable AI Loops: Fault Tolerance across Frameworks — Restate](https://www.restate.dev/blog/durable-ai-loops-fault-tolerance-across-frameworks-and-without-handcuffs)
- [Why Postgres is a Good Choice for Durable Workflow Execution — DBOS](https://www.dbos.dev/blog/why-postgres-durable-execution)
- [DBOS Architecture](https://docs.dbos.dev/architecture)
- [Safely deploying changes to Workflow code — Temporal](https://docs.temporal.io/develop/safe-deployments)
- [Versioning — Temporal (Go/TS SDK)](https://docs.temporal.io/develop/typescript/versioning)
- [Workflow Execution limits — Temporal](https://docs.temporal.io/workflow-execution/limits)
- [System limits — Temporal Cloud](https://docs.temporal.io/cloud/limits)
- [Troubleshoot payload / blob size limit errors — Temporal](https://docs.temporal.io/troubleshooting/blob-size-limit-error)
- [Saga Compensating Transactions — Temporal](https://temporal.io/blog/compensating-actions-part-of-a-complete-breakfast-with-sagas)
- [Saga Design Pattern — Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [What is idempotency? And why it matters for durable systems — Temporal](https://temporal.io/blog/idempotency-and-durable-execution)
- [Durable Execution: The Key to Harnessing AI Agents in Production — Inngest](https://www.inngest.com/blog/durable-execution-key-to-harnessing-ai-agents)
- [Durable execution — LangChain/LangGraph docs](https://docs.langchain.com/oss/python/langgraph/durable-execution)
