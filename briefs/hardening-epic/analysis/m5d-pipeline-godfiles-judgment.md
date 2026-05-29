# Judgment — milestone m5d-pipeline-godfiles

**(a) Verdict:** FINE — a clean, efficient ~1h50m behavior-preserving refactor (plan → 9-lens critique → gate → 26-min execute, zero rework). The facts file's headline "~25.5h / overnight review gap" is a **log-attribution artifact** and is wrong; the only real inefficiency is mild critique over-provisioning for a pure code-move.

Chain config (chain.yaml:99-106): `vendor: codex`, `profile: directed` (directed//high), `robustness: full`, `depth: high`, `adaptive_critique: true`.

## (b) Seven lenses

| # | Lens | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Blockers / dead-ends | FINE | No `timeout`/`SIGKILL`/`heartbeat`/`max_blocked`/`resume` in any genuine M5d session. The 10 "retry" hits are WRITE-ACCESS-CONTRACT boilerplate. **No blocked states.** |
| 2 | Excessive revision | FINE | 0 execute→review→rework cycles. Two execute turns (20:29, 20:47 UTC), one commit each per locked decision "one commit per file"; no reflag loop. The 13 "revise/ITERATE" hits are plan text being read, not directives. |
| 3 | Low-value critiques | MINOR | All 9 lenses fired on an ~870+720 LoC **pure code-move** (no logic change). `correctness`/`callers`/`all_locations` on a behavior-preserving relocation is low marginal value; the two real catches were stale plan cross-refs to *other* milestones' test files, not M5d defects. |
| 4 | Model-tier mismatch (orchestration) | MINOR | Orchestration ran premium GPT-5.5 (plan + critique-dispatch + gate/review) + GPT-5.4 execute. For a directed//high *behavior-preserving relocation* with an explicit import-smoke gate, the gate/review reasoning did not obviously need GPT-5.5. Critique correctly used DeepSeek (4 pro + 5 flash), 0 premium — that part is right-sized. |
| 5 | Repeated/bloated context | FINE (by design) | ~95K-token harness prompt re-sent per session but **95.9% cache hit** (3.68M of 3.84M input cached). Plan re-injected to both execute turns is the harness contract. Tokens earned their place. |
| 6 | Model confusion | FINE | No wrong-file edits, contradictions, or looping in M5d execute. The two "factual errors" the facts cite were the *plan* citing other plans' test files (test_gate.py / test_execute.py) — caught by critique, not acted on wrongly. |
| 7 | Inefficiency / waste | FINE | Real span ~1h50m (19:06–20:55 UTC, see below); execute 26 min; ~3.85M tokens almost entirely cached. Proportionate to a two-file decomposition. The claimed 25.5h waste does not exist. |

## Adversarial spot-checks (the facts file's two highest-impact claims)

1. **"~25.5h total with a ~23.5h overnight review gap" — [VERIFIED FALSE].** The two files the facts attribute to M5d's gate/review (`...21-59-55...` and `...22-37-53...`) are **not megaplan sessions**. Their `session_meta` shows `originator: codex-tui` and `cwd: .../reigh-workspace/vibecomfy` (1567 comfy hits vs 70 incidental "patterns/phase_result" word-collisions) and `.../reigh-workspace/Astrid` respectively. They are unrelated interactive Codex sessions in other repos that merely overlap in time and were mis-bucketed by the DeepSeek extraction. **The overnight gap is a phantom.**
2. **Real M5d span — [VERIFIED].** Every genuine M5d session is `originator: codex_exec`, `cwd: .../.megaplan-worktrees/hardening-run`, all confined to **2026-05-27T19:06:26Z → 20:55:49Z (~1h50m)**, matching the brief's claimed 21:06–23:07 CEST. Execute 20:29–20:55 (~26 min) is the only genuine number the facts kept.

**Prior-finding cross-refs:** adaptive-critique KeyError fallback — **NOT present here** (evaluator_model `gpt-5`, `skipped:[]`, no fallback/static error); contradicts the "every codex-chain milestone" claim for M5d. max_blocked_retries, idle-cap kills, OpenRouter mis-route, gate TIEBREAKER→ITERATE downgrade — **none observed.**

## (c) Top 3 improvements

1. **Phantom 25.5h gap from cross-session log attribution → fix the analysis pipeline. [HARNESS]**
   - *Problem:* the facts file (and any judge trusting it) reported a 23.5h idle review gap that never happened.
   - *Root cause:* the log-bucketing step (`briefs/hardening-epic/analysis/manifests/m5d-pipeline-godfiles-logs.txt` generation) selects session files by keyword hits (`patterns`/`phase_result`) instead of by `session_meta.cwd == worktree` and `originator == codex_exec`. Common English/code words collide across concurrent unrelated TUI sessions.
   - *Fix:* in the manifest builder, filter sessions on `cwd` prefix = the run's worktree AND `originator == codex_exec`; drop `codex-tui` sessions outright. Re-derive `*-facts.md` wall-clock from that filtered set. This single change corrects lenses #1/#7/#9 for the whole epic, not just M5d.

2. **Critique over-fired on a behavior-preserving relocation. [DRIVING]**
   - *Problem:* 9 lenses (incl. `correctness`, `callers`, `all_locations`) ran on a no-logic-change code move; marginal value low.
   - *Root cause:* `directed//high` + `robustness: full` selects the full lens set regardless of "behavior-preserving" task class.
   - *Fix:* for relocation/rename milestones, drop to `robustness: light` (or a refactor lens subset: `scope`, `all_locations`, `verification`) — the import-smoke gate already guards correctness. Cheap; loses little.

3. **Premium GPT-5.5 drove gate/review on a gated mechanical task. [DRIVING]**
   - *Problem:* orchestration premium spend where a hard import-smoke + golden gate does the real verification.
   - *Root cause:* uniform premium driver across all epic milestones.
   - *Fix:* allow a cheaper driver tier (e.g. gpt-5-mini / deepseek-v4-pro) for behavior-preserving milestones with an objective pass/fail gate; reserve GPT-5.5 for design-bearing ones. Cache amortization (95.9%) means the win is in output/reasoning tokens, not input.

*(~640 words)*
