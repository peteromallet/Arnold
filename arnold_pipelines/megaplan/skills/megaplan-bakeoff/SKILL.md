---
name: megaplan-bakeoff
description: Methodology for running multi-profile LLM bake-offs via megaplan and presenting fair, blind-assessed comparisons. Cost/quality discipline, prompt hygiene, pre-merge gates, and reporting patterns. Use when the user says "bakeoff", "bake off", "megaplan bakeoff", or asks to compare profile mixes head-to-head.
---

# Bake-off methodology

A bake-off runs the same task through N profiles concurrently and picks a winner. Use it to test profile mixes (which model leads, who critiques, who executes), to evaluate cost-quality trade-offs, or to compare codebases head-to-head. This skill captures the operational knowledge that separates "well-run bake-off" from "expensive shrug."

## When to bake off

- Comparing profile mixes on a real, scoped task (light robustness, clear deliverable).
- Establishing baselines before a big project.
- Debating whether a cheaper profile is "good enough."

Don't bake off for: tiny tasks (overhead > value), tasks with no measurable deliverable, or one-shot questions.

## Profile setup

Built-in profiles (megaplan): `standard`, `all-claude`, `kimi`, `claude-kimi-deepseek`. Project-local in `<project>/.megaplan/profiles.toml`.

Useful mix dimensions:
- **Who leads** (plan/revise/finalize): Claude vs DeepSeek vs all-X
- **Who critiques**: Claude tends to add disproportionate value as a critic
- **Who executes**: cheapest dimension to vary; biggest cost lever

Test profiles 2×2: lead × critic. `all-claude` is the control.

## Smoke test before real bake-off

**Always** smoke-test profiles with a tiny `--mode doc` task before launching code-mode bake-offs. Reasons:

1. Catches API/key/routing failures cheaply.
2. Catches Fireworks streaming bug (`max_tokens > 4096` requires `stream=true`) — fixed in current megaplan but always worth verifying.
3. Doc-mode is ~5-15 min/arm vs code-mode's 30-60 min/arm.

Smoke prompt template: a 250-word note on a topic the model knows. Cost: ~$0.15-1.70/arm depending on profile.

## Prompt hygiene (the load-bearing rule)

**Do NOT include absolute paths in the idea text.** Specifically: never write `Project: /abs/path/to/repo` or any equivalent. Megaplan injects its own `Project directory: <worktree>` line. If your idea text has a competing path, models will trust the user-authored line and execute against the wrong directory.

Symptom when this happens: bakeoff arm reports `final_state: done` but `git -C <worktree> diff main --stat` is empty. Files appear in your *main* repo instead, polluting it. Megaplan's audit catches this (`files_in_diff: []` while `files_claimed` is non-empty) but light-robustness review auto-approves it anyway.

**Defense in depth:**
- Strip absolute paths from idea text. Use relative paths or describe by intent only.
- Megaplan ≥ commit `a0ed9f51` (sandbox fix) enforces this at the tool layer — any `cd /escape && ...` is refused.
- Always pre-merge gate (below).

## Launching a bake-off

```bash
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan bakeoff run \
  --idea-file /tmp/<task>-idea.txt \
  --profiles all-claude deepseek-kimi-deepseek claude-kimi-deepseek-or all-deepseek-or deepseek-claude-critique \
  --robustness light \
  --allow-dirty \
  --exp-id <task>-<date> \
  --detach
```

`--allow-dirty` lets you start from a worktree with unrelated uncommitted changes (they stay on main, don't enter worktrees). `--detach` returns immediately; poll with `bakeoff status --exp <id>`.

Light robustness loop: plan → critique → revise → finalize → execute → review. No prep, no gate.

## Polling cadence

- Initial check: 5-10 min after launch (catches early stalls).
- Then every 15 min.
- Light + code-mode = 20-60 min/arm typical. Don't poll faster (cache pressure, no signal).
- The `bakeoff status` table can lag — last write to state.json is the truth. Check `<worktree>/.megaplan/plans/<plan>/state.json`'s `current_state` field if status seems stuck.

## Pre-merge gate (don't trust outcome.json alone)

Before `bakeoff pick`, verify each arm:

```bash
for p in <profile-list>; do
  d=/Users/.../.megaplan-worktrees/<exp-id>/$p
  echo "$p: $(git -C $d diff main --stat 2>/dev/null | tail -1)"
done
```

An arm with empty diff after `final_state: done` is misdirected (or fabricated, pre-sandbox). Exclude it from comparison. Stash any pollution in main:

```bash
git status --short  # if dirty
git stash push -u -m "<exp-id>-pollution"
```

## Blind assessment

Always blind. Sub-agent must not know which profile produced which output. Pattern:

1. Map profiles to randomized Doc A/B/C/... letters in your *own* head.
2. Brief the sub-agent with only the letter labels and worktree paths.
3. Tell it the rubric explicitly:
   - Spec adherence (does it satisfy /tmp/<task>-idea.txt?)
   - Code quality (idiomatic, readable, complete)
   - Test coverage (assertions match the spec, no decorative tests)
   - Idiomatic fit with existing codebase patterns
4. Ask for /5 per axis, /20 or /25 total, plus qualitative notes.
5. Forbid the sub-agent from peeking at `.megaplan/` files inside worktrees (those reveal the profile via plan_v2.md or state.json).
6. Forbid inferring from path/dirname (worktree dirs may be named after profiles).

Sub-agent returns ranking + winner pick + tiebreaker reasoning. Un-blind on receipt and present to user.

## Reporting comparisons

Standard table format:

| Profile | Cost | Time | Score | Verdict |
|---|---|---|---|---|

Add a "cost-adjusted take" paragraph that calls out:
- **Surprising cost asymmetries** (e.g. "X profile is 12× cheaper for similar quality")
- **Role specialization findings** (e.g. "Claude as critic raises non-Claude plans by a full grade")
- **Production-readiness gap** (literalist vs engineer-extends-the-spec)

Quote 1-2 sentences from each output that capture its voice — scores miss style.

End with a "ship this one" pick and the dimension that tipped it.

## Pick + merge

```bash
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan bakeoff compare --exp <id>  # required before pick
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan bakeoff pick --exp <id> --profile <winner> --rationale "..."
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan bakeoff merge --exp <id>
```

Merge brings the winner's worktree changes into main as uncommitted edits — review, run pytest, then commit yourself. Don't auto-commit blindly; the merge step doesn't run tests.

## Cost guidance

Rough order-of-magnitude per arm at light robustness:
- doc-mode: $0.15 (deepseek-everywhere) → $1.70 (all-claude)
- code-mode (small phase): $0.30 → $5
- code-mode (large phase): $0.50 → $15

Multi-arm bake-off totals = sum of arms. A 5-arm code-mode phase can run $10-40. A 4-phase pipeline of 5-arm bake-offs can run $50-200.

## Failure modes

- **Stuck arm**: check `ps aux | grep megaplan` and `lsof -p <pid> | grep TCP` — if no socket activity, kill and re-launch single-profile via `megaplan auto`.
- **Empty critique output**: check `<plan>/critique_v1_raw.txt` for HTTP errors. Fireworks 400 streaming bug pattern: "max_tokens > 4096 must have stream=true". Megaplan ≥ `c2bbc729` fixes this.
- **Stale `bakeoff status` table**: check actual `outcome.json` files in `~/.megaplan/bakeoffs/<exp>/<profile>/` — those are authoritative when the run completes.
- **Codex rate limit**: pass `--phase-model execute=claude` or use a profile that doesn't depend on codex.

## When to abandon an arm

- Diff is empty 30 min after `final_state: done` (model misdirected; sandbox may not be installed).
- Critique returned `{"checks": [], "flags": []}` and state stuck at `planned` (silent worker failure).
- Cost > 5× your budget cap with no execute progress.

`megaplan bakeoff abandon --exp <id>` discards worktrees but keeps audit data for forensics.

## Multi-phase pipelines

For sequential phases (e.g. orchestrator V1 phases 6→9), bake-off each phase, merge winner, then bake off the next from the new main. Don't bake off all phases as one giant idea — losses compound and you can't isolate which phase regressed.

After all phases, deploy a final-assessment sub-agent to write a structured `.md` covering: profile mix performance across phases, cost trends, quality trends, harness bugs surfaced and fixed. Pin it in `docs/`.
