# Custom resident agents — install, customize, deploy

This document covers the full custom-agent workflow: running `arnold` locally,
customizing agents, and scaffolding a Discord resident bot into any repository
with `agentbox new-resident`.

## Run arnold (R1)

Install the packaged named agent, then talk to it with the `arnold` console
command:

```bash
agentbox install-omp-agent arnold
arnold "State your name and rules."      # one-shot question
arnold                                   # interactive AgentBox Operator session
arnold --agent scout "…"                  # talk to a different installed agent
```

### Continue a conversation

One-shot runs save their session by default, so follow-ups just work:

```bash
arnold -c "Follow-up question"            # continue the most recent conversation
arnold --resume <id-prefix> "…"           # resume a specific session
arnold                                    # interactive TUI (has a session picker)
```

Sessions are global to omp (not per-agent), so `-c` continues whatever ran
last regardless of which agent it belonged to. Use `--resume` when you need
a specific thread.

The workflow/operator tooling lives on the `megaplan` command. The `arnold`
entry resolves its omp launcher itself: `ARNOLD_AGENT_LAUNCHER` env var, then
`~/.bun/bin/agent`, then a trusted `agent` on PATH. If you drive omp's
launcher manually instead (outside the `arnold` entry), note that bare
`agent` may resolve to another vendor's binary — prefer `~/.bun/bin/agent`
or set `OMP_BIN` for that manual invocation. In-session dispatch is separate:
`{"agent": "arnold", "task": "…"}`.

The body of `agentbox/agents/arnold.md` is byte-identical to
`AgentBoxOperatorProfile.system_prompt()` (`agentbox-operator-v1`). The parity
test is the guard against the named agent and Discord resident drifting apart.

## Customize (R2)

The installer exposes only name and description overrides. Edit all other
omp-owned settings in the generated markdown:

```bash
agentbox install-omp-agent arnold \
  --name my-op \
  --description "Operator for X" \
  --target /path/to/agents
```

- The positional argument is the source template. `--name` changes the output
  filename and frontmatter `name`; `--description` changes frontmatter only.
  The prompt body is unchanged.
- Names must match `^[A-Za-z0-9._-]+$`, excluding `.` and `..`. Writes are
  atomic and never overwrite an existing destination.
- Edit the agent file's `model`, `thinking-level`, and `tools` frontmatter for
  omp named-agent behavior. Do not add installer flags that duplicate those
  markdown fields.

**Agent-tools versus Discord-tools:** the agent file's `tools` field controls
the omp named-agent run. It does not grant Discord actions. Discord actions
come from the selected resident profile's tool registry and authorizer.

Canonical persona changes follow three steps: update
`agentbox/agents/arnold.md`, apply the identical body change to
`AgentBoxOperatorProfile.system_prompt()`, and bump
`AGENTBOX_OPERATOR_PROMPT_VERSION`. The byte-parity test must remain green.

## Scaffold a bot in another repo (R3)

From an installed package, run:

```bash
agentbox new-resident astrid \
  --repo /path/to/astrid \
  --description "Astrid resident operator"
```

`--description` is optional; without it the implementation uses
`Resident operator (astrid)`. The command creates exactly these five files:

| File | Purpose |
|---|---|
| `.omp/agents/astrid.md` | Project-scoped named agent; it shadows the user-level agent inside this repo. |
| `.agentbox/resident_profile.py` | `AstridResidentProfile`, a subclass of `AgentBoxOperatorProfile`. |
| `.agentbox/resident.env.example` | Starting environment file with token, mode, and allowlists. |
| `.agentbox/run-resident` | Fixed-root executable launcher. |
| `.agentbox/astrid-resident.service` | Systemd unit that runs the launcher. |

The profile reads the body below the agent file's frontmatter as its Discord
system prompt. The external profile selector is the trusted, repo-relative
`.agentbox/resident_profile.py:AstridResidentProfile`; loading is unsandboxed
project code and is contained under the target repository.

## Deploy

### Configure the environment

Copy the generated example to the name-specific file that the launcher reads:

```bash
cd /path/to/astrid
cp .agentbox/resident.env.example .agentbox/astrid.env
${EDITOR:-vi} .agentbox/astrid.env
chmod 600 .agentbox/astrid.env
```

Set `DISCORD_BOT_TOKEN`, `MEGAPLAN_RESIDENT_MODE`, and the guild/channel/user/admin
allowlists. Keep this file uncommitted. The generated launcher owns the exact
external profile and store root; `.agentbox/astrid.env` is the sole secret and
deployment source.

An empty or missing token is refused before attestation:

```text
run-resident: DISCORD_BOT_TOKEN is empty in .../.agentbox/astrid.env; refusing to start
```

### Attest the exact project and runtime

The implemented subcommand is `resident attest`, with two independent
custody identities: the target repository (`--repo-root`, `--expected-head`)
and the imported Arnold runtime checkout (`--runtime-root`,
`--expected-runtime-head`):

```bash
REPO_ROOT="$(pwd -P)"
HEAD="$(git rev-parse HEAD)"
RUNTIME_ROOT="$(python -c 'import os, arnold_pipelines; print(os.path.dirname(os.path.dirname(os.path.abspath(arnold_pipelines.__file__))))')"
RUNTIME_HEAD="$(git -C "$RUNTIME_ROOT" rev-parse HEAD)"
python -m arnold_pipelines.megaplan resident attest \
  --repo-root "$REPO_ROOT" \
  --expected-head "$HEAD" \
  --runtime-root "$RUNTIME_ROOT" \
  --expected-runtime-head "$RUNTIME_HEAD"
```

The target repository does NOT need to contain (or be) Arnold — a fresh
non-Arnold repository succeeds using an external Arnold checkout. The two
roots are admitted separately and may be equal only when the target repo
genuinely is the Arnold checkout:

- **Project custody** (`--repo-root` + `--expected-head`): Git admission of
  the exact top-level, its live HEAD, the launch state directory
  (`<project_root>/.megaplan/resident/runtime-launch`), dispatch pointer,
  issuance receipt, and process-status attestation.
- **Runtime custody** (`--runtime-root` + `--expected-runtime-head`): strict
  provenance (`import_root == --runtime-root`), the exact runtime revision,
  and every loaded-code vector (modules, `.pth`, wrappers, interpreter),
  re-collected on each validation.

Any mismatch exits with `runtime_launch_attestation_mismatch` before the
dispatch pointer advances or Discord starts.

**Runtime import contract:** the interpreter must import `arnold_pipelines`
from `--runtime-root`. Either install Arnold editable from that checkout:

```bash
python -m pip install -e /path/to/arnold
```

or expose the checkout explicitly through `PYTHONPATH`:

```bash
PYTHONPATH=/path/to/arnold python -m arnold_pipelines.megaplan resident attest \
  --repo-root "$REPO_ROOT" \
  --expected-head "$HEAD" \
  --runtime-root "$RUNTIME_ROOT" \
  --expected-runtime-head "$RUNTIME_HEAD"
```

Attestation admits only the exact Git top-levels passed as `--repo-root` and
`--runtime-root` with their live HEADs as `--expected-head` and
`--expected-runtime-head`; runtime provenance must also resolve to the
importable Arnold runtime at `--runtime-root`. The generated launcher resolves
the imported runtime root with its own interpreter, performs this same check
automatically, exports the returned seed as `MEGAPLAN_RUNTIME_LAUNCH_SEED`,
and refuses startup on any failure.

### Dry-run, then systemd

Run the generated launcher from the target repository:

```bash
./.agentbox/run-resident --dry-run
```

This performs attestation and constructs the selected profile without opening
a Discord connection. The launcher still requires a non-empty token because
its shell-level secret check runs before the no-network resident dry-run.

Install the generated unit and start it only after the dry-run succeeds:

```bash
sudo install -m 0644 .agentbox/astrid-resident.service \
  /etc/systemd/system/astrid-resident.service
sudo systemctl daemon-reload
sudo systemctl enable --now astrid-resident.service
sudo systemctl status astrid-resident.service
```

### Discord developer portal (manual)

1. Open the Discord Developer Portal and create one application for this
   repository.
2. Add a bot, reset/copy its token into `.agentbox/astrid.env`, and enable the
   Message Content Intent when the bot needs message contents.
3. Configure the OAuth2 installation URL with only the bot/application-command
   scopes and permissions required by the resident's Discord profile.
4. Install the bot in the intended guild, then set the generated environment
   allowlists before starting systemd. Keep the token out of the repository
   and out of the service unit.

The runtime boundary, configuration surface, and cloud/deployment day-2
operations are documented separately:

- [Resident boundary](agentbox-resident-boundary.md)
- [Configuration](configuration.md)
- [Bootstrap and day-2 operations](agentbox/bootstrap-and-day2.md)
