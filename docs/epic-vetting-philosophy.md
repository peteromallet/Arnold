# Epic vetting philosophy

How to pressure-test a large design/epic *before* building it — distilled from vetting the
planning-unification epic (worked example: `briefs/pipeline-unification-planning-as-pack.md`; tracked
as ticket `01KSAWQFZBJMXE6JHXN01PJ5SR`). The aim is a plan that's robust because its premises and its
load-bearing facts have both been attacked, not because it's long.

## The failure mode this prevents

Big plans rarely fail for lack of detail. They fail two other ways:
1. **Unexamined premises** — the whole effort rests on a goal or framing nobody challenged.
2. **Confidently-wrong specifics** — the document states things as fact ("X silently corrupts
   state", "Y is the signal Z reads") that are plausible, cited, and *false*, and the plan inherits
   their danger weighting.

Vetting has to catch both. They need different techniques.

## 1. Critique at escalating levels of abstraction

Run separate critique passes, each at one level, each with its own lens — don't blend them. A single
"review this" prompt collapses into vague mush. The levels, roughly outermost to innermost:

- **Premise / ROI** — should this exist at all? What's the cheapest thing that captures most of the
  value? (The skeptic. Always include one.)
- **End-state / architecture** — is the target shape right? Is it the right abstraction, or symmetry
  for its own sake?
- **Mechanism** — is the chosen approach (the specific pattern/API) sound, or does it just relocate
  the problem?
- **Capability / inventory** — what actually has to move/exist? The full bill of materials.
- **Implementation landmines** — what breaks in practice: state, observability, hidden consumers,
  blast radius.
- **Sequencing** — what order, what's reversible, where are the shippable checkpoints.
- **Sizing / pre-mortem / rollout** — how big really; how does it fail; how does it ship under version
  skew.

Give each agent **only its lens** and tell it to take a position and not hedge. For a multi-lens
review of one artifact, never show one agent's output to another — independence is the value.

## 2. Use multi-model juries for the subtle, high-stakes calls

For a hard-to-reverse architecture call or a spicy judgment, send the *same* prompt to several model
families in parallel (e.g. DeepSeek + Claude + Kimi; Codex when available). **Convergence across
families is real confidence; divergence is the signal to dig.** Reserve juries for the calls that
deserve them — don't fan out routine lookups.

Match model to task: cheapest capable model for fact-finding/inventory; a reasoning model for
"is this sound"; the frontier only for genuine multi-step subtlety. A reasoning model handed a
mechanical brief will refactor; a non-reasoning model handed an architectural brief will execute
fragments blindly. Match brief *shape* to model *mode*.

## 3. Don't overcorrect (the integrator's discipline)

This is the part that's easy to get wrong, because accepting feedback *feels* like diligence.

- **Accepting a critique is itself a decision that can be wrong.** A near-zero rejection rate is a
  red flag, not a sign of thoroughness. If you fold in every finding, you're not integrating, you're
  transcribing.
- **Corrections can overshoot.** In this epic, an agent rightly flagged that a "drift" justification
  was overstated; the fix swung to "drift is trivial, it's a wrapper of itself" — which a later
  verification pass found was *also* wrong (real divergence vectors existed). One eager acceptance
  bred an eager over-correction. Watch for the pendulum.
- **Rhetorical inflation is contagious.** Calling every finding "killer" / "high signal" manufactures
  false confidence. Report findings flatly; let weight come from evidence.
- **Decisions stay with the owner.** Surface the genuine forks as choices; don't auto-flip the plan
  because the last agent was persuasive. When a critique re-challenges a settled decision, present it
  as dissent to weigh — especially if new information (e.g. sizing) emerged — but don't quietly
  reverse course.

## 4. Separate the load-bearing claims — then verify them alone

Critique tests *reasoning*. It does not reliably test *facts*. After the document stabilizes:

1. **Extract the load-bearing claims** — the falsifiable, usually code-level assertions the plan
   would break without ("the bridge drops non-allowlisted keys", "auto routes on file X", "only one
   consumer writes this state"). Aim for the ~10 the whole structure rests on.
2. **Verify each one independently**, one agent per claim, against the real source — *not* bundled
   into a critique. Verification is a different job from critique and must be isolated from it.

In this epic that pass found: of 10 load-bearing claims, **3 were clean, 1 overstated, 5 partial, 1
contradicted** — and the single most-cited "deepest hazard" was substantially overblown. None of the
abstraction-level critiques caught these; only direct verification did.

## 5. Citations are not framings — verify the framing

Subagent **file:line citations were reliable**; their **severity/danger framings were not**. "The
allowlist drops keys" (true) became "silent state corruption / zombie plans" (false — disk
persistence preserved the data). So: trust a located fact more than its interpretation, and verify
the *interpretation* before you let it set the plan's risk weighting.

## 6. Write briefs that investigate, not briefs that confirm

A verification brief framed as *"CLAIM: X is true. Verify."* with confirm-weighted verdict options
**leads the witness** — a reasoning model will find what it's told to find. That's the same eagerness
bug, one level up. Instead:

- **Investigate the neutral question first** ("How does the bridge compute the patch? Which keys
  propagate?"), *then* present the assertion as a hypothesis to break.
- **Make refutation a first-class, valued outcome** ("a CONTRADICTED finding is as valuable as a
  confirmation; do not assume the claim is true").
- **Treat cited line numbers as suspect** — have the agent report the *actual* current location.
- Use a neutral verdict scale (SUPPORTED / CONTRADICTED / PARTIAL / CANNOT-DETERMINE), not three
  flavors of "true".

## 7. Consolidate, and know when to stop

- **Consolidate periodically.** Appending each wave grows a document by accretion; every few passes,
  rewrite it top-to-bottom into one coherent spec so contradictions surface and dead weight is cut.
- **Diminishing returns are real.** Abstraction-level critique saturates. When the remaining
  uncertainty is *empirical* (does the approach actually work in code?) rather than *analytical*
  (is the reasoning sound?), more agents won't help — switch modes.

## 8. The switch: from vetting to the cheapest falsifying experiment

The endpoint of vetting is not a perfect document — it's knowing the smallest thing you could build
that would *falsify the plan if it's wrong*. Usually that's the load-bearing safety mechanism plus
one vertical slice. Building it validates feasibility, the sizing estimate, and the riskiest
assumption at once, and converts the plan from analysis into evidence. Vet until the open questions
are empirical; then go run the experiment.

---

### Checklist

- [ ] One skeptic challenging the premise/ROI at full scope.
- [ ] A critique pass per abstraction level, each its own lens, agents independent.
- [ ] Multi-model jury on the few hard-to-reverse calls.
- [ ] Forks surfaced to the owner; no silent reversals; watch for over-correction.
- [ ] Document consolidated into one coherent spec.
- [ ] Load-bearing claims extracted and **separately, falsification-first** verified.
- [ ] Framings (not just citations) checked; risk weightings corrected.
- [ ] Stop when remaining uncertainty is empirical → build the smallest falsifying slice.
