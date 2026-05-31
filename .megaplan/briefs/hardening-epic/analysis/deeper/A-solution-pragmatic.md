# A — Pragmatic / ROI / Risk referee on critique-loop non-convergence

The other two perspectives are right about the *mechanism*. They are wrong if they
let the mechanism dictate the *build order*. This is a cost/value/risk ruling. The
governing fact from A1: across M2's 9 rounds **zero flags were disputed, zero
re-opened** — the loop was honest, just unbounded. That single fact collapses most
of the algorithmic agenda's urgency: we are not fighting a flaky critic or
re-litigation; we are fighting *no ceiling*. A ceiling is cheap. Everything else is
treating a wound that, empirically, mostly stops bleeding once you cap it.

## 1. Leverage ranking (value captured / engineering cost)

| Fix | Value | Eng cost | Ratio | Verdict |
|---|---|---|---|---|
| **Hard round cap (sev-gated action)** | very high | ~tiny (mirror `review.py:248`, count history, add 3 DEFAULTS keys) | **★★★★★** | **SHIP FIRST** |
| **No-net-progress early stop** | high | low (gate_signals already has `resolved_flags` + blocking list; 2-round window) | **★★★★☆** | **SHIP FIRST (pair)** |
| Near-last-round prompt signaling | medium | low (thread `iteration`/`max` into revise+critic prompt) | ★★★☆☆ | Phase 2 |
| Severity-gated cap *action* | (counted inside the cap — it's the cap's switch, not a separate build) | — | — | part of #1 |
| Front-loaded exhaustive enumeration | medium-high but *uncertain* | medium (lens-prompt redesign + "prove the list is closed" contract) | ★★☆☆☆ | Phase 3, data-gated |
| Diff-aware anchored re-critique | medium | **high** (per-section verdict state, carry-forward, anchoring) | ★★☆☆☆ | Phase 3, only if residual proven |
| Bounded revise churn | medium | medium (per-round delta budget, touch-only-flagged) | ★★☆☆☆ | Phase 3 |

**The 80/20 that ships first: hard cap + no-progress stop, sharing one severity-gated
exit branch.** Both hook the *same* point (`_apply_gate_outcome`, `gate.py:360-361`),
reuse the *same* predicate (`gate.py:328`), and mirror an *already-shipped* mechanism
(the review cap). One small PR. The prompt-signaling and the three algorithmic fixes
all reduce *how many rounds you spend below the cap* — they are optimizations on a
loop the cap has already made finite.

## 2. Quantify

- **M2: 9 rounds, ~1.09M premium tokens.** Tokens/round ≈ 121K. A `full` cap of 4
  stops the loop after round 4 → rounds 5–9 (5 rounds) never run ≈ **605K saved
  (~55%)**. The no-progress stop fires *earlier still*: A1 shows two concern threads
  each peeling one location/round with `resolved_delta` small and `new_blocking ≥ 1`
  most rounds — the 2-round stall window plausibly trips around round 5–6 anyway, so
  in practice the cap and the stall catch the same tail; the stall just trims a round
  or two more and protects the `thorough`/`extreme` tiers where the cap sits at 6/8.
- **M4: 8 rounds, ~450K wasted.** Cap=4 → ~half the rounds elided ≈ **~225K saved**;
  no-progress likely trims more.
- **Would cap=4 + no-progress alone catch most of it? Yes — ~55–60% of M2's burn and
  ~50%+ of M4's, for a few hours of work.** That is the bulk of the recoverable waste.
- **Residual the algorithmic fixes add:** they don't raise the ceiling's savings; they
  lower the *floor* — making rounds 1–4 each do more, so genuine convergence lands at
  round 2–3 instead of bumping the cap. Optimistically that's another **~120–240K
  (1–2 rounds) on a hard plan**, but it is *speculative* and *plan-dependent*, versus
  the cap's *guaranteed* 5-round elimination. Build the guaranteed win first; measure
  whether the speculative residual is even worth chasing.

## 3. Over-engineering guard — where to STOP

- **Diff-aware anchored re-critique is the scope-creep landmine.** It demands
  per-section verdict state, carry-forward, and an anchoring scheme — the most code,
  the most new surface to break. Worse, it carries a *correctness* risk the cap does
  not: carrying a prior PASS forward means a revise that churned 53% of the plan
  (A1's measured churn) can silently *regress a previously-passing area* that the
  anchored critic now skips. You'd be trading token cost for a class of missed
  defects — exactly the wrong trade in a *hardening* epic. If built at all, it must be
  gated on "section unchanged by this round's diff," which then leans on bounded churn
  to be meaningful. **Don't build it standalone.**
- **Front-loaded enumeration** is the most *defensible* of the three (it attacks A1's
  true root: discovery-shaped lenses peeling one location/round). But it's a prompt +
  lens-contract redesign with its own failure mode (a forced "prove the list is closed"
  step can hallucinate closure). Worth a *prompt-only* experiment, not a state-machine
  feature, until data shows the cap leaves a real residual.
- **Bounded churn** is benign but only pays off *with* diff-aware critique; alone it
  mildly speeds convergence. Low urgency.

**STOP after Phase 1 unless post-cap telemetry shows plans still routinely *hitting*
the cap with open correctness flags.** If most plans now finish at round 2–3 well
under the cap, the algorithmic fixes are solving a problem you no longer have.

## 4. Risk of the cap itself

Force-proceeding at the cap with open flags *can* ship something imperfect — that is
the point of a cap. The **severity gate is what makes it safe**: open
`significant`/`likely-significant` flags → **ESCALATE** via `override add-note`, which
under `strict_notes` stops for the human; only *cosmetic* flags get force-proceeded
with an auditable note (mirroring `review.py:248-252`). So the cap can ship a plan
with deferred *cosmetic* nits, never with an unresolved correctness/security concern.

Could a cap ship something genuinely broken? Only if the critic *mis-severities* a
real defect as cosmetic — and that exact failure already exists without the cap (the
loop would force-proceed there too, just later and 600K tokens poorer). The residual
is further backstopped by the **M0 completion contract (B)** and the **execute-review
loop**, which validate against objective evidence (diff, green-suite) downstream. The
cap operates on a *plan*, not shipped code; two evidence gates sit between it and
production. **A bounded, severity-gated, double-backstopped cap is acceptable risk.**

## 5. Recommended shipping sequence

- **Phase 1 (MUST):** Hard round cap + no-net-progress early stop, sharing one
  severity-gated exit (escalate-on-correctness / proceed-with-note-on-cosmetic). One
  PR in `_apply_gate_outcome`, 3 DEFAULTS/`_SETTABLE_NUMERIC` keys, mirror
  `review.py`. Captures ~55% of the demonstrated waste. **This is the recommended
  Phase-1 fix.**
- **Phase 2 (SHOULD):** Near-last-round prompt signaling (3 tiers) into revise *and*
  critic prompts. Cheap, no new state, lowers the average round count under the cap and
  de-fangs the "critic manufactures fresh cosmetic blockers" dynamic. Ship once Phase 1
  telemetry exists.
- **Phase 3 (NICE-TO-HAVE, data-gated):** *Only if* telemetry shows plans still hitting
  the cap with real residual. Then, in order of ROI: front-loaded enumeration
  (prompt-first), bounded revise churn, and — last and only if the prior two leave a gap
  — diff-aware anchored re-critique, with mandatory unchanged-section gating to avoid
  regressing previously-passing areas.
