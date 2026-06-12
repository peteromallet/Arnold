# VibeComfy Agent Bootstrap

The canonical long-form agent instructions live in
[docs/agent-skill/SKILL.md](docs/agent-skill/SKILL.md). Read that file before
making repository changes, running workflows, converting ComfyUI JSON, or editing
ready templates.

Keep this file short. `scripts/sync_agent_skill.py` checks that this bootstrap
and [CLAUDE.md](CLAUDE.md) do not duplicate the canonical VibeComfy skill
frontmatter.

For reusable local setup, `python scripts/sync_agent_skill.py --install-user`
uses SkillSinker to symlink the canonical VibeComfy skill into detected Claude,
Codex, and Hermes skill directories. For Codex it also keeps the VibeComfy
fenced block in `~/.codex/AGENTS.md` in sync.
