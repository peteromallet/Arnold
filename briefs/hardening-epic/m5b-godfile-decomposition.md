# M5b — CLI / chain / workers god-file decomposition

**Rubric:** `directed//high`, robustness `full`
**Position in epic:** milestone 8 of 12. Depends on M4 (names) + M5a (store already sliced). Pure behavior-preserving refactor. (The orchestration/execute god files — evaluation.py, execute/core.py, patterns.py, phase_result.py, prep_research.py — moved to the new **M5c**; they're coupled to each other and deserve their own pass.)

## Outcome
Split the cli/chain/workers god files along their natural seams, with public import paths preserved and zero behavior change. Each split is its own commit so regressions bisect cleanly.

## Scope (IN)
- **`cli.py` (~5216 loc)** → `cli/` package: `cli/parser.py` (the ~1050-line `build_parser()`), `cli/status_view.py` (`_build_*_payload`/`_build_*_context`), `cli/setup.py` (`_install_owned_*`, `handle_setup_*`), `cli/skills.py` (`_canonical_*`), and **(added per review) `cli/feedback.py`** for the orphan cluster tests import directly — `_collect_feedback_rows` (`:2505`), `_filter_feedback_rows` (`:2602`), `_render_feedback_table` (`:2646`), plus handling for `_compute_user_action_blockers` (`:231`), `_resolve_project_root` (`:4532`). Leave `cli/__init__.py` as thin dispatch (`main()` + `COMMAND_HANDLERS`).
- **`chain.py` (~2427 loc)** → extract ~1000 loc of git/PR plumbing (`_checkout_milestone_branch`, `_ensure_milestone_pr`, `_commit_and_push_phase`, `_pr_state`, `_reconcile_terminal_pr_state`, `_refresh_base_branch`, `_is_worktree_dirty`, `_classify_sync_state`, `_capture_sync_state`, `_remote_branch_exists`, `_claimed_paths`) into `chain/git_ops.py`.
- **`workers/_impl.py`** → extract the ~15 `_default_mock_*_payload` functions (`:1540-2090`) into `workers/_mock_payloads.py`. **Per review: `workers/__init__.py` does `from megaplan.workers._impl import *`** and `shannon.py:30`/`hermes.py:17` import from `_impl` — preserve those symbols (re-export).
- **Cross-handler write-path dedup (added per gap-hunt — same fork class as M1).** `gate.json` is written from **3 different paths**: `gate.py:525` via the `_write_json_artifact` wrapper, but `critique.py:341` and `override.py:294` call `atomic_write_json(plan_dir/"gate.json", …)` directly, bypassing the hash-returning wrapper + `_write_gate_carry`. Converge on one helper. Likewise receipt-building is copy-pasted between `review.py:423-443` and `shared.py:341-356` (extract a shared `_emit_receipt`); and `critique.py:96-98` inline-repeats its own `_safe_roster_rank` helper (`:51-63`).
- **Prompt re-export shims (moved here from M6 per review).** The 8 verified shim files in `prompts/` (`critique_creative.py`, `critique_joke.py`, `execute_creative.py`, `execute_doc.py`, `execute_joke.py`, `prep_joke.py`, `revise_creative.py`, `revise_joke.py`) forwarding to `pipelines.*` are import-path cruft — collapse them as part of this import-path milestone (finish the migration: point callers at the canonical `pipelines.*` location, delete the shims).
- **Duplicate `"user-action"` key** `cli.py:4510` and `:4523`. **Verified (Opus): both map to the same `handle_user_action`, so removing either is a pure no-op** — just delete the redundant entry; no behavior risk despite the earlier "confirm which is intended" caution.

## Locked decisions
- **Behavior-preserving** (except the documented one-line `user-action` dedup).
- Preserve public import paths via re-exports; collapse-don't-fork.
- **One commit per split** (cli, chain, workers, cross-handler dedup, prompt-shims) for clean bisection.

## Open questions (for plan to resolve)
- For the `gate.json` write-path convergence: does the `_write_json_artifact` wrapper's hash return value matter to the `critique.py`/`override.py` callers, or can they adopt it cleanly?

## Constraints
- Full suite + M0 baselines green; **the M0 remote-exec import guard must pass** — `cloud/supervise.py:54` builds a remote one-liner importing `_capture_sync_state` from `megaplan.chain`; moving it without keeping the symbol importable from `megaplan.chain` silently breaks all cloud-supervised chains (the old string-presence test won't catch it).
- No circular imports.

## Done criteria
- `cli.py`, `chain.py`, `workers/_impl.py` each below a sane size (no new module > ~800 loc) and single-responsibility.
- `gate.json` written through one helper from all 3 sites; receipt-building shared; `_safe_roster_rank` called not re-inlined.
- Prompt shim files gone; callers point at `pipelines.*`.
- Duplicate `"user-action"` key removed (intended entry confirmed).
- M0 import-smoke + remote-exec guard + CLI parser snapshot all green; zero behavior diff elsewhere.

## Touchpoints
`megaplan/cli.py`→`cli/`, `chain.py`→`chain/`, `workers/_impl.py` + `workers/__init__.py`, `handlers/{gate,critique,override,review,shared}.py` (write-path dedup), `prompts/` (8 shims + callers), `cloud/supervise.py` (verify), `tests/` (import paths).

## Step order (per review)
cli (simplest import graph) → workers/_mock_payloads (fully internal) → chain/git_ops → cross-handler write-path dedup → prompt-shims. Each a separate commit with full-suite verification.

## Anti-scope
- Do NOT change behavior beyond the documented `user-action` dedup; no bug fixes, no error-handling changes (M3*).
- Do NOT rename concepts (M4) or change store parity/routing (M2/M5a) — only move.
- Do NOT decompose the store backends (M5a) or the orchestration/execute god files (M5c/M5d).
- **Enforceable guardrail:** splitting `chain.py` (which imports `auto.drive`) must be a re-export-only move — NO edits to `_phase_command`, `drive()` next-step selection, `workflow_next`/`infer_next_steps`, `loop/engine.py` dispatch, or the chain↔auto coupling logic. A reviewer greps these symbols to confirm they only moved, never changed.
