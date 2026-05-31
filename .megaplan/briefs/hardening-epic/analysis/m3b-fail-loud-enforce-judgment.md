# Judgment — milestone `m3b-fail-loud-enforce`

**Verdict (one line):** Clean, efficient execute phase (5 batches, ~89% cache hit, 0 retries/errors), but the capture is execute-only — orchestration premium spend and the known critique-fallback bug are invisible here; the one concrete waste is a **26-minute dead-air gap** mid-chain and the **partnered//high premium tier driving mechanical guardrail edits**.

## Coverage honesty
The 5 in-scope sessions are megaplan **execute batches 2–6 of 7** (GPT-5.4 driver, header `batch 2 of 7`, 20× `EXECUTE`). No plan/critique/review/gate phase appears in this capture — those ran in separate sessions (the 7 manifest files with 0 plan-name hits) and/or in cheap DeepSeek execute-worker subprocesses whose logs are not in this set. So lenses 2/3 (revision/critique) are **not assessable from this evidence**, and I do not claim "no critique happened" — it happened off-capture.

## The 7 lenses

| # | Lens | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Blockers / dead-ends | FINE | 0 retries, 0 resumes, 0 blocked states; all 5 batches ran start-to-finish. `STATE_BLOCKED`/`DEFAULT_MAX_BLOCKED_RETRIES` hits are source reads of `auto.py`, not events. |
| 2 | Excessive revision | NOT ASSESSABLE | Execute-only capture; 0 review verdicts in-frame. 137 "rework" grep hits are inlined `auto.py` constants, not loops. |
| 3 | Low-value critiques | NOT ASSESSABLE | No critique invocation in capture; 3 `critique_evaluator` hits are **pytest output** (test filenames + an assertion diff), not a runtime fallback. Cannot confirm the epic-wide KeyError-fallback bug from these logs. |
| 4 | Model-tier mismatch | **SIGNIFICANT** | All 5 execute batches drove on **GPT-5.4** (`"model":"gpt-5.4"` ×2/session, verified). Profile is `partnered//high`. The work is mechanical guardrail surgery (replace `except: pass` with a raise/emit token, atomic-rename backup) — premium orchestration tier is overspec for this driving. |
| 5 | Repeated / bloated context | MINOR | System prompt (skills+personality) re-sent per batch — inherent to Codex fresh-session-per-batch — but mitigated: **~89% cache hit** (389,888 cached of 473,791 input on the final session). Tokens largely earned their place. |
| 6 | Model confusion | FINE | 0 wrong-file edits / contradictions / scope misreads; 11 "mistake/contradict" hits all source/test reads. Edits stayed on the enumerated touchpoints. |
| 7 | Inefficiency / waste | **SIGNIFICANT** | 1h07m wall-clock with a **~26-minute idle gap** between batch 3 end (11:16:10Z) and batch 4 start (11:42:12Z) — verified in both rollout files. That's ~39% of wall-clock with no captured work. |

## ADVERSARIAL CHECK
- **[VERIFIED]** Premium tier on execute: `grep '"model"'` on `rollout-...T13-05-22` returns only `gpt-5.4` (×2). No cheap model drove these batches.
- **[VERIFIED]** 26-min gap: last timestamp of `T13-05-22` session = `11:16:10.881Z`; first timestamp of `T13-42-11` session = `11:42:12.116Z`. Gap is real, not a DeepSeek extraction artifact.

## TOP 3 IMPROVEMENTS

**1. Downgrade execute-batch driving off premium for mechanical-guardrail milestones. [DRIVING]**
- *Problem:* `partnered//high` ran every execute batch on GPT-5.4; the diffs are rote (swap `except: pass` → `raise CliError("M3B_HALT_…")`, add atomic rename, emit `TIEBREAKER_DOWNGRADED_MISSING_FIELDS`).
- *Root cause:* the chain entry sets one tier for the whole milestone; execute farming to cheap workers is the design but the **Codex driver itself** stayed premium.
- *Fix:* for census-driven enforcement milestones (M3b-class) set `profile: directed` (or a cheaper driver tier) in `chain.yaml`; reserve `partnered//high` for the design-heavy census milestone (M3a). Verify the execute farm-out actually used DeepSeek workers — if the GPT-5.4 driver did the edits inline rather than dispatching, that's the larger leak.

**2. Close the 26-minute mid-chain dead-air gap. [HARNESS]**
- *Problem:* ~26 min of zero captured activity between batch 3 and batch 4 — ~39% of the run's wall-clock.
- *Root cause:* either an off-capture orchestration phase (review/gate between batch groups) with no heartbeat to `state.json`, or a stalled-but-not-killed transition — echoes the prior "hermes heartbeat never touched state.json → silent false-stall" finding.
- *Fix:* ensure batch→batch transitions emit a `state.json` heartbeat/trace event so a gap is attributable; if the gap was a real orchestration phase, pull those session files into the manifest so this lens is assessable instead of dark.

**3. Make the manifest capture orchestration phases, not just execute. [DRIVING]**
- *Problem:* 7 of 12 manifest files have 0 plan-name hits; the actual plan/critique/review/gate sessions are excluded, leaving lenses 2/3 and the known critique-fallback bug unverifiable.
- *Root cause:* manifest built by plan-name grep against execute-batch prompts; orchestration sessions name the plan differently or live elsewhere.
- *Fix:* extend the manifest builder (the judge-brief pipeline) to resolve orchestration sessions by plan-run ID / time window, not just batch-prompt grep, so the critique-fallback regression can be confirmed per-milestone instead of assumed.

---
**File written:** `/Users/peteromalley/Documents/megaplan/.megaplan/briefs/hardening-epic/analysis/m3b-fail-loud-enforce-judgment.md`
