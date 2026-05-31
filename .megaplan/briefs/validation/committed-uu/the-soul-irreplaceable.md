# The Soul: Keeping the PEV Harness + Cheapest-Capable Routing Irreplaceable

Vantage: the self-improving Plan-Execute-Verify harness + cheapest-capable-model
routing as the privileged HEART of Arnold. We are committed to building the full
vision. This brief asks only: what keeps the heart genuinely irreplaceable, what
is the compounding loop, and what bites if the heart erodes into just-another-module.

## What the code actually is today (ground truth)

I traced the live mechanics, not the aspiration:

- **Difficulty is judged once, by a model, at finalize.** `_validate_finalize_payload`
  (megaplan/handlers/finalize.py:264) hard-requires an integer `complexity` 1–5 plus a
  non-empty `complexity_justification` argued from concrete files/risk. Good: it forces
  adjudication. But the score is a *one-shot prediction* with no record of whether it was
  right.
- **Score → model is a STATIC table.** `tier_models.<phase>.<tier>` is read from TOML
  profiles (megaplan/profiles/__init__.py:34, 297) and routed per-batch by `max(complexity)`
  (megaplan/handlers/execute.py:110-154; megaplan/prompts/finalize.py:89). The mapping is
  hand-authored config.
- **"Cheapest-capable" is a HUMAN-MAINTAINED capability table.** `_CLAUDE_MODEL_TO_CODEX_SPEC`
  (megaplan/profiles/__init__.py:1195) hardcodes "sonnet ≈ gpt-5.4, opus ≈ gpt-5.5, haiku
  collapses to sonnet." A person decided these equivalences. Nothing measures them.
- **Receipts capture the raw materials but the loop is OPEN.** `Receipt`
  (megaplan/receipts/schema.py:11) records `model_configured`, `model_actual`, `cost_usd`,
  `verdict`. So we KNOW, per phase per run: which model ran, what it cost, and whether it
  passed. But NOTHING reads receipts back into routing or adjudication. I grepped: no
  `calibration`, no `priors`, no `did_survive`, no historical lookup in profiles/auto/execute/
  finalize. The flywheel's input data is being written to disk and never consumed.
- **No escalation-on-failure.** A blocked retry (`_is_blocked_retry`,
  megaplan/handlers/execute.py:72) re-runs the SAME tier. A cheap model that fails review is
  re-run on the same cheap model, not bumped up. The "did the cheap model survive review?"
  signal exists in the verdict but never changes the next routing decision.

So the "self-improving" heart is, today, a **statically-configured** heart with a perfect
audit trail it ignores. This is the crux of every finding below: the moat we think we have
(self-improvement) is latent, not realized — and the moat we actually have (the journaled
PEV substrate that makes the loop *possible*) is the thing we must protect as we open the
platform.

---

## UNKNOWN-UNKNOWNS

### UU-1. The calibration flywheel is open-loop, and closing it naively creates a self-reinforcing cheapness trap

**Insight.** Everyone (including us) describes the heart as "self-improving cheapest-capable
routing." The data says it's open-loop: receipts record the outcome of every (complexity,
model, verdict) triple and never feed back. The naive fix — "lower the tier for task-classes
where the cheap model survived review" — is a *positive feedback loop on a censored, biased
signal*. The reward (survived review) is only observed for tasks we actually routed cheap;
we never see the counterfactual ("would a cheaper model also have survived?"). Worse, the
reviewer is itself often a cheap-tier model, so "survived review" can mean "two cheap models
agreed," not "the work was good." A closed loop on this signal will *ratchet itself down* —
each generation routes cheaper, review standards drift cheaper with it, and quality erodes
invisibly because the metric (pass rate) stays green while the ground truth rots. This is the
classic bandit problem (no exploration → premature convergence) fused with reward hacking
(the verifier is in the same cost-optimization loop as the executor).

**Why invisible to us.** We have the audit trail and we trust it. The trap is precisely that
the trail will look *better* as quality degrades: cheaper routing + a co-degrading reviewer
yields rising pass rates and falling cost — the exact dashboard that says "the flywheel is
working." The failure is indistinguishable from success on the metrics we'd naturally build.
Memory note `project_complexity_adjudication.md` already shows we lean on "rater ≥ dispatchee"
as the guard — but that's a static rule, and cheap-finalize profiles already violate it. We're
guarding the symptom, not the loop dynamics.

**What it threatens.** The single most-claimed differentiator (self-improving routing).
If we ship a closed loop without explicit exploration budget, an out-of-loop ground-truth
oracle, and a reviewer that is *insulated* from the cost pressure on the executor, the
flagship capability silently converts into a quality-decay machine that is hardest to detect
exactly when it matters most (at scale, across many tenants whose work we can't eyeball).

**Severity: could-sink-the-build.**

---

### UU-2. "Capable" is undefined, untyped, and non-transferable — the routing index has no schema, so it can't generalize past megaplan's own task shapes

**Insight.** Today "capable" is encoded three ways, none of them a model the system can reason
over: a 1–5 integer whose meaning lives in a prompt rubric, a hand-keyed cross-vendor
equivalence tuple, and a TOML tier→spec map. There is no *first-class representation of a
capability claim*. When the platform opens and other tenants (and AI-authored pipelines) emit
their own pipelines, their tasks are NOT megaplan planning tasks — they're video renders, SQL
migrations, legal review, GPU kernels. The 1–5 rubric is implicitly "difficulty of a coding/
planning task as judged by Claude." It does not transfer. A tenant's "complexity 3" and our
"complexity 3" are different currencies, but they index into the *same* static `tier_models`
table. The routing heart cannot serve foreign topologies without a typed, per-domain,
calibrate-able notion of "what capability does this task demand, and which models have
demonstrated that capability *on this kind of task*." Right now capability is a scalar with no
domain dimension and no provenance.

**Why invisible to us.** Because megaplan is the flagship tenant and dogfood subject, every
calibration signal we have is megaplan-shaped. The routing table *appears* general (it's just
numbers and model names) but is silently overfit to one task distribution. We won't see the
gap until a second serious tenant routes garbage — and by then the table, the rubric prompts,
and a hundred profiles all assume the scalar.

**What it threatens.** The platform thesis itself: "others build new pipelines on the same
pieces, the heart routes them." If the heart can only route megaplan-shaped work well, the
heart is not a platform primitive — it's a megaplan feature wearing a platform costume. Every
new tenant either gets bad routing or has to fork the heart, which is exactly the "heart
erodes into just-another-module" failure the vantage warns about.

**Severity: reshapes-architecture.**

---

### UU-3. The model index churns underneath a frozen calibration; the half-life of "cheapest-capable" knowledge is weeks, but our learned signal accrues over months

**Insight.** The compounding loop's value comes from accumulating outcome data per
(task-class, model). But the model market re-shuffles every few weeks — new models, price
cuts, capability jumps, deprecations (the code already hardcodes gpt-5.4/5.5, haiku-4-5,
sonnet-4-6; these WILL move). The moment a new cheaper-capable model lands, our entire
hard-won calibration history is about a model that is no longer the right answer — and we have
zero observations on the newcomer, so a cold-start policy routes it nowhere, so we never learn
it's better, so we keep paying for the incumbent. The flywheel we're counting on to compound
is simultaneously the thing that *decays fastest*. Calibration data has a half-life; we're
treating it as an asset that only grows. There's no notion of capability *transfer* between
models (this new model is in the same family/size class as one we've calibrated, so seed its
priors) and no notion of *staleness decay* on old observations.

**Why invisible to us.** Within a single dogfooding window the model set is fixed, so the
problem never manifests in development. It only bites in production-over-time, and it bites as
a slow leak (we're routing to a stale-optimal model, paying 2x, and the dashboard shows
healthy pass rates) rather than a crash. The very durability/journaling we're proud of
(content-hashed, append-only) makes it *tempting* to treat the calibration corpus as
monotonically valuable, when it's actually a depreciating asset.

**What it threatens.** The economic moat. "Cheapest-capable" is only a moat if it tracks the
frontier in near-real-time. A flywheel that compounds slower than the market churns is a moat
that's always one generation behind — we'd be the platform that confidently routes you to last
quarter's cheapest model. It also threatens the cold-start onboarding of every new model,
which is the single highest-leverage routing decision (newest models are usually where the
price/capability arbitrage is largest).

**Severity: reshapes-architecture.**

---

### UU-4. Exposing the heart as a module severs the heart from its data, not just its code — and the data is the only irreplaceable part

**Insight.** The vision says open the platform but keep PEV+routing as the gravitational
center. The real erosion risk isn't that someone swaps the *code* (the algorithm is
copyable — escalation ladders and difficulty rubrics aren't secret). It's that opening the
platform fragments the *outcome corpus*. The moat is the cross-tenant, cross-domain dataset of
"this shaped task, routed to this model, at this cost, survived/failed this verifier" — a
dataset only WE sit downstream of because the PEV harness is the chokepoint every pipeline's
verify-step flows through. The instant a tenant runs PEV in an isolated workspace, or pipes
around the verify step, or runs the harness on their own keys with their own private receipts,
the chokepoint leaks and the corpus fragments. Per-tenant calibration silos are individually
too sparse to compound (UU-3's half-life problem times N). The irreplaceable asset requires
*aggregation across all tenants* — which collides head-on with the Port=type+version+
provenance+**taint** spine: if a tenant's data is tainted/private, it can't enter the shared
calibration corpus, so privacy-respecting tenants get worse routing, so they leave or silo,
so the corpus shrinks. The heart's irreplaceability and the platform's safe-composition spine
are in direct tension and nobody has named the trade.

**Why invisible to us.** We think of "keep the heart central" as an API-surface / dependency-
graph problem (don't let it become an optional plugin). The actual centrality that matters is
*data gravity*, and data gravity is invisible in code review — it's an emergent property of
where the verify-step receipts physically land and whether taint rules let them aggregate.
We're architecting the code coupling and ignoring the data coupling, which is the only one
that's irreplaceable.

**What it threatens.** The entire "data flywheel only WE can build" thesis. If receipts
fragment per-tenant (the natural outcome of multi-tenancy + taint + privacy), there is no
flywheel — there are N tiny puddles, each below the threshold to beat a static table. The
heart becomes just-another-module not because someone demoted it in the DAG, but because it
was quietly starved of the aggregate signal that made it special.

**Severity: could-sink-the-build.**

---

## THE UNNAMED ABSTRACTION

**The Calibration Ledger** — a first-class, content-hashed, append-only record of
*capability claims and their adjudicated outcomes*, treated as a primary platform object with
the same status as a Port.

Today we have receipts (an audit byproduct) and tier_models (static config). What we've never
named is the object that *closes the loop and makes the heart irreplaceable*: a typed entry of
the form

  `CapabilityClaim{ task-signature (typed, domain-tagged, provenance), predicted-tier,
  routed-model, verifier-identity-and-tier, verdict, cost, counterfactual-tag, observation-timestamp }`

with three operations the platform must support as primitives:

1. **Decay & churn** — observations age out; a new model's claims are seeded from a typed
   capability-class prior, not cold (answers UU-3).
2. **Exploration budget** — a fraction of routing is deliberately off-policy to keep the
   ledger un-censored and the loop from ratcheting (answers UU-1), with the verifier's
   identity recorded so a cost-pressured reviewer can't be trusted as ground truth.
3. **Taint-aware aggregation** — the Port taint/provenance spine governs which claims can
   enter the *shared* ledger vs. stay tenant-local, making the privacy↔flywheel trade-off
   explicit and tunable rather than emergent (answers UU-4).

The 1–5 difficulty score, the cross-vendor equivalence table, and tier_models all become
*projections of the Ledger* rather than hand-authored constants. Routing stops being "read the
TOML" and becomes "query the Ledger for the cheapest model whose typed capability claims for
this task-signature survived an insulated verifier, within an exploration budget." That is the
object that makes the heart self-improving in fact rather than in slogan, that lets it route
foreign tenant topologies (typed task-signatures, not a megaplan-shaped scalar), and that
turns the journaled foundation from an audit trail into the one asset a competitor cannot copy
because they don't sit on the cross-tenant verify-step chokepoint. Name it, make it a Port-
peer primitive, and build the heart as the Ledger's query engine — that is how the heart stays
the gravitational center while everything else opens.
