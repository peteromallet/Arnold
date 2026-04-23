# Auto-Improve Findings

Per-iteration results are in `iterations/NNN/analysis.md` and `changes.md`. This file captures cross-cutting learnings that apply to ALL future iterations.

## Pipeline bugs fixed (pre-iteration)
- Critique concern/evidence alias bug — GLM outputs `summary`/`detail` instead of `concern`/`evidence`. Fixed in merge.py.
- Gate hermes preflight — skipped when agent=hermes.
- Execute infinite loop — capped at 12 attempts, force proceed after max gate iterations.
- Finalize/gate now include flag evidence, not just concerns.
- No schema enforcement for Hermes — all prompt-only. Explains field mismatches.

## What actually changes model behavior
- **Simple prompt sentences work.** "Grep all usages" fixed under-scoping. "Read the traceback" fixes blind retries. One sentence > one taxonomy.
- **Formal systems don't.** Classification schemas, error category enums, structured diagnosis frameworks — these add code but rarely change what the model does.
- **The prep phase matters most.** A good brief that says "this needs changes in 3 places" directly prevents the top failure pattern.
- **Prep brief is a hypothesis, not gospel.** Plan was told "trust prep, don't re-explore." This caused plan to commit without considering alternatives (pytest-5840: fixed `unique_path` instead of removing it). Now: "use as starting hypothesis, consider if there's a simpler fix."
- **Structured critique checks work.** 7 checks with findings force the model to actually examine each area. django-16560 showed perfect usage: 5 flags → revise → 0 flags → clean proceed.

## Structured critique system (deployed)
7 checks from `checks.py`, single source of truth:
1. issue_hints — does the work address the issue?
2. correctness — is the logic right?
3. scope — right scale? minimal patch vs restructuring?
4. all_locations — all instances AND supporting infrastructure?
5. callers — right place? would it break callers?
6. conventions — matches how codebase solves similar problems?
7. verification — can we test it? trace the test's execution path.

Key design decisions:
- Checks with `default_severity: "uncertain"` resolve to `minor` (non-blocking) — conventions and verification don't force unnecessary ITERATE
- Multiple findings per check get unique flag IDs (check_id-N) to avoid overwrites
- Gate sees checks summary (what was checked, what was flagged)
- Iteration 2+ shows prior findings with status (addressed/open/disputed)
- `flags[]` is for additional concerns beyond the 7 checks

## Scoring truths
- Docker fails on Apple Silicon for non-Django repos. Use Modal.
- Modal is slow (~12 min/task) and flaky. But it works.
- "Correct but unscorable" is usually wrong. Always check FAIL_TO_PASS test status.
- Watch scorer must use Modal by default, max_workers=4 for parallel scoring.
- Patches must end with trailing newline or SWE-bench rejects as "malformed."
- Editable pip installs leak into global site-packages and break anyio. Clean before each task.

## Process truths
- Don't change prompts OR megaplan code mid-iteration. Workers load code at startup.
- If prep is doing legitimate work on a big codebase, let it run.
- The README is the only process doc.
- FINDINGS.md is institutional memory. Write learnings as they happen.
- Dashboard first, then dig.
- Don't modify megaplan source while eval runs are active — workers use live source tree.
- Distinguish: pipeline failure vs scoring infra failure vs model nondeterminism vs broken tooling.

## Structural issues identified (not yet fixed)
- `STATE_RESEARCHED` is a dead-end bug — state defined, no transitions
- Finalize has no quality gate — goes straight to execute
- `finalize.json` is mutable across 3 phases — should be immutable artifacts
- Review → rework cycle is hidden — not in WORKFLOW table
- Handler boilerplate copy-pasted 8 times — needs `run_step()` helper
- Callback injection in handle_execute — circular dependency workaround
- Flag management should be extracted to `flags.py`
- No distinction between infra errors (ImportError) and task errors — retry is pointless for broken tooling
- Need pre-flight check that verifies megaplan imports before starting tasks

## Iteration trajectory
| Iter | Raw | On scored | Key change |
|------|-----|-----------|------------|
| 001 | 56% (10/18) | 56% | prompt hardening, prep phase |
| 002 | 63% (12/19) | 63% | grep all usages, NotImplementedError signal |
| 003 | 59% (10/17) | 59% | estimated_scope, verify diagnosis |
| 004 | 76% (13/17) | 76% | 20 fresh tasks, anyio fix, structured critique |
