You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality.

Working directory: /Users/peteromalley/Documents/megaplan

Read:
- docs/agentbox-persistent-machine-plan.md
- arnold_pipelines/megaplan/cloud/supervise.py
- arnold_pipelines/megaplan/supervisor/
- arnold_pipelines/megaplan/pipelines/live_supervisor/
- arnold_pipelines/megaplan/resident/scheduler.py
- docs/megaplan_live_watchdog.md if useful

Focus only on the Guardian daemon: periodic checks, safe actions, unblocking, operation classification, notifications, and approval boundaries.

Return:
- Existing functionality we can reuse directly.
- Existing functionality that needs extraction/generalization.
- Missing pieces for AgentBox.
- Risks/gotchas.
- A recommended first implementation slice.

Keep the answer under 900 words. Use file references.
