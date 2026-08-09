# Main-unification — Sense-check findings + dispositions (2026-08-09)

Codex tree-review of the merged `main-unification` branch identified 3 CRITICAL /
2 HIGH / 1 MEDIUM. Dispositions:

## CRITICAL — resolved

1. **Stale runtime authority state committed** — removed 1461 tracked runtime-state
   files (`.megaplan/authority/` SQLite + leases, `system_logs/`, `runs/`,
   `incident-evidence/`, `repair-queue/`, `watchdog-run-logs/`, `cloud-logs/`,
   `test_store/`, loose `.megaplan/*.log`). Added `.gitignore` rules so they are
   never re-committed; authority state initializes at runtime. Retained:
   `initiatives/` (versioned source/evidence), `fixer-sessions/` (30 files,
   required), `tickets/`, `incident-ledger/`, research dirs.

2. **Watchdog manifest resolution fails open** — `arnold-watchdog` now fails
   closed (exit 78) when a manifest declares a non-executable repair bin, instead
   of silently falling back to a different runtime. Fallback only when the
   manifest is absent.

3. **Fenced job state machine not wired to production** — DEFERRED (not a merge
   defect): the new `acquire_job_lock`/`advance_job_state` state machine is
   unification Phase-3A scaffold (plan: "3A = adapters over current
   implementations"). Production callers use the working legacy
   `acquire_repair_lock`. Rewiring production repair paths is follow-up work,
   tracked in the longer-term fixes (single fenced repair coordinator).

## HIGH — resolved

4. **GOAL-fixer-unification.md missing** — restored from the local working tree
   (untracked; required by merge context).

5. **Skill symlinks absolute/broken** — 8 `skills/*/SKILL.md` symlinks restored
   to RT1's relative `../../data/...` targets (were absolute
   `/Users/peteromalley/Documents/Arnold/...` from the workspace lineage);
   all resolve.

## MEDIUM — resolved

6. **Duplicate `_escalate_persistent_unroutable_rework`** in execute/batch.py
   (pre-existing in RT1) — consolidated to the single later definition.

## Pre-existing lineage debt (documented, NOT merge regressions — verified byte-identical to RT1)

- resident subagent-launcher tests (absolute `/workspace/runtime-candidates/...` paths)
- test_managed_agent (16), m11 validation shard (6), phase_handoff_custody (2)
- These fail identically on RT1's tip; the merge did not worsen them.
