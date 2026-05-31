# Interrogation — Cross-cutting concerns (adversarial)

**Lens:** concerns that span ALL pieces and resist being "a piece": error handling & retries,
observability OF a composition (not just emit), cost/budget across composed pieces, security/sandbox,
config precedence, versioning, testing. **Posture:** full ambition is assumed and non-negotiable. Findings
say what the plan must ADD / re-sequence / abstract differently — never what to cut.

Grounded against `main` 2026-05-29. Read: EPIC; m1/m3/m4/m5/m6 briefs; confidence a2, a5, d1, d3, d4, SYNTHESIS.

---

## The shape of the problem

The EPIC's "interfaces-with-backends" discipline is the right answer for the *vertical* pieces —
dispatch, state, emit, evidence, config each become an interface + N backends. But every concern in my
lens is **horizontal**: it has to be coherent *across* a composition of those pieces, at the point where
the driver walks them. The plan repeatedly assigns a horizontal concern to whichever vertical piece it
most resembles, then declares it owned. It is not owned — it is **smeared**, because the thing that
actually sequences the pieces (the driver) is the only place these concerns can cohere, and the plan
gives the driver tier almost no horizontal responsibility.

Concretely: M3 builds the `loop`/`process` drivers as *mechanism* (iteration count, OS isolation), M4
builds services with backends, M5 extracts features. **No milestone owns "what a driver guarantees about
errors, retries, budget, observability, and config-resolution to every piece it composes."** Today that
guarantee exists — it lives, undecomposed, in `auto.py`. The plan extracts the *parts* of `auto.py`
(its subprocess loop → `process` driver in M3; its features → M5) but never extracts `auto.py`'s
**cross-cutting policy spine**, and never names where it lands. That spine is the single weakest story.

---

## TOP BITES

### BITE 1 — Error/retry/recovery is a planning-shaped taxonomy with no SDK home (CRITICAL)

`auto.py` is not just "planning's subprocess loop" (the thing M3 extracts as the `process` driver). It is
the **recovery state machine** for the whole run. Verified on `main`:

- `ExitKind` enum (`auto.py:92`) and the 14-value `status` taxonomy (`auto.py:135`): `context_exhausted`,
  `context_retry_exhausted`, `worker_blocked`, `cost_cap_exceeded`, `escalated`, `stalled`, `cap`, …
- **Three independent retry loops** with distinct caps and counters:
  context-exhaustion retry (`context_retry_count`, `auto.py:1099,1777-1819` — re-dispatches `--fresh`),
  targeted external/transient retry (`external_retry_count` + per-phase `external_retry_counts_by_phase`,
  `auto.py:1100-1101,1824+`, gated by `_is_retryable_external_error`, `auto.py:196`), and
  blocked-task retry (`blocked_retry_count` / `max_blocked_retries`, `auto.py:1102,149`).
- The retry/recovery vocabulary appears **65 times** in `auto.py` (grep `ExitKind|_retry_count|_retries_used|halt_reason|exit_kind`).
- The `RuntimePolicy` path (`executor.py:343`) has exactly ONE recovery primitive — `max_iterations`. M1
  is *explicitly forbidden* from adding even a max-iteration cap to the bare `run_pipeline` path
  (m1 Open-questions L90-91, anti-scope L125). So today bare `run_pipeline` has NO retry story at all,
  and the rich story lives only in the planning supervisor.

**Why it bites the full ambition:** a fourth, non-planning tool (acceptance #1 — the bisect/tournament/
search) WILL hit transient provider errors, context exhaustion, and stuck units. With the plan as
written it has three bad options: (a) reach into the planning binding's retry logic (planning privilege
the EPIC forbids), (b) reinvent its own retry loop (the exact "builder reinvents dispatch" symptom the
SDK exists to cure — EPIC L22-23), or (c) get none. M3's `loop` driver brief has a `finally`/teardown
hook and a `max_iterations` cap but **says nothing about retry classification, retry budgets, or
error→consequence mapping**; M3 even reuses the *idea* of containment for the `process` driver while
leaving the *retry policy that decides what to do with a contained failure* in `auto.py`.

**What it forces (add, don't cut):** a milestone must extract `auto.py`'s recovery spine into a
**driver-level error/retry policy piece** — an injected `RecoveryPolicy` (classify(error)→{retry_fresh,
retry_transient, escalate, halt(kind)} + per-class budgets) that ALL drivers (graph/loop/process) consult
on a step failure, with the 14 `ExitKind`s split into SDK-general outcomes vs planning-named bindings (the
M2 4-verdict move is the exact precedent — do the same for exit/halt taxonomy). This is currently nobody's
job across M1-M6 and is the single biggest missing abstraction. Sequence it with M3 (drivers are where it
must live) — M3 cannot honestly claim a "real loop/process driver" while the retry policy stays in `auto.py`.

### BITE 2 — Observability OF a composition is unowned; emit is conflated with trace (HIGH)

The plan's entire observability story is `emit` (M4 Outcome 2): one verb, two backends, pinned envelope
(d3). That is **event *transport***, not **composition *observability***. The questions a builder of a
fourth tool will ask — "which piece is my run stuck in? how many retries has step K burned? what did the
driver decide at the last gate and why? what's the live cost trajectory of THIS composition?" — are today
answered by `introspect.py`, `doctor.py`, `trace.py`, and `workflow_next`, all of which **reconstruct
run-shape by reading `plan_dir/events.ndjson` + `state.json` and hardcoding planning payload field names**
(d3 §1-2: `trace.py:176-282`, `cost.py:100-128` read `payload.model`/`cost_usd`/phase). They are planning
introspectors wearing an observability hat.

M4 pins the *envelope* (`schema_version`, per-kind payload models — d3 §4) — good, necessary, not
sufficient. It does **not** define what a driver must emit so that a *generic* introspector can narrate ANY
composition: step-enter/exit, decision-with-rationale, retry-with-class, budget-deltas, piece-identity. d3
itself flags the deeper rot — **two parallel event systems** (`events.ndjson` vs Store `EpicEvent`) with
**colliding kind names** (`phase_start` exists in both with different payloads, d3 §3) and **no bridge**.
M4 explicitly decides to keep them separate ("opaque scope token, separate taxonomies", brief L28, L38).
That is defensible for transport but means **observability-of-a-composition has no single surface** — a
fourth tool on the Store backend and planning on the ndjson backend produce un-unifiable trace/cost views,
and `introspect`/`doctor`/`trace`/`cost` (the actual observability tools) are hardwired to ndjson + planning
payloads and will simply not work for the fourth tool.

**What it forces:** name a **composition-observability contract** owned by the driver tier — a small set of
driver-emitted structured events (step boundary, decision+rationale, retry+class, budget delta) that BOTH
emit backends carry and that a *backend-agnostic* introspector consumes. Re-home `introspect`/`doctor`/
`trace`/`cost` onto that contract (M4 or M5), or the acceptance-test fourth tool ships blind. The d3 "two
systems, document the split" decision is fine for `emit`; it is a hole for *observability*, which the plan
never separates from `emit`.

### BITE 3 — Cost/budget is two disconnected mechanisms that never compose into one cap (HIGH)

The plan has **two** money concerns and treats them as unrelated:
- M4/d1: cost *attribution* — make non-plan dispatch's cost not vanish (tenant journal when `plan_dir is
  None`, d1 §2; `cost` CLI fallback, d1 §3). This is accounting, post-hoc.
- M3: a typed depletable **`budget`** the loop predicate reads (m3 Scope, L32, L66) — explicitly scoped as
  "a per-run loop resource, NOT a cross-tenant quota broker" (m3 Constraints L114-116).

Nothing connects them, and a third actor — `CostTracker` (`_pipeline/runtime.py:~70`), the live spend cap —
reads only `state["meta"]["total_cost_usd"]` (plan-dir-scoped, d1 §13). So across a composition you have:
M3 budget (per-run, in-process, loop-local), the CostTracker cap (plan-dir state, planning-only), and the
M4 tenant cost journal (post-hoc accounting). **A composition that fans out (M5 F2) across a `process`-driver
(M3) while a CostTracker cap is set has THREE different ledgers and no single authority that can stop spend
when the *whole composition* exceeds budget.** M3 itself flags the hole and defers it: "a shared depletable
budget cannot accumulate across sibling shards without a fold channel … M3 ships budget as a single-tenant
loop resource … Flag, don't solve here" (m3 Open-questions L93-97). M4 open-question 3 (L47) flags the same
thing from the other side: "Confirm the `CostTracker` cap … must see both plan and non-plan spend for caps
to hold." Both briefs point at the gap and both punt it to the other.

**What it forces:** a **budget/cost as one cross-cutting capability** with a single live authority that the
driver consults *before* dispatching a step (not a post-hoc journal): one ledger that (a) M3's loop predicate
reads, (b) the CostTracker cap enforces, (c) the M4 attribution journal records, (d) folds across fan-out
shards (the M3-deferred fold channel). Assign it an owner milestone (it spans M3+M4+M5-F2; right now it spans
them with no owner). The a2 `key_broker`/`rate_broker` (M4 Scope 1, L26) is the natural sibling home — rate
and spend are the same "shared depletable resource across concurrent pieces" problem, and the plan already
gives rate a cross-process flock'd ledger but gives spend three uncoordinated in-process counters.

### BITE 4 — Config precedence is asserted, not designed; "config base" hides a 4+ -layer overlay (HIGH)

M4 Outcome 4 / Scope 4 says "`config` is a base a package extends" and re-expresses planning's args bus
(`argparse.Namespace`) and resident's `ResidentConfig` as bindings over one base (brief L15, L33). This
quietly assumes config is a *type* problem (share a spine, extend per package). It is actually a
**precedence** problem, and the plan never states the precedence rule. On `main` the effective value of a
setting is resolved by `get_effective(section, key)` (`_core/io.py:764`) over exactly TWO layers:
`DEFAULTS` ← user `load_config()`. But the *running* value a piece sees is layered over at least FOUR more
surfaces that `get_effective` does NOT compose:
- profile presets (`profiles/__init__.py`, `tier_models`, `apply_profile_expansion`),
- robustness presets (M5 F6 / EPIC reshape-graph-by-config),
- the args bus (`argparse.Namespace`, `handlers/execute.py:45,96`),
- `state.config` written at runtime by the override plane (`set-robustness`/`set-profile`/`set-model`
  mutate `state.config` to take effect next phase — M5 F7, `override.py`),
- and `setting_is_explicit` (`io.py:777`) exists *precisely because* one layer (profile default) must only
  win when the user hasn't pinned a value — i.e. precedence is already subtle and already only half-handled.

**Why it bites:** when planning becomes "a module like any other" (M6) and a fourth tool composes the same
pieces, every piece will read config, and there is **no single documented precedence order** that says
env > args > state.config(override) > profile > robustness > DEFAULTS (or whatever it is). M5 F7's override
plane *mutates config at runtime* and M5 F4's tiering *reads* config — if precedence isn't owned by the
`config` piece, each piece re-derives "who wins" and they will disagree (this is already a live bug class:
memory `project_gate_tiebreaker_downgrade` is a config/state-field-missing silent downgrade). M4's "share a
spine, extend per package" is a *typing* decoupling; it does nothing for precedence.

**What it forces:** the M4 `config` piece must own a **declared, tested precedence chain** (a single resolver
all pieces call, generalizing `get_effective` + `setting_is_explicit` to N layers with explicit order), and
M5 F7's runtime mutation must write *through* that resolver's layer model, not blind-poke `state.config`.
Add a precedence characterization test (the d4 CI marker-switch makes it enforceable). Without this, config
is the most-smeared concern in the system.

---

## VERSIONING (secondary, but under-owned)

The plan pins exactly two contracts: state `schema_version` (M1 W3, `extra="ignore"` + fixture corpus) and
the event envelope `schema_version` (M4, d3). Good. But the EPIC's whole premise is **external packages
discovered like jokes/doc** (M6) composing SDK pieces. There is **no version contract on the piece
interfaces themselves** — the `Dispatcher` protocol, `EventSink.emit` signature, the node-library macro
signatures (M5 F9 "stable signature"), the package manifest. M6 makes `SKILL.md` required and drops
`_BUILTIN_NAMES`, but nothing says what happens when an external package built against `Dispatcher` v1 meets
an SDK that shipped `Dispatcher` v2. For an SDK whose success metric is "a third builder ships a fourth
thing," **interface/manifest versioning is a first-class concern with no owner.** Add a manifest
`requires_sdk`/`api_version` field + a discovery-time compat check (natural home: M6's discovery-integrity
guard, which M1 W5 already scaffolds for loud failure).

## TESTING (cross-cutting, partially owned)

d4 + M1 W1 fix the *enforcement* gap (4/50 files → `pytest -m "not slow"`) — genuinely high-ROI, correctly
sequenced first. The remaining cross-cutting test hole: **the parity gate proves planning didn't regress; it
proves nothing about the fourth tool.** Every milestone's done-criteria leans on "the non-planning acceptance
package" (M2 select-tournament, M3 solver/bisect, M4 oracle caller, M5 F2/F8, M6 fourth tool) but these are
described as *separate* toys per milestone. There is no **single, evolving conformance suite** a piece must
pass to claim "backend N satisfies interface X" — M4 says "shared contract test" for Dispatcher (done-crit 1)
but not for emit/evidence/config, and the per-milestone toys aren't required to be the *same* tool growing.
Add a **piece-conformance test matrix** (every interface × every backend × the cross-cutting guarantees:
retry, sandbox-fail-closed, cost-attribution, observability-emit) as a standing suite, not N disposable toys.

---

## SYNTHESIS NOTE (honest tension, not a scope cut)

The confidence SYNTHESIS argues the real second tool (resident) shares only the Store, so the shared-dispatch
cross-cutting risks (a2/a4/d1) "only arise if we build the shared service." Under the fixed full ambition we
ARE building it (M4) and standing up a deliberately-divergent fourth tool (acceptance #1) that exercises it.
So those risks are not conditional — they are **on the critical path the moment M4 ships**, and the four bites
above are exactly the cross-cutting stories that must exist *before* the fourth tool can be honest proof
rather than a toy that quietly reaches back into planning for its error/budget/observability/config behavior.
