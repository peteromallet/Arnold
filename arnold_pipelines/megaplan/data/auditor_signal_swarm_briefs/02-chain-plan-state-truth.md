You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate signals around chain truth vs plan truth. Include chain state files, chain-health progress markers, plan state, events.ndjson, cloud-chain logs, completed[] semantics, current_milestone_index, PR state, and stale plan shadows.

Context paths:
- arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
- tests/cloud/test_progress_auditor.py
- tests/cloud/test_watchdog_wrappers.py
- /workspace/.megaplan/cloud-sessions/*.chain-health.progress.json on cloud
- <workspace>/.megaplan/plans/.chains/*.json on cloud

Return candidate signals as structured bullets:
- signal_name
- exact evidence to collect
- interpretation
- false-positive guard
- how to group/dedupe
- report placement

Think broadly: stale shadows, terminal-looking incomplete state, complete-but-open-PR, merged-but-awaiting-merge, plan active while chain stale, plan replaced by later milestone, current_plan_name mismatch, completed[] label-only entries, missing chain spec, missing chain-health marker, and contradictory timestamps.
