# Judgment — m3a-fail-loud-policy

**Milestone verdict:** A clean, efficient run that delivered correct work (census + low-risk fixes, full suite green at T8) — but the orchestration ran on **premium GPT-5.4 for mechanical census/edit work it didn't need**, and the harness fired **5 zombie sessions** that did zero work, the only real waste signals.

## The 7 lenses

| # | Lens | Verdict | Single most concrete evidence |
|---|------|---------|-------------------------------|
| 1 | Blockers / dead-ends | **MINOR** | 0 runtime blockers/retries/resumes. But **5 stub sessions** launched 18:00–18:03Z, each 12–59s, 14 lines, **0 function_calls** vs 336 lines/138 calls in a real session. [VERIFIED] |
| 2 | Excessive revision | **FINE** | 0 review rounds; every `reviewer_verdict` is `""`. No execute→review→rework loop in these (orchestration) logs. |
| 3 | Low-value critiques | **FINE** | 0 critique invocations. All 17 "critique" hits are task prose referencing `critique.py` as an edit site, not critique rounds. (Note: no adaptive-critique config on m3a, so the epic-wide KeyError fallback bug does not implicate this run.) |
| 4 | Model-tier mismatch | **SIGNIFICANT** | Orchestration ran on **gpt-5.4** (`model_provider:openai, model:gpt-5.4`, all 3 main sessions). [VERIFIED] The work was a bounded AST/grep census + add-WARNING-log + 2 read-resilience guards + tests — mechanical, well-specified, zero review/critique adjudication. Premium reasoning earned nothing here. |
| 5 | Repeated / bloated context | **SIGNIFICANT** | The full ~50KB batch payload (9 task descrs, 30+ debt-watch items, 5 sense checks, SD1–SD3, 13 watch_items) re-sent verbatim **8×** — incl. the 5 zombie sessions that consumed it and produced nothing. All T5–T9 refs appear in every session because the whole batch ships each turn. [VERIFIED] |
| 6 | Model confusion | **FINE** | No wrong-file edits, no contradiction, correct ordering T5→T6→T7+T8. One self-inflicted test miss (patched emit at wrong target → `M3A_WARN_EMIT_ARTIFACT_WRITTEN` vs `_FLAG_EVENT`), self-resolved by T8. |
| 7 | Inefficiency / waste | **MINOR** | 60 min wall-clock / ~37 min real work; the 23-min tail is harness gaps + 5 dead sessions. Diff (census doc + low-risk guards + tests, 2970 passed) is proportionate to the ~37 min of real work — the waste is the premium tier (#4) and dead sessions (#1), not the working turns. |

## Coverage note
These are **orchestration-layer** Codex logs (plan/driver turns on gpt-5.4); execute was farmed to cheap DeepSeek workers whose logs are absent. "0 review/critique" reflects what m3a was configured to run (no `adaptive_critique` flag), not missing data. Tier verdict (#4) is scoped to whether *orchestration* needed premium — it did not.

## Top 3 improvements

**1. Stop spending premium GPT-5.4 to drive mechanical, fully-specified milestones. [DRIVING]**
- *Problem:* m3a's orchestration ran on gpt-5.4 for a bounded census + add-a-WARNING-line + read-guards + tests — no adjudication, no review, no ambiguity.
- *Root cause:* `chain.yaml` pins m3a to `profile: partnered // high` (depth high → premium driver), the same tier as genuinely hard milestones (m2 store integrity). Profile is chosen by milestone "importance," not by orchestration difficulty.
- *Fix:* Downgrade m3a (and similar census/mechanical-edit milestones) to a `directed`/lower-depth driver, or split the dimension so **execute robustness stays `full` while the driver model drops to a mid-tier**. The census's exhaustiveness is enforced by the AST script + done-criteria greps, not by driver IQ. Change: `chain.yaml` m3a `profile`/`depth`; codify "driver tier ≠ milestone stakes" in `megaplan-decision`.

**2. The harness spawned 5 zombie orchestration sessions (0 function_calls) and silently moved on. [HARNESS]**
- *Problem:* 5 sessions 18:00–18:03Z each ingested the full ~50KB batch and exited in 12–59s having done nothing — no error, no timeout, no retry log.
- *Root cause:* Session launch succeeds, the model returns an empty/no-tool turn, and the driver treats "no function_call" as a benign no-op instead of a failed session — so it relaunches (5×) without surfacing anything. This is a silent-failure pattern — exactly what *this milestone* exists to kill.
- *Fix:* In the driver's session-completion check (auto.py liveness / session-result path), treat a completed session with **0 function_calls and no terminal status** as a hard WARN-and-count event with a grep-stable token (e.g. `EMPTY_SESSION_NO_TOOLCALLS`), bounded by `max_blocked_retries`. Eat your own dogfood from the m3a policy.

**3. Re-sending the entire 50KB batch every turn (incl. to dead sessions) is pure token waste. [HARNESS]**
- *Problem:* All 9 task descrs + 30+ debt-watch items + sense checks + decisions shipped verbatim 8×, including to the 5 zombies.
- *Root cause:* The batch prompt is monolithic and stateless per session; there's no "completed-task elision" so finished T5/T6 context rides along into T7/T8 and into every relaunch.
- *Fix:* Have the driver pass only the **active task(s) + shared decisions/watch_items**, eliding descriptions of already-completed tasks (or reference them by ID + summary). Combined with fix #2 (no zombie relaunches), this removes the largest repeated-token cost on premium tier.

---
*File written to `.megaplan/briefs/hardening-epic/analysis/m3a-fail-loud-policy-judgment.md`.*
