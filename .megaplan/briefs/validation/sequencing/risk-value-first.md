# Arnold build sequence — RISK-AND-VALUE-FIRST ordering

**Author:** principal-architect sequencing pass (one of three independent orderings to be reconciled).
**Date:** 2026-05-29.
**Lens:** front-load the highest-uncertainty / most-likely-to-invalidate pieces so we fail fast, and make
every milestone deliver a *provable* increment (a demoable capability + its machine gate), not plumbing.
**Architecture:** SETTLED (11 organs, 7 reshapers, `committed-uu/SYNTHESIS.md`). This document does NOT
relitigate it; it sequences it.

---

## 0. The reframe this lens forces on the inherited m1..m7 program

The inherited briefs (`epic-pipeline-unification/m1..m7`) sequence a **plumbing extraction**: hygiene →
de-planning the verdict types → drivers → services → node-lib → execute → control plane → relocate
planning → docs. The event-sourced foundation (Reshaper #1) is *implicit and late* — it lives as a
"separate backend behind the interface, scaffolded with no real backend in M3" (EPIC M3 resolution) and the
Activation primitive is named but never load-bearingly proven. The committed-UU synthesis is blunt about
why that order is dangerous: **"We will believe the 'foundation pillar' is in progress when the actual
event-sourced substrate has never been built"** (UU#6), and **"building [the reshapers] last means
re-touching every edge, every cache entry, every receipt, and silently corrupting in-flight runs."**

Under a risk-and-value-first lens the dependency skeleton **inverts**: the order is no longer "extract the
easy decoupling first, build the hard foundation behind a flag last." It is **"prove the load-bearing,
most-invalidating reshaper alive under a real workload as early as the strangler permits, and let the
hygiene/decoupling work be sequenced for exactly what it unblocks."** Three reshapers carry essentially all
the invalidation risk; everything else is comparatively de-risked engineering:

- **Reshaper #1 — state = deterministic fold over an append-only, effect-typed, taint-carrying log.**
  Everything stands on it. If the fold cannot reproduce a real multi-day planning run, the architecture is
  wrong and we want to know in week 2, not month 4.
- **The Activation primitive (Reshaper #2)** — if "pluggable readiness rule + lifecycle" cannot host
  DAG **and** loop **and** standing **and** market as ONE field, then the whole "not a DAG-walker" thesis
  is false and we are back to a switch-statement mush.
- **Two physics tensions that no amount of clean code dissolves**: self-improvement-vs-durable-replay
  (UU#1, Tier S) and cheapest-routing-vs-prompt-caching (UU#12). These are not built; they are *measured
  and designed-against*, and the measurement instruments must exist before the regime that needs them.

So the question "what's the riskiest thing we'd want dead-or-alive by milestone 2?" has a precise answer:
**the event-sourced fold replaying a real, multi-phase planning run byte-faithfully, with the Activation
record as its event grain, while the OLD engine still drives the live epic.** If that is green at M2, the
foundation is real; if it is red, we have failed cheap and re-aimed before spending apex budget on
services, node libraries, and a control plane built atop a substrate that doesn't hold.

---

## 1. What proving a hard assumption early does to the skeleton

Three reorderings fall out, each justified by an invalidation risk:

1. **The event-sourced fold + Activation record move from "scaffolded behind a flag in M3" to the
   FIRST real build after hygiene (M2 here).** Rationale: it is Reshaper #1; it is the substrate every
   later organ records into; and it is the single thing the committed-UU swarm says is most likely to be
   *believed-done-while-never-built*. We refuse that failure mode by making M2's gate a **replay oracle**:
   fold(events) of a recorded real planning run == the run's actual state.json, and resume = re-fold. This
   is the inherited p3/B4 "swap-detecting oracle" promoted from a side-gate to the milestone's reason to
   exist. The inherited M2 ("de-planning the verdict enum") is *demoted* to a prerequisite slice folded
   into M1/M2 — it is real and necessary (it unblocks generic `reduce`/`select` and the Port), but it
   carries near-zero architecture-invalidation risk and must not sit on the critical path as if it did.

2. **The Governor + Capacity-Lease (Reshaper #4) moves EARLIER than its inherited M4 position — to
   immediately after the fold is real and before any concurrent/emergent activation is allowed to fire.**
   Rationale: the committed-UU pair "the data model's unsoundness is invisible exactly as long as
   concurrency is banned, and concurrency is banned exactly because the data model is unsound" (UU#6).
   The moment M2 makes the log authoritative, the *reason* to ban concurrency dissolves — and the moment
   you unban it, an AI-emitted or fan-out activation tree is a fork-bomb against the shared key pool and
   wallet (UU#8) **with no tree-scoped budget to stop it.** You cannot safely demo "the Activation
   subsumes market/fan-out" (the M3 value increment) without the Governor already underneath it. So the
   Governor is not a "service" that arrives with dispatch in M4; it is **the safety precondition for the
   first concurrent activation** and must land with/just-before M3.

3. **The two physics tensions are seeded as MEASUREMENT + PINNING in M1–M2, not designed-against in a late
   milestone.** Reshaper #7 (model-identity hash-pinned) and the prompt-cache-hit-rate / monoculture-index
   sensors are *one-line recorded facts and a no-op hook* today and *un-retrofittable* once the calibration
   flywheel and the multi-provider routing are live (UU#7, UU#12, principle #14: "the sensors must exist
   before the regime that needs them"). They cost almost nothing now and are load-bearing for the M6
   Calibration Ledger. So they ride in the earliest milestones as seeded fields, and the *tension itself*
   becomes a gated experiment at M6 (Calibration) and M7 (Evaluand), where its data finally exists.

The net shape: **Foundation reshapers front-loaded and proven on real traffic by M2–M3; the type system
and ledgers built on a substrate already known to hold; planning relocation and the supervisor tier
(the ship-of-Theseus killzone, B2) stay LAST, exactly as the inherited program correctly placed them.**
Risk-and-value-first reorders the *foundation-vs-decoupling* front half; it does not touch the
correctly-conservative back half.

---

## 2. The riskiest thing we want dead-or-alive by milestone 2

**The event-sourced fold, with the Activation as its event grain, replaying a real multi-phase planning
run — proven by a replay oracle, under the strangler (OLD engine still drives the live epic).**

Why this and not something else:
- It is Reshaper #1; if it's wrong, *every* subsequent milestone is built on sand (committed-UU Part 3 #1).
- It is the most *invisible* failure: the inherited plan would let us believe it's "in progress" for
  months. A replay-oracle gate at M2 converts an invisible architectural bet into a green/red CI fact.
- It is where self-improvement-vs-durable-replay (Tier S UU#1) first becomes *touchable*: a real run that
  re-plans mid-flight is exactly the trace that exposes "replay a stale plan vs re-plan into a different
  universe." We want that divergence visible against a real recorded trace at M2, while it's a science
  experiment, not a production outage at month 5.

If M2 is red, we re-aim the architecture having spent only foundation+hygiene budget. That is the entire
point of the lens.

---

## 3. The ordering (every reshaper/organ placed)

### M1 — Foundation hygiene + the contract-checker + the seeded-facts pass *(enabling; low risk; high leverage)*
Inherits the m1-foundation brief verbatim in spirit: CI marker-switch, executor-merge superset, state
back-compat (`extra="ignore"` + fixture corpus), pin status/chain contracts, discovery-integrity guard,
sandbox fail-open fix, **`pipelines check`/`doctor`/`new` graph linter**, and the **chain.yaml↔EPIC↔briefs
anti-drift lint** (the B1-critical fix: the executable artifact currently drives the STALE program; this
lint makes that un-shippable).
**Re-aim additions under this lens:** (a) seed Reshaper #7 — **model-identity as a hash-pinned provenance
field** on every receipt (a recorded fact, costs nothing, un-retrofittable later, UU#7); (b) seed the two
invisible sensors as no-op-cheap first-class metrics — **per-phase prefix-cache-hit-rate** and a
**model-diversity/monoculture index** (principle #14); (c) fold in the *first half* of inherited M2's type
work that is pure hygiene — the **ZERO-`GateRecommendation`-in-SDK grep gate scaffold** — so the
decoupling is enforced from line one, not retrofitted.
**Provable increment:** a green graph-linter that statically rejects a mis-wired composition; a chain that
provably cannot run the stale program; receipts that now record which weights actually answered.
**Gate:** `pipelines check` exits non-zero on a hand-mangled fixture; anti-drift lint red on a mismatched
chain.yaml; grep gate red on a seeded `GateRecommendation` import.

### M2 — The event-sourced fold + the Activation record + the replay oracle *(THE bet; apex/extreme; the dead-or-alive milestone)*
Build Reshaper #1 and Reshaper #2 together because the Activation IS the event grain of the fold (the
synthesis: "transitions ARE the events; state.json becomes a derived cache"). **State becomes a
deterministic fold over an append-only, effect-typed, taint-carrying log; the WAL is authoritative;
state.json is a rebuilt cache.** The Activation is the persisted, supervised record of a node firing with
a *pluggable readiness rule* — built now while the only rule is "upstream done," so DAG/loop/standing/
market are one field later, not a retrofit (Reshaper #2). Seed the **taint lattice inside the event/hash**
as a propagation hook now (Reshaper #3's enforcement comes at M4, but the field must be in the log from the
first event or it's unrecoverable — UU#4). Also lands the de-planning **structured `reduce`/`select` +
`Reduce[T]`** and the **dropped `iterate_until` predicate** (completes inherited M2), because the fold's
loop-readiness rule needs a real data predicate.
**Provable increment:** `fold(events)` of a *recorded real multi-phase planning run* reproduces its actual
final state.json; **resume = re-fold from the log** survives a kill-mid-run.
**Gate (the load-bearing one):** the **replay oracle** — recorded real-run traces re-fold byte-faithfully;
a crash-resume oracle (kill between model-return and journal-write, assert no double-fold and no silent
re-plan). This is where self-improvement-vs-replay (UU#1) is first measured against a real re-planning
trace. **Strangler:** OLD subprocess engine still drives the live epic throughout; the fold runs as a
read-side shadow over the SAME runs, proving parity before it is ever authoritative.

### M3 — The Activation as the real scheduler primitive + the Governor/Capacity-Lease underneath it *(prove the "not a DAG-walker" thesis; high risk)*
Now make the Activation *actually schedule* — demonstrate it hosts more than DAG: a **loop** (fixpoint:
changed-not-converged), a **standing** (mailbox) and a **market** (fire-N-select-K) readiness rule as the
SAME field, with lifecycle/supervision (BEAM/OTP-style). This is the second invalidation bet: if the
readiness predicate can't express these as peers, the primitive thesis is false. **Reshaper #4 lands
here, not at M4:** a tree-scoped Governor (recursion/cost/fan-out/concurrency budget charged per-subgraph
against a fixed pool) + a linearizable Capacity-Lease arbiter (fencing tokens) over the key pool — because
the *first* concurrent/market activation is a fork-bomb without it (UU#8), and unbanning concurrency was
only safe once M2 made the log authoritative (UU#6). The cloud `_phase_command` shim is born here with the
process-substrate driver (the inherited M3 + the BITE-2 cloud-recoupling owner).
**Provable increment:** a **`select`-based market / fan-out demo** runs N activations, the Governor caps
the tree, the Capacity-Lease prevents the two-tenant stampede — a capability the OLD engine structurally
cannot do (it *bans* this).
**Gate:** fork-bomb oracle (an emergent recursive graph is bounded, not unbounded); two-tenant
shared-key contention test (no double-issue under simulated clock skew); the
`{robustness}×{prep,feedback}×{states}×{verdicts}` topology-realizer parity test (the inherited M3 gate —
the projection-faithfulness collapse is unsafe until proven).

### M4 — Port runtime-enforcement + the Contract Ledger + the Effect Ledger *(the type system + the act-safety layer; high risk on AI-emitted graphs)*
With a sound substrate and a real scheduler, build the two ledgers that make the runtime able to **reject
what it has no type system to name** (UU#5) and to **stop conflating artifact-idempotency with
act-idempotency** (UU#3). **Reshaper #3 enforcement:** Port = (kind × content-type × schema) + envelope,
runtime-enforced, taint a propagating lattice inside the hash, with a typed declassification edge (the PEV
verifier is the principalled declassifier — UU#13). **Contract Ledger** = the admission validator + the
machine repair-negotiation gradient + taint-in-cache-key (Reshaper #5's "recorded-into" discipline begins
here). **Effect Ledger** = typed world-acts with replay-class + external idempotency-key≠content-hash +
declared compensation — built *before* the supervisor tier journals the first real merge/spend (principle
#10). The Conveyance/Work-Envelope is the carrier that threads all of this (cost/lineage/taint/cancel
ride it; "nothing crosses a seam naked"). This subsumes inherited M4's dispatch/emit/evidence/config + the
RecoveryPolicy spine, now expressed as ledger operations rather than ad-hoc services.
**Provable increment:** a deliberately **malformed AI-shaped graph is rejected at admission with a
machine-readable repair gradient** (not by crashing at runtime); a **crash between model-return and
journal-write does NOT double-charge** (Effect Ledger idempotency key honored).
**Gate:** admission-rejection oracle (feral graph caught at build, repair gradient emitted); taint-launder
oracle (two identical-byte values with different taint do NOT collide-and-launder in the cache); effect
replay oracle (at-most-once act survives resume).

### M5 — Node library + execute realm + the Behavioral Identity Manifest + the Capsule + the Warrant skeleton *(value-delivery + identity; medium risk)*
Formalize `patterns` as the composition vocabulary (inherited M5a). Build the execute task-DAG scheduler as
a composition of the now-real primitives (inherited M5b), reducer returns app-defined outcomes. **Reshaper
#6 lands here:** the **Behavioral Identity Manifest** is the object the content-hash points at (topology +
step-code hashes + resolved prompt bodies + routing-taken + ABI + dep-closure) — this is what makes resume
version-aware (chimera-run defense, UU#9) and what M6's relocated planning is *identified by*. The
**Replayable Capsule** (Definition+Contract+Lineage+Evidence) and the **Warrant skeleton** (authority
envelope + verified-work-unit + decision-time rationale anchor) are seeded here while the human is still
authority+payer+rationale, so the fields exist when those split (principle #11, #12).
**Provable increment:** **resume across a definition edit** is pin/refuse/migrate (no silent chimera run);
the run emits a portable Capsule a cold recipient can rehydrate-or-refuse-loudly.
**Gate:** manifest-diff resume oracle (edit the def mid-run; resume refuses or migrates, never silently
chimeras); capsule rehydration oracle (a fork-with-back-edge accretes lineage, doesn't flatten).

### M6 — The Calibration Ledger + Evaluand-and-one-Ledger + planning relocation + trust boundary *(the soul + the ship-of-Theseus killzone; apex)*
This is where the heart and the two hardest tensions resolve **on data that finally exists.** **Calibration
Ledger** (Reshaper #5 fully): CapabilityClaims + decay/churn + exploration budget + taint-aware
aggregation; the 1-5 score and `tier_models` become *projections*, routing becomes a query. **Evaluand +
one Ledger**: versioned attributable judgments; the eval ruler is no longer an unversioned float (UU#2);
eval IS the spine. Here the **cheapest-routing-vs-prompt-caching** tension (UU#12) and the
**monoculture/co-degradation** tension (UU#7, UU#10) become gated experiments using the M1-seeded sensors —
the exploration budget keeps the flywheel un-censored. **Then, and only now, planning relocates:** drop
`_BUILTIN_NAMES`, manifest + driver + bindings + SKILL.md, manifest-first non-executing discovery + trust
tier + `arnold_api_version`, the `arnold` namespace/CLI migration (inherited M6). This is the B2
ship-of-Theseus killzone — it lands LAST among the build because everything beneath it is now proven.
**Provable increment:** **routing is a query over the Calibration Ledger**; "is the new version better?" is
a **join over hashed identities, not a vibe**; planning reads as a composition with no privileged path.
**Gate:** anti-Goodhart oracle (a measurement regression is distinguishable from a quality regression — the
optimizer and evaluator provably don't share machinery); a fourth, non-planning tool ships on the same
parts; **no binding carries `STATE_*` as mechanism** (grep gate).

### M7 — Supervisor tier + builder docs + the canary epic *(the last extraction; medium risk, gated on M6)*
The cross-run orchestration tier (inherited M5d/F8) — chain/epic/bakeoff as general control ops over the
M4 Effect Ledger and the M6 control vocabulary. This is extracted **last and behind a default-off flag,
never adopted by the driving chain** (B2). Builder documentation (inherited M7): generated-from-types
reference, worked examples, package contract.
**Provable increment + gate:** a **throwaway canary epic** (2-3 trivial milestones, ≥1 dep edge, ≥1
induced failure) runs end-to-end on the NEW supervisor tier — the only honest acceptance for F8 since the
real (frozen) epic cannot exercise it; an external builder ships the `select`-tournament from docs alone
(zero planning vocabulary, grep-proven).

---

## 4. The critical path

`M1 (hygiene + seeded facts + grep gate) → M2 (event-sourced fold + Activation + replay oracle) →
M3 (Activation-as-scheduler + Governor/Capacity-Lease) → M4 (Port enforcement + Contract Ledger + Effect
Ledger) → M6 (Calibration + Evaluand + planning relocation) → M7 (supervisor canary)`.

M5 (node-lib + execute + Manifest + Capsule + Warrant) is **largely parallelizable off the M4 base** — it
needs the Port/Contract/Effect ledgers but not the Calibration/Evaluand ledgers, so it runs concurrently
with the early part of M6's calibration-flywheel work and rejoins before planning relocation. The strict
serial spine is M1→M2→M3→M4→(planning-relocation tail of M6)→M7.

---

## 5. What parallelizes

- **M1 deliverables land as independent PRs to main as each passes** (p7 drift-armor), not bundled — the
  seeded model-identity field, the two sensors, the grep gate, and each linter are separable.
- **The de-planning type work** (`reduce`/`select`/`Reduce[T]`, the dropped predicate) splits across
  M1's grep-gate scaffold and M2's structured-data conversion; it has no architecture-invalidation risk
  and rides alongside the fold rather than gating it.
- **M5 (node-lib + execute + Manifest + Capsule + Warrant) runs parallel to the early Calibration/Evaluand
  work of M6** off the shared M4 base.
- **Sensors and seeded fields (model-identity, cache-hit-rate, monoculture index)** are seeded in M1 and
  *consumed* in M6 — months apart, deliberately, so the instrument predates the regime.
- **Builder docs (M7) drafting** can begin against the M4 type surface and finalize after M6.

---

## 6. The strangler invariant I maintain

**At every milestone: the OLD subprocess engine still boots and drives a throwaway 1-milestone plan to
green, AND a planning-shaped plan runs on the NEW pieces built so far — gated as a per-milestone done
criterion, never deferred.** Concretely, the foundation is brought up as a **read-side shadow first**: M2's
fold runs over the SAME real runs the OLD engine drives and is proven byte-faithful by the replay oracle
*before* it is ever made authoritative; the new pieces grow alongside the old behind default-off flags;
the old path is deleted only after the new path has soaked on real traffic; and planning relocation (the
one irreversible self-reference change) is the LAST build step, after every organ beneath it is green.
There is no multi-week broken window because the new substrate never becomes load-bearing for the live epic
until M6, and the live epic always runs on the frozen old engine until then. Autonomy: one t0 go (recorded,
EPIC §3-21), then every milestone auto-arms on its machine gate; failure/escalate are the bounded auto-
ladders (retry×2 → bump profile → stop_chain + auto-ticket).

---

## 7. The biggest sequencing risk THIS ordering carries

**Front-loading the event-sourced fold (M2) onto a real multi-day workload risks a long, deep M2 that
becomes the single chokepoint the whole epic is gated behind — the same "riskiest knot at position 3"
failure p7 warns about, now pulled to position 2 and made even more load-bearing.** By choosing to prove
Reshaper #1 against a *real recorded run* (not a toy) at M2, I make M2 simultaneously the highest-value and
highest-uncertainty milestone, and `stop_chain` after a red M2 freezes everything. This is a deliberate
trade — failing fast on the foundation is the entire lens — but it is a real risk, and the mitigations are
load-bearing, not optional:
1. **Split M2 into a characterization spike + the port** (p7 rec): write the replay oracle against
   *today's* recorded runs and land it on main FIRST as permanent CI; only then attempt the fold. The
   highest-uncertainty discovery (what a real run's event stream actually is) happens on a cheap spike, not
   inside the apex milestone.
2. **The fold is a read-side shadow before it is authoritative** (the strangler), so a red oracle is a
   "don't promote yet" signal, not a broken live engine — the OLD engine keeps the epic moving while M2
   iterates.
3. **M5 is parallelized off M4** precisely so that a slow M2/M3 doesn't serialize the value-delivery half
   of the program behind the foundation half.

A secondary carried risk: pulling the Governor/Capacity-Lease forward to M3 means building a
cross-tenant arbiter before there is a second real tenant to test it against — mitigated by the
fork-bomb and simulated-clock-skew oracles (synthetic adversary now, real tenant later), since the
alternative (unban concurrency at M3 with no Governor) is a fork-bomb against the live wallet.
