You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate every useful signal the 6-hour progress auditor could surface about megaplan execution lifecycle itself: init, prep, plan, critique, gate, finalize, execute, review, feedback, chain advance, PR publication, and resume/retry.

Context:
- Repo: /Users/peteromalley/Documents/Arnold
- Cloud target: Hetzner box root@159.69.51.216, container megaplan-cloud-agent.
- Current auditor code: arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor
- Watchdog code: arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
- Recent decision record: arnold_pipelines/megaplan/data/progress_auditor_fix_decision_20260704.md
- Skill doc: arnold_pipelines/megaplan/data/_codex_skills/progress-auditor-debug/SKILL.md

Use file and terminal tools. You may inspect cloud data read-only with ssh/docker.

Return a ranked list of candidate signals. For each signal include:
- signal_name
- failure plane
- evidence fields/files
- why it matters
- false-positive guard
- where to surface it: finding reason, green veto, coverage matrix, report metadata, or model prompt context
- one test fixture idea

Focus on lifecycle breadth, not repair/meta details unless they directly affect phase progression.
