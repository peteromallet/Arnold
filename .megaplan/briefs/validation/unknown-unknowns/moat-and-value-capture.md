# Unknown-Unknowns — Moat & Value Capture (Strategy vantage)

Vantage: I am not auditing Arnold's internals. I stand in the position of an investor /
competitor / strategist asking one question the epic never asks: **if composable agent
orchestration is commoditizing, what does only Arnold have — and does turning it into a
free SDK strengthen or dilute that?** Sibling briefs already cover the framework landscape
(LangGraph/CrewAI/MCP commoditization) and ecosystem dynamics. This brief attacks a
different seam: **the SDK plan may be extracting the one genuinely scarce asset and giving
it away as a "teaching example," while keeping and dressing up the commodity.**

Grounding read: `docs/megaplan-intro-v2.md` (the public value story), the EPIC framing
(`.megaplan/briefs/pipeline-unification-EPIC.md`), `m6-megaplan-as-module.md`, `m7-builder-docs.md`,
and the two sibling landscape briefs.

---

## The contradiction the frame can't see

Two documents describe the same project and disagree about where the value is.

- **`docs/megaplan-intro-v2.md`** — the thing Peter actually shows the world — says the
  value is: *move >90% of coding to DeepSeek at ~2.5% of the cost, without losing
  robustness, because a frontier model scores each task's difficulty 1–5 and routes the
  cheapest-capable model at every step, and the harness ENFORCES research/critique/tests
  a raw model skips.* That is a **vertical product claim** about money and reliability.
  The proof is a real invoice ($12 vs $422) and an enforced PEV loop. Composability
  appears in exactly one sentence at the end ("built on Arnold... assemble your own").

- **The EPIC + `m6`/`m7`** say the value is: *composability* — Arnold is a builder SDK of
  pieces, success = "a fourth builder ships a fourth thing cheaply," planning "becomes a
  module like any other," and the load-bearing acceptance test is a **non-planning** tool
  (a `select`-tournament, a bisect) built with **zero planning vocabulary** in it.

These are not two views of one strategy. They are two different companies. The intro sells
**routing intelligence + enforced robustness as a moat**; the epic's stated success
criterion is to prove that an *unrelated, non-planning* builder can succeed *without ever
touching* the routing/planning intelligence. The epic is optimizing to make the thing the
intro sells **subtractable from** and **invisible inside** the artifact. The whole prior
investigation took "value = composability" for granted (it is the first line of the EPIC),
so no pass ever asked whether composability is the asset or the giveaway.

---

## UU-1 — We are extracting the moat and shipping it as "example #3"

**Insight.** The genuinely scarce, hard-to-copy asset here is **not** the node library and
**not** the drivers. It is the *judgment layer*: the finalize-stage difficulty scoring
(1–5), the routing policy that maps difficulty→cheapest-capable model, the rater≥dispatchee
guarantees, the tier maps, the robustness presets, the critique-lens selection — the
accumulated, dogfooded, evidence-backed *operating knowledge of when a cheap model is safe*.
That knowledge is what produced a $12 invoice on store-surgery that "should" need a frontier
model. The pieces (produce/judge/gate/fan_out) are commodity — LangGraph, the OpenAI Agents
SDK, and a hundred forks have equivalents. The M6/M7 plan **deliberately demotes the moat to
"planning content / thinnest possible bindings"** and elevates the commodity (the pieces) to
"the SDK, the product." Worse, M7's acceptance test treats the routing intelligence as
something a real builder should be able to *grep out and never see* ("no planning
vocabulary"). We are taking the one asset competitors cannot cheaply reproduce — because it
took months of real-money dogfooding to calibrate — relabeling it "the planning package's
private content," and structuring the whole release so that asset is the *example*, not the
*product*. An "SDK example" is, by definition, the thing you give away to teach people to
build the thing you actually sell. We have it backwards.

**Why the process was blind.** Every prior pass accepted "value = composability" as the
goal line (EPIC line 1). The discipline test — *"would an unrelated builder want this? →
SDK; planning-only → stays in the app"* — is a **moat-destruction machine when applied to
intelligence**: it systematically routes anything reusable into the free SDK and anything
defensible (because it's specific, tuned, and earned) into the "stays put, it's just app
content" bucket. The test was designed to find clean abstractions; it cannot perceive that
the clean-abstraction layer is the commodity and the "messy app-specific content" is the
moat. Nobody asked "of the things we're sorting, which one would a competitor pay to copy?"

**If true.** Redirect. The SDK should expose the pieces but keep the *routing-and-robustness
calibration* as the differentiated, possibly-not-fully-open layer — the "LangSmith of
cheapest-capable routing." The acceptance test ("a non-planning tool with zero planning
vocab") is then proving the *wrong* thing: it proves the giveaway is general, not that the
moat is defensible. At minimum, the public framing (intro-v2) and the build framing (epic)
must be reconciled: pick whether Arnold is a *router product with an SDK underneath* or an
*SDK with a router example on top* — they imply opposite roadmaps, opposite acceptance
tests, and opposite things-to-open-source.

**Severity: would-redirect.**

---

## UU-2 — "A fourth builder ships a fourth thing" is the wrong success metric; the moat is a benchmark, not a build

**Insight.** The epic's definition of success is **supply-side and one-time**: can a third
party *build* a module. Every dead agent-framework (sibling brief: the graveyard) could be
built on — buildability was never the constraint. The thing that would actually be
defensible and valuable is **demand-side and continuous**: a *living, published,
adversarially-maintained benchmark of which model is cheapest-capable for which task class,
at today's prices.* That asset compounds: every dogfooded run adds calibration data; model
prices and capabilities churn weekly (the intro itself notes "subsidised shifting-sand");
whoever owns the most-current "DeepSeek can now safely do X, Opus still required for Y" map
owns the routing decision the whole pitch rests on. Arnold is *uniquely positioned* to own
this — it already runs the experiments — but the SDK frame treats each run as a private
event that produces a module, not as a data point in a public, defensible index. We are
sitting on a routing-calibration dataset and a measurement methodology and choosing to ship
a node library instead.

**Why the process was blind.** The frame fixed "the unit is a pipeline (DAG/loop)" and "the
builder is a developer." Both lock attention on the *artifact a developer produces*. Neither
can see that the durable asset might be **the accumulated knowledge across all runs**, not
any single pipeline — i.e., the value accrues to whoever aggregates, not to the toolmaker.
DSPy already reframed this one layer over (sibling brief: "optimization/learning over a
program, not hand-wired graphs"); Arnold's equivalent reframe — *the optimizer is the
cheapest-capable-routing policy, and it should learn from every run* — is invisible because
"learning/aggregation" isn't in the pieces-and-drivers vocabulary at all.

**If true.** Reshape. The roadmap gains a missing pillar: capture routing outcomes (did the
cheap model's work survive review? did finalize's 1–5 score predict the actual escalation?)
as a feedback signal that improves the policy and ideally becomes a public, citeable
"cheapest-capable model index." Self-improving harnesses already exist (sibling brief:
Live-SWE-agent, self-evolving). Arnold's routing policy being *static and hand-tuned* while
the whole pitch is "the frontier model judges difficulty" is the gap: the judgment never
learns from whether it was right.

**Severity: would-reshape.**

---

## UU-3 — Open-sourcing the enforced-robustness layer arms the people who profit from cheap-token volume to commoditize you

**Insight.** Follow the money one hop out. The intro's claim is "you can move 90% of spend
off frontier models onto DeepSeek." The parties who *most* want that claim to be true and
turnkey are: (a) the cheap-model providers (DeepSeek, Moonshot/Kimi, Zhipu) who win every
token moved their way, and (b) the inference aggregators (OpenRouter, Together, Fireworks).
For them, "the enforced harness that makes it *safe* to route to cheap models" is the
missing adoption-unlock for their entire business — and Arnold is open-sourcing exactly
that, MIT-style, with no reciprocity. The most likely outcome is not "a community of
builders ships modules"; it's that **a well-capitalized party who profits from cheap-token
volume absorbs the routing-and-robustness layer into their own offering** (a button in
OpenRouter, a mode in a coding IDE, a feature in DeepSeek's own tooling) and Arnold becomes
upstream plumbing with no capture. The SDK plan accelerates this by making the layer maximally
extractable, documented, and generically composed — the M7 docs are, from this angle, an
integration manual for your own disintermediation.

**Why the process was blind.** The epic models the outside world as *cooperative builders*
("other people build on the same pieces"). It never models *adversarial absorbers* —
parties whose interest is to ingest the free layer and capture the value downstream. The
plugin-ecosystem sibling brief gets close ("community builds it is a myth; a few people
write 90%") but stays inside the cooperative frame. The competitive-dynamics question —
*who eats this if it's free, and do they have more distribution than us?* — was never on any
checklist because the frame assumed the threat was technical (will it compose?) not
strategic (will someone with a billion users copy the one good idea?).

**If true.** Worth-knowing → reshapes licensing/positioning. Consider: keep the pieces
permissive but the *routing policy + calibration + enforced-PEV presets* under a
source-available / non-compete / "open-core" boundary; or move fast to own distribution
(the index in UU-2, a hosted runner, a brand) before the layer is absorbed. The naive-MIT
default for the whole stack is the highest-disintermediation-risk choice available.

**Severity: would-reshape.**

---

## UU-4 — "Megaplan becomes a module like any other" may destroy the only thing that makes the SDK adoptable: the proof it works on real money

**Insight.** Why would a developer adopt Arnold over LangGraph (34M downloads, LangSmith,
enterprise default)? Not for the pieces — those are at parity or behind. The *only*
non-commodity reason in the entire corpus is the intro's evidence: **a real, audited, on-a-
real-codebase demonstration that this specific harness moved 90% of work to a model 35×
cheaper without regression.** That credibility lives entirely in megaplan-the-planning-app
being a *flagship, deeply-tuned, battle-scarred* application — the proof artifact. The epic's
explicit goal is to **strip megaplan of all privilege and reduce it to "thinnest possible
bindings + content," discovered identically to a jokes-telling toy.** That is structurally
the act of *demoting your flagship to a sample app.* The SDK's adoption story is "look what
megaplan did"; the SDK's build plan is "make megaplan indistinguishable from `jokes`." A
sample app cannot carry a moat. The more successfully M6 achieves "planning reads as just
another composition," the *less* the planning result reads as a hard-won, defensible
capability and the more it reads as "an obvious thing the pieces make easy" — which invites
the reader to skip Arnold and wire the obvious thing themselves (the 12-factor-agents
doctrine the sibling brief flags: "own your control flow in plain code").

**Why the process was blind.** "No privilege, no exit, no opportunistic adoption" was
adopted as an *architectural purity* goal (a beautiful, true engineering instinct: kill the
special case). The process evaluated it only on the inside-the-frame axis — is the code
cleaner, is discovery uniform — and that axis says unambiguously *yes, demote it.* The
strategic axis — *is our credibility asset a special case we should protect, not erase?* —
is orthogonal to architecture and was never in scope. Architectural purity and strategic
value can point in opposite directions, and the frame only had the architectural ruler.

**If true.** Reshape. Decouple the architecture from the positioning: megaplan can be
*technically* a discovered module **and** still be the privileged flagship in every
docs/marketing/benchmark surface — but the epic currently conflates "no code privilege" with
"no special status," and M7's "zero planning vocabulary" test actively pushes builders away
from the flagship. Keep the demotion in code; reverse it in narrative; and treat the
real-money proof as a first-class, continuously-refreshed asset (ties to UU-2's index), not
a one-off blog post about a thing you then dissolved.

**Severity: would-reshape.**

---

## THE single biggest REFRAME

**We have inverted product and example.** Arnold is being built as *an SDK of composable
pieces (the product) with a cheapest-capable-routing harness as its showcase module (the
example).* The evidence — the only thing that makes anyone care, the only thing competitors
can't cheaply copy, the only thing tied to real money — says it is the reverse: **the
product is the cheapest-capable-routing-with-enforced-robustness intelligence (and the
living calibration of *when a cheap model is safe*); the composable pieces are the
commodity substrate it happens to be built on.** The epic's success metric ("a fourth,
non-planning builder ships cheaply, with zero planning vocabulary") is therefore a metric
for *how completely we've extracted and given away the moat and dressed up the commodity.*

The reframe: **stop asking "can someone build a fourth thing on the pieces?" and start
asking "what does only Arnold know, does the artifact still carry that knowledge after M6,
and who captures the value when it's free?"** Today the honest answers are: *the routing
calibration*; *no — M6/M7 deliberately make the artifact carry zero of it*; and *whoever has
more distribution than us absorbs it.* The pieces should still be open and composable — that
is good engineering and a fine on-ramp. But the strategy must be organized around the
intelligence and the proof, not around the composability. Pick the company: a router/
robustness product with an SDK underneath, or an SDK with a router example on top. The epic
silently chose the second; the intro is selling the first; that gap is the strategic
unknown-unknown this whole effort was structurally unable to see.
