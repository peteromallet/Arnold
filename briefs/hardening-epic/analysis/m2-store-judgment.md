# Judgment — milestone m2-store

**(a) Verdict: SIGNIFICANT inefficiency.** The plan/critique phase ran a **non-converging 9-round premium critique loop** that accreted flags (FLAG-M2-001 → 017) instead of closing them — the dominant driver of this milestone being the epic's cost outlier (16h, 89M tokens, 100% GPT-5.x). The thorough/premium pinning was reasonable for the data-integrity *outcome*, but nothing throttled the critique loop, so premium tokens were spent re-deriving and re-flagging the same plan eight extra times.

## (b) Seven lenses

| Lens | Verdict | Evidence |
|---|---|---|
| 1. Blockers / dead-ends | FINE | No runtime retries/SIGKILL/resume events in raw logs; "blocked/retry/resume" hits are all code being *read*, not operational. `max_blocked_retries=3` never triggered. |
| 2. Excessive revision | **SIGNIFICANT** | **9 critique iterations** ("This is critique iteration 2…9"), each in a session dominated by plan `abstraction-20260525-2003`, sequential 20:16→21:04 UTC. Flags grew monotonically to **17** (FLAG-M2-017 still churning ×9 at iter9). [VERIFIED] |
| 3. Low-value critiques | **SIGNIFICANT** | Every round added 1–3 *new* flags rather than converging — classic adversarial-critique non-termination. ~1.09M premium tokens across the 9 critique sessions (146K→133K→…→87K) for a plan that never reached a clean critique. [VERIFIED] |
| 4. Model-tier mismatch (orchestration) | MINOR→SIGNIFICANT | 100% GPT-5.5 (30 sessions) / GPT-5.4 (2) — zero cheap models in orchestration [VERIFIED]. Planning a data-integrity contract warrants premium; running **9 identical-template critique passes** on premium does not. The marginal rounds (iter 4–9) are mechanical re-verification a cheaper tier could drive. |
| 5. Repeated/bloated context | MINOR | Identical ~400K-char base instruction block (full personality + ~40-skill list) re-sent every session [VERIFIED: sample session 716KB, block present]. 95% provider cache absorbed cost, but every new critique round re-paid uncached overhead — the 9-round loop multiplied this. |
| 6. Model confusion | FINE | No wrong-file edits or iteration miscounting. The plan *did* miss writers (FLAG-M2-001: `auto.py`/`chain.py` state writers, FLAG-M2-008 schema `codebase_id`) — but that's the critique working, not confusion. |
| 7. Inefficiency / waste | **SIGNIFICANT** | 16h16m / 89.3M tokens / 100% premium for a plan-only milestone (execute farmed elsewhere). The ~1h, 9-round critique loop is the clearest waste signal; cost is out of proportion to a planning deliverable. |

**Coverage note:** these logs are orchestration-only (plan/critique/gate, premium GPT-5.x). Execute ran in separate cheap DeepSeek subprocesses not in this set — I do **not** claim execute was absent or premium.

**Contradiction of the facts file:** the facts file reports "2 critique iterations + 1 tiebreaker." That is wrong — it grepped a 32-file subset and missed iterations 3–9. Raw logs show iterations **2 through 9** in time-ordered m2-store sessions. This is the single most important correction.

**Prior-finding cross-ref:** No KeyError/static-fallback in this milestone's critique (the adaptive-critique-silent-fallback bug did *not* manifest here — m2-store uses the default evaluator, not `adaptive_critique: true`). Gate auto-downgrade (TIEBREAKER→ITERATE) not observed firing. `max_blocked_retries=3` fix present, untriggered.

## (c) Top 3 improvements

**1. Cap and force-converge the critique loop. [HARNESS]**
*Problem:* critique ran 9 rounds, monotonically accreting flags (→17), never converging — ~1.09M premium tokens for an unresolved plan.
*Root cause:* the critique/gate controller has no convergence guard — no max-iteration ceiling and no "new-flags-only, no-net-resolution → escalate to human/tiebreaker" stop condition. An adversarial premium critic will always find one more nit.
*Fix:* add a critique-iteration ceiling (e.g. 3) in the critique handler (`megaplan/handlers/critique.py`, the iteration-driving loop that emits "critique iteration N") and a convergence check: if round N raises ≥1 new flag while resolving 0 prior flags for 2 consecutive rounds, force TIEBREAKER/gate-stop instead of another revise→critique cycle.

**2. Tier-split the critique passes. [HARNESS / DRIVING]**
*Problem:* all 9 critique rounds on GPT-5.5; later rounds are mechanical "was prior flag actually fixed?" re-verification.
*Root cause:* `premium/thorough/high` pins one premium model to *every* orchestration sub-phase, including cheap verification.
*Fix:* allow the critique evaluator to use a cheaper tier for re-verification rounds (iter ≥2), reserving premium for round 1 plan critique. Wire a `critique_evaluator` model override into the `premium` profile so thorough≠premium-on-everything.

**3. Don't auto-escalate robustness on a planning-only milestone without a loop budget. [DRIVING]**
*Problem:* `thorough` (which adds prep + extra critique depth) on m2 produced the cost outlier with no quality gate that the extra rounds were *earning* their cost.
*Root cause:* robustness was set to `thorough` for data-integrity stakes (correct intent) but the chain has no per-milestone critique-token budget, so "thorough" became "loop until interrupted."
*Fix:* in `chain.yaml`, pair `thorough` milestones with an explicit critique-round cap (driver-level `max_critique_iterations`) so the high-stakes setting buys *depth-per-round*, not *unbounded rounds*.

---
*File written: briefs/hardening-epic/analysis/m2-store-judgment.md*
