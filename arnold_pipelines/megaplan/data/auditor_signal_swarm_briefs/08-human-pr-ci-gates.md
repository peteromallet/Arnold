You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate signals around human gates, PR/merge state, CI/build state, user_actions, user_action_resolutions, unresolved vs resolved-but-unconsumed actions, PR closed/merged drift, auto-vs-manual merge policy, and CI failures that block chain progress.

Inspect:
- arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
- arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- tests around PR reconciliation and user actions
- cloud data read-only where useful

Return candidate signals. Identify which need GitHub API/gh, which can be inferred from existing chain state, and which should be optional to avoid slow audits.
