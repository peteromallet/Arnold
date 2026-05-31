# Unknown-Unknowns at the Integration Seams — Arnold full-vision build

Vantage: the seams between subsystems (durable store, scheduler/activation, dispatch,
evidence/receipts, the P-E-V harness, the safe-composition Port layer, AI-authoring,
observability). The killers in big platforms live *between* components, not inside them.
This is grounded in the current megaplan codebase, read as the seed of the full vision.

Commitment is settled. Everything below is about how to build it *right* and what will bite.

---

## What the code actually shows about the seams today

The current runtime already exhibits the seam shapes the full vision will scale up:

1. **The typed step contract carries almost nothing cross-cutting.**
   `megaplan/_pipeline/types.py::StepResult` is `{outputs, verdict, next, state_patch}`.
   There is **no error channel, no cost field, no taint/provenance field, no cancellation
   token, no lineage edge**. Everything cross-cutting rides *beside* the typed contract,
   through `state.json`:
   - Cost: `state["meta"]["total_cost_usd"]`, read by `runtime.py::CostTracker.should_abort`
     as a side-channel poll *after* the step returns.
   - Progress/stall: `StallDetector.observe(state)` reconstructs progress by counting
     `history` entries with `step == "review"` — a string match on a side log.
   - Retry signals: `ContextRetry`/`BlockedRetry` switch on a *different* untyped protocol,
     `phase_result["result"] == "context_exhausted" | "blocked"` — strings, not the typed
     `GateRecommendation` literals the executor dispatches on.
   So the platform already has **two parallel languages**: the typed edge/verdict language
   the executor understands, and an untyped string/state-dict language that everything
   cross-cutting actually speaks. The seam is the translation layer between them, and it is
   implicit and lossy.

2. **Error meaning is reconstructed by regex at the far end of the seam.**
   `megaplan/orchestration/phase_result_classify.py::classify_external_error_payload`
   rebuilds the entire error taxonomy (rate_limit / balance / auth / provider_failure /
   network / stalled_stream) by **regex-scanning `str(exc)`** — matching "rate limit",
   "insufficient balance", HTTP 402/429/503, "stalled stream". The executor itself
   (`executor.py:249`) catches `BaseException`, writes `error.json` as `repr(exc)`, and
   reraises. Error *semantics* are therefore not carried across the dispatch→worker→executor
   →state seam at all; they are guessed by string-matching after the fact. This is the
   textbook "cross-cutting concern smeared inconsistently" failure, already live.

3. **There are two unjoined durability domains.**
   `store/base.py` exposes a real journaled, content-hashed, snapshot+revert
   transaction model (`Store.transaction()`, `capture_epic_snapshot`, `revert`,
   `expected_revision`, `idempotency_key`). But the executor never touches it — it does
   `os.replace(tmp, state.json)` directly (`executor.py::_atomic_write_json`,
   `_merge_state_to_disk`). So a run's *truth* lives in two stores that are atomic
   individually and **transactionally unrelated to each other**: the journaled DB and the
   per-plan state file. Nothing spans both.

4. **Lineage is reconstructed by hardcoded per-phase rules, not carried on edges.**
   `receipts/schema.py::upstream_artifact_hashes` is a literal `if phase == "critique":
   hash plan_v{i}.md; elif phase == "gate": ...` table. Provenance/lineage is *recomputed*
   from filename conventions, not *propagated* through the composition. The vision's
   "Port = type+version+provenance+taint" is, in code today, only present in docs and the
   security tool (`agent/tools/tirith_security.py`) — it does **not exist as a runtime
   construct**. The spine the vision names is currently aspirational.

These four are not separate problems. They are one missing thing seen from four angles.

---

## Unknown-Unknowns

### UU-1 — The cross-cutting metadata has no carrier; every subsystem invents its own side-channel
**Insight.** Cost, taint, lineage, error-class, cancellation, retry-budget, and deadline are
all *ride-along* facts that must travel with every unit of work through every piece. Today
each rides a different channel: cost via `state.meta`, error via regex on `repr(exc)`,
lineage via filename rules, retry via a separate `phase_result` string protocol. There is
no single envelope. At full-vision scale (models emitting topologies, emergent graphs,
standing processes, loops) these channels will **diverge silently**: a model-authored
pipeline that doesn't write `state.meta.total_cost_usd` in the exact shape `CostTracker`
expects gets *no cost cap* and burns unbounded; a new worker whose exception string doesn't
match the regex gets classified `None` → treated as a hard unknown failure → no retry.
**Why invisible to us.** Each side-channel works fine in the one pipeline it was born in
(planning). The divergence only manifests when a *second author* (another tenant, or an AI)
composes pieces that were never co-tested, so the gaps look like "that pipeline's bug,"
never "the platform has no metadata carrier." We will keep patching individual regexes and
state keys for years before seeing the missing abstraction.
**What it threatens.** The safe-composition spine, cost governance, retry correctness,
and the entire AI-authoring premise (the runtime cannot "enforce invariants" on metadata it
doesn't carry). It threatens the core promise that arbitrary composed pieces are safe.
**Severity.** reshapes-architecture.

### UU-2 — Cancellation and timeout do not propagate through a composition; they are honored only at the outermost boundary
**Insight.** `executor.py` honors `KeyboardInterrupt`/`SystemExit` by reraising — i.e.
cancellation is a process-level signal, not a composition-level one. A `ParallelStage`
(`_run_parallel_stage`) submits to a `ThreadPoolExecutor` and blocks on
`as_completed`/`fut.result()`; there is **no cooperative cancel**, no deadline token threaded
into `StepContext`, no way to cancel siblings when one fails or when a parent budget is hit.
`SubloopStep` runs a *child pipeline* — a cancel of the parent has no defined meaning for the
running child. The full vision adds *loops, standing/interactive processes, and emergent
graphs* — exactly the topologies where "stop this whole sub-tree now, cleanly, and account
for what it already spent" is the central operation. Without a propagating cancel/deadline,
a cost-cap breach (UU-1) or a user abort can only *stop reading results*; the spawned LLM
calls, sub-pipelines, and standing processes keep running and keep spending.
**Why invisible to us.** Every current pipeline is a short, terminating DAG run from a CLI,
where process-kill == cancel and the blast radius is one terminal. Cancellation semantics
only become load-bearing once compositions are long-lived, nested, and concurrent — the
features the vision is *for* but the current code has never exercised.
**What it threatens.** Cost governance under emergent/standing topologies, clean teardown,
resource leaks (orphaned cloud containers — note `cloud/supervise.py`), and the ability to
bound spend on a runaway AI-authored graph. A self-improving harness that can't cleanly
cancel a bad self-modification is dangerous.
**Severity.** could-sink-the-build.

### UU-3 — No transaction spans the run; "durable + journaled" is true per-store but false across the composition
**Insight.** The vision's durable, content-hashed, journaled foundation exists
(`Store.transaction`, snapshots, revert) — but the *run* is not a transaction over it. The
executor writes `state.json` outside any DB transaction; receipts are appended; the DB epic
state is updated by separate calls. A failure between two stages leaves: state.json advanced,
receipt written, DB possibly not — with **no enclosing unit of work that can roll all three
back to a consistent point.** `_merge_state_to_disk`'s "executor-owned keys win, on-disk
handler keys win otherwise" merge is a hand-rolled conflict resolution *because* there is no
real transaction boundary. At full-vision scale (multi-piece runs, emergent graphs, multiple
authors writing to the shared foundation concurrently) the absence of a run-level transaction
/ saga boundary means partial failures produce states that *no consistency rule describes* —
and the self-improving harness will learn from corrupted evidence.
**Why invisible to us.** Each store is individually atomic (`os.replace`, DB `expected_revision`),
so every component passes its own durability test. "Are the stores consistent *with each
other* after a mid-run crash?" is a question no single component owns and no test asks —
the classic seam blind spot.
**What it threatens.** Evidence integrity (the harness verifies against possibly-torn state),
resumability/replay correctness, content-hash determinism (a re-run from a torn point won't
reproduce hashes), and multi-tenant correctness on the shared foundation.
**Severity.** reshapes-architecture.

### UU-4 — The typed dispatch language and the untyped operational language will drift apart as authors multiply
**Insight.** The executor dispatches on a *closed, typed* vocabulary
(`GateRecommendation = proceed|iterate|tiebreaker|escalate`, `OverrideAction`,
`EdgeKind`). But operational reality flows through an *open, untyped* vocabulary
(`phase_result["result"] == "context_exhausted"|"blocked"`, `error_kind` regex strings,
`halt_reason` literals like `"stalled"|"cost_cap"|"awaiting_user"|"max_iterations"`
invented ad-hoc in `executor.py` return dicts). These two vocabularies must stay in
correspondence, but nothing enforces it — `halt_reason` strings are minted at return sites,
not declared in `types.py`. When AI-authored pipelines and third-party tenants emit their own
result/error/halt strings, the gate's typed edges won't match them, and dispatch falls through
to `LookupError` *or*, worse, to a silent wrong edge. The memory note
`project_gate_tiebreaker_downgrade.md` ("Gate silently auto-downgrades TIEBREAKER→ITERATE when
schema fields missing") is this drift already biting once.
**Why invisible to us.** With one author (us) writing both the typed edges and the untyped
signals, we keep them in sync by hand and by memory. The contract is "in our heads," so it's
invisible that it isn't *in the type system*. It only breaks when an author who wasn't in the
room emits a signal — i.e. the moment AI-authoring or multi-tenancy turns on.
**What it threatens.** The "models emit pipelines; the runtime enforces invariants" thesis
directly — the runtime can only enforce invariants it can *name*, and half the operational
vocabulary is unnamed strings.
**Severity.** worth-designing-for (rising to reshapes-architecture once AI-authoring is live).

---

## The single biggest unnamed abstraction this vantage reveals

**The Work-Envelope (a.k.a. the Conserved Run Context): a single, typed, propagating
container that every unit of work is wrapped in and that rides every edge of every
composition — carrying identity + lineage(provenance) + taint + cost-ledger + deadline +
cancellation-token + error-class + retry-budget — and that the durable foundation treats as
the unit of transaction, journaling, and replay.**

Everything above is the *absence of this one thing*, seen from different seams:
- UU-1 is "the envelope has no carrier, so each fact rides a separate side-channel."
- UU-2 is "the envelope's deadline/cancel doesn't propagate into children."
- UU-3 is "the envelope isn't the transaction boundary, so stores tear apart."
- UU-4 is "half the envelope's fields are untyped strings, so authors can't honor them."

The vision already named *half* of this — `Port = type+version+provenance+taint` is the
**spatial / data-flow** half (the envelope on a value crossing a boundary). What is unnamed
is the **temporal / control-flow** half: the same conserved context riding a *unit of
execution* through dispatch, retry, cancellation, cost accrual, and the journal. Ports
govern what flows *between* pieces; the Work-Envelope governs what is conserved *through* a
piece and through a whole composed run. They are the two faces of one law:

> Nothing crosses a seam — spatial (Port) or temporal (Envelope) — naked.
> Type, provenance, taint, cost, and cancellation are conserved quantities; the runtime's
> job is to make them impossible to drop.

Concretely, this means: make `StepContext`/`StepResult` carry a typed `RunEnvelope` instead
of letting cost/error/lineage/cancel leak through `state.json` and `repr(exc)`; make the
envelope's cost-ledger and lineage *append on every edge traversal* (not be reconstructed by
phase-name rules); make the deadline/cancel-token thread into `ParallelStage` and
`SubloopStep` children; and make `Store.transaction()` open and close *on the envelope*, so
"durable + journaled + content-hashed + replayable" becomes a property of the *run*, not of
each store in isolation. Name it now, while there is one author, before AI-authoring and
multi-tenancy make every unnamed string a divergence we can't recall.
