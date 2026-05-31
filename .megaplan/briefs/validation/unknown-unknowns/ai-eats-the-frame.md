# Unknown-Unknowns — EXOGENOUS / TIME: does AI eat the frame?

**Vantage:** the ground is moving. Models + agents improve fast. The whole epic assumes a 2026 abstraction
(explicit pipeline-composition, a human developer reading docs to wire produce/judge/gate/revise loops)
stays load-bearing through the 12–24 months it takes to build, harden, and adopt. This brief attacks the
*time-stability* of the frame — not its internal correctness.

**Out of scope (inside the frame, already hardened):** typed Ports, realized graph, policy spine, trust
boundary, 4-verdict eviction, substrate×topology drivers. I do not re-audit any of that. I also do not
rehash the prior-art/landscape file (market-converged) or the substrate file (protocol-vs-library) — those
attack *space*, not *time*.

---

## The structural reason our process could not see this

Every prior pass reasoned about Arnold against a **frozen model**. The two seed apps (planning, resident)
were built on the models of 2024–2025; the stress-test sketched 5 domains *as they would be built today*;
the acceptance tests ("an external builder ships a fourth thing") imagine *a 2026 developer*. There is no
artifact anywhere in `.megaplan/briefs/validation/**` that asks "what does this look like when the model is 10× more
capable, has 10M-token context, durable memory, and writes its own pipelines." A `grep -ri "model improv\|
12 month\|18 month\|future model\|model capabilit\|when models\|obsolesce\|half-life"` across the validation
corpus returns essentially nothing about *capability trajectory*. The process held the model constant and
varied the architecture. **The one variable most likely to invalidate the deliverable was the one variable
held fixed by construction.** That is the blindness this brief pries open — not because the team is naive,
but because a roadmap is, by its nature, a bet that the world stands still long enough to finish it.

A second structural blindness: the *builder* in every acceptance test is a human reading `docs/arnold/`.
M7's literal proof of success is "a human developer ships the select-tournament from docs ALONE." The epic
never asks whether, by the time M7 lands, the *typical* author of a new pipeline is an agent, not a person —
which would invert what "success" even means. The docs-for-humans deliverable is graded against a population
(human builders) that the exogenous trend is actively shrinking.

---

## UU-1 — The critique→revise→gate LOOP is a model-weakness crutch, and the weakness is the thing improving fastest

**Insight.** Arnold's flagship node — `critique_revise_gate_loop`, the pattern planning *is* — exists because
a single 2024-era forward pass produced low-quality output, so you wrap it in an external loop that re-prompts
until a separate judge is satisfied. That loop is **scaffolding around a capability gap**: the model can't
self-verify or self-correct in one shot, so the *pipeline author* hand-builds the verify-and-retry control
flow outside the model. But test-time-compute / extended-reasoning models (the o-series lineage,
thinking-budget models, agentic self-critique) are explicitly internalizing exactly this loop *inside one
inference call*. The frontier direction of 2025→2027 is "give the model a reasoning/verification budget and
it does the critique-revise-gate internally." If that lands, the single most-elaborated, most-hardened verb
in the entire SDK (the whole M2 4-verdict eviction, the gate-consequence parameterization, the dropped
`iterate_until` predicate, the realized-graph projection of robustness levels) is **externalizing a loop the
model now runs better internally** — and an external loop is strictly *worse* than an internal one because it
loses the model's intermediate state between turns and pays full prompt cost per iteration.

**Why our process was blind.** The 5-domain stress-test asked "are the verbs at the right altitude?" and
concluded yes. But "right altitude" was judged against *today's* model, which genuinely needs an external
critique loop. The test could not return "this verb is a crutch that dissolves" because every sketch assumed
a model that needs the crutch. The team hardened the crutch into a load-bearing primitive precisely because,
right now, it bears load.

**If true.** The center of gravity of the SDK shifts from *control-flow nodes* (gate/revise/judge/loop —
the thing models absorb) to *substrate nodes* (state/emit/evidence/dispatch/durability/budget — the thing
models still can't do for themselves because it lives outside the inference boundary). The epic's effort
allocation is inverted: M2/M3/M5c (the loop/verdict/control-flow machinery, the hardest and largest chunk)
is depreciating; M4 (services: durable state, cost authority, evidence, dispatch) is the part that *survives*
a stronger model. You'd want to ship M4-shaped value first and treat the loop vocabulary as a thin,
deprecatable convenience.

**Severity: would-reshape.** Doesn't kill the epic, but it argues the milestone *ordering and emphasis*
are backwards relative to where capability is heading.

---

## UU-2 — When pipelines are AI-authored on demand, the deliverable is a RUNTIME CONTRACT, not a builder SDK — and M7 (docs for humans) is value spent on the wrong consumer

**Insight.** The entire onward surface (M6 trust boundary, M7 `docs/arnold/`, the SKILL.md package contract,
`pipelines new` scaffold, the generated-from-types reference, "an external human builder ships from docs
alone") presumes a **human** is the author of a new module. But the same models that make Arnold worth using
are, on the same 12–24-month curve, becoming the *cheapest authors of pipelines*. The natural 2027 product
is not "a human composes a pipeline from documented pieces" — it's "an agent, given a goal, *emits* a pipeline
(or just *acts* without materializing one) on demand." If the author is an agent:

- **Docs-for-humans (M7) is the wrong artifact.** An agent doesn't read `authoring-guide.md`; it needs a
  machine-checkable schema + a fast validator in its tool loop. The valuable half of M7 is the *generator*
  and `pipelines check` (a tool an agent calls to know if its emitted graph is wired); the authored prose,
  worked examples, and skill-integration narrative are written for a reader who is being automated away.
- **The trust/discovery story (M6) inverts.** M6's trust tiers (in-tree / blessed / quarantined) and
  manifest-first non-executing discovery were designed to gate *human-contributed packages* in a registry.
  When modules are *generated per-task by an agent*, the threat model is no longer "is this third-party
  package malicious" but "this composition was synthesized 4 seconds ago by an LLM, will never be reused, and
  needs to be sandboxed and thrown away." That is a *runtime ephemeral-sandbox* problem (a la code-interpreter
  / ACE on every run), not a *package-registry trust-tier* problem. The epic builds a publishing-and-curation
  trust model for a world that may instead need a generate-execute-discard trust model.
- **Composability as the value proposition weakens.** "Reusable pieces a human composes" assumes composition
  is the expensive, scarce act worth amortizing across builders. If an agent can re-synthesize the
  composition for free each time, the durable value is not the *reusable library of verbs* but the *invariants
  the runtime enforces no matter what the agent emits* — typed Ports that fail loud, CAS state that can't be
  corrupted, a budget authority that can't be overrun, an evidence/oracle layer that can't be faked. Those
  are guardrails on *machine-generated* graphs, not ergonomics for human authors.

**Why our process was blind.** Peter's north star is literally "**other people** build on the same pieces"
(EPIC L10) — and "other people" was unexamined as *humans*. The two seed apps were both human-authored, the
acceptance tests are both human-performed, so the population of builders was set to "developers" by the only
data points available. The process triangulated who-builds from a sample where every builder was a person,
and could not extrapolate to a builder that didn't exist in the sample.

**If true.** M7 should be split: keep the generator + `pipelines check` (an agent's tool-loop validator,
high value either way) and **defer or radically shrink the authored docs/examples**, which are insurance
against a human-builder world that the trend is eroding. M6's trust model should be re-scoped from
"package-registry curation" toward "per-run ephemeral sandbox for machine-emitted compositions." The product
one-liner shifts from "a builder SDK" to "a **safe runtime contract for executing LLM-emitted agent
workflows**" — the value migrates from authoring ergonomics to execution invariants.

**Severity: would-redirect.** This changes *who the customer is* and therefore which milestones are the
product vs. which are scaffolding. That is a redirection, not a refinement.

---

## UU-3 — The hardening half-life: by the time the epic lands, the abstraction it hardened may be a generation behind, and the *cost* of the hardening is the moat working against you

**Insight.** This is a multi-week-to-multi-month epic (M1→M7, "wait to run," strangler boundary gated *every*
milestone, behavioral-replay + substrate-swap oracles per milestone, a throwaway canary epic for M5d). That
is an enormous, deliberately *slow and rigorous* program — the rigor is the point. But rigor is a bet on
*durability*: you only amortize a substrate-swap oracle and a typed-Port realizer if the abstraction they
protect is still the right abstraction in 12–24 months. The exogenous trend means the abstraction has a
**half-life**, and the more you harden it the more *sunk cost* resists adapting when the half-life expires.
A leaner, scrappier, more disposable Arnold would be *better positioned* for a moving target than a
beautifully-hardened one — because hardening converts agility into commitment. The epic's greatest internal
virtue (it is exhaustively de-risked) is, against a moving exogenous frontier, a *liability*: you are
pouring concrete around a 2026 shape.

**Why our process was blind.** Every prior pass optimized for *internal* robustness (premortems, confidence
ledgers, interrogation lenses, 10 milestones of oracles). Robustness-against-our-own-bugs is orthogonal to —
and can be actively traded against — *robustness-against-the-world-changing*. The validation machinery has no
lens for "are we over-investing in durability for a thing with a short shelf life?" Its whole apparatus
measures "will this break?" never "will this still matter?"

**If true.** Re-budget the epic toward *optionality*: ship the smallest core that delivers value *now*
(probably M1 + the M4 substrate services), keep the control-flow vocabulary thin and explicitly *deprecatable*,
and refuse to build the heavy strangler/oracle apparatus around verbs (UU-1) that may be a generation behind
before M7 lands. Treat "wait to run" as a warning sign: a deliverable too big to even start running is a
deliverable whose world may change before it ships.

**Severity: would-reshape.** Argues for re-budgeting toward speed/optionality and against the
maximal-rigor-everywhere posture, especially around the depreciating control-flow milestones.

---

## UU-4 (worth-knowing) — "Memory + long context" may subsume STATE/EVIDENCE the way reasoning subsumes the loop

**Insight.** UU-1 says internal reasoning eats the *control-flow* verbs. The symmetric question: does
native model **memory + 10M-token context** eat the *state/evidence* substrate — the part UU-1 assumed
survives? Today Arnold's Store exists because the model can't carry a plan's state across turns/processes, and
the evidence layer exists because the model can't reliably attest to what it did. If durable per-agent memory
and verifiable tool-trace become native model features, even the substrate moat narrows. The reason this is
only *worth-knowing* (not redirect/reshape): the **durability, transactionality, multi-tenancy, audit, and
budget-enforcement** properties of a real Store are *systems* guarantees that a model's memory — however long
— structurally cannot provide (a model can't promise a CAS write survives a crash or that a tenant can't
overrun a budget). So the substrate is the *most* defensible layer, but it is not *infinitely* defensible, and
the "context is the new RAM" trend will keep pushing the line of what's worth externalizing.

**Why blind / if true / severity.** Blind for the same held-model-constant reason as UU-1. If true, it
narrows even the surviving moat toward the *systems-guarantee* core (crash-safety, multi-tenancy, budget,
audit) and away from "we hold your state because the model can't." **Severity: worth-knowing** — it sharpens
the moat's boundary rather than moving the epic.

---

## THE SINGLE BIGGEST REFRAME

**Stop building "a builder SDK of composable pipeline pieces (graded by: can a human ship a fourth module?)"
and start building "the durable, safe RUNTIME CONTRACT under which LLM-emitted agent workflows execute
(graded by: when an agent synthesizes and runs an arbitrary composition, the invariants hold — typed ports
fail loud, state is crash-safe and multi-tenant, the budget can't be overrun, the evidence can't be faked)."**

The exogenous trend cuts the SDK in two along a clean seam, and the two halves age in opposite directions:

- **The control-flow vocabulary** (gate/revise/judge/loop/critique — M2, M3, M5c, most of M5a/b, the whole
  4-verdict eviction) is the half models are *absorbing into a single inference call*. It is depreciating. It
  is also the largest, hardest, most-hardened chunk of the epic. We are pouring the most concrete around the
  part with the shortest half-life.

- **The runtime substrate + the machine-checkable contract** (durable/transactional/leased Store, the budget
  authority, evidence/oracle, dispatch, typed Ports, `pipelines check`) is the half that *survives and grows
  more valuable* as agents author and run arbitrary compositions at scale — because it's the guardrail on
  machine-generated, single-use graphs. It is the smaller, less-emphasized part of the plan.

The frame assumed the *composition* (a human wiring durable, reusable pipelines) is the scarce, valuable,
amortizable act. The trend says the composition becomes *free and disposable* (agents emit it per-task) while
the *enforcement of invariants on whatever gets emitted* becomes the scarce, valuable thing. Arnold's true
2027 product is not the library of verbs a developer composes — it is the **trustworthy execution floor under
graphs nobody hand-wrote**. Re-grade success accordingly: not "a human builder ships a module from docs," but
"**an agent emits a never-before-seen composition and the runtime contract holds.**" Everything that serves
that survives the frontier; everything that serves human-authoring ergonomics is insurance on a shrinking
population. Build, harden, and order the milestones to that seam.
