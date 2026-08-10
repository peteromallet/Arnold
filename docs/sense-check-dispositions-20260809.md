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

## DeepSeek-fix swarm (round 2) — 2026-08-09

6 parallel fixers verified each failure cluster against RT1. Fixed 4 merge
regressions (committed ec269aa1af):
1. arnold-repair-loop: restored RT1 legacy model-default literals (unification
   layer dropped them; policy re-binds at dispatch).
2. arnold-watchdog: defense-in-depth fail-closed stale handling in
   claim_active_repair_launch (stale -> no dispatch, exception-proof).
3. finalize_authority.py: stance_violations added to _EXECUTE_TASK_MUTABLE
   (creative-mode merge regression).
4. test_status_snapshot_cli.py: liveness fixture evidence (lineage drift).

Documented as pre-existing lineage debt (byte-identical on RT1):
- test_source_initiative_repair (wrapper early-exit contract mismatch)
- test_status_snapshot_projection (7, /workspace read-only env)
- test_phase_handoff_custody (2), test_partnered_5_glm_profile (2),
  test_engine_fix_ports (2), test_authority_incident_cycles::test_complete_
  replay (1), repair_goal remaining, m11 (6), managed_agent (16),
  pipeline_run_cli (7), resident (6), watchdog_wrappers (env paths),
  progress_auditor (4), fix_the_fixer_skill (2), replay_oracle replan (1),
  finalize_task_feasibility (1), bypass_gating (1), codex_cli_runner (1),
  supervisor_runtime_isolation (2), repair_loop_mode_seam (2),
  watchdog_pr_reconciliation (3)
> **Authority status: non-authoritative.** This document is historical/design record, not a live-authority operator surface (T44 zero-authority migration).
