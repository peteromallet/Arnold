You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality.

Working directory: /Users/peteromalley/Documents/megaplan

Read:
- docs/agentbox-persistent-machine-plan.md
- arnold_pipelines/megaplan/resident/discord.py
- arnold_pipelines/megaplan/resident/runtime.py
- arnold_pipelines/megaplan/resident/cli.py
- arnold_pipelines/megaplan/resident/auth.py
- arnold_pipelines/megaplan/resident/profile.py
- arnold_pipelines/megaplan/resident/cloud.py
- arnold/agent/tools/send_message_tool.py if useful

Focus only on Discord Operator overlap: message-triggered agent, tools, auth, confirmations, conversation state, and outbound notifications.

Return:
- Existing functionality we can reuse directly.
- Existing functionality that needs extraction/generalization.
- Missing pieces for AgentBox.
- Risks/gotchas.
- A recommended first implementation slice.

Keep the answer under 900 words. Use file references.
