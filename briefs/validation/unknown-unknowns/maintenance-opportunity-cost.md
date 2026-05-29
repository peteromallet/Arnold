# Unknown-Unknowns — HUMAN COST / OPPORTUNITY COST (the build reality outside the code)

**Vantage.** I am not auditing the architecture. I stand where no prior pass stood: in the
calendar and the org chart. The whole validation corpus (c1–c7, s1–s4, premortem, confidence,
interrogation, the sibling u-u briefs on moat / AI-eating-the-frame / node-graph ecosystems /
durable-workflow-engines) asks "is the SDK *well-designed* and *feasible*?" Not one asks "who
*maintains* it for the next two years, what *else* could those two years build, and is 'turn our
working planner into a public SDK' the **highest-leverage bet** this person can make right now?"
I attack the BET, not the blueprint.

## Grounding facts (measured, not asserted)

- **Solo project.** `git shortlog` since 2026-04-01: **POM = 399 commits, "Hermes Evals" = 47
  (automated agent commits), "Peter O'Malley" = 5. Zero other humans.** The teknium/Nous commits
  are the upstream fork ancestry, not collaborators on this work. This is a **one-person codebase**
  with a **one-person mental model.**
- **Scale.** 882 Python files, **~320K LOC of `megaplan/`** + **88K LOC of tests**. That is already
  a large surface for one maintainer, *before* the epic adds a public SDK boundary, a discovery/trust
  layer, a contract checker, a typed-Port system, a realized-graph realizer, a policy spine, drivers,
  a supervisor tier, and `docs/arnold/` builder docs.
- **The epic is heavy.** chain.yaml = **10 milestones**, several pinned `profile: apex` (all-premium),
  `robustness: extreme`/`depth: max` (M3). STATUS itself flags self-reference hazard ("drive from a
  pinned engine, not the live editable checkout"). This is multi-month, frontier-priced, and it
  refactors the engine *while the engine is the tool building the refactor.*
- **A working, fundable product already exists.** `docs/megaplan-intro-v2.md` is a sharp vertical
  story with a **real invoice**: $12 vs $422, ~79–90% of code written by DeepSeek, frontier reserved
  for adjudication + the one unrecoverable milestone. The README was just **rebranded** to "Arnold —
  Intelligence Coordination System," megaplan demoted to "its first tool," repo pushed to a public
  `github.com/peteromallet/arnold`. The pivot is already in motion in the public surface.

---

## The structural reason our process was blind to all of this

Every artifact in `briefs/validation/**` is an **engineering-design** artifact produced by an
**engineering-design** process (megaplan critiquing its own plan, adversarial lenses, premortems on
*technical* failure modes). That process is constitutionally incapable of asking "should a single
person spend their next quarter on this at all?" — because the question is **out of frame for a
design review.** A design review's job is to make the design good *given that we build it.* It cannot
cost the *decision to build it* against the founder's other moves, because (a) there is only one
person, so there is no second voice whose time is being spent, and (b) the tool doing the
critiquing *is the artifact under question* — megaplan will happily produce a beautiful 10-milestone
plan to convert itself into an SDK, because producing beautiful plans is what it does. **The
planner cannot be the thing that decides whether the planner should become an SDK.** That is the
deepest blindness here: the validation apparatus is endogenous to the bet.

---

## UU-1 — The maintainer of the public SDK is the same person who is the product's only growth engine, and those two jobs are mutually exclusive in calendar time

**Insight.** An SDK is not a deliverable; it is a **standing liability**. The moment `docs/arnold/`
ships and a fourth builder wires `produce/judge/gate`, POM owns: a public API-compat contract
(`arnold_api_version` is already in the plan — versioning implies you can't freely break it),
triage of *other people's broken compositions* (a class of bug report that is unbounded because the
composition space is unbounded — that is the entire point of the SDK), discovery/trust-boundary CVEs
(M5's non-executing discovery + `exec_module` gate is a security surface), and the social debt of an
ecosystem that expects responsiveness. **None of that work grows the product or the founder's
position; all of it is pure carrying cost, and it lands on the one person who is also the only
person who can sell, calibrate, dogfood, and improve megaplan itself.** The tier maps and routing
calibration that produced the $12 invoice — the actual moat per the sibling brief — *degrade* the
moment the founder's attention is consumed by issue triage for strangers' DAGs.

**Why our process was blind.** Solo dev = no one whose time is visibly "spent" on maintenance, so
maintenance cost reads as $0 in a design review. The cost is real but **off the engineering
balance sheet** — it shows up only as future calendars that no design artifact models. Every
premortem asked "will the migration break?"; none asked "what does week 30, post-launch, *as a
support queue*, do to the founder's ability to ship anything else?"

**If true.** The epic should be re-scoped from "ship a public composable SDK" to "**extract a clean
internal boundary, keep it private/source-available-but-unsupported**, and explicitly *refuse* the
ecosystem-maintainer role until there is a second maintainer or revenue to fund support." The
public-builder acceptance test (M7: "a stranger ships the select-tournament from docs alone")
becomes the *most expensive* and *least reversible* commitment in the plan — it is the gate that
converts a refactor into a permanent obligation. Defer or delete it.

**Severity: would-redirect.**

---

## UU-2 — The opportunity cost is not "other features" — it is the validated vertical product that the SDK pivot actively dilutes

**Insight.** Reframe the choice as a portfolio bet. In the **same** quarter the epic consumes, the
already-validated asset is the **routing-and-robustness vertical**: a tool that demonstrably moves
~90% of real coding to a model that costs 35× less, with a *checkable invoice*. That is a
product with a **market, a number, and a wedge** (cost-of-coding is the single hottest buyer pain
of 2026). The SDK pivot spends the quarter making that product *subtractable* (the moat brief's
finding) AND *unsold* (no one is doing distribution, pricing, design partners, or a hosted offering
while the founder refactors internals into pieces). The README rebrand — "Arnold, megaplan is its
first tool" — is the tell: the founder is **moving up the abstraction ladder away from the thing
that has traction toward a thing whose traction is hypothetical** ("a fourth builder ships a fourth
thing"). Comparable history is brutal here: horizontal "compose-your-own-agent" frameworks
(LangChain/LangGraph, CrewAI, Autogen, Griptape, the Vercel AI SDK, the OpenAI Agents SDK, plus
every fork) are a **red ocean with near-zero willingness-to-pay for the framework itself** —
value capture is in the vertical or the hosting, never the pieces. The validated $12-invoice
product is the rarer, more defensible thing, and the plan trades it for the commoditized one.

**Why our process was blind.** The validation corpus treats "value = composability" as the *first
line of the EPIC* (literally: "Other people build on the same pieces to CREATE new things"). Once
that is the axiom, every downstream pass optimizes *how* to be a good SDK, never *whether* being an
SDK beats being a product. Opportunity cost is invisible because the alternative use of the time
(go-to-market on the existing product) was never represented as a milestone, so it never competed
for the slot. A design process scores plans; it does not score the *non-existence* of a plan.

**If true.** The highest-leverage move is the opposite of the epic: **freeze internals at "good
enough to extend privately," spend the quarter on distribution/pricing/design-partners for the
routing product**, and let SDK-ification be *pulled* by a real second builder with budget, not
*pushed* by an internal aesthetic of composability. The internal boundary cleanup (a 1–2 week
sprint, not a 10-milestone epic) is worth doing for the founder's own velocity; the *public
ecosystem* is worth doing only when demand for it is demonstrated externally.

**Severity: would-redirect.**

---

## UU-3 — Key-person risk is not a footnote; the whole asset is one undocumented human, and the SDK *multiplies* the bus-factor exposure instead of reducing it

**Insight.** The genuinely scarce asset (per the moat brief) is **calibration judgment** — *when is
a cheap model safe* — and it lives **entirely in one head**, encoded as tier maps, robustness
presets, profile mixes, and critique-lens selection that were hand-tuned against real invoices.
A 320K-LOC engine with one author and one mental model already has a bus-factor of 1. The epic's
public-SDK framing makes this *worse*, not better, in two ways: (1) it adds a large **public**
surface (versioned API, docs, discovery, trust boundary) whose maintenance *also* has bus-factor 1,
so a single point of failure now has external dependents who get stranded; (2) it spends the
quarter on **abstraction** (pieces a stranger could compose) instead of **transfer** (writing down
the calibration knowledge so a second human or an automated process could reproduce the routing
judgment). The plan optimizes for "a stranger can compose pieces" while leaving "a second person
could run/calibrate/sell this if POM steps away for a month" completely unaddressed. That is
exactly backwards if the goal is durability.

**Why our process was blind.** Bus-factor is an *organizational* property; the validation corpus
has no organizational lens — it has technical lenses (concurrency, blast-radius, sandbox-trust)
and strategic lenses (moat, market). "What happens to this if the one person is unavailable for
6 weeks" is nobody's section. And because the one person *is* doing all the analysis, the risk is
structurally invisible to the analysis — you cannot see your own indispensability from inside it.

**If true.** Before (or instead of) the SDK epic, the highest-durability investment is **knowledge
transfer of the calibration moat**: a written, evidence-backed "routing playbook" (why each tier
maps where, which invoices justify it), an automated calibration harness so routing decisions are
*reproducible from data* rather than from memory, and at minimum a second pair of hands on the
critical path. This is a *smaller* effort than the epic and de-risks the actual asset. The SDK can
wait; the bus-factor cannot.

**Severity: would-reshape.**

---

## UU-4 — Building the SDK *with* the SDK creates a recursive time-tax that the plan acknowledges but does not cost

**Insight.** STATUS.md already flags the self-reference hazard ("drive from a pinned engine /
`--no-git-refresh` off a frozen branch, not the live editable checkout") and the deferred premortem
(`p3-self-reference.md`) exists. But the *human* cost of this recursion is uncounted: every
milestone that refactors dispatch/state/emit/drivers is refactoring **the machinery currently
executing the refactor**, which means the founder cannot simply "let it run" — each milestone needs
a pinned-engine setup, a parity oracle, careful staging so a half-migrated engine doesn't corrupt
the run building the migration, and live babysitting of a tool whose substrate is shifting under it.
Several milestones are `apex` (all-premium) and `extreme/max` robustness precisely because the
blast radius is the engine itself. The realistic per-milestone *attention* cost (setup, supervision,
recovery from self-inflicted breakage) is far higher than a normal refactor of an external target,
and it is **serial and non-delegable** because there is no second person to hold the pinned-engine
discipline while the founder does something else. The dogfood memory note
(`project_dogfood_engine_shadow_and_openrouter.md`) is a live example: the worktree's own megaplan
ran as the engine and editable-install fixes didn't apply — exactly the recursion biting already.

**Why our process was blind.** Self-reference was scoped as a **technical** risk (will the migration
corrupt state?) and answered with a technical control (pin the engine, run oracles). The *human*
multiplier — that recursion makes every milestone high-attention and non-parallelizable for a solo
operator — was never converted into a calendar cost, because the calendar has no owner in a design
doc. "Pin the engine" is cheap to *write* and expensive to *live every day for a quarter.*

**If true.** Estimate the epic in **founder-attention-weeks**, not milestones, and apply a large
multiplier for self-reference and solo non-delegability. If the honest number is "this eats ~a full
quarter of the only person who can also sell the product," that alone may flip the bet (see UU-2).
At minimum, sequence so the **least self-referential, highest-external-value** work (the calibration
playbook, the GTM, a clean *private* boundary) comes first, and the deeply recursive engine surgery
(M3/M5c, evicting STATE_* from the control plane) is gated on whether the SDK bet is still live by
the time you get there.

**Severity: would-reshape.**

---

## The single biggest REFRAME this vantage suggests

**Stop treating this as an engineering epic ("turn the planner into a well-designed SDK") and treat
it as a founder's portfolio bet under bus-factor-1 ("what is the highest-leverage use of the only
person's next quarter?"). Under that lens the epic is the *wrong shape*: it spends a non-renewable
solo quarter converting a *validated vertical product* into a *commodity horizontal framework*,
taking on an *unbounded, non-revenue-generating support liability*, while leaving the *actual moat*
(calibration judgment) trapped in one undocumented head and the *actual market* (35×-cheaper coding)
unsold.** The composability goal is real but *premature*: an SDK should be **pulled** into existence
by a paying second builder, not **pushed** by an internal aesthetic — and the prerequisite to any
durable version of this company is **transferring the calibration moat out of one person's head**,
which is a smaller, cheaper, more urgent project than the 10-milestone extraction. The honest
re-sequence: (1) write down + automate the routing-calibration playbook (de-risk bus-factor); (2)
do the *minimal private* internal-boundary cleanup that speeds the founder's own velocity (~1–2
weeks, not 10 milestones); (3) sell the routing-and-robustness product and find the real second
builder; (4) let *their* demand define the public SDK surface — at which point you also have the
revenue or the headcount to carry the maintenance liability the epic currently hands, unfunded, to
a sample size of one.
