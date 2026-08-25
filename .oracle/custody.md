# Custody baseline — onboard-oracle run

- Date: 2026-08-25
- Repo: /Users/peteromalley/Documents/Arnold (origin https://github.com/peteromallet/Arnold.git)
- Source ref: `native/build-forward-epic` @ `370d7f6f739c27fe447060b82bc01cd45de0d535`
- Worktree: /Users/peteromalley/Documents/Arnold-onboard-oracle, branch `onboard-oracle`
- Protected local work that must survive (lives ONLY in main checkout, not this worktree):
  - Deleted: arnold_pipelines/megaplan/skills/{babysit,babysitter,babysitting-principles}/SKILL.md
  - Modified: skills/cleanup-loose-branches/SKILL.md, skills/subagent-launcher/SKILL.md
  - Untracked: .megaplan/initiatives/chain.yaml, skills/pipeline-babysitting/, tests/agentbox/test_standalone_runtime_attestation.py
- Other worktrees observed: ~/Documents/arnold-oracle (oracle-run @736c08d9, prior megado wave — untouched),
  ~/Documents/native-bf-oracle (oracle-run-2 @9744f21c), several .megaplan-worktrees entries.
- Environment: darwin arm64, M2; omp binary /Users/peteromalley/.bun/bin/omp -> oh-my-pi fork dev checkout, omp/17.4.0;
  fork repo /Users/peteromalley/Documents/oh-my-pi is CLEAN at baseline and must stay clean (fork changes out of scope
  unless proven impossible without them).
- Machine HAS live provider credentials (grok CLI login, codex OAuth, deepseek/openrouter env) — usable for verify smoke tests.
