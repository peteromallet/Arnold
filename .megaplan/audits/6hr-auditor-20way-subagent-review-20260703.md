# 6-Hour Auditor 20-Way Subagent Review - 2026-07-03

DeepSeek fanout: 20/20 completed successfully via `subagent-launcher/fan.py`.
Results directory: `/tmp/auditor-20way/results`.

## Verdicts

- PARTIAL: stale-state replay
- WEAK: live-agent progress misread
- WEAK: ordinary repair running forever
- PARTIAL: meta-repair not dispatched
- WEAK: meta-repair dispatched but no retrigger verification
- WEAK: subagent launch failure
- WEAK: wrong model tier routing
- WEAK: merge-policy PR wait
- WEAK: draft/premature merge
- WEAK: require_clean_base drift
- WEAK: workspace drift engine-vs-project
- PARTIAL: inconsistent done chain state
- PARTIAL: one-milestone-per-relaunch
- WEAK: agent transcripts hard to find
- WEAK: repair-data shape drift
- WEAK: stale watchdog report
- WEAK: redaction over/under
- WEAK: persistent findings not actionable
- WEAK: repair fixes committed but not installed
- WEAK: auditor overfixes project/workspace instead of root cause

## Consolidated Findings

The auditor prompt is conceptually strong: it tells the agent to inspect the project run,
immediate repair, meta-repair, watchdog, reports, sidecars, transcripts, and to ship
repair-system fixes when appropriate. The weakness is that too much remains implicit.
The auditor often gives paths and prose instructions, but not enough first-class evidence
fields, contradiction flags, freshness checks, active-install checks, or persistent
problem IDs.

The highest-risk gap is meta-repair verification. The auditor can now see "meta-repair
should have dispatched but no record/log exists", but it still does not clearly see:
meta-repair ran but wrote no record; meta-repair returned FIXED but did not retrigger
ordinary repair; or a patch was committed but the installed wrapper remained stale.

The second major gap is persistence. The auditor reads `/workspace/findings/persistent-problems.md`
and tickets, but it does not reliably write stable long-term findings with recurrence IDs.
Cross-plan patterns are computed in one audit report, then effectively become archive prose.

The third major gap is operational telemetry. The auditor needs structured liveness/process
evidence, watchdog-report freshness, subagent-launch health, and installed-wrapper freshness.
Without those, it can misclassify slow live work, stale reports, or a committed-but-inactive
repair as success.

## Recommended Root Fixes

1. Add `watchdog_report_age_min` and `watchdog_report_is_stale` to every finding.
2. Add `live_process_evidence`: PID alive, process age, CPU/IO/log growth, active worker model.
3. Flag `repair_data.outcome == running && iteration_count == 0` as suspicious partial liveness.
4. Expand `meta_repair_summary` to include partial failures: run log exists but no record, FIXED but no retrigger, no ordinary repair attempt after meta record.
5. Make meta-repair wrapper enforce retrigger verification itself after `FIXED`, rather than trusting Codex prose.
6. Add subagent dispatch health: Codex rc, stderr tail, whether DeepSeek/Hermes actually launched, and timeout/auth/path failure classification.
7. Add installed-runtime freshness evidence: source wrapper SHA/mtime versus `/usr/local/bin/arnold-*`, plus editable install refresh status.
8. Inject `root_cause_patterns` / cross-plan recurrence into each per-plan Codex brief before dispatch, not only final report assembly.
9. Add stable persistent problem IDs for recurring signatures: normalized signature hash, first_seen, last_seen, occurrence_count, affected sessions/plans.
10. Add append/update path for `/workspace/findings/persistent-problems.md` and/or `/workspace/findings/problem-index.json` from the auditor.
11. Strengthen redaction with a pre-dispatch scan and `redaction_audit` field, not only post-hoc file redaction.
12. Add explicit transcript index evidence: concrete candidate paths for Codex/Claude/Hermes/Kimi transcripts, not just broad directory names.

## Immediate Priorities

1. Fix meta-repair post-FIXED retrigger verification.
2. Add active-install freshness checks so "FIXED <sha>" means the running wrapper changed.
3. Add persistent problem index writeback.
4. Add watchdog-report freshness and live-process evidence to reduce false diagnoses.

