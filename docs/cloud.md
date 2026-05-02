# Megaplan Cloud

`megaplan cloud` keeps cloud orchestration thin. Core megaplan owns plan, auto, and chain behavior; cloud subcommands stage files, pick a transport, and run the core commands remotely.

Examples below use `megaplan ...`; in this repo run `./.venv/bin/python -m megaplan ...`. Add `--cloud-yaml /path/to/cloud.yaml` when `cloud.yaml` is not at the project root.

## Providers

| Provider | Use case | Notes |
|---|---|---|
| `railway` | Hosted runner with Railway SSH/logs/volume primitives | Good default for shared remote runs. |
| `local` | Fast local iteration and CI-friendly smoke tests | Uses `docker compose` from a persistent deploy dir under `~/.megaplan/cloud/<compose_project>/`. |
| `ssh` | Any reachable Docker host over SSH | Syncs the deploy dir to `ssh.remote_dir` with `rsync`, or `scp -r` when `rsync` is unavailable. |

`provider: fly` remains reserved for a future release.

## Quick Start

1. Scaffold:

```bash
megaplan cloud init
```

2. Edit `cloud.yaml` for repo, provider, mode, secrets, and optional toolchains.

3. Export the local secrets named under `secrets:`:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...        # optional, but recommended for push/private clone
export ANTHROPIC_API_KEY=...   # optional
```

4. Build and deploy:

```bash
megaplan cloud build
megaplan cloud deploy
```

5. Start work remotely:

```bash
megaplan cloud bootstrap ideas/tiny-plan.txt
megaplan cloud chain chain.yaml --idea-dir ideas
```

6. Inspect and connect:

```bash
megaplan cloud status
megaplan cloud status --chain
megaplan cloud logs
megaplan cloud attach
```

## `cloud.yaml` Reference

### Top-level fields

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `provider` | no | `railway` | One of `railway`, `local`, or `ssh`. |
| `mode` | no | `idle` | Runner mode: `auto`, `chain`, or `idle`. |
| `secrets` | no | `[]` | Local env var names uploaded during `megaplan cloud deploy` and redacted from cloud log output where possible. |
| `toolchains` | no | `[]` | Extra language toolchains layered into the image. Use aliases `rust`, `go`, `java`, or `{name, install}` mappings. |

### `repo`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `repo.url` | yes | none | Git URL cloned into the remote workspace. |
| `repo.branch` | no | `main` | Branch checked out on clone. |
| `repo.workspace` | no | `/workspace/app` | Absolute repo path used for remote `cd`, tmux, file uploads, and wrapper commands. |

### `agents`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `agents.default` | no | `codex` | Default megaplan agent for routed steps. |
| `agents.<step>` | no | inherits `default` | Optional per-step override such as `plan`, `review`, `execute`, or `loop_execute`. |

### `codex`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `codex.model` | no | `gpt-5.4` | Written into `/root/.codex/config.toml` on boot. |
| `codex.reasoning` | no | `high` | Reasoning level written into `/root/.codex/config.toml` on boot. |

### `auto`

Used only when `mode: auto`.

| Field | Required in `auto` mode | Default | Meaning |
|---|---|---:|---|
| `auto.plan_name` | yes | none | Remote plan name for boot-time `megaplan auto --plan ...`. |
| `auto.idea_file` | yes | none | Absolute remote path to the idea file already staged on the workspace volume. |
| `auto.robustness` | no | `standard` | Robustness for the boot-time init fallback. |

### `chain`

Used only when `mode: chain`.

| Field | Required in `chain` mode | Default | Meaning |
|---|---|---:|---|
| `chain.spec` | yes | none | Absolute remote path to the already-staged chain spec. |

### `megaplan`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `megaplan.ref` | no | `main` | Branch, tag, or SHA installed on boot via `pip install --upgrade git+...@<ref>`. |

### `resources`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `resources.volume` | no | none | Provider-specific persistent volume name. `destroy` deletes it only when set. |
| `resources.port` | no | `8080` | Health server port exposed by the container. |

### `railway`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `railway.service` | no | `agent` | Railway service name used by `deploy`, `logs`, and `down`. |
| `railway.session` | no | `agent` | Railway SSH session name used for interactive attaches. |
| `railway.project` | no | unset | Optional project passed to Railway commands. |
| `railway.environment` | no | unset | Optional environment passed to Railway commands. |

### `local`

| Field | Required when `provider: local` | Default | Meaning |
|---|---|---:|---|
| `local.compose_project` | no | `megaplan-cloud` | Docker Compose project name used for build, logs, exec, and teardown. |
| `local.workdir` | no | `workspace` | Bind-mounted directory inside the persistent local deploy dir. |

### `ssh`

| Field | Required when `provider: ssh` | Default | Meaning |
|---|---|---:|---|
| `ssh.host` | yes | none | Remote SSH host. |
| `ssh.user` | no | unset | Optional SSH username. |
| `ssh.port` | no | `22` | SSH port. |
| `ssh.identity_file` | no | unset | Optional identity file passed to `ssh`, `scp`, and `rsync`. |
| `ssh.remote_dir` | no | `/tmp/megaplan-cloud` | Remote directory used for synced Docker build context and `.env`. |
| `ssh.container` | no | `megaplan-cloud-agent` | Remote container name and image tag. |

## Toolchains

Without `toolchains:`, the image is Python/Node only. Add built-in aliases or a custom install snippet:

```yaml
toolchains:
  - rust
  - go
  - name: custom
    install: |
      RUN curl -fsSL https://example.com/tool/install.sh | bash
```

## Wrapper Workflows

### `megaplan cloud bootstrap <idea-file>`

`cloud bootstrap` uploads a local idea file to `<repo.workspace>/idea.txt`, then runs:

```bash
megaplan init --project-dir <workspace> --idea-file <workspace>/idea.txt --auto-start --robustness <level>
```

`--plan-name` is optional. If omitted, cloud does **not** pass `--name`; core megaplan chooses the default slug from the idea text.

### `megaplan cloud chain <spec> [--idea-dir <dir>]`

`cloud chain` is the preferred path for remote chain runs. It:

1. Parses the local chain spec with core `megaplan.chain.load_spec(...)`.
2. Resolves each milestone idea file from `--idea-dir` or, by default, the local spec's parent directory.
3. Uploads each idea file to the remote path named in the chain spec.
4. Uploads the chain spec to `<repo.workspace>/chain.yaml`.
5. Runs remote `megaplan chain start --spec <repo.workspace>/chain.yaml`.

After upload + dispatch, cloud writes a provider-independent marker:

```text
~/.megaplan/cloud/markers/<sha256(abs_path_of_cloud.yaml)[:16]>/last_chain.json
```

That marker survives Railway's ephemeral deploy dir and is used by `cloud status --chain`.

### `megaplan cloud status --chain`

`cloud status --chain` fetches remote `chain_state.json`, then reuses core chain status formatting. Remote spec resolution precedence is:

1. `--remote-spec <path>`
2. `~/.megaplan/cloud/markers/<sha>/last_chain.json`
3. `spec.chain.spec` from `cloud.yaml` when `mode: chain`
4. Otherwise `missing_remote_spec`

The command prints the structured payload on stdout and the same human-readable chain summary block that local `megaplan chain status --spec ...` prints on stderr.

### `megaplan cloud status`

Without `--chain`, `cloud status` still runs remote `megaplan status` and prints that JSON payload unchanged.

## Boot-Time Runner Modes

`mode: auto` and `mode: chain` still control what the long-running remote `agent` session launches on boot. Those boot paths expect the referenced remote files to already exist on the workspace volume.

Use `cloud bootstrap` and `cloud chain` when you want cloud to stage the local input files for you. If you set `mode: auto` or `mode: chain` directly in `cloud.yaml`, make sure the referenced remote files already exist before restart.

## Logs, Redaction, And Attach

`megaplan cloud logs` redacts:

- literal values for secret names listed under `secrets:` when those values are present locally
- `NAME=value` and `NAME: value` patterns for those secret names
- known token shapes such as `sk-...`, `ghp_...`, and `xoxb-...`

This redaction applies to:

- `megaplan cloud logs`
- `megaplan cloud exec`
- wrapper-dispatched output from `cloud bootstrap`, `cloud chain`, and `cloud resume`

`megaplan cloud attach` is different. It opens a raw interactive PTY, so line-buffered redaction is not applied there. Treat attach sessions as trusted terminals.

## Provider Notes

### `provider: local`

- Uses `docker compose -p <compose_project> -f ~/.megaplan/cloud/<compose_project>/docker-compose.yaml ...`
- Materializes a persistent deploy dir under `~/.megaplan/cloud/<compose_project>/`
- Bind-mounts `./<local.workdir>` into `<repo.workspace>`
- Best for local iteration and CI smoke tests

### `provider: ssh`

- Uses plain `ssh` for exec/logs/attach/status
- Syncs the materialized deploy dir to `ssh.remote_dir`
- Prefers `rsync`; falls back to `scp -r` with a warning when `rsync` is unavailable
- Runs a single long-lived Docker container named `ssh.container`

### `provider: railway`

- Uses Railway SSH/logs/down/volume primitives
- Markers are stored outside the Railway deploy dir so chain status survives redeploys
- `--session` remains Railway-only

## Runtime Requirements

- Railway CLI install docs: https://docs.railway.app/develop/cli
- Docker install docs: https://docs.docker.com/get-docker/
- OpenSSH project/docs: https://www.openssh.com/

## Migration From `reigh-megaplan-dev`

Use the human-executed runbook at [docs/cloud-migration-from-reigh.md](cloud-migration-from-reigh.md). The important rule is: write `MIGRATED.md` first, then remove siblings while preserving that pointer file.
