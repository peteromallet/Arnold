# A1 — Mechanism behind the M2-store non-converging critique loop

**Plan:** `m2-store-abstraction-20260525-2003` · worktree `/Users/peteromalley/Documents/.megaplan-worktrees/hardening-run` · originator `codex_exec`
**Source of truth:** 50 hardening-run codex_exec sessions in `manifests/m2-store-logs.txt`. The M2-store loop ran 18:07–19:04 on 2026-05-25: plan_v1 → … → plan_v9 (**9 plan versions, 8 revise rounds, 8 critique rounds**). The worktree + plan dir are deleted, so the diff/critique payloads were reconstructed from the prompts embedded in each critique session (the revise step emits a "Unified diff between plan versions" that the *next* critique prompt carries verbatim).

## Plan-version diff sizes (parsed from the embedded unified-diff blocks)

Plan size at v9 ≈ **229 lines / ~7.2K tokens, 26 `##` headers, 20 numbered steps.**

| Round | versions | + added | − removed | hunks | churn (add+rem) | churn % of plan |
|------:|:--------:|------:|------:|----:|----:|----:|
| R1 | v1→v2 | 98 | 75 | 1 | **173** | ~75% |
| R2 | v2→v3 | 54 | 45 | 7 | 99 | ~43% |
| R3 | v3→v4 | 79 | 68 | 1 | **147** | ~64% |
| R4 | v4→v5 | 81 | 58 | 6 | 139 | ~61% |
| R5 | v5→v6 | 36 | 30 | 7 | 66 | ~29% |
| R6 | v6→v7 | 54 | 48 | 10 | 102 | ~45% |
| R7 | v7→v8 | 111 | 95 | 5 | **206** | ~90% |
| R8 | v8→v9 | 28 | 23 | 7 | 51 | ~22% |
| | | | | | **Σ 983** | mean **122 / round (~53%)** |

(Conservative: each block was parsed up to its first closing fence; true churn is ≥ these numbers.) Flagged-true findings per round trended **60 → 47 → 41 → 67 → 34 → 35 → 29 → 46 → 10** — high and *non-monotonic* (R4 and R7 spike), only collapsing on the final pass. Critique was never converging on a shrinking residual; it kept finding ~30–60 issues against a plan that had just been rewritten by ~50%.

## How the critic evaluates: WHOLE plan, every round (not the diff)

- The critic prompt embeds the **entire current plan** as `Plan:\n{context["latest_plan"]}` — `megaplan/prompts/critique.py:298-299`, sourced from `latest_plan_path(...)` at `:139`. The diff is only *additional* context (`revise_block`), `:275-280` / `:314`. So the critic re-reads and re-investigates the full ~229-line plan each round; it is **not** scoped to changed sections.
- Memory anchoring *does* exist but is partial:
  - Prior findings are re-attached per check via `_build_checks_template` — `megaplan/prompts/critique.py:233-264` — **but only for check_ids still active this iteration** (`active_check_ids` filter, `:238-241`).
  - The evaluator re-selects the lens set from scratch every iteration (`selections` → `active_checks`, `megaplan/handlers/critique.py:208-217`); flag-lifecycle/diff/resolution context is fed to the *evaluator* (`:132-155`) and to the critic as `revise_context` (`:336-357`). When the lens set shifts round-to-round, dropped lenses lose their prior-findings anchor and newly-added lenses scan the whole plan blind.
- `compute_recurring_critiques` (`handlers/critique.py:455`) and the "Reuse existing flag IDs" / "verified_flag_ids" instructions (`prompts/critique.py:320`) try to suppress re-flagging, but they cannot anchor what the revise step has physically rewritten.

## Verdict: primarily (A) revise churn → a moving target

The dominant driver is **(A)**. Every revise rewrote on the order of **half the plan** (mean 122 churn lines vs a 229-line plan; three rounds ≥147, peak 206 at R7), so each subsequent critique was legitimately reviewing largely **new text**, and the whole-plan critic (prompts/critique.py:298-299) re-investigated all of it from scratch. The flag count never decayed toward zero (it re-spiked at R4/R7), which is the signature of churn manufacturing fresh surface area, not of a stable plan being nitpicked.

**(B) is a strong amplifier, not the root cause:** the critic always re-scans the full plan, prior-findings anchoring is limited to lenses that survive the evaluator's per-round re-selection, so any churned or newly-lensed section is reviewed blind. **(C) genuine complexity is minor** — the plan is only ~229 lines / 20 steps; that volume does not justify 8 rounds. The loop didn't converge because `revise` treated each round as a near-rewrite (A) and the critic had no diff-scoped, fully-anchored view to confirm "this section is settled" (B).

**Fix direction:** cap/penalize revise churn (a delta budget per round, or "touch only flagged sections") and make the critic diff-aware + fully anchor prior verdicts across the evaluator's lens re-selection so unchanged sections are not re-litigated.
