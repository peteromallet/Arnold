# Custody baseline — megado run on Arnold

Captured before worktree creation; immutable for this run.

## Source ref
- HEAD: `744a4171987469109fd50e5094ff74d686ffe6fd` (`fix(chain): rearm typed validation retry failures`)
- Branch at start: `main` (in sync with `origin/main`)
- Worktree base SHA: `744a417198`; foundation commit on `oracle-run`: `b7c682798e`

## Repo identity
- Repo: `/Users/peteromalley/Documents/Arnold` (remote `origin` = `https://github.com/peteromallet/Arnold.git`)
- Worktree for this run: `/Users/peteromalley/Documents/arnold-oracle` (branch `oracle-run`)

## Worktrees at baseline
- `/Users/peteromalley/Documents/Arnold` (main, branch `main`)
- `/private/tmp/arnold-e943-check` (detached, HEAD e943455d95)

## Environment identity
- macOS Darwin 24.4.0 arm64 (Apple M2)
- `codex-cli 0.148.0` at `/Users/peteromalley/.nvm/versions/node/v20.19.4/bin/codex`
- omp launcher: `~/.bun/bin/agent` (omp 17.4.0); `~/.grok/bin/agent` shadows bare `agent` on PATH — use `~/.bun/bin/agent`
- Python via pyenv (3.11/3.12 present); use `PYENV_VERSION=3.11.11` for launcher/fan invocations
- Model routes via omp: `codex:gpt-5.6-sol` / `codex:gpt-5.6-luna` (ChatGPT subscription), `deepseek:deepseek-v4-flash`

## Protected local work (must survive; NOT part of this run's tree)
- Main-tree uncommitted work as of baseline:
  - Branding foundation (identical content committed in this worktree as `b7c682798e`): `agentbox/agents/arnold.md`, `agentbox/cli.py`, `pyproject.toml`, `tests/agentbox/test_cli.py`
  - **In-flight hermes→omp label purge** (DeepSeek Flash subagent, job bg_7) actively editing the main tree: `.env.example`, `AGENTS.md`, `README.md`, `agentbox/systemd/agentbox-discord-resident.service`, `arnold/agent/*`, `arnold_pipelines/megaplan/*` (resident config/runner, profiles, workers, cloud templates), skills launcher copy, tests. NOT committed yet; lands on main separately.
  - `arnold_pipelines/megaplan/skills/*/SKILL.md` symlink rebinds pointing into `.megaplan-worktrees` (environment state; never commit)

## Facts the run relies on (verified earlier in this session)
- omp named agents = markdown files (frontmatter `name`/`description` required; optional `tools`/`model`/`thinking-level`); discovery: project `.omp/agents/` → `~/.omp/agent/agents/` → bundled; first-wins by exact name.
- Resident prompt = `agentbox/resident_profile.py` `AgentBoxOperatorProfile.system_prompt()` (`AGENTBOX_OPERATOR_PROMPT_VERSION = "agentbox-operator-v1"`), brand-neutral, byte-identical to `agentbox/agents/arnold.md` body.
- Discord resident dispatch is omp-backed via `arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py` (omp-backed launcher under a legacy name; model `zhipu:glm-5.2` → omp `openrouter/z-ai/glm-latest`). The hermes→omp label purge in the main tree is flipping the labels; this run treats the resident as omp-based.
- Discord bot display name is the developer-portal application name (not in code); renaming preserves the token.
- Resident platform infra (four-part contract) already exists: profile pattern, `ToolRegistry`/`ResidentAuthorizer`, `FileStore`/`provenance.py`/custody, `delivery_effects.py`/watchdog systemd.
- Compat surfaces that must never be renamed: `arnold.megaplan.*` schema ids, `arnold-resident-*` namespaces, `ARNOLD_RESIDENT_DELEGATION_CONTEXT`, `arnold:resident-delivery:` UUID ns.

## Receipt rule
Every receipt records: model/provider, command, cwd, base SHA (744a417198 or later), PID/exit, timestamps, result digest, output path. No secrets in receipts.
