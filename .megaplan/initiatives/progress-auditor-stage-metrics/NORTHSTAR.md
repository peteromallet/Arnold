---
type: anchor
anchor_type: north_star
slug: progress-auditor-stage-metrics
title: 'North Star: Progress Auditor Stage Metrics'
created_at: '2026-07-04T13:55:04.569241+00:00'
---

# North Star: Progress Auditor Stage Metrics

## End State

The 6-hour progress auditor has a deterministic, non-agentic accounting surface that summarizes lifecycle health by stage. A report can say, for each relevant stage, how many stalls, retries, repair attempts, meta-repair attempts, no-op loops, handoff gaps, and human/PR/CI waits were observed, with evidence pointers and explicit unknown/missing data.

The model/repair phase consumes those metrics after gather/report. It does not invent stage counts from prose logs.

## Non-Negotiables

- Preserve report-only safety: report-only mode must not dispatch Codex, Claude, Kimi, DeepSeek, repair-loop, or meta-repair work.
- Stage metrics must be derived from durable evidence such as plan state, events, chain state/logs, watchdog reports, repair-data, meta-repair records, user-actions, PR/CI state when available, and process/runtime evidence.
- Missing evidence must be represented as unknown or missing, never silently counted as zero.
- Existing deterministic signals must keep working: `repair_data_ghost_running`, `green_with_recent_repair_churn`, and `watchdog_chain_health_disagreement`.
- The output schema must be stable enough for downstream model prompts and dashboards.
- Tests must cover both positive counts and evidence-missing cases.

## Explicit Non-Goals

- Do not redesign all watchdog/repair custody machinery.
- Do not replace the current 6-hour auditor with a new service.
- Do not build a full dashboard UI.
- Do not require GitHub/CI credentials for the core local report to be useful.
- Do not make the gather phase agentic or expensive.

## Allowed Temporary Bridges

- It is acceptable for first-pass PR/CI stage metrics to report `not_checked` when credentials or local metadata are unavailable.
- It is acceptable to implement stage classification as a conservative mapper over current artifact names and states before extracting a larger typed lifecycle model.
- It is acceptable for high-level efficiency metrics to be partial if the report clearly marks missing inputs.

## Drift Signals

- The implementation adds model prompting but no deterministic `stage_metrics` block.
- Counts are generated from natural-language summaries instead of durable events/state.
- Missing logs or state files are treated as healthy zero-count stages.
- The sprint expands into broad repair/watchdog refactoring without first shipping the auditor accounting surface.
- Report-only mode regresses and launches an agent or repair command.
