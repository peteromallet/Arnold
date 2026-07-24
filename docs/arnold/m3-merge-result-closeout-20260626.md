# M3 Merge Result Closeout — 2026-06-26

This document records the post-merge closeout of the `arnold-complete-cleanup-single-root` epic.

## Checkout under test

- **SHA:** `7acae0837623a5398c504669ee743ab522ab2d66`
- **Branch:** `cleanup-single-root-m3-closeout`
- **Date:** 2026-06-26

## Verification results

| Gate | Command | Result |
|------|---------|--------|
| Scoped baseline | `pytest tests/arnold/conformance/test_conformance.py tests/arnold/conformance/test_checks.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_legacy_reference_allowlist.py tests/arnold/conformance/test_megaplan_coupling_gate.py tests/arnold/workflow/test_canonical_megaplan_conformance.py` | 152 passed |
| Full conformance | `python -c "from arnold.conformance.suite import run_conformance_suite; result = run_conformance_suite(); print(result); raise SystemExit(0 if result.passed else 1)"` | all checks passed |
| Legacy root absent | `test ! -e arnold/pipelines/megaplan` | pass |
| Legacy root not in HEAD | `git ls-tree -r HEAD --name-only | rg '^arnold/pipelines/megaplan/'` | none |
| Canonical root present | `test -d arnold_pipelines/megaplan` | pass |
| Canonical import | `python -c "import arnold_pipelines.megaplan"` | ok |

## Single-root state

- `arnold/pipelines/megaplan/` is absent from the working tree and from `HEAD`.
- `arnold_pipelines/megaplan/` is present, importable, and contains the canonical Megaplan implementation.
- The only hits for legacy path strings under `arnold_pipelines/megaplan/` are in `arnold_pipelines/megaplan/audits/hermes_vendoring.py`, which performs git-history inspection and is allowlisted in `arnold/conformance/legacy_reference_allowlist.json`.

## External cleanup exceptions

- The old operational worktree `.megaplan-worktrees/native-python-pipelines-completion-thread2` is already removed.
- The TypeScript snapshot at `/Users/peteromalley/Documents/Arnold.pre-megaplan-rename-20260624-142318` remains because no concrete `archive/typescript-bot-era` target exists in this checkout. A blocker artifact records the required owner decision and deletion trigger.

## Ticket

Ticket `01KVZZ45DAZW9P5H4JA66JWNY3` is closed by this evidence, blocked only by the externally-owned TypeScript snapshot archive decision.
