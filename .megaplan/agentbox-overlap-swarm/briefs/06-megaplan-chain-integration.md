You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality.

Working directory: /Users/peteromalley/Documents/megaplan

Read:
- docs/agentbox-persistent-machine-plan.md
- docs/cloud.md
- arnold_pipelines/megaplan/chain/__init__.py
- arnold_pipelines/megaplan/chain/spec.py
- arnold_pipelines/megaplan/chain/git_ops.py
- arnold_pipelines/megaplan/cloud/cli.py
- arnold_pipelines/megaplan/resident/cloud.py

Focus only on launching Megaplan plans/chains as AgentBox operations and letting Guardian/Discord Operator inspect/advance them.

Return:
- Existing functionality we can reuse directly.
- Existing functionality that needs extraction/generalization.
- Missing pieces for AgentBox.
- Risks/gotchas.
- A recommended first implementation slice.

Keep the answer under 900 words. Use file references.
