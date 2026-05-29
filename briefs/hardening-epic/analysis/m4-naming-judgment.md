# Judgment — milestone m4-naming

**Verdict (one line):** A clean, low-friction run (zero stalls, zero rework loops, one self-inflicted verification-script bug) whose only real inefficiency is over-critique — 7 near-identical pre-execution plan-review rounds re-sending the same ~64.6k-token context — and premium GPT-5.x driving wall-to-wall orchestration that a cheaper model could have handled.

## Config (chain.yaml)
`directed//high +prep`, robustness `full`, vendor `codex`, `with_prep: true`, `adaptive_critique: true`.

## The 7 lenses

| # | Lens | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Blockers / dead-ends | **FINE** | Zero retries, zero resumes, zero SIGKILL/timeouts across all 17 files. The 163 raw `blocked` hits are Codex base-prompt text, not events. The 4h56m midday gap is a human break, not a stall. |
| 2 | Excessive revision | **MINOR** | No execute→review→rework cycles at all. But 7 pre-execution plan-review rounds fired the **identical 9 check_ids** each time (`issue_hints, correctness, scope, all_locations, callers, conventions, verification, criteria_quality, prerequisite_ordering`) — re-reviewing the same plan, not converging rework. [VERIFIED] |
| 3 | Low-value critiques | **SIGNIFICANT** | 72 sub-checks = 8 rounds × 9 checks. 5 of the 7 substantive rounds re-sent **exactly 64,638 input tokens** (byte-identical context) for the same 9-check sweep → ~450k input tokens spent re-reviewing an unchanged plan. The reviews are observational (no APPROVE/REJECT gating verdict drives them). [VERIFIED] |
| 4 | Model-tier mismatch | **SIGNIFICANT** | Orchestration ran **17/17 premium** main-agent sessions (11×gpt-5.5, 6×gpt-5.4). The work is mechanical renames + one locked, fully-specified data migration; the plan brief pre-decided every homonym survivor. Planning + the 8 review rounds did not need premium GPT-5.x to drive. Critics were correctly tiered (47 cheap deepseek / 25 premium) — the waste is the **driver**, not the critics. |
| 5 | Repeated/bloated context | **SIGNIFICANT** | Same as #3: 5 review rounds at identical 64,638-token input is the textbook signature of un-cached, re-sent context that earned nothing. [VERIFIED] |
| 6 | Model confusion | **MINOR** | Two self-corrected path misses (`rg prompts` no-such-dir; `sed tests/test_prompts_shared.py` missing). One real consistency bug: `tmp_verify_m4_vocabulary_compat.py` called `_build_gate_carry(recommendation=...)` after the agent itself renamed the field → `TypeError`. [VERIFIED] Small, agent-introduced, caught by its own verification. |
| 7 | Inefficiency / waste | **MINOR–SIGNIFICANT** | ~450k input tokens on redundant reviews + all-premium orchestration, against a diff that is mostly renames. Wall clock (7h28m active) is dominated by the human break, not machine waste. |

## Contradictions / extensions of prior epic findings
- **CONTRADICTS** "adaptive critique fell back to static on EVERY codex-chain milestone (KeyError critique_evaluator)." On m4 the critique was **genuinely adaptive**: per-check `critic_model` assignments mixed deepseek-v4-pro/flash, claude-sonnet-4-6, and gpt-5.5; no `KeyError`, `fallback`, or `static` in any of the 17 logs. [VERIFIED] Either the fix landed by m4, or this milestone is the exception — worth confirming which.
- **CONFIRMS (absence):** none of max_blocked_retries=1, worktree-carry scope noise, 900s idle kills, or OpenRouter mis-routing appear here. The run was unusually clean.

## Top 3 improvements

**1. Stop re-running the full 9-check plan review when the plan hasn't changed.** [HARNESS]
Problem: 7 review rounds, 5 with byte-identical 64,638-token input, all firing the same 9 checks → ~450k wasted input tokens and zero convergence value. Root cause: the review loop has no "plan unchanged since last review → skip / short-circuit" guard, and reviews are observational (no gating verdict to terminate the loop). Fix: in the review orchestration (the step that emits the `selections` array of `check_id`s), hash the plan artifact and skip a re-review when the hash is unchanged; cap pre-execution review rounds (e.g. 2) for `directed` profiles where the brief already locks decisions. This is the single highest-ROI change.

**2. Drive `directed`+locked-decision milestones with a cheaper orchestrator.** [DRIVING]
Problem: 17/17 premium main-agent sessions for mechanical renames whose every homonym survivor was pre-decided in the brief/chain notes. Root cause: the chain profile pins gpt-5.x for the driver regardless of how locked the work is. Fix: for milestones where the brief contains "DECISION (verified)/LOCKED" survivors and anti-scope guardrails (m4 is the archetype), route the **driver** to a mid-tier model and keep premium only for the critic panel. Capture the rename plan as a checklist the cheap driver executes.

**3. Make agent-authored verification scripts rename-aware.** [HARNESS]
Problem: the agent renamed `gate_carry`'s field, then its own `tmp_verify_m4_vocabulary_compat.py` called `_build_gate_carry(recommendation=...)` → `TypeError`. [VERIFIED in rollout-…T21-29-54] Root cause: throwaway verify scripts are written before the rename fully propagates and aren't re-derived from the post-migration signature. Fix: for data-migration milestones, require the back-compat read + a *real* test in the suite (the brief asked for this) rather than an ad-hoc `tmp_verify_*.py`; lint/reject `tmp_*` verification scripts in favor of a pytest the gate actually runs.

---
*Adversarial spot-checks: Lens #3/#5 (7 identical 64,638-token review rounds, 9 check_ids each) — [VERIFIED] by parsing raw `check_id`/`input_tokens` from rollout files. Lens #6 (gate_carry TypeError) — [VERIFIED] verbatim in rollout-2026-05-26T21-29-54. Adaptive-critique contradiction — [VERIFIED] mixed `critic_model` values, no fallback/KeyError in any log.*
