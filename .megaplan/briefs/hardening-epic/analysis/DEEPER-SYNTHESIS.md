# Deeper synthesis — A (why no convergence + cap policy), B (completion contract), C (decision-skill)

Companion to ROOTCAUSE-SYNTHESIS.md. Each section reconciles the deep-dive agents.

---

## A1. Why M2's critique couldn't converge

Two forensic agents read the raw M2 rounds from different angles and *appeared* to disagree on
the dominant cause. They are two faces of ONE self-reinforcing loop:

**The dynamic (reconciled).** M2's 17 flags were not noise — they were **2 recursive concern
threads**, each peeling exactly one adjacent code location per round:
- *"enumerate all plan-run state.json writers"* → 001→005→007→012→016→017
- *"FileStore/DBStore ticket + codebase parity"* → 002→006→008→009→010→011→013→014→015

Every prior round's flags were genuinely **closed** (0 disputed, 0 re-opened across all 9 rounds) —
so it was **not** re-litigation and **not** a flaky critic. Instead, two forces compounded:

1. **Unbounded iterative discovery, no front-loaded sweep** (content agent). The `scope`/
   `all_locations` lens is *discovery-shaped*: with no "enumerate ALL writers/callers exhaustively
   NOW" requirement, it finds exactly **one more** adjacent location each pass. Round 1 actually
   spent its evidence budget *validating that its own JSON was well-formed* ("confirmed 9 populated
   checks") instead of sweeping the multi-store surface — so it under-covered from the start.
2. **Moving target + blind whole-plan re-scan** (mechanism agent). Revise answered each flag by
   rewriting **~53% of the plan every round** (mean 122 churn lines on a ~229-line plan; 9 versions,
   peak 206 lines at R7). And the critic re-evaluates the **whole** plan from scratch each round
   (`prompts/critique.py:298-299` embeds full `latest_plan`; the diff is only supplementary), with
   the lens set **re-selected from scratch** each iteration (`handlers/critique.py:208-217`) and
   prior findings re-attached *only for lenses still active that round*. So unchanged-but-churned
   sections get re-scanned blind, and "this part already passed" is never anchored.

**So "why didn't it find most stuff on the first go?"** Because nothing *forced* an exhaustive
first-pass enumeration, the one lens that mattered (scope) only ever peels one layer at a time, and
the oversized revise churn kept handing the next critic fresh surface with no memory of prior passes.
Discovery wasn't bounded *and* the target kept moving.

**Implication for the fix.** A round cap (A2) stops the *bleeding* but treats the symptom. The
*wound* needs three things the cap can't provide:
- **(i) Front-load completeness**: for scope/all_locations/callers lenses, require an exhaustive
  enumeration sweep up front ("list ALL X and prove the list is closed") rather than incremental peeling.
- **(ii) Diff-aware critique with anchored verdicts**: re-critique the *changed* sections; carry
  prior PASS verdicts forward so settled areas aren't re-scanned blind.
- **(iii) Bound revise churn**: touch-only-flagged / a per-round delta budget, so the plan stops
  being a moving target.
Caps + these three together = real convergence. Caps alone = a forced stop at round N with flags still open.

---

## A2. The cap / termination policy (proposed)

Mirrors the *existing* execute-review cap (`review.py:248`) which the plan-critique loop never got.

| Knob | Value | Rationale |
|---|---|---|
| `max_critique_iterations` | **4** (full, default) | enough for genuine multi-pass, well short of 9 |
| `max_robust_critique_iterations` | **6** (thorough) / 8 (extreme) | thorough buys more passes, not infinite |
| light / bare | 2 / 0 | bare structurally has no revise edge |
| `max_critique_no_progress` | **2** | early-stop before the hard cap |
| scaling input | **robustness only** | plan size scales the *no-progress window*, NOT the round count |

- **Tell the agent it's near the last round** — inject into the revise *and* critic prompts in 3 tiers:
  *normal* → *penultimate* ("second-to-last; prioritize correctness, stop adding scope") →
  *final* ("only resolve significant / likely-significant flags; raise no new scope"). This turns the
  existing advisory HINT (`gate_checks.py:125-129`) into an enforced, surfaced instruction.
- **At the cap, severity is the switch** (reuse the predicate at `gate.py:328`): cosmetic-only open
  flags → *force-proceed-with-note* (mirrors `review.py:248-252`); any open correctness/security flag
  → **ESCALATE** via `override add-note` (stops for the human under strict_notes). Never silently ship a correctness flag.
- **No-net-progress early stop**: 2 consecutive rounds where `resolved_delta == 0 AND new_blocking >= 1`
  → take the same severity-gated branch. Generalizes `max_execute_no_progress`.
- **Hook**: replace the unconditional `revise` return in `_apply_gate_outcome` (`gate.py:360-361`)
  with a history-count cap; add the three keys to `DEFAULTS` (`types.py:672`) + `_SETTABLE_NUMERIC`.

**What should influence the setting**: robustness tier (primary), and severity of remaining flags
(gates the *action* at the cap). Not plan size, not stakes.

---

## B. A nicely-engineered completion contract (Claude + Codex CONVERGED)

Two independent model families, blind to each other, produced the **same** design — high confidence:

**The invariant**: *a terminal state is a claim; a completion verdict is the authority.* The phase
may report "done"; the state machine does not believe it until an objective contract validates
**independent evidence** (git diff, test suite, on-disk artifacts, worker transcript) — never the
LLM's `review_verdict` or the self-reported `current_state`, which are the *claims being checked*.

**Shape** — `megaplan/orchestration/completion_contract.py`:
- A `CompletionContract` = a composition of `EvidenceProvider`s, returning a `CompletionVerdict`
  (`accepted | blocked | awaiting_human`, the evidence list, failures, a resume cursor).
- **Evidence providers** (composable, reused across phases & pipelines):
  `phase_coverage` (did the required phases actually run this iteration?),
  `worker_did_work` (real tool calls / commands / edits — not just tokens),
  `landed_diff` (checkpoint vs current tree / PR head),
  `green_suite` (run the configured test command — not just the baseline),
  `review_disposition` (review can inform, never be sole authority; a force-proceeded review is
  recorded as `fail`, not converted to success).
- Contracts are **additive**: `EXECUTE_CONTRACT ⊂ MILESTONE_DONE_CONTRACT`; `CritiqueDoneContract`
  and `ExecuteDoneContract` are thin policies over the same providers — so the contract generalizes
  to "is critique really done?" / "did execute really finish?" and to other pipelines.

**Anti-brittleness (the hard part) — declared-intent vs fact.** An honest no-op / docs-only /
deferred milestone passes because it *declares* its intent in a typed, signed artifact
(`completion/noop.json` or a finalize waiver: reason + scope_checked + commands_run + evidence).
Silent abandonment fails because it has **no diff, no green-suite, no tool calls, AND no declared
no-op**. Strictness is uniform; the discriminator is *declared-intent-vs-fact*, not bolted-on rules.
Deferred work becomes `awaiting_human` / `blocked` with a resume cursor — never `done`.

**Placement & hooks** (both drivers reuse it; the trust boundary stays outside the worker/LLM path):
- `auto.py:1363` — verify before the terminal `done` transition; on fail, `blocked` + durable `latest_failure`.
- `chain/__init__.py:1418` — replace the unconditional milestone append with `verify_completion`;
  this also **revives dead `merge_policy`** — merge/PR becomes one evidence provider, not the
  enclosing `if bool(milestone.branch)` condition.
- `execute.py:211`, `review.py:248` — same verifier at phase boundaries.
- Composes existing code: `PhaseResult`, `orchestration/execution_evidence.py`
  (`validate_execution_evidence` already catches phantom file claims / hollow done tasks),
  `_capture_test_baseline`.

**Fail-loud composition**: verification failure leaves the plan non-terminal, writes
`completion_verdict.json` with every result, emits a `COMPLETION_VERIFICATION_FAILED` event, and
surfaces in `megaplan status`. The override **does not mutate a failure into a pass** — it appends
`EvidenceRef(status="waived", human_waiver)`, preserving the fact that objective verification failed.
*Failures can be accepted by a human; they cannot disappear.* That directly inverts today's silent-success default.

---

## C. Over-tiering: yes, mostly fixable in /megaplan-decision

**The documentation that pointed us astray (verbatim, for THESE milestones):**
- `megaplan-decision/SKILL.md:41` — "high-stakes infra → higher tier."
- `:46` — "one profile per sprint, match the highest-stakes deliverable; lower-stakes inherit the tier."
- Reinforced by the tier-4 row (`:84`) and the `thorough` row (`:153`), which frame tiers around
  **consequence** ("regression = production incident").

**Why it misled here**: the flawed mental model is **stakes == tier**. The author pattern-matched on
dangerous nouns (*store*, *state machine*) and assigned a premium driver — even though the work was
*behavior-preserving* and backstopped by the green M0 characterization gate. `:46` actively pushes
the *whole sprint* up to the highest-stakes milestone's tier.

**The counter-guidance exists but lost**: `:82`/`:84` ("drop to `solo` when the plan is obvious",
"decision-difficulty alone doesn't justify tier 4"), `:22` ("residual complexity, not nominal scope").
But it's buried as parenthetical asides inside tier rows, is weaker/hedged than the bolded sizing
rules, never names the *decisive* fact (an objective gate backstops behavior), and is directly
contradicted by `:46`.

**Docs-fix vs code-fix boundary**:
- **THIS epic's over-tiering is fully DOCS-fixable.** `solo` (cheap DeepSeek driver) + the green M0
  gate were both available; the author chose `directed`/`partnered`/`premium` anyway — a pure
  *selection* error. Better guidance removes it entirely.
- **Code wiring is needed only for a separate refinement**: *intra-milestone* difficulty mixing
  (cheap driver on the easy turns of an otherwise-premium milestone), since driver tier is fixed once
  per milestone and `tier_models.<phase>` difficulty routing is consumed only by the execute worker.
  Not needed to fix what happened here.

**Proposed SKILL.md edit** — a bolded decision-rule right after `:46`:
> **Driver tier tracks decision *difficulty*, not stakes.** For behavior-preserving work (renames,
> file moves, decompositions, dead-code) backstopped by an objective gate (characterization suite,
> green-test gate), default the driver to `solo`/cheap — the gate is the safety net, not the tier.
> Reserve premium drivers for work with genuine decision-difficulty or no safe recovery.

…and soften `:46`'s "lower-stakes inherit the tier" to apply only to *unsplit* sprints, with a
cross-link from `:84`.

---

## The through-line across A, B, C
All three are the same architectural smell: **the harness trusts a phase's self-report instead of an
objective check.** Critique trusts the critic's "still issues" (no convergence test) → unbounded
rounds. Done trusts the plan's "done" (no evidence contract) → false completion. Tiering trusts the
author's stakes-judgement (no difficulty signal / a doc that conflates the two) → over-spend. And in
all three, the *fix shape* is the same: replace the self-report with an objective, bounded,
evidence-backed predicate — patterns the execute path already has and the rest of the pipeline lacks.
