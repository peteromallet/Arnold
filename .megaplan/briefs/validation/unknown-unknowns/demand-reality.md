# Unknown-Unknowns — the DEMAND vantage: is the builder imaginary?

**Vantage:** Steelman that NOBODY builds modules. The entire epic rests on one sentence Peter wrote at the
top of the EPIC: *"Other people build on the same pieces to CREATE new things."* Every milestone, every
validation pass, every premortem inherits that as an axiom. This brief attacks it from outside. Not "can a
builder adopt" (plugin-ecosystem-patterns, node-graph-ecosystems own that) and not "is the category
crowded" (agent-framework-landscape owns that) — but **does the want for an SDK exist at all, and for
whom?** Is this a build-it-and-they-won't-come trap?

**Status:** adversarial, 2026-05-29. Evidence is from the repo itself, not opinion.

---

## The structural blindness, stated plainly

I grepped the **entire** `.megaplan/briefs/validation/**` corpus for any form of the demand-existence question —
`no one will build`, `imaginary demand`, `do people even want`, `who would use`, `market for`,
`product-market`, `are there other users/builders`, `finished tool vs SDK`. **Zero hits.** The corpus is
enormous and ferociously rigorous: c1–c7, s1–s4, u1–u2, eight premortems, eleven confidence docs, ten
interrogation lenses, four decision docs, six prior unknown-unknowns. Not one of them asks whether the
demand is real. They all start *after* "yes" and ask "given builders arrive, is the abstraction right / is
it safe / can it scale / is it the right substrate."

Why the process was blind: **the demand axiom was authored, not investigated.** It is the one premise in
the entire program that was never assigned an evidence doc, because it was the *frame* every evidence doc
was commissioned inside. You cannot commission an adversary against your own definition of success when
that definition is what tells the adversary what "success" means. The interrogation lens called
"success-second-order" is the tell: it explicitly says *"Assume the epic ships at full ambition and
succeeds: third parties compose the same SDK pieces…"* — it spends its entire rigor on the **problems of
success** and never once prices the **probability of success**.

---

## The hard evidence (from the repo, not theory)

I checked who has ever actually built a "module / pipeline pack" on these pieces:

- `git log --format='%an' -- megaplan/pipelines/` → **7 commits, 100% `POM`.**
- Every pack that exists — `creative`, `doc`, `epic_blitz`, `writing_panel_strict`, and `planning` itself —
  was authored by **Peter, and only Peter.**
- `resident`, the *second* of the "two seed apps" the entire keystone reframe is triangulated from
  (`EPIC:14,18,21,31,41`), is **4,201 lines, 100% authored by POM**, and — critically — **it does not
  compose the pipeline SDK at all.** Its imports are `megaplan.store`, `megaplan.control`,
  `megaplan.editorial`, `megaplan.cloud.cli`, `megaplan.types`. It is a *consumer of megaplan's ordinary
  utility modules*, not a *composer of produce/judge/gate/fan_out pieces*. `resident_exports/` is empty.

So the load-bearing "diversity between two apps = the menu of backends" insight (EPIC §"framing") reduces
to: **one person reused his own libraries to build a second thing.** That is not evidence of SDK demand. It
is evidence that a Python codebase lets you `import` your own code — which is true of every codebase and
requires no epic. The N=2 that the keystone leans on is N=1 (Peter) building 2 things, and the second thing
isn't even on the SDK path the epic is designed to create.

**Net:** across the most rigorously-validated plan in this repo's history, the population of demonstrated
builders-who-are-not-Peter is exactly **zero**, and the population of things-built-by-composing-the-pieces-
that-Peter-didn't-build is exactly **zero**. The demand is, at this moment, literally imaginary in the
strict sense: it exists only in the EPIC's opening sentence.

---

## UNKNOWN-UNKNOWN 1 — The job-to-be-done is "Peter ships tools fast," not "others build modules." The SDK is being built for a user who doesn't exist to serve a need that's actually Peter's own. (would-redirect)

**Insight.** Strip the aspirational sentence and look at revealed behavior: every artifact in this repo is
Peter building finished tools (megaplan, resident, the cost subcommand, cloud, the epic harness) and
*reusing his own code* to do it faster. The actual, demonstrated job-to-be-done is **"let one expert
(Peter) ship the next tool with less reinvention."** That is a real, valuable job — but it is satisfied by
*internal consolidation and good module hygiene*, NOT by a public SDK with a trust boundary, an
`arnold_api_version`, SemVer'd node signatures, manifest-first discovery of untrusted third-party packages,
per-tenant quota partitioning, and "an external builder ships a fourth thing cheaply." Roughly half the
milestone program (M5c control plane, M5d supervisor tier, M6 trust boundary, much of M4's multi-tenancy)
exists **only** to serve the imaginary external builder. If the JTBD is "Peter ships faster," that half is
overhead that makes Peter ship *slower*.

**Why we were blind.** The aspiration ("others build") and the behavior ("Peter consolidates") were never
separated, because the person who wrote the aspiration is the person whose behavior would have falsified
it, and he was also the person commissioning the validation. The reframe "what does a *new builder* need?"
felt like rigor but was actually the moment the imaginary user was installed as the design authority,
displacing the only real user (Peter himself).

**If true.** Cut the epic to its Peter-serving core: M1 (hygiene/contract-checker — useful to anyone),
M2 (de-planning the types — pays off the first time Peter writes pack #6 regardless of externals), and the
node-library decouplings. **Defer or delete everything justified solely by "external builders":** the trust
boundary, manifest-first untrusted discovery, API versioning, per-package quota isolation, the supervisor
tier as a *public* surface. This is not a 10% trim; it is a different epic, maybe 40–50% smaller, that
ships in weeks and is fully validated by Peter building his next tool on it.

---

## UNKNOWN-UNKNOWN 2 — "Compose your own agent pipeline" has a near-zero-size audience, and that audience self-hand-rolls. The unit of demand is a FINISHED tool, not a kit. (would-reshape)

**Insight.** First-principles on who could even be the buyer: to want Arnold you must (a) be building an
LLM-agent tool, (b) be a Python developer comfortable composing typed pipeline pieces in code, (c) find
megaplan's plan→critique→execute→review shape close enough to your problem to adopt its pieces, yet (d) not
so close that you'd just *use megaplan*, and (e) not so far that you'd reach for LangGraph/Temporal/the
OpenAI Agents SDK (which the agent-framework brief shows are commoditized and free). The intersection of
those five filters is a sliver — and crucially, **everyone in that sliver is exactly the kind of expert who
hand-rolls.** The defining trait of someone who wants composable primitives is that they are skilled enough
not to need yours. This is the classic library paradox: the people sophisticated enough to adopt your
abstraction are sophisticated enough to have already built their own, and the people who can't build their
own want a *finished product*, not a kit. ComfyUI's lesson (node-graph brief) is the same from the other
side: its adoption came from artists who wanted *outputs*, served by a visual canvas and one-click installs
— not from developers wanting "composability of nodes in code," which is precisely Arnold's pitch.

**Why we were blind.** Peter is himself the sliver — expert, Python-native, building agent tools. The
process used him as the prototype user without noticing that *being the prototype user means the audience is
people exactly like the author*, which is the smallest and least-needy market there is. The plan optimized
the composition DX (interrogation/composition-DX.md) to a high polish for a user whose existence is the
unexamined assumption.

**If true.** The output that has demand is **the finished tools** — megaplan, resident, epic-harness — sold
or distributed as *products*, with the pieces kept as a **private internal library** (Peter's force
multiplier), never a public SDK. "Arnold the SDK" should be reframed as "Arnold the internal kit that lets
*us* ship more finished tools faster," and the public artifact should be a tool catalog, not a primitive
library. The entire builder-docs milestone (M7) is then aimed at the wrong reader.

---

## UNKNOWN-UNKNOWN 3 — There is a cheap, decisive demand test available RIGHT NOW, and the fact that it was never run is itself the strongest evidence demand is weak. (would-redirect)

**Insight.** You do not need to ship the epic to test the demand. The test is: **get one real
non-Peter person to build one real thing by composing the existing pieces** — today, on the pre-epic
codebase, which already has `build_pipeline`, discovery, a node library (`patterns.py`), and five example
packs. If that is hard to arrange — if there is no one to ask, or the one person you ask bounces off or
just uses LangGraph — that *is the finding*, and it cost a day, not months. The asymmetry is brutal: the
epic is a multi-week, ~10-milestone, trust-boundary-and-versioning program premised on builders arriving;
the test that would tell you whether builders exist is a single afternoon of watching one outsider try.
**The plan spent enormous validation effort on whether the abstraction is *correct* and ~none on whether
anyone *wants* it.** In a startup frame this is the canonical inversion: heavy build-validation, zero
demand-validation, for a two-sided product (you + builders) where you only control one side.

**Why we were blind.** The validation machinery the team is good at — premortems, confidence docs,
interrogation lenses — all operate on *the artifact*. There is no machinery in this repo for *customer
discovery*, because the repo's whole culture is "harden the plan." A demand test isn't a `pytest` you can
run, so it was never on the board. The absence of even an attempt to recruit a second builder, in a
months-long program explicitly *for* second builders, is the loudest signal in the whole corpus.

**If true.** Insert a **demand gate before M2** (the keystone, the point of no return where types get
de-planned for hypothetical external diversity). Concrete cheap tests, in ascending cost: (1) ship the M1
contract-checker + `pipelines new` scaffold *alone*, publish the SKILL.md docs, and instrument discovery —
does *one* non-Peter pack ever appear in `~/.megaplan/pipelines/`? (2) Hand a sharp friend the current repo
and a one-paragraph brief: "build a small agent tool by composing these pieces," watch where they bounce.
(3) A waitlist / "intent to build" signal. If none produce a single genuine outside build in, say, 30 days,
the keystone milestones (M5c/M5d/M6 trust+versioning) do not get built; the epic collapses to the
Peter-serving core from UU-1.

---

## The single biggest REFRAME

**Arnold is not an SDK awaiting builders; it is Peter's private force-multiplier mis-cast as a public
platform.** The demand the epic names ("others build modules") is, by the repo's own evidence, imaginary —
N=0 outside builders, N=0 pieces-composed-by-anyone-but-Peter, and the second "seed app" doesn't even use
the SDK. The real, demonstrated, valuable job-to-be-done is **"let Peter ship the next finished tool with
less reinvention,"** and that job is fully served by internal module hygiene + the type decouplings (M1,
M2, node-library) — *not* by the trust boundary, API versioning, untrusted-package discovery, and
multi-tenant quota machinery that exist only to host a builder who has never appeared and, on first
principles, occupies a near-empty market that self-hand-rolls. **So: invert the build order. Run a
one-afternoon demand test (one outsider, one build) before the keystone M2, and until a single real
external build exists, treat every "external builder" milestone as deferred.** Build the half that makes
Peter faster; let demand — not aspiration — unlock the half that makes Arnold public. The cheapest possible
experiment to de-risk a months-long epic is sitting unrun, and its very unrun-ness is the answer.
