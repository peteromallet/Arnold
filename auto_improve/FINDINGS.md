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
- **Formal systems don't.** Classification schemas, error category enums, structured diagnosis frameworks — these add code but rarely change what the model does. The model already knows how to classify; it needs to be told to ACT on what it finds.
- **The prep phase matters most.** A good brief that says "this needs changes in 3 places" or "this function has NotImplementedError for these inputs" directly prevents the top failure pattern.

## Scoring truths
- Docker fails on Apple Silicon for matplotlib, pytest, requests, sphinx. Use Modal.
- Modal is slow (~12 min/task) and flaky (sandbox timeouts, billing limits). But it works.
- "Correct but unscorable" is usually wrong. We assumed 3 patches were correct. Only 1 was. Always check FAIL_TO_PASS test status in the report.
- Watch scorer must use Modal by default, retry up to 3 times, capture stderr.

## Process truths
- Don't change prompts mid-iteration. Run → score → analyze → THEN change.
- If prep is doing legitimate work on a big codebase, let it run. Don't cap useful exploration.
- The README is the only process doc. Re-read it every check-in.
- FINDINGS.md is institutional memory. Write learnings as they happen.
- Dashboard first (`python -m auto_improve.dashboard`), then dig.
- The megaplan executor doesn't have your wisdom. Feed it the iteration docs + these learnings + explicit constraints.
- Review megaplan output critically — it builds what you describe, including overengineered systems if that's what you described.
- Distinguish: pipeline failure vs scoring infra failure vs model nondeterminism. Three different problems.

## Iteration trajectory
| Iter | Raw | Improvements | Regressions | Key change |
|------|-----|-------------|-------------|------------|
| 001 | 56% (10/18) | baseline | baseline | prompt hardening, prep phase |
| 002 | 63% (12/19) | pytest, sklearn-12973, sympy-20590 | pylint-4970 | grep all usages, NotImplementedError signal |
