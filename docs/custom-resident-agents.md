# Custom resident agents — install, customize, deploy

This document covers the full custom-agent workflow: running `arnold` locally,
customizing agents, and scaffolding a Discord resident bot into any repository
with `agentbox new-resident`.

> STATUS: skeleton drafted by the megado orchestrator (host). Executor T11
> completes sections marked `[T11]` against the implemented behavior.

## Run arnold (R1)

```bash
agentbox install-omp-agent arnold        # packaged source -> ~/.omp/agent/agents/
~/.bun/bin/agent list                    # arnold appears
~/.bun/bin/agent run arnold "State your name and rules."
```

**PATH caveat:** bare `agent` resolves to grok's binary (`~/.grok/bin/agent`) on
this machine. Use `~/.bun/bin/agent` or set `OMP_BIN`.

In-session dispatch: `{"agent": "arnold", "task": "…"}`.

The prompt body of `agentbox/agents/arnold.md` is byte-identical to the live
Discord resident prompt (`AgentBoxOperatorProfile.system_prompt()`,
`agentbox-operator-v1`). A parity test enforces this.

## Customize (R2)

Two CLI flags only — everything else is edited in markdown:

```bash
agentbox install-omp-agent arnold --name my-op --description "Op for X" --target <dir>
```

- positional = source template; `--name` renames output + frontmatter;
  `--description` replaces description; body bytes untouched.
- names must match `^[A-Za-z0-9._-]+$` (not `.` / `..`); writes are atomic and
  non-overwriting.
- model / thinking-level / tools: edit the agent file frontmatter directly
  (`model:`, `thinking-level:`, `tools:`), or use omp-native
  `task.agentModelOverrides.<name>` / `modelRoles`.
- **Agent-file `tools` never change Discord actions** — Discord tools come from
  the resident profile's tool registry + authorizer.

Canonical persona changes require all three: edit `agentbox/agents/arnold.md`,
apply the identical change to `AgentBoxOperatorProfile.system_prompt()`, bump
`AGENTBOX_OPERATOR_PROMPT_VERSION`. The parity test enforces byte equality.

## Scaffold a bot in another repo (R3)

```bash
agentbox new-resident astrid --repo /path/to/astrid --description "…"
```

Generates exactly five files `[T11: confirm final set]`:

| File | Purpose |
|---|---|
| `.omp/agents/<name>.md` | project-scoped named agent (shadows user-level inside this repo) |
| `.agentbox/resident_profile.py` | profile subclass; system prompt from the project agent file |
| `.agentbox/resident.env.example` | token var, model, allowlists, mode, store root |
| `.agentbox/run-resident` | fixed-cwd launcher (executable) |
| `.agentbox/<name>-resident.service` | systemd unit |

External profiles are loaded repo-relative via `.agentbox/resident_profile.py:<Class>`
— trusted project code, imported unsandboxed, contained under the repo root.

## Deploy `[T11]`

- one Discord application per repo (developer portal: name/avatar/message-content intent/permissions)
- env file (uncommitted): `DISCORD_BOT_TOKEN`, allowlists, mode, store root
- store: `<repo>/.megaplan/resident/` (FileStore; created on demand)
- attestation: `<repo>` must be a clean git checkout at the expected HEAD;
  provision the launch seed with `resident attest` `[T11: exact command per implementation]`
- dry-run first: `--dry-run` constructs the profile without network
- then systemd: `systemctl enable --now <name>-resident.service`
