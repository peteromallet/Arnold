# C — megaplan-decision SKILL.md audit (over-tiering of mechanical milestones)

Scope: the mechanical, behavior-preserving milestones (m4-naming, m5b/c/d
decomposition, m6a/b) that ran with premium GPT-5.x/Opus **drivers** (plan /
loop_plan / review / tiebreakers) when a cheap-driver `solo` behind the green M0
characterization gate would have done. `directed`+ all drive `plan` on `claude:low`
(directed.toml:31,39,42-43); only `solo` drives on DeepSeek (solo.toml:29-41).

## (a) The verbatim misleading lines + why each misled here

**SKILL.md:41** —
> "Deliverables with different stakes — high-stakes infra warrants its own sprint,
> at a higher tier; bundling it with cheap work either over-pays for the cheap work
> or under-protects the expensive part."

**SKILL.md:46** —
> "**But: one profile per sprint.** Within a sprint, pick the profile that matches
> the **highest-stakes deliverable** — lower-stakes items inherit the tier."

**SKILL.md:84 (tier-4 `premium` row)** —
> "Schema definitions, wire formats, security-critical code paths ... migration logic
> against production data, kernel-invariant changes."

**SKILL.md:153 (`thorough`)** —
> "Security, data migration, public API contract — anything where a regression =
> production incident."

Why each misled **here**:

- **:46** is the load-bearing error. Each hardening milestone IS a sprint in a
  chain, so "one profile per sprint, by the highest-stakes deliverable" tells the
  author to tier *each milestone* by its worst-case content. But these milestones
  were already split per-front (m4, m5b/c/d, m6a/b are independent), so there was
  no expensive deliverable to inherit from — yet the rule's framing ("match the
  highest-stakes deliverable") anchored every milestone to STAKES, not difficulty.
- **:41** legitimized the whole stakes lens: it says stakes is the axis you split
  on and that higher stakes -> higher tier. Applied to "this is the core state
  machine, a regression is bad" it reads as "-> premium tier," ignoring that the
  M0 gate makes a regression *cheaply detectable*, not *catastrophic*.
- **:84 / :153** are written around CONSEQUENCE ("regression = production incident",
  "kernel-invariant"). The hardening work touches exactly those nouns (store,
  state machine, dispatch), so pattern-matching on the noun pulls the author to
  tier 4 / thorough — even though the *driver's decision* is "rename intact files"
  or "move code, re-export." The driver tier scales orchestration difficulty; these
  rows scale blast radius. The conflation is the flawed mental model: **stakes ==
  tier**, i.e. "important/dangerous milestone -> premium driver."

## (b) The counter-guidance, and why it lost

The correct rule IS present, three times:

- **:82 (directed row)** — "Drop down to `solo` when the plan is obvious — DeepSeek
  can plan mechanical work just fine."
- **:84 (premium row)** — "decision-difficulty alone doesn't justify tier 4."
- **:81 (solo row)** — solo is *for* "mechanical refactors, ... config changes ...
  anything where patterns are stable"; solo.toml:11-13 repeats "don't over-reach."
- **:22** — "The dials measure residual complexity, not nominal scope. Discount for
  decisions already made."

Why it lost:

1. **It's buried inside the tier rows** as a parenthetical "drop down" caveat, while
   the stakes framing is promoted to a top-level sizing heading ("Signs you should
   split", "But: one profile per sprint") that the author reads *first*, at the
   sizing step — before they ever reach the tier table.
2. **It's weaker / hedged.** :82/:84 are one-clause asides; :41/:46 are bolded
   rules. The counter-rule never names the decisive fact here: *an objective gate
   backstops behavior-preserving work.* :22's "residual complexity" is abstract;
   nothing connects it to "a green characterization gate = the safety net, so the
   driver tier need not be."
3. **It's contradicted by :46.** "Match the highest-stakes deliverable; lower-stakes
   inherit" directly opposes "drop to solo when the plan is obvious." When two rules
   conflict, the bolded sizing rule wins. The author let the store-risk tier set the
   tone and never exercised the documented permission (:46) to split cheap work down
   — even though it applied (substantial, independent decomposition fronts).

## (c) Docs-fix vs code-fix boundary

Two distinct defects; the doc fix and the code fix address different ones.

- **What docs CAN fix (the policy/selection defect):** the author had `solo` and a
  green M0 gate available and chose `directed`+ anyway. That is a *selection* error
  the skill caused and the skill can correct — a clear "behavior-preserving + objective
  gate -> cheap driver" rule, applied *per milestone*, removes the over-tier entirely
  for this epic. **This epic's over-tiering is fully fixable in docs**: every offending
  milestone could have been `solo` by hand.

- **What docs CANNOT fix (the capability/granularity defect):** the driver tier is
  chosen **once per milestone** and is uniform across all of a milestone's turns
  (overtier-resolution.md §2-3; overtier-architecture.md §1-2). Per-*difficulty*
  routing exists but is consumed only by the **execute worker** (`tier_models.execute`,
  execute.py:149-154, batch.py:527-537); plan/critique/review drivers ignore it.
  So docs cannot make a *single* milestone that contains both a hard decision and
  mechanical turns drive cheap on the easy turns and premium on the hard one — that
  needs the wiring (extend `tier_models.<phase>` consumption into `resolve_agent_mode`,
  _impl.py:2313 / shared.py:219; the schema already validates non-execute phases per
  overtier-architecture.md §4).

**The line:** docs fix *coarse, per-milestone* over-tiering when the whole milestone
is mechanical behind a gate (this epic). Code is required only for *intra-milestone*
difficulty mixing — driving cheap on the easy turns of an otherwise-premium milestone.
The doc fix is the high-leverage one now; the code fix is the long-tail refinement.

## (d) Proposed concrete SKILL.md edit

Add a bolded decision-rule **immediately after :46** (the rule it qualifies), so the
counter-guidance sits next to the stakes rule that currently overrides it:

> **The driver tier tracks decision DIFFICULTY, not stakes — especially behind an
> objective gate.** Stakes decide *robustness* and the *execute routing ceiling*; they
> do NOT by themselves justify a premium **driver** (plan/critique/review). When the
> work is **behavior-preserving** (renames, file splits, re-exports, mechanical
> refactors) **and an objective gate backstops behavior** (characterization tests, a
> green e2e baseline, exact-count gates), default the driver to **`solo`** — the gate
> is the safety net, not the driver tier. A high-stakes *noun* (store, schema, state
> machine) does not raise the tier if the *decision* is "move code, keep behavior" and
> a test proves it. Only keep a premium driver on the milestone(s) where the planner
> must make a genuinely novel or cross-cutting decision. In a split epic this is the
> common case, not the exception: tier each milestone by its own decision difficulty,
> not by the riskiest milestone in the chain.

Then soften the conflicting clause in **:46** from "lower-stakes items inherit the
tier" to: "lower-stakes items inherit the tier *only within a single sprint you chose
not to split*; once split into per-front milestones, tier each on its own difficulty
(see the difficulty-not-stakes rule above)."

Optionally cross-link from the tier-4 row (:84) caveat: change "decision-difficulty
alone doesn't justify tier 4" to "decision-difficulty alone doesn't justify tier 4 —
and high stakes alone don't justify a premium *driver*; behind a green gate, mechanical
work drops to `solo` regardless of the noun it touches."
