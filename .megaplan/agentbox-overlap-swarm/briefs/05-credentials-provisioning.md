You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality.

Working directory: /Users/peteromalley/Documents/megaplan

Read:
- docs/agentbox-persistent-machine-plan.md
- docs/cloud.md
- arnold_pipelines/megaplan/cloud/auth.py
- arnold_pipelines/megaplan/cloud/template.py
- arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl
- arnold_pipelines/megaplan/cloud/providers/ssh.py
- scripts/refresh-cloud-claude-key.sh if present

Focus only on machine provisioning and credential sync overlap.

Return:
- Existing functionality we can reuse directly.
- Existing functionality that needs extraction/generalization.
- Missing pieces for AgentBox.
- Risks/gotchas, especially secret storage and OAuth rotation.
- A recommended first implementation slice.

Keep the answer under 900 words. Use file references.
