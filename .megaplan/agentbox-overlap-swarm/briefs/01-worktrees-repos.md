You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality.

Working directory: /Users/peteromalley/Documents/megaplan

Read:
- docs/agentbox-persistent-machine-plan.md
- arnold_pipelines/megaplan/bakeoff/worktree.py
- arnold_pipelines/megaplan/cli/__init__.py sections around _setup_init_worktree and _setup_chain_worktree
- arnold_pipelines/megaplan/chain/git_ops.py as needed
- tests/bakeoff/test_worktree.py and any chain worktree tests you find

Focus only on repo registry and worktree service overlap.

Return:
- Existing functionality we can reuse directly.
- Existing functionality that needs extraction/generalization.
- Missing pieces for AgentBox.
- Risks/gotchas.
- A recommended first implementation slice.

Keep the answer under 900 words. Use file references.
