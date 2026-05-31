# A — Prompt-side solution to plan-critique non-convergence

**Lens:** AGENT-COGNITION / PROMPT-ENGINEERING. Fix the loop from the *model's side* —
instructions, not control flow. Grounded in `A1-content-why-no-converge.md` (M2: 17
flags = 2 recursive concern threads peeling one location per round; 0 disputed, 0
re-opened; R1 spent budget validating its own JSON instead of sweeping).

The four mechanisms that kept the loop alive map to four prompt edits. Each is in
`megaplan/prompts/critique.py` / `robustness.py` / `critique_evaluator.py`.

---

## 1. EXHAUSTIVE-FIRST instruction (the scope-crawl killer)

**Root:** `scope` / `all_locations` / `callers` are *discovery-shaped* lenses. Their
guidance (`robustness.py:47-82`) says "Search for related code… Grep for call sites" —
it never demands a *closed* enumeration, so the model returns the first hit and peels
the next one next round.

**Edit — `robustness.py`, the `guidance` field of each of the three lenses.** Append a
closure clause. For `all_locations` (lines 62-66), change guidance to end with:

> "ENUMERATE EXHAUSTIVELY ON THIS PASS. Run the full sweep NOW (`rg`/grep across the
> whole repo, not one module) and emit a CLOSED list of every location: every writer,
> every call site, every supporting/glue site. Then state your completeness proof: the
> exact search command(s) you ran and why they cover the whole surface. If you CANNOT
> prove the list is complete, say so explicitly and widen the sweep before you finish —
> do NOT defer 'one more location' to a later round. A list you can't close is itself a
> `flagged: true` finding ('enumeration incomplete: <what's unswept>')."

Same closure clause, retargeted, on `scope` (lines 49-54: "list every related concept
/ symptom site") and `callers` (lines 74-78: "list every caller and the argument shape
each passes; prove no caller is unlisted").

This converts "find one more" into "find all now, or admit the gap loudly." A loud
incompleteness flag is *one* flag the gate can act on, instead of 9 rounds of silent
peeling. It also kills the R1 failure mode directly: an explicit completeness-proof
requirement leaves no budget to spend re-validating JSON shape.

**Reinforce in `_build_critique_prompt`** (`critique.py:316-326`, "Additional
guidelines") with a global rule so it applies even to evaluator-synthesized `other`
lenses:

> "- Enumeration discipline: any lens asking 'all X' must return a CLOSED set this
>   pass with a stated search command and completeness rationale — never an open-ended
>   sample you intend to extend next iteration."

---

## 2. ANCHORING prior verdicts (stop re-scanning settled areas blind)

**Root:** the critic re-embeds the *whole* plan (`critique.py:298-299`,
`Plan:\n{context["latest_plan"]}`) and the lens set is re-selected fresh each round
(`handlers/critique.py:217-218`); a passed area is never told "this stayed clean."
`_build_checks_template` (`critique.py:234-264`) already attaches `prior_findings` with
`status` — but the prompt never *instructs the model what to do with them*.

**Data to feed:** already assembled. The evaluator block has "Verified Flags — Do Not
Re-Litigate" (`critique_evaluator.py:56-66`) and `prior_findings[].status`
(`critique.py:253-263`). Add a derived field per check: `prior_outcome ∈ {clean,
flagged-now-fixed, flagged-open}` plus a `diff_touches_this: bool` computed by testing
whether the plan-version unified diff (`_plan_version_unified_diff`, already built at
`critique.py:147`) touched any section that check cited.

**Edit — `iteration_context` text** (`critique.py:392-399`), replace with a 3-clause
anchor rule:

> "This is critique iteration {iteration}. Each check carries `prior_findings` with a
> `status` and a `diff_touches_this` flag.
> (a) For a check whose prior finding was `clean`/`verified` AND `diff_touches_this`
>     is false: it is ANCHORED. Do NOT re-investigate it. Emit a single finding
>     `{detail: 'Anchored: passed at iter N; revision diff did not touch this surface',
>     flagged: false}` and move on. Re-open ONLY if you have concrete NEW evidence the
>     revision elsewhere broke it — and then cite the specific diff lines.
> (b) For a check whose surface the diff DID touch: re-investigate fully — verify the
>     prior fix and look for regressions the change introduced.
> (c) Spend your investigation budget on (b), not (a)."

Effect: settled threads stay settled; the critic's effort concentrates on the churned
delta instead of re-deriving the whole plan and manufacturing adjacent scope.

---

## 3. NEAR-LAST-ROUND signaling (3-tier, critic + reviser)

**Root:** no signal that the cap is near, so the critic keeps opening cosmetic scope at
R7-R8 and the reviser keeps treating every flag as equal. A2 sets the cap (4 full / 6
thorough); the prompt must *say which tier we're in*. Pass `round_phase ∈ {normal,
penultimate, final}` (derived from `iteration` vs the resolved cap) into both builders.

**CRITIC** — insert into `critique_review_block` (`critique.py:391-423`):

- *normal:* (no extra text — current behavior).
- *penultimate:*
  > "ROUND PHASE: PENULTIMATE (one revise pass remains after this). Do NOT open new
  > cosmetic, stylistic, or 'nice-to-have' scope. Only `flagged: true` for issues that
  > are correctness-, security-, or completeness-blocking, OR for a NEW location that
  > genuinely breaks the stated goal. Everything else: `flagged: false` with a note."
- *final:*
  > "ROUND PHASE: FINAL (no revise pass follows — this is the last critique). Raise NO
  > new scope of any kind. Restrict findings to `significant` / `likely-significant`
  > correctness or security defects that would cause the plan to fail at execution.
  > Cosmetic, maintainability, and convention concerns must be `flagged: false`. If
  > nothing blocking remains, say so plainly so the loop can close."

**REVISER** — insert into the revise Requirements list (`critique.py:115-131`):

- *penultimate:*
  > "- ROUND PHASE PENULTIMATE: prioritize correctness over polish. Address every
  >   significant/likely-significant flag fully; for minor/cosmetic flags do the
  >   minimal safe fix or explicitly `reject` with reason. Do not refactor beyond the
  >   flags."
- *final:*
  > "- ROUND PHASE FINAL: this is the last revision. Resolve ONLY significant flags.
  >   Make the smallest change that closes each. Reject cosmetic flags with a one-line
  >   reason. Do not restructure the plan."

---

## 4. COSMETIC-vs-CRITICAL discipline (the flag that kept the loop alive)

**Root:** "When in doubt, flag it" (`critique.py:411`) + binary `flagged` with no
severity gradient means every divergence becomes a blocker the gate must clear, so the
loop never empties. The lens specs already carry `default_severity`
(`robustness.py:31,43,92,105…`) but the per-finding instruction ignores it.

**Edit — finding schema instruction** (`critique.py:405-417`). Add a required
`severity` per finding and a routing rule:

> "Each `flagged: true` finding MUST include `severity` ∈ {significant, likely-
> significant, minor, cosmetic}. Use this scale honestly:
> - significant/likely-significant: would cause wrong behavior, data loss, security
>   exposure, or leave the stated goal unmet.
> - minor: real but non-blocking (a missing edge-case test, a weaker-than-ideal name).
> - cosmetic: style, wording, ordering — zero behavioral impact.
> A cosmetic or minor finding is NOT a reason to keep iterating. Flag it (the gate
> still sees it) but NEVER inflate its severity to force another round. 'When in doubt,
> flag it' applies to *visibility*, not to *blocking* — doubt resolves toward `minor`,
> not toward `significant`."

This decouples "surface the observation" (keep — visibility is good) from "block the
loop" (now severity-gated). Combined with §3-final, the critic can no longer keep the
loop alive on polish.

---

## 5. DELEGATE / REVISE churn bound

**Root:** revise rewrote ~53% of the plan per round (122 churn lines on ~229),
re-presenting fresh surface to the next critic. Existing requirement (`critique.py:128`)
only says "remove unjustified scope growth" — nothing forbids rewriting *passing*
sections.

**Edit — revise Requirements list** (`critique.py:115-131`), add:

> "- TOUCH ONLY FLAGGED SECTIONS. Edit exactly the plan sections named in the open
>   flags (and their direct dependencies). Do NOT rewrite, re-word, or re-order
>   sections no flag points at — copy them through verbatim. Your diff should be
>   proportional to the flags: a handful of flags is a handful of edited sections, not
>   a full rewrite. In `changes_summary`, list which sections you touched and confirm
>   the rest are unchanged."

Pairs with §2: if revise leaves passing sections byte-identical, `diff_touches_this` is
reliably false and the critic's anchor rule fires correctly. The two edits are
mutually reinforcing — bounded churn makes anchoring trustworthy; anchoring rewards
bounded churn.

---

## What this lens CANNOT fix (needs A2 control-flow)

- **A hard stop.** Prompts bias the model toward closure but cannot *guarantee* it; a
  stubborn model can still emit a real significant flag at round 7. Only the
  `max_critique_iterations` cap (`gate.py` history-count, A2) forces termination.
- **The severity SWITCH at the cap.** Classifying a flag cosmetic (§4) is the model's
  job; *acting* on it — force-proceed-with-note for cosmetic-only vs ESCALATE for an
  open correctness flag (`gate.py:328` predicate, `review.py:248-252` mirror) — is
  deterministic control flow that must not be left to a prompt.
- **No-net-progress detection.** "2 rounds, 0 resolved, ≥1 new blocking" is a measured
  state-machine condition, not something a single-pass prompt can self-observe.
- **Computing `round_phase` and `diff_touches_this`.** The prompt *consumes* these; the
  harness must derive them (iteration vs cap; diff-vs-section overlap) and inject them.

Prompts close the *wound* (front-load completeness, anchor, bound churn, sever cosmetic
from blocking); the cap stops the *bleeding* if a genuine defect survives. Both are
required — caps alone forces a stop with flags still open; prompts alone can still spin
on a determined model.
