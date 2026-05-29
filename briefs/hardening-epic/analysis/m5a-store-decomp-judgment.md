# Judgment — milestone `m5a-store-decomp`

**Verdict (one line):** A clean, confusion-free, behavior-preserving refactor that the work itself nailed, but the run ended in a FALSE `needs_rework` driven entirely by worktree-carry contamination (pre-existing failures + foreign files in the diff) — and it spent 100% premium GPT-5 on orchestration that didn't need it.

Config (chain.yaml): `vendor: codex`, `profile: partnered` (`partnered//high`), `robustness: full`, `depth: high`, `adaptive_critique: true`.

## 7 lenses

| # | Lens | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Blockers / dead-ends | FINE | 0 stalls/retries/resumes/timeouts; 5 task_started + 5 task_complete, all clean (facts §3). |
| 2 | Excessive revision | MINOR | Exactly 1 review session, 3 progressive verdict updates all `needs_rework`; no execute→rework loop ran. The rework was never *actioned* — but the verdict is a false reject (see lens 6), so the "1 round" is itself wasted. **[VERIFIED]** `review_verdict` set to `needs_rework`, T10 fails. |
| 3 | Low-value critiques | FINE | Adaptive critique configured but no critique model ever invoked; 0 fallbacks/KeyError/static (facts §2). Notably this CONTRADICTS the prior epic finding of a silent static-fallback KeyError on every codex milestone — here critique simply never fired at all. |
| 4 | Model-tier mismatch | SIGNIFICANT | Orchestration ran 100% premium: planning `gpt-5.5/high`, review `gpt-5.5/low`, 3 execute-driver turns `gpt-5.4/medium` (facts §5). Planning a *pure mechanical seam-split* (helper `_*_dir()` blocks are the seam, stated in brief) at `high` effort, and a deterministic review at premium, is over-tiered. |
| 5 | Repeated/bloated context | SIGNIFICANT | ~40% dup of the ~23K developer prompt (3 hashes / 5 sessions); user message grew 11K→48K→52K→57K→155K chars as full prior execute output was re-appended into the review turn (facts §7). 89.6% cache hit softens cost but not context-window pressure. |
| 6 | Model confusion | FINE (agent) / SIGNIFICANT (harness-induced) | The agent itself showed zero confusion — no wrong-file edits, no contradictions (facts §8). The confusion is the *reviewer's*, caused by contaminated inputs (lens 7). |
| 7 | Inefficiency / waste | SIGNIFICANT | 15.7M tokens / 1h59m for a behavior-preserving move-code milestone, and the run's terminal output is a false reject. The DIFF_SIZE_SANITY flag fired on `changed_lines=15150, files=112` — but its own `evidence_file` is `docs/execute-token-aggregation.md`, a token/cost-tracking doc with NO relation to store decomposition. **[VERIFIED]** git shows that file belongs to commit `a4399a4e "Track tokens and cost on every phase"`. |

## Worktree-carry assessment (the central problem)

This is a textbook worktree-carry false-positive, on TWO axes:

1. **Pre-existing test failures.** Execute correctly reported `3023 passed … 8 failed; those 8 failures match the unrelated cloud/config/review/worker failures already seen in prior batch context` **[VERIFIED]**. The reviewer rejected T10 anyway: `Full test suite does not pass: executor reports 6 non-DB failures and no baseline failure list proves they pre-existed.` **[VERIFIED]**. The failures are real, pre-existing, and out of scope — the reject is purely because no clean baseline was captured to exonerate them.
2. **Foreign files in the diff.** 112 files / 15,150 changed lines is wildly larger than a store split (~13 entity slices). The flagged evidence file proves unrelated work (token-tracking docs/code) was carried into the worktree and counted against this milestone's diff. **[VERIFIED]**

Net: the milestone's actual deliverable (store decomposed, single Store protocol intact, EpicSummary/EpicSearchSummary fork collapsed to one canonical class with an identity assertion `schemas.EpicSearchSummary is store.EpicSummary` — verified in the 14-31 execute log) appears DONE and correct. The `needs_rework` is an artifact, not a real quality signal.

## Top 3 improvements

**1. Capture a pre-run failure baseline so review can't false-reject on inherited failures. [HARNESS]**
- Problem: review demands proof the 8/6 failures pre-existed; none exists, so it rejects correct work.
- Root cause: no baseline failure manifest is snapshotted before execute; the reviewer's "full suite must be green" criterion can't subtract inherited noise.
- Fix: run+store `pytest --co`/failure list at worktree creation (extend the M0 import-smoke harness), pass it to the review gate, and have the review prompt compare against baseline rather than requiring zero failures. Same root cause as the epic's known worktree-carry finding — generalize the fix.

**2. Exclude carried/foreign files from the milestone diff before the diff-size sanity check. [HARNESS]**
- Problem: DIFF_SIZE_SANITY fired `ratio=1515` on a diff whose evidence file (`docs/execute-token-aggregation.md`) is from a different feature.
- Root cause: the worktree forked MAIN's dirty state; the gate diffs worktree-vs-base including pre-existing uncommitted changes.
- Fix: scope the review diff to files touched by *this milestone's commits only* (diff against the milestone's own base commit, not working tree), or refuse to start a milestone off a dirty worktree. Touch: the review-gate diff assembly + worktree-init cleanliness check.

**3. Down-tier orchestration for mechanical refactors. [DRIVING]**
- Problem: planning at `gpt-5.5/high` and review at premium for a seam-defined move-code task; ~40% prompt duplication compounds the spend.
- Root cause: `partnered//high` + `depth: high` applied uniformly regardless of how mechanical the milestone is.
- Fix: for behavior-preserving refactor milestones, drop plan/review to `depth: medium` (or route orchestration to a cheaper model) in chain.yaml; the seam is already enumerated in the brief, so high-effort planning earns nothing here. Execute-driver tier can stay.

---
**Adversarial check:** Both highest-impact claims spot-checked against raw `rollout-…15-11-26….jsonl` and `…14-31-29….jsonl` and `git log`. The `needs_rework` verdict, the "no baseline proves they pre-existed" rationale, the diff-size flag's foreign evidence file, and execute's pre-existing-failure framing are all **[VERIFIED]** in raw logs, not DeepSeek extraction artifacts.
