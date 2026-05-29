# XCUT — Cost & Model-Tier Analysis (hardening epic, 12 milestones)

**Scope:** premium (GPT-5.x) *orchestration* spend — plan / critique-dispatch / gate / review / execute-driver turns. Execute *workers* (DeepSeek) run off-log and are not in these sessions; this is the orchestration layer only, which is the question being asked.

**Method (contamination fix):** the `*-facts.md` aggregates are contaminated — the time-bucketed manifests pulled in unrelated `codex-tui` sessions from other repos (vibecomfy, Astrid). I re-derived every number by re-scanning each manifest's files and keeping **only** sessions where `session_meta.originator == codex_exec` AND `cwd == .../​.megaplan-worktrees/hardening-run`. All retained sessions are 100% GPT-5.x (gpt-5.5 / gpt-5.4); zero cheap models appear in orchestration. Tokens = sum of each session's final cumulative `token_count`. Cost priced at the intro doc's own GPT-5.5 rates ($5.00/M miss, $0.50/M cached, $30.00/M out).

## (a) Clean per-milestone premium-token table

Contaminated rows in the raw facts are flagged; the clean column is the truth.

| Milestone | clean / contam sessions | Premium tokens (clean) | Uncached-in | Out | GPT-5.5 cost | % epic $ |
|---|---|---:|---:|---:|---:|---:|
| **m2-store** | 50 / **83** ⚠ | **87.7M** | 5,097K | 361K | **$77.47** | **33.6%** |
| m4-naming | 17 / 29 ⚠ | 28.0M | 1,418K | 107K | $23.54 | 10.2% |
| m5b-godfiles | 8 / 3 | 23.8M | 1,683K | 88K | $22.06 | 9.6% |
| m3a-fail-loud-policy | 12 / 8 | 26.9M | 1,262K | 86K | $21.63 | 9.4% |
| m5a-store-decomp | 9 / 2 | 15.9M | 1,786K | 82K | $18.39 | 8.0% |
| m5c-eval-execute | 13 / 4 | 19.8M | 1,156K | 100K | $18.06 | 7.8% |
| m3b-fail-loud-enforce | 8 / 4 | 21.4M | 726K | 70K | $16.06 | 7.0% |
| m0-characterization | 4 / 1 | 12.8M | 479K | 42K | $9.81 | 4.3% |
| m5d-pipeline-godfiles | 16 / **8** ⚠ | 8.5M | 756K | 48K | $9.06 | 3.9% |
| m6b-deadcode-tests | 4 / **16** ⚠ | 8.8M | 295K | 36K | $6.81 | 3.0% |
| m1-resolution | 5 / 6 ⚠ | 6.2M | 512K | 36K | $6.49 | 2.8% |
| m6a-surface-config | 3 / **12** ⚠ (abandoned) | 0.46M | 159K | 12K | $1.30 | 0.6% |
| **TOTAL** | | **260.3M** | 15.3M | 1.07M | **$230.67** | 100% |

**Trust note:** ⚠ rows had heavy contamination in the raw facts — m2 (83 foreign sessions vs 50 real), m6b (16 vs 4), m6a (12 vs 3) — so any number copied from those `*-facts.md` headline aggregates (e.g. m5d's phantom "25.5h / 89M") is **untrustworthy**. The clean column above is trustworthy. ~93% of all tokens are cached harness re-sends; the load-bearing premium signal is uncached-input + output.

**#1 is M2, confirmed** — 33.6% of premium tokens *and* premium cost, single-handedly. M4, M5b, M3a form the next tier (~$22 each).

## (b) Ranked over-tiering offenders

Over-tiered = premium driver on mechanical work (census / rename / file-move / behavior-preserving split / dead-code) that a hard objective gate already protects. Every per-milestone judge independently scored lens-4 (tier mismatch) **SIGNIFICANT** for these:

1. **m4-naming — $23.54.** 17/17 premium sessions for mechanical renames + one *fully pre-decided* data migration; plus ~450K tokens re-reviewing a byte-identical plan 5×. Worst absolute premium waste on locked work.
2. **m5b-godfiles — $22.06.** Behavior-preserving file-move; premium on review/gate/driving turns.
3. **m3a-fail-loud-policy — $21.63.** Bounded AST/grep census + add-warning edits; "premium reasoning earned nothing here." (+5 zombie sessions.)
4. **m5a-store-decomp — $18.39.** Pure seam-split; premium *and* ended in a false `needs_rework` from worktree-carry noise.
5. **m5c-eval-execute — $18.06.** Two-file mechanical split; `adaptive_critique` bought nothing.
6. **m3b / m0 / m5d / m6b — $9.06–$16.06 each.** Guardrail surgery, test scaffolding, code-moves, a hand-merged test split — all mechanical, all premium-driven.

**Wasted premium share:** the 9 mechanical milestones consumed **$130.66 = 56.6%** of all premium orchestration cost. Only **M2** ($77.47, 33.6%) had a stakes-based justification — and even there the judge flagged a non-converging 9-round critique loop (FLAG-M2-001→017) as the real waste, not the planning itself. So **well over half** of premium orchestration dollars drove work a cheaper orchestrator could have run behind the existing characterization gate.

## (c) Proposed tier policy

The root cause is real: `chain.yaml` pins `profile`/`depth` by milestone **stakes** (M2 = data integrity → premium/thorough/high) and applies the resulting premium driver uniformly to *every* orchestration turn — plan, critique-dispatch, gate, review, execute-driver. But stakes and orchestration *difficulty* are different axes. A behavior-preserving rename is high-blast-radius (stakes) yet trivial to *drive* (difficulty) — and the M0 characterization gate makes any regression cheap to catch and revert, collapsing the residual risk of a cheap driver.

Proposed policy — split the two axes:

- **[DRIVING] Tier the driver by orchestration difficulty, not stakes.** Add a per-milestone `driver_model` override. Default the *driver* to mid-tier (gpt-5-mini / deepseek-v4-pro) for any milestone tagged `behavior_preserving: true` or whose brief contains LOCKED/DECIDED survivors (m4 archetype). Reserve premium driving for *design-bearing* turns only (the M2 ownership-map plan, genuinely open critiques). Caching means the win is in output/reasoning tokens.
- **[DRIVING] Gate-credits-cheap.** When a milestone has an objective pass/fail gate (import-smoke, golden e2e, `--collect-only` parity), the gate *is* the correctness guarantee — let the cheaper driver run and trust the gate. Keep stakes-based premium only where there is **no safe recovery path** (M2's persisted run-state) — that's the one true exception.
- **[DRIVING] Scale the lens/critique budget to blast radius.** Cap behavior-preserving milestones at a refactor subset (`scope`, `all_locations`, `verification`); drop `robustness: full` → `light`. 9/9 lenses on a pure code-move is low marginal value (m5d, m6a).
- **[HARNESS] Throttle non-converging critique.** Add a max-critique-rounds / convergence check so an M2-style loop can't accrete flags indefinitely on premium.
- **[HARNESS] Fix the audit pipeline + milestone-outcome record.** Key manifest selection on exact plan id + `originator==codex_exec` + worktree `cwd` (not substring/time-window); emit a `milestone_outcome` (completed/failed/abandoned) per boundary so a silent decompose-then-stop (m6a) is visible.

## (d) Verdict on the intro-doc cost claim

**The ~78% DeepSeek / ~$12 claim is internally honest but measures a different thing, and it materially understates *orchestration* cost.** The $12 is explicitly "the DeepSeek line item" — the execute-worker API bill — and the doc openly states the premium slice "rode a flat Codex/ChatGPT subscription (≈$0 marginal)." That's a defensible framing for out-of-pocket cost.

But the premium *orchestration* it counts as ~$0 is **not** small: priced like-for-like on the doc's own GPT-5.5 rates, the clean orchestration spend is **~$231** — roughly **19× the $12 DeepSeek line**, and it sits almost entirely *outside* execute. The doc's "execute is 74% of all tokens" frames execute as the cost center; on a true-API basis, premium plan/critique/review/gate/driving is the larger bill, and M2 alone ($77) dwarfs the entire DeepSeek invoice. The doc's all-premium counterfactual ($422) and "29×/37×" ratios remain directionally right. The needed correction: the $12 is real out-of-pocket *given a sunk subscription*, but "78% DeepSeek" is a token share that hides that the premium 22% is the expensive 22% — and it is over half over-tiered.

*(~990 words)*
