You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate all useful signals the 6-hour auditor should surface about watchdog supervision: marker discovery, should-run/operator status, watchdog report items/issues, current-target evidence, liveness, repair dispatch, relaunch, reaping, stale markers, status drift, and no-advance/stuck counters.

Inspect:
- arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
- arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- docs/hetzner-watchdog-meta-loop.md
- latest /workspace/watchdog-report.json and /workspace/watchdog.log on cloud

Return:
- current signals already present
- missing signals
- signal taxonomy
- high-value false-positive guards
- what should be deterministic vs left to model judgement

Be explicit about signals that catch process inefficiency, not just hard failure.
