You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality.

Working directory: /Users/peteromalley/Documents/megaplan

Read:
- docs/agentbox-persistent-machine-plan.md
- arnold_pipelines/megaplan/cloud/cli.py
- arnold_pipelines/megaplan/cloud/providers/base.py
- arnold_pipelines/megaplan/cloud/providers/railway.py
- arnold_pipelines/megaplan/cloud/providers/ssh.py
- arnold_pipelines/megaplan/store/base.py as needed for state models
- arnold_pipelines/megaplan/types.py as needed for TmuxSession/CloudRun types

Focus only on operation registry, tmux/process runner, logs, status, attach/stop/restart overlap.

Return:
- Existing functionality we can reuse directly.
- Existing functionality that needs extraction/generalization.
- Missing pieces for AgentBox.
- Risks/gotchas.
- A recommended first implementation slice.

Keep the answer under 900 words. Use file references.
