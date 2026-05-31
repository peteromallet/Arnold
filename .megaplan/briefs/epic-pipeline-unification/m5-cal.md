# M5-cal — Calibration Ledger: CapabilityClaims + decay/exploration; routing = a query

**Epic:** Pipeline Unification (`.megaplan/briefs/pipeline-unification-EPIC.md` §M5-cal + "The architecture" Calibration Ledger L39–40; `committed-uu/SYNTHESIS.md` Calibration Ledger L275–284, Tier-S UU#2/#10, Tier-A UU#7/#11/#12, design principles #6/#7/#13/#14). **Position (PROGRAM.md L242–253):** M5-eval (versioned attributable judgments — the ruler) → **M5-cal [T2]** → M5c. **Tier/robustness:** premium · thorough/high. **Depends_on:** **M5-eval** (a CapabilityClaim's outcome IS an Evaluand — no routing query before the versioned ruler exists; PROGRAM L250, the single most order-sensitive edge in the program L240/L437–441), M4 (the one Ledger + dispatches that already route; the Calibration record lands in the one Ledger), M3 (reads the taint lattice on the Envelope), R7 (keyed on hash-pinned model-identity, seeded at M1 `cost.py`). **Code verified against `main` 2026-05-29.**

> **What this milestone is.** Today routing is a TOML read: a profile expansion produces `metadata["tier_models"]` (`profiles/__init__.py:34,119–138`), a finalize step adjudicates an integer `complexity` in 1..5 against a rubric (`handlers/finalize.py:264–268`, defaulting out-of-range to tier 4, `:582–586`), and `batch.py:79–98` resolves `tier_models.execute.<tier>` → agent/model with no record read back. The (complexity, model, verdict, cost) receipts that DO get written (`_pipeline/receipt.py:105–110`, `cost.py:100–118` `COST_RECORDED`) are **never read back** to inform the next route (SYNTHESIS UU#10). M5-cal makes the Calibration Ledger the authority: a content-hashed, append-only record of **CapabilityClaims + adjudicated outcomes**, with the three primitives the soul-lens demands — **DECAY/CHURN**, **EXPLORATION BUDGET**, **TAINT-AWARE AGGREGATION** — so that the 1–5 score and `tier_models` become **projections of the Ledger** and **routing becomes a query, not a TOML read**.

---

## Outcome

A first-class, content-hashed, append-only **Calibration Ledger** of CapabilityClaims `{typed domain-tagged task-signature, predicted-tier, routed-model (hash-pinned identity / R7), verifier-identity-and-tier, verdict (an Evaluand ref, NEVER a bare float), cost, counterfactual-tag, taint-class, timestamp}` recorded into the M4 one Ledger, with: (1) **routing as a query** over the Ledger that, behind a default-OFF flag, supplies the tier→model decision `batch.py` currently reads from TOML — the old TOML path stays default-ON; (2) **decay/churn** so observations age and a new model seeds from a **capability-class prior** rather than cold-start; (3) an **exploration budget** — a deliberate off-policy routing fraction that keeps the signal un-censored and forbids the loop ratcheting, with the **cost-pressured reviewer never trusted as ground truth**; (4) **taint-aware aggregation** — the M3 Envelope's taint lattice governs which claims enter the SHARED ledger vs stay tenant-local, making the privacy↔flywheel trade an explicit, tunable knob. The 1–5 score and the cross-vendor equivalence become projections; the projection is asserted byte-equivalent to today's TOML resolution under the parity gate before the query path is ever trusted, and the calibration-loop oracle (replay a recorded routing trace and prove the closed loop cannot drive ground-truth down while the dashboard reads green) is the sole retirement authority for the TOML path — which is **not** retired in this milestone.

## Scope (work items tied to current file:line)

1. **CapabilityClaim record + write path into the one Ledger.** New record `CapabilityClaim{task_signature (typed, domain-tagged), predicted_tier:int, routed_model:ModelIdentity, verifier_identity, verifier_tier, outcome:EvaluandRef, cost, counterfactual_tag, taint_class, recorded_at}`. **The `outcome:EvaluandRef` references M5-eval's FULL attributable, taint-bearing Evaluand record `{piece-version, judge-version, rubric-version, input-set-hash, score, provenance, taint, recorded_at}` (m5-eval.md Outcome #2 / Scope #2 / Done #2) — NOT M4's thinner `{judge-version, rubric-version, input-set-hash, score}` scaffold.** This is the single taint source: M5-cal's taint-aware aggregation (Scope #6) reads the `taint` field that ONLY the M5-eval attributable record carries (the M4 scaffold has no taint field). The outcome is **never a bare float** — enforced by a type assertion + grep gate. Write on every adjudicated dispatch via the M4 `EventSink.emit` one-log path (m4 §7, R5), keyed by the R7 hash-pinned `model_identity` seeded into `COST_RECORDED` at M1 (`cost.py:100–118`). New module `megaplan/calibration/ledger.py`.

2. **Routing as a query (new path, default-OFF).** `route(task_signature, taint_class, budget) -> (tier, model)` reading the Ledger projection. Wired BEHIND a default-OFF flag beside the live TOML resolution at the two routing sites: finalize tier-adjudication (`handlers/finalize.py:264–268`) and per-batch tier→model (`execute/batch.py:79–98`, `_resolve_tier_spec`). Old path stays default-ON; the new path only reads — it never rewrites the TOML.

3. **Projection: 1–5 score + `tier_models` as views.** A `project_tier_models()` that reconstructs the `metadata["tier_models"]` shape (`profiles/__init__.py:119–138`) and the 1–5 complexity score (`finalize.py:264`) as deterministic folds over the Ledger. Parity-gated byte-equivalent to the current TOML read for the seeded single-tenant corpus.

4. **DECAY/CHURN.** Observations carry an age; a freshness-decay weight down-weights stale claims (SYNTHESIS UU#10 — "calibration data has a half-life"). A **capability-class prior**: an unseen `model_identity` seeds from the prior of its declared capability class (a class table, reserve-then-fill), NOT cold-start, so churn (the market reshuffles every few weeks) does not zero the flywheel.

5. **EXPLORATION BUDGET (anti-ratchet, anti-Goodhart).** A configurable off-policy fraction `exploration_budget` (default 0.0 in this milestone's seeded path — the field + mechanism land, the value is opt-in) deliberately routes off the greedy cheapest-capable choice so the loop keeps a counterfactual for tasks it would otherwise never route cheap (SYNTHESIS UU#10, principle #6). The **cost-pressured reviewer is never trusted as ground truth**: a claim whose verifier_tier < routed_model tier is recorded with a `low_confidence_signal` flag and is *excluded from* the shared aggregation that closes the loop (the co-degradation guard, UU#10).

6. **TAINT-AWARE AGGREGATION.** The claim's taint travels with its `outcome:EvaluandRef` — the `taint` field on M5-eval's attributable Evaluand record (Scope #1), which M5-eval rode off the M3 Conveyance Envelope (m5-eval.md Scope #2). **One taint source: the M5-eval Evaluand, not a re-read of the M3 Envelope.** A claim's `taint_class` (derived from that Evaluand `taint`) decides SHARED-ledger vs tenant-local: tainted/private claims stay tenant-local and never enter the cross-tenant corpus (UU#11). The privacy↔flywheel trade is an explicit tunable `aggregation_policy` knob (default: in-tree single-tenant = shared; out-of-tree = tenant-local), not an emergent shatter.

7. **Sensors → gated experiments.** The M1 sensors (per-phase prefix-cache-hit-rate + monoculture index, `cost.py` aggregate, recorded-no-consumer per m1 W10 L109–116) become the inputs to two **gated experiments** (not live policy): the cheapest-routing-vs-prompt-caching tension (UU#12) and the monoculture/co-degradation attractor (UU#7/#10). Each is a recorded experiment over the Ledger, governing nothing in this milestone.

8. **Grep gate + binder.** Mirror the M2 `GateRecommendation` / M5b `_PHASE_OUTCOMES` gates: a CI grep proving the Calibration Ledger NEVER stores a bare float as an outcome (every outcome resolves to an EvaluandRef) and the routing query NEVER imports planning's `STATE_*` / `GateRecommendation`. Red auto-halts.

## Locked decisions

- **Routing is a query over the Ledger; the 1–5 score and `tier_models` are projections** (EPIC L39–40, L242). Not a refactor of TOML — a re-homing of the authority, TOML retained as default-ON old path.
- **An outcome is an Evaluand ref, never a bare float** (SYNTHESIS principle #7; the M5-eval→M5-cal edge is non-negotiable, PROGRAM L240/L437–441). Calibrating against bare floats is the Goodhart/co-degradation failure — forbidden by the grep gate.
- **The optimizer and the evaluator do not share machinery** (principle #6): the exploration budget keeps an un-censored counterfactual and the cost-pressured reviewer is excluded from ground-truth aggregation.
- **New models seed from a capability-class prior, not cold-start** (SYNTHESIS L280); decay gives claims a half-life.
- **Taint governs shared-vs-tenant-local** via an explicit `aggregation_policy` knob (SYNTHESIS L282, UU#11) — the privacy↔flywheel trade is tunable, never emergent.
- **Strangler:** the query path lands default-OFF beside the default-ON TOML read; no TOML-path deletion in this PR; the calibration-loop oracle (not the happy-path parity gate) is the sole retirement authority (PROGRAM L361–389).

## Open questions (each RESOLVED to its default)

- **Where does the Ledger physically live?** → DEFAULT: in the M4 one Ledger via `EventSink.emit` (R5, m4 §7), a new event kind `CAPABILITY_CLAIM`; no new store backend. Reversible.
- **Capability-class prior table — built or reserved?** → DEFAULT: reserve the class table + the prior-lookup hook now, fill from the seeded single-tenant corpus; an unseen class falls back to the conservative tier (tier 4, matching `finalize.py:582` out-of-range default). Mirrors M4's reserve-don't-partition stance (REGISTER M4 "per-tenant sub-budget → reserve").
- **Exploration budget default value?** → DEFAULT: 0.0 in the seeded path (mechanism + field land; non-zero is opt-in config) — a non-zero default would spend real money off-policy before a second tenant exists; the field's PRESENCE is the un-retrofittable seed (principle, "seed cheaply now").
- **Decay function shape?** → DEFAULT: a single configurable half-life weight (one parameter), not a per-class curve; upgrade only if an experiment needs it.
- **Does routing-as-query replace finalize's adjudication or wrap it?** → DEFAULT: WRAP — the query supplies a *suggestion* the finalize rubric still adjudicates against; the projection must reproduce finalize's 1..5 byte-for-byte under parity (REGISTER pattern: projection proven before authority).
- **`aggregation_policy` default?** → DEFAULT: in-tree single-tenant = SHARED, out-of-tree = TENANT-LOCAL (path-derived, matching the M6 trust-tier classifier, REGISTER §"Trust-tier default policy").
- **Cost-pressured-reviewer threshold?** → DEFAULT: verifier_tier < routed_model tier ⇒ `low_confidence_signal`, excluded from shared aggregation (the rater≥dispatchee invariant, `audits/critique_evaluator.py`; carries the M5b cheap-finalize KNOWN GAP forward as a recorded flag, not a stop). All `must_ask_peter = false`.

## Constraints

- **Order:** must not start before M5-eval is green (the versioned ruler must exist — PROGRAM L250). Gate the start on M5-eval's CI being green (REGISTER X3: dependency readiness = test result, no human scheduler).
- **Strangler liveness (every-milestone, PROGRAM L361–389):** OLD engine still self-hosts the build on the pinned/frozen external venv, schema report-only, flag-OFF; a planning-shaped throwaway runs on the new query path behind the default-OFF flag.
- **No bare floats** as outcomes anywhere in the Ledger (grep-gated).
- **The query NEVER rewrites TOML** and governs nothing live in this milestone (default-OFF).
- **Back-compat:** `tier_models` profile shape (`profiles/__init__.py:34,119–138`) and `complexity` 1..5 (`finalize.py:264`) remain valid and authoritative on the old path; the projection is additive.
- **Autonomy:** red on any gate auto-halts+reverts or runs the bounded escalation ladder (retry ×2 → bump profile/robustness one tier → `stop_chain` + auto-ticket), never parks on a human (REGISTER §1, §4).

## Done criteria (testable, incl. the milestone's oracle gate)

1. A CapabilityClaim round-trips through the M4 one Ledger as a content-hashed record whose outcome is an EvaluandRef (a join over judge×rubric×input-set), **never a bare float** — asserted by a unit test + the grep gate (item 8).
2. **THE M5-CAL ORACLE GATE (the calibration-loop oracle, sole retirement authority):** replay a recorded routing+verdict trace through the closed loop and prove the loop **cannot ratchet ground-truth down while the dashboard reads green** — i.e. with the exploration budget engaged and the cost-pressured reviewer excluded, a synthetic co-degradation scenario (cheap reviewer rubber-stamps a cheap model) is DETECTED, not absorbed as "passed review" (SYNTHESIS UU#10). Red = halt; this gate, NOT the happy-path parity gate, authorizes any future TOML retirement.
3. **Projection parity:** `project_tier_models()` and the projected 1..5 score reproduce the current TOML resolution (`profiles/__init__.py` / `finalize.py:264`) byte-for-byte for the seeded corpus (parity gate, honestly labelled "happy-path projection equivalence, not drift-provably-zero").
4. **Decay/churn:** an unseen `model_identity` resolves via its capability-class prior (not cold-start); a stale claim is down-weighted by the half-life — both unit-asserted.
5. **Exploration budget:** with `exploration_budget>0` a measurable off-policy fraction is routed and recorded with a counterfactual tag; the cost-pressured reviewer claim is flagged `low_confidence_signal` and excluded from shared aggregation — asserted.
6. **Taint-aware aggregation:** a tainted claim (M3 Envelope taint lattice) stays tenant-local and never enters the shared corpus; an untainted in-tree claim is shared — asserted under both `aggregation_policy` settings.
7. **Routing-as-query default-OFF:** flag OFF ⇒ the TOML path drives unchanged (characterization parity on a real run); flag ON ⇒ the query supplies the route and the projection matches.
8. Grep gate green (no bare-float outcome, no `STATE_*`/`GateRecommendation` in the calibration module); strangler liveness green; M5-eval-green start-gate enforced.

## Touchpoints

- `megaplan/calibration/ledger.py` (NEW — record, write path, query, projections, decay, exploration, aggregation).
- `megaplan/observability/cost.py:23,71–118` — R7 `model_identity` source (seeded M1); the sensors (prefix-cache-hit-rate, monoculture index) feeding the gated experiments; the NEW path stops reading the substring `_classify_vendor` once the Ledger is the source (report-only here; the OLD read stays live, retired with R5 at M6 per m4 §7).
- `megaplan/handlers/finalize.py:264–268,559–608` — tier adjudication wrap site (projection parity; query suggestion).
- `megaplan/execute/batch.py:79–98` (`_resolve_tier_spec`) — per-batch tier→model query site (default-OFF).
- `megaplan/profiles/__init__.py:34,119–138` — `tier_models` shape the projection reproduces.
- `megaplan/_pipeline/receipt.py:105–110` — verdict/outcome receipt the CapabilityClaim references.
- M4 one Ledger `EventSink.emit` / `store/_db/events.py`, `store/base.py:261,447` (transaction boundary) — the write path.
- M3 Envelope taint lattice — read for `taint_class`.

## Anti-scope

- **No retirement of the TOML `tier_models` path** — it stays default-ON; only the calibration-loop oracle (not this milestone) may authorize that, and never in an organ-swap-plus-deletion PR (PROGRAM L374–379).
- **No live closed-loop self-improvement** — the loop is recorded, gated, and exploration defaults to 0.0; turning the ratchet on is downstream, deliberately fenced.
- **No multi-tenant partitioning build** — `aggregation_policy` is a knob + tenant-local-vs-shared decision; the per-tenant partitioning is reserved, not built (matches M4's reserve stance).
- **No new store backend** — records ride the M4 one Ledger.
- **No model-market churn ingestion / live capability-class population** beyond the seeded single-tenant corpus — the prior table is reserve-then-fill.
- **Not the eval ruler itself** — that is M5-eval (the hard prerequisite); M5-cal only *consumes* its versioned judgments.
- **Not the Warrant/account unit** (UU#16, M7-warrant) — calibration outcomes are not yet a durable unit of account here.
