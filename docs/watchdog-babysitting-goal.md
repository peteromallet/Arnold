# Goal — babysitting the live-agentic self-improving watchdog

This document is the north star for *my* job (the operator one level above the
watchdog). It says what "working well" means and when babysitting is done. The
companion `watchdog-babysitting-loop.md` is the per-hour check-in protocol that
gets me here.

## What I'm actually doing

I am running `scripts/live_agentic_watchdog.py` repeatedly and **babysitting it**:
watching each turn, judging whether Codex is genuinely improving the pipeline,
and fixing **process** problems (wedges, auth, regressions, gaming) or restarting
when needed — until the whole thing runs well. I am NOT writing the harness
improvements myself; Codex does that, inside an allowlist. My job is to keep the
machine running and steer it when it goes off the rails.

## What "working well" means (the five success criteria)

These are observable. I judge each from `outcome.json`, `auto.log`, the per-turn
reports, and the live background-task state.

1. **The suite runs reliably.** No wedges, no timeout-storms, no harness errors
   dominating. DeepSeek key self-hydrates; Codex stays authed. The watchdog
   process does not crash.

2. **The tests are legitimately good.** Pass/fail reflects real model behavior,
   not brittleness. Failing scenarios fail *for the right reason*. The
   `intent_judge` gives meaningful verdicts, not boilerplate. Scenarios that are
   genuinely impossible or broken get identified (flagged in `bigger_swings.md`
   or a report), not gamed.

3. **Codex is actually improving the pipeline.** Pass count trends up over turns
   (not strictly — but the trajectory is real). Codex's edits land in the
   high-leverage files — `provider.py` prompts, `executor/prompts.py`,
   `intent/prompts/text_judge.prompt.md`, `agent/artifacts.py` — and target the
   prompts + the data passed between stages. Each turn's diagnosis is specific
   (failure → change → why it generalizes), not boilerplate.

4. **The process runs smoothly.** No repeated restarts needed. Safety gate passes
   (no import breaks, no out-of-allowlist edits). Commits are allowlist-only and
   cleanly tagged `watchdog-<run_id>-rN`. The watchdog itself stays up.

5. **No regressions that stick.** When Codex fixes a scenario it does not silently
   break others. `newly-fixed ≥ regressions` across the run, and movement is
   tracked in the digest.

## The hard rules (what "done" is NOT)

- Not gamed: pass count rising because tests got easier or expected answers got
  hardcoded = failure, not success. I must catch this and intervene.
- Not one-off: no deterministic changes that pass exactly one run. Codex must
  make the pipeline *fundamentally* better.
- Not noisy: a green run earned by luck or by weakening checks is not done.

## When babysitting is DONE

I stop and hand back to the user when, in a finished run, **all five** hold:
suite stable; tests measure real things; Codex improving the right files with
real diagnoses; process smooth; no sticky regressions — **and** the pass count
has plateaued near a sensible ceiling OR is clearly converging, so further turns
are diminishing returns. At that point: stop the run, delete the hourly cron,
and write the user a plain summary of what changed and where the pipeline landed.

## Non-negotiables while operating

- Allowlist-only edits, verified every turn. Out-of-allowlist → revert + retry.
- Never `git add -A`. Commits are per-round, allowlist-only, on the dirty branch.
- Codex runs with bypassed approvals by design (user-accepted); my safety net is
  the allowlist + import check + baseline-diff, not approvals.
- Real DeepSeek + Codex spend is expected and accepted; I only stop for cost if
  something is clearly runaway (a single turn costing wildly more than usual).
