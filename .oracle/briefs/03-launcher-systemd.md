# Brief — Area 3: Launcher, env, and systemd conventions

Explore this area in depth in `/Users/peteromalley/Documents/arnold-oracle` (worktree). Link: `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Goal: R3 generates `.agentbox/run-resident` (launcher) and `.agentbox/<name>-resident.service` (systemd) for a fresh repo. Establish the existing conventions to mirror.

Read:
- `agentbox/systemd/agentbox-discord-resident.service` — ExecStart, Environment lines (esp. `MEGAPLAN_RESIDENT_MODEL_PROVIDER`, `MEGAPLAN_RESIDENT_MODEL`, `MEGAPLAN_RESIDENT_PROFILE`, store root, mode/role), WorkingDirectory, Restart policy.
- `arnold_pipelines/megaplan/cloud/systemd/` — `megaplan-resident-ensure` + `.service`/`.timer` and `arnold-resident-schedule-run-once-r7`: how the resident is kept alive (tmux? direct ExecStart?), how env is sourced (`.secrets/…env` files).
- `arnold_pipelines/megaplan/resident/cli.py` + `restart_resident.py` — the `python -m arnold_pipelines.megaplan resident discord` entry; env vars the CLI reads (`DISCORD_BOT_TOKEN`, `MEGAPLAN_RESIDENT_MODE`, `MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE`, allowlists, voice, store root).
- `arnold_pipelines/megaplan/resident/config.py` — env names + defaults.
- `tests/agentbox/test_services.py` or similar for unit conventions.

Report (verified facts, file:line): (1) canonical resident launch command + required env; (2) how the store root is set per project and whether a repo-local `.megaplan/resident/` needs no extra setup; (3) systemd unit shape (WorkingDirectory, ExecStart quoting, env file) to replicate for a per-repo unit; (4) executable-mode and shebang conventions for launcher scripts in this repo; (5) token handling: how secrets are kept out of git/units; (6) unknowns and risks. Ranked findings, <300 words.
