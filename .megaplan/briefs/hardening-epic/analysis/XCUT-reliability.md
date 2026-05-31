# XCUT — Harness reliability & process gaps across the 12-milestone hardening epic

Cross-cutting synthesis of the 12 per-milestone judgment/facts pairs against
`chain.yaml` and the chain pointer (`chain-f0921037b540.json`). The pointer marks
**all 12 milestones `done`, every `pr_number: null`, `dirty_flag: false`** — yet
`merge_policy: auto` promised a PR per milestone. The absence of any PR record is
itself the first integrity smell: "done" is being written without a landed,
gated PR behind it.

## (a) Done-status integrity

| Milestone | Truly done? | Caveat |
|---|---|---|
| m0-characterization | YES | Clean, ~21m, one legit test-caught fix. Premium over-tier only. |
| m1-resolution | YES | Clean single review pass; review emitted premature verdicts then self-corrected. |
| m3a-fail-loud-policy | YES (work) | **5 zombie sessions** fired silently (see b). Diff landed green. |
| m2-store | YES (work) | Plan landed but via a **non-converging 9-round critique loop** (flags →17); cost outlier (16h/89M tok). |
| m3b-fail-loud-enforce | YES | Execute-only capture green; 26-min dead-air gap. |
| m4-naming | YES | 7 redundant identical plan-review rounds; 1 self-inflicted `TypeError` caught by its own script. |
| m5a-store-decomp | **QUESTIONABLE** | Ended in a **FALSE `needs_rework`** from worktree-carry (pre-existing failures + a foreign `docs/execute-token-aggregation.md` from commit `a4399a4e` inflating the diff to 112 files/15,150 lines). Marked done despite a red terminal verdict. |
| m5b-godfiles | YES | 3 orphan-code IndentationErrors + 1 duplicated patch, all self-healed. |
| m5c-eval-execute | YES | `adaptive_critique:true` was inert (bought nothing); `jq` crashed on own critique output. |
| m5d-pipeline-godfiles | YES | Clean ~1h50m. The "25.5h overnight gap" is a **phantom** — facts mis-bucketed unrelated `codex-tui` sessions from vibecomfy/Astrid repos. |
| m6a-surface-config | **NO — ABANDONED AFTER PLAN** | Plan + critique-assign + 18-task decompose ran on premium (174K tok), then **stopped**. No execute/review/gate session for plan id `...20260527-2307`, no worktree, no branch, no commit. Chain still wrote `done`. Zero landed diff. |
| m6b-deadcode-tests | **NO — PIPELINE BYPASSED** | Declared `directed/light + adaptive_critique` never ran (0 real `megaplan run/auto/chain`). Closed by a **hand-driven `git merge --no-ff`**. Execute ended **RED** (`test_step_schema_filenames` failed on `critique_evaluator.json` schema desync), sat unnoticed ~10h, swept into the manual merge. No gate caught the red suite. |

**Verdict: 3 of 12 have a questionable/false "done"** (m6a abandoned, m6b red-suite-bypass, m5a false-reject), plus m2's done rests on a non-converged critique.

**Root cause of unreliable done-detection:** the chain marks a milestone `done`
on *execute-finished* (or, for m6a, on *decompose-finished*), not on
*gate-passed-green-PR-merged*. Three failure modes share this root:
- **m6a** — decompose-then-exit emits no terminal `milestone_outcome` event, so a
  silent drop is indistinguishable from success.
- **m6b** — no post-execute hard gate, so "execute stopped (red)" == "done"; the
  out-of-band manual merge skipped the gate entirely.
- **m5a** — done was recorded despite the review's terminal `needs_rework`,
  meaning the chain ignores the very gate verdict it solicited.
`pr_number: null` across all 12 confirms no milestone actually transited a
gated-PR boundary; `auto` merge-policy was never exercised as designed.

## (b) Catalog of silent failures (ironic for a fail-loud epic)

1. **m3a — 5 zombie sessions.** Launched 18:00–18:03Z, 12–59s each, ~50KB payload
   ingested, **0 function_calls**, no error/timeout/retry; driver relaunched 5×
   and moved on. The exact silent-no-op pattern m3a existed to kill.
2. **m6a — abandonment without error.** 174K premium tokens of plan/critique/
   decompose, then nothing. No failure record; `done` written anyway.
3. **m6b — red suite slipped 10h.** `test_step_schema_filenames` left failing at
   execute-stop, survived the overnight gap, swept into the manual merge with no
   gate ever flagging red. (`critique_evaluator.json` missing from
   `schemas.SCHEMAS` — same fragile evaluator plumbing as the known epic bug.)
4. **m5a — false reject treated as terminal then overridden to done.** Review
   couldn't baseline inherited failures, so it rejected correct work; the chain
   then recorded done anyway — failure signal was both wrong *and* ignored.
5. **m5c / m4 — inert `adaptive_critique`.** Flag set, no adaptive evaluator
   fired (m5c bought nothing; m4 happened to run genuine mixed critics — the flag
   is not reliably honored on codex vendor).

## (c) Worktree-carry incidents

- **m5a — confirmed, two-axis contamination.** (i) Pre-existing test failures the
  reviewer couldn't exonerate (no baseline manifest) → rejection. (ii) Foreign
  uncommitted files forked from MAIN's dirty state inflated the diff
  (`docs/execute-token-aggregation.md`, commit `a4399a4e`, unrelated token-tracking
  work) → spurious `DIFF_SIZE_SANITY ratio=1515` on 112 files/15,150 lines.
- **m6b — PR-isolation damage.** The hand `git merge --no-ff` of `hardening-epic`
  into MAIN forks main's dirty state in (the known carry hazard) and makes the
  epic's diff un-isolatable for a reviewable PR.
- Other 10 milestones: no carry contamination observed (m5d's apparent gap was a
  log-attribution artifact, not carry).

## (d) Idle / scheduling waste (VERIFIED gaps only)

Excluding the debunked m5d "25.5h" (cross-repo contamination) and human breaks:
- m3b: **26m** mid-chain dead-air (~39% of its wall-clock).
- m5b: **12m + 25m** between sessions.
- m5c: **78m + 46m** orchestration gaps (critique→T5, T8→T11).
- m5a: **31m** between sessions.
- m6b: **10h11m** overnight (execute-stop → manual merge next morning).
- m4: 4h56m is a human afternoon break (excluded as not a harness stall).

**Verified machine/orchestration dead-air ≈ 3h28m** (26+12+25+78+46+31), plus
the **10h11m m6b overnight** during which a red suite sat unobserved — the single
largest and most damaging idle window because it hid a failure.

## Top 3 reliability fixes (ranked by severity)

1. **[HARNESS] Gate the `done` transition on green-suite + merged-PR, not
   execute-finished.** Root cause of m6a (abandoned→done), m6b (red→done), and
   m5a (rejected→done). Write a per-milestone `milestone_outcome`
   (completed|failed|abandoned) at every boundary; refuse `done` unless a gate
   ran and passed and a PR landed (`pr_number` non-null). `chain status` must show
   "decomposed-but-never-executed" and "stopped-red" as distinct non-green states.
2. **[HARNESS] Snapshot a pre-run failure baseline + scope the review diff to this
   milestone's own commits.** Kills the recurring worktree-carry false-positive
   (m5a). Capture `pytest` failure list + base commit at worktree creation; review
   subtracts inherited noise and diffs against the milestone base, not the dirty
   working tree. Refuse to start a milestone off a dirty worktree.
3. **[HARNESS] Treat a completed session with 0 function_calls (and no terminal
   status) as a hard WARN-and-count event** (`EMPTY_SESSION_NO_TOOLCALLS`),
   bounded by `max_blocked_retries`. Kills m3a's 5 silent zombies — the literal
   fail-loud regression this epic was meant to prevent.

[DRIVING] runner-up: stop hand-merging mid-chain (m6b) and drive every milestone
close through `megaplan chain` in the worktree so the declared gate actually runs.
