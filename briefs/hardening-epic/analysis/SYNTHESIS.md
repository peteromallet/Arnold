# Hardening-epic retrospective — synthesis

Forensic analysis of the 12-milestone core-hardening epic (2026-05-25 → 05-28).
Method: 12 DeepSeek extractors mined the Codex orchestration logs → 12 Claude judges
applied a 7-lens rubric with adversarial spot-checks → 3 Claude cross-cutting agents
re-quantified cost/critique/reliability. All numbers below are the *clean* re-derived
figures (foreign cross-repo sessions filtered out — see Data-quality caveat).

## TL;DR
The epic **succeeded technically** (242 files, +21.7k/−18.4k landed; near-zero runtime
crashes or stalls) but carried **three systemic inefficiencies**, all in the
ORCHESTRATION layer (plan/critique/review/gate driven by premium GPT-5.x), not execute:
1. **Over-tiering** — 56.6% of premium spend went to mechanical work a cheap driver could run.
2. **No critique convergence guard** — two runaway critique loops burned ~1.5M premium tokens.
3. **Broken "done" integrity** — 3 of 12 milestones were marked done without passing a gate.

## The clean numbers
- **Premium (GPT-5.x) orchestration: ~260M tokens ≈ $231** at GPT-5.5 rates.
- **M2-store alone: 87.7M tokens, $77.47 — 33.6% of the entire premium bill.**
- **Over-tiered mechanical milestones: $130.66 = 56.6% of premium dollars.**
- Intro-doc's "$12 / 78% DeepSeek" is honest but counts only execute workers; like-for-like
  premium **orchestration is ~$231, ~19× the DeepSeek bill**, and sits almost entirely
  outside execute. The cheap-execute story is real but it's not where the money went.

## Ranked findings (impact × fixability)

### 1. Over-tiering: tier pinned by stakes, not difficulty — [DRIVING]+[HARNESS] · $130/$231 wasted
chain.yaml sets the driver tier by milestone *stakes*, then runs premium on *every* turn.
9 mechanical milestones (renames, census, file-moves, behavior-preserving splits, dead-code)
got a GPT-5.x driver for work whose hardest check is a grep — all 12 judges independently
scored tier-mismatch SIGNIFICANT. **Fix:** split the axes — tier the *driver* by
orchestration difficulty; let the objective characterization gate (M0, which worked) credit
a cheap driver; reserve premium for no-safe-recovery work (M2 only).

### 2. No critique convergence guard — [HARNESS] · ~1.5M premium tokens
- M2: **9 critique iterations** (2→9), flags FLAG-M2-001..017 *accreting* instead of closing
  (~1.09M premium tokens) — the dominant driver of M2 being the cost outlier.
- M4: **7–8 plan-review rounds** firing the *identical* 9 check_ids, re-sending byte-identical
  64,638-token context 5× (~450K wasted input).
- There is **no iteration ceiling or convergence stop** anywhere; max_iterations/
  max_blocked_retries only guard runtime failure, not critique rounds.
- Value is concentrated: only **3 of 13** critique rounds caught a real actionable bug.
**Fix:** round ceiling + no-net-progress stop (new flags but zero resolutions → escalate/stop)
+ plan-hash short-circuit (skip re-critique of unchanged plan) + dedup the re-sent context.

### 3. "Done" integrity broken — [HARNESS] · 3/12 false done
Chain writes `done` on execute/decompose-*finished*, not gate-*passed*. `pr_number: null`
on all 12 despite `merge_policy: auto`.
- **m6a — abandoned after plan**: plan + critique-assign + 18-task decompose ran on premium,
  then stopped. No execute/review/gate, no worktree/branch/commit. 174K premium tokens →
  zero landed diff, yet marked "done".
- **m6b — pipeline bypassed**: declared directed/light+adaptive_critique config was inert;
  closed by a hand-driven `git merge`. Execute ended RED (`test_step_schema_filenames`
  failed on critique_evaluator.json schema desync), sat unnoticed ~10h, swept into the merge.
- **m5a — done despite terminal `needs_rework`** (see #4).
**Fix:** gate `done` on green-suite + merged-PR; write a per-milestone outcome record.

### 4. Worktree-carry false positives — [HARNESS] · known recurring
- **m5a**: FALSE `needs_rework` — review couldn't baseline pre-existing failures + a
  DIFF_SIZE_SANITY flag citing `docs/execute-token-aggregation.md`, a foreign file from an
  unrelated carried commit (inflated diff to 112 files / 15,150 lines).
- **m6b**: out-of-band manual merge forked main's dirty state, breaking PR isolation.
**Fix:** snapshot a pre-run failure baseline; scope the review diff to the milestone's own commits.

### 5. Silent failures inside the fail-loud epic — [HARNESS] · ironic
- **m3a**: 5 zombie sessions (0 function_calls, ~50KB payload ingested, exited doing nothing,
  relaunched 5× with no error/retry signal).
- **m6a** abandonment-without-error; **m6b** red-suite-unnoticed; **adaptive_critique inert**
  on m5c/m5b despite the flag, with no marker distinguishing real-adaptive from degraded.
**Fix:** WARN-and-count 0-function-call sessions; fail-loud assertion when adaptive critique
silently degrades to static.

### 6. Idle / scheduling — [DRIVING] · lower priority
~3h28m of VERIFIED orchestration dead-air (m3b 26m; m5b 12m+25m; m5c 78m+46m; m5a 31m).
m6b's 10h overnight gap is what hid the red suite. (The m5d "25.5h gap" was a debunked
cross-repo log phantom; m4's ~5h is a human break.)

## What went WELL (don't regress these)
- Technical outcome landed cleanly; **near-zero runtime crashes/stalls/retries** — execution was smooth.
- The **M0 characterization gate worked** as the safety net every later milestone relied on.
- Critique **did** catch real bugs where it mattered (m2 scope misses + schema mismatch; m5b
  orphan-code; m5c caller scope-drift).
- Several prior known-bugs **did NOT reproduce** (adaptive-critique KeyError fallback,
  chain max_blocked_retries kill) — those fixes held.

## Data-quality caveat (matters for future retros)
Time-bucketing `~/.codex/sessions` pulled in unrelated sessions from other repos
(vibecomfy, Astrid, codex-tui) that matched milestone windows. The facts files were
contaminated (M2: 83 foreign of 133; m6a: 12 of 15; m6b: 16 of 20). Clean numbers above
filter sessions by **cwd == hardening worktree AND originator == codex_exec**. Any future
log-based analysis must apply this filter or it will wildly inflate token/time totals.

## The one-sentence meta-finding
The epic proved the *cheap-execute* thesis but exposed that **the real cost and the real
fragility both live in premium orchestration** — over-tiered drivers, unbounded critique
loops, and a "done" signal that doesn't require passing the gate.
