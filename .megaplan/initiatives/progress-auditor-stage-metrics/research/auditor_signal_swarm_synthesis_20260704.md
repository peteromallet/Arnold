# Progress Auditor Signal Swarm Synthesis

Date: 2026-07-04

Scope: signal ideas for the megaplan 6-hour progress auditor, including low-level execution signals, cloud/runtime signals, human/PR/CI gates, repair/meta-repair custody, and high-level process inefficiencies.

Source: 9 DeepSeek subagents, one per plane:

- execution lifecycle
- chain/plan state truth
- watchdog supervision
- repair-loop custody
- meta-repair
- auditor reporting/model dispatch
- deployment/runtime environment
- human/PR/CI gates
- high-level process/product health

Raw outputs live under:

```text
/tmp/auditor-signal-swarm-wave1/
```

## Executive Judgment

The 6-hour auditor should become two explicitly separated phases:

1. `gather/report`: cheap, deterministic, non-agentic, exhaustive enough to describe the evidence surface and suspicious patterns.
2. `interpret/act`: model dispatch, repair recommendations, or automated repair, operating from the deterministic report.

The main improvement is not just more issue detectors. It is better evidence coverage and better shape. The report should tell the model what planes were inspected, what evidence was missing, what contradictions exist, and which signals are negative controls. That nudges the model toward breadth without making the gather phase agentic.

The highest-value signals are the ones that catch false green states and stale custody:

- chain says done but plan/session/PR says not done
- watchdog says healthy while repair/meta-repair churn is recent
- repair loop claims running but no process/log progress exists
- live worker exists but phase/event/session evidence does not advance
- model repair was launched but its verdict, deployment, or relaunch was not consumed
- human/PR/CI gate is blocking but the system keeps treating it as execution work

## Recommended Report Shape

Add a stable top-level schema to every report-only run:

```json
{
  "audit_mode": "report_only",
  "generated_at": "...",
  "subject": {
    "host": "...",
    "container": "...",
    "workspace": "...",
    "chain_id": "...",
    "plan_id": "..."
  },
  "coverage": {
    "plan_state": "present|missing|stale|contradictory",
    "plan_vs_discovered_sessions": "checked|missing",
    "events_ndjson": "present|missing|stale|invalid",
    "chain_log": "present|missing|stale",
    "chain_state": "present|missing|stale|contradictory",
    "watchdog_report": "present|missing|stale",
    "repair_data": "present|missing|stale|corrupt",
    "meta_repair_records": "present|missing|stale",
    "user_actions": "present|missing|stale",
    "git_pr_ci": "checked|not_checked|unavailable"
  },
  "data_quality": {
    "missing_evidence": [],
    "stale_evidence": [],
    "contradictions": [],
    "negative_controls": []
  },
  "signal_counts": {},
  "findings": [],
  "efficiency_metrics": {},
  "dispatch_summary": {
    "model_dispatch_enabled": false,
    "would_dispatch": false,
    "dispatch_reason": null
  }
}
```

Per finding, prefer this shape:

```json
{
  "signal": "green_with_recent_repair_churn",
  "severity": "high",
  "plane": "repair_custody",
  "entity": "session|plan|chain|host|pr",
  "evidence": {
    "positive": [],
    "negative_controls": [],
    "missing": []
  },
  "interpretation_hint": "why this is suspicious, not a model conclusion",
  "suggested_next_check": "specific deterministic check or model prompt topic"
}
```

## P0 Signals

These should be built or hardened first because they catch real blind spots and prevent false confidence.

### Gather/Dispatch Safety

- `dispatch_summary_present`: every audit states whether model dispatch was enabled, skipped, or would have happened.
- `report_only_no_model_process`: report-only mode verifies it did not launch Codex/Claude/Kimi/DeepSeek.
- `coverage_block_present`: every report includes evidence coverage, missing evidence, stale evidence, and contradictions.
- `prompt_shell_safe`: generated prompts/heredocs cannot execute backticks or shell substitutions.
- `model_dispatch_separate_phase`: no automatic repair/model run from the default diagnostic surface.

Reason: this prevents the audit from becoming another opaque actor in the same system it is diagnosing.

### Chain/Plan Truth

- `chain_inconsistent_done`: chain claims complete, but plan/session/PR/user-action evidence disagrees.
- `completed_label_only`: only a textual completed label exists; index/count/session state does not support completion.
- `completed_count_index_disagreement`: completed count and current plan index disagree.
- `state_mismatch`: chain state, plan state, latest session state, and watchdog report disagree.
- `missing_chain_state`: expected chain state artifact is absent.
- `stale_chain_health_artifact`: chain-health artifact exists but is older than the last meaningful event.
- `between_milestone_cycling`: chain repeatedly moves around milestone boundaries without durable output.
- `latest_failure_is_stale`: the recorded latest failure is older than subsequent progress and should not drive repair.

Reason: the current system has multiple truth surfaces. False green and false stuck states come from trusting only one.

### Watchdog Supervision

- `watchdog_chain_health_disagreement`: watchdog says stuck/no-advance while chain-health shows active progress, or the reverse.
- `watchdog_report_stale`: report age exceeds the expected tick window.
- `watchdog_tick_gap`: watchdog process exists but no new tick/report appears.
- `watchdog_no_current_target_evidence`: watchdog claims a current target but cannot point to current session/plan artifacts.
- `watchdog_no_delta`: repeated ticks produce identical issue sets, counters, and timestamps.
- `watchdog_should_have_meta_repaired`: meta-repair trigger conditions are present but no meta-repair attempt exists.

Reason: watchdog output should be treated as one witness, not the authoritative state.

### Repair Custody

- `repair_data_ghost_running`: repair sidecar claims running but no process/log progress supports it.
- `repair_without_relaunch`: a repair claims success or action, but the target session was not relaunched/resumed.
- `repair_attempt_missing_record`: repair loop evidence exists in logs but no sidecar/attempt record exists.
- `repair_record_without_log`: sidecar records an attempt, but run dir/operator log is absent.
- `repair_sidecar_corrupt`: JSON sidecar cannot be parsed or required fields are missing.
- `repair_stale_lock`: lock/PID/custody marker is old and unsupported by a live process.
- `green_with_recent_repair_churn`: chain/session looks green while recent repair/meta-repair attempts indicate instability.
- `repair_same_root_cause_repeated`: multiple repair attempts target the same root cause without durable progress.

Reason: repair state is currently too easy to confuse with actual progress.

### Meta-Repair

- `meta_trigger_present_no_launch`: trigger threshold crossed but no meta-repair launched.
- `meta_launch_failed`: meta-repair process/container/session failed to start.
- `meta_verdict_untrusted`: verdict says fixed but lacks commit/install/restart evidence.
- `meta_fix_not_deployed`: meta-repair changed source but wrapper/container/host binary still uses old code.
- `meta_fix_not_consumed`: meta-repair succeeded but ordinary repair/watchdog did not re-run with the fixed logic.
- `meta_recursion_guard_active`: meta-repair is suppressed by recursion guard; report should say so explicitly.

Reason: meta-repair is only useful if its fix crosses the boundary into the live runtime.

### Deployment/Runtime

- `host_container_wrapper_drift`: host wrapper, container wrapper, and source wrapper differ.
- `running_process_older_than_wrapper`: process started before the wrapper/source fix it is supposed to use.
- `editable_install_stale`: Python import path or installed package is not the checkout expected by the operator.
- `container_not_healthy`: container missing, restarting, paused, or using unexpected image/volume.
- `tmux_session_dead`: expected watchdog/session/repair tmux session missing.
- `session_process_dead`: session state says running but PID/process is gone.
- `disk_or_memory_pressure`: resources are low enough to explain stalls or crashes.
- `auth_provider_unhealthy`: required API/provider credential is absent, expired, rate-limited, or failing smoke checks.

Reason: many apparent planning failures are actually environment drift.

## P1 Signals

These are the next layer: useful for breadth, triage, and preventing repeated waste.

### Execution Lifecycle

- `phase_transition_gap`: no expected phase transition after a reasonable window.
- `phase_duration_exceeded`: phase runtime exceeds baseline for plan size/profile.
- `execute_worker_dead`: execute phase has no live worker despite active state.
- `gate_permanent_iterate`: review/gate sends work back repeatedly without new evidence.
- `prep_clarification_stall`: prep waits for clarification when enough defaults/context exist.
- `events_sequence_gap`: events log has impossible or missing sequence transitions.
- `resume_stale_pid`: resumed session points to dead/old process.
- `plan_loop_degenerate`: plan keeps producing equivalent subplans with no execution progress.
- `finalize_output_empty`: chain reaches finalize but deliverable artifacts are missing.

### Human/PR/CI Gates

- `human_action_blocking`: open user action blocks progress and should be surfaced as a human gate, not a repair problem.
- `human_action_resolved_not_consumed`: action is resolved but the chain/session has not advanced from it.
- `pr_open_no_merge_path`: PR exists but no auto-merge/manual merge path is active.
- `pr_merged_chain_not_advanced`: PR merged but chain still waits on review/merge.
- `pr_closed_unmerged`: PR closed without merge while chain treats it as pending.
- `ci_failing_blocks_progress`: failing required check explains lack of advance.
- `ci_success_unconsumed`: checks passed but chain did not proceed.
- `ci_not_checked`: GitHub/CI state unavailable; report should mark this as unknown, not healthy.

### Repair Effectiveness

- `repair_success_rate_low`: recent repair attempts rarely produce durable progress.
- `repair_cost_high`: many model minutes/tokens/attempts spent per milestone or per merged PR.
- `repair_helped_then_regressed`: repair produced progress that later reverted to same failure.
- `repair_target_flapping`: repair alternates between targets without resolving any.
- `repair_queue_overlap`: multiple repair loops claim custody of the same target.

### Root Cause Clustering

- `same_root_cause_many_sessions`: same failure pattern appears across sessions/plans.
- `same_fix_repeated`: identical/similar patch attempted more than once.
- `false_positive_repeated`: same auditor/watchdog signal later disproven repeatedly.
- `stale_block_replay`: old blocking narrative keeps being replayed after newer evidence.

## P2 Signals

These are dashboard/process quality signals. They are lower urgency but high leverage once P0/P1 are stable.

### High-Level Efficiency

- `cycle_time_by_phase`: time spent in prep/execute/review/finalize/repair/waiting.
- `milestones_per_day`: durable completed milestones over time.
- `repair_to_progress_ratio`: repair attempts or model cost per useful progress unit.
- `wip_overload`: too many active sessions/plans/repairs relative to throughput.
- `queue_wait_time`: time from detected issue to repair start.
- `mttr_by_failure_type`: mean time to recover from common failure classes.
- `model_provider_roi`: progress per provider/model/time/cost, with failure class context.
- `plan_churn_rate`: plans rewritten/replaced before completion.
- `handoff_loss`: transitions where state/evidence was lost between agents/tools.

### Product/Process Quality

- `signal_coverage_unknown_high`: too much of the report is unknown/missing evidence.
- `operator_intervention_rate`: how often humans need to diagnose or unblock.
- `self_healing_claim_accuracy`: how often watchdog/repair claims match eventual reality.
- `audit_actionability_score`: percentage of findings with concrete next checks or fixes.
- `top_root_cause_families`: ranked recurring failure families with evidence examples.

## How To Nudge The Model Toward Breadth

The deterministic report should explicitly hand the model a coverage map. That makes breadth the default without asking the model to rediscover the system.

Recommended model input sections:

```text
Failure planes inspected:
- execution_lifecycle: findings=N, unknowns=N
- chain_plan_truth: findings=N, unknowns=N
- watchdog_supervision: findings=N, unknowns=N
- repair_custody: findings=N, unknowns=N
- meta_repair: findings=N, unknowns=N
- deployment_runtime: findings=N, unknowns=N
- human_pr_ci: findings=N, unknowns=N
- high_level_efficiency: findings=N, unknowns=N

Negative controls:
- Evidence that argues against the obvious diagnosis.

Contradictions:
- Surfaces that disagree and need reconciliation.

Missing evidence:
- What was not inspected or unavailable.

Question budget:
- Answer at least one question for every non-empty failure plane.
- Do not conclude green if any P0 contradiction or unknown remains unresolved.
```

This gives the model an agenda:

- reconcile contradictions
- separate missing evidence from healthy state
- consider every plane with findings
- avoid overfitting to the first salient log line

## Implementation Order

### First

1. Make `coverage`, `data_quality`, and `dispatch_summary` mandatory in report-only output.
2. Add tests that report-only mode cannot dispatch a model process.
3. Promote `repair_data_ghost_running`, `green_with_recent_repair_churn`, and `watchdog_chain_health_disagreement` into hourly/watchdog-visible checks, not only 6-hour audit checks.
4. Add chain/plan truth reconciliation: completed label, completed count, current index, latest session state, PR state, and user actions.
5. Add deployment/runtime drift checks for wrapper source/container/host and running process start time vs wrapper mtime.

### Second

1. Add repair custody reconciliation across sidecars, attempt logs, run dirs, locks, PIDs, and relaunch evidence.
2. Add meta-repair lifecycle checks: trigger, launch, verdict, deploy, consume, re-run.
3. Add lifecycle transition checks: phase gaps, duration exceeded, dead worker, empty finalize.
4. Add human/PR/CI gate classification, with optional GitHub checks when credentials are available.
5. Add root-cause clustering and stale-block replay detection.

### Third

1. Add dashboards/summary metrics for cycle time, repair cost, MTTR, WIP, provider/model ROI.
2. Track false-positive/false-negative history for watchdog and auditor signals.
3. Score audit actionability and evidence coverage over time.

## Current Concrete Changes Already Made

These were implemented before this synthesis:

- report-only mode forwards host env flags into the container
- report-only mode skips Codex/model dispatch when autofix is disabled
- prompt heredoc is quoted to avoid shell execution from backticks
- watchdog `chain_no_advance` guard checks live activity
- meta-repair launch wrapper accepts valid `FIXED` stdout instead of failing on stderr noise
- deterministic audit checks added for:
  - `repair_data_ghost_running`
  - `green_with_recent_repair_churn`
  - `watchdog_chain_health_disagreement`

## Bottom Line

The audit should stop being framed as "find the broken session" and become "produce an evidence coverage map across all failure planes." The model phase can then reason from that map. That is how the first phase informs the second without becoming expensive or agentic itself.

