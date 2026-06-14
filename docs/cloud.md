# Megaplan Cloud

`python -m arnold.pipelines.megaplan cloud` keeps cloud orchestration thin. Core megaplan owns plan, auto, and chain behavior; cloud subcommands stage files, pick a transport, and run the core commands remotely.

Examples below use `python -m arnold.pipelines.megaplan ...`; reuse that verified module launcher for every cloud command. Add `--cloud-yaml /path/to/cloud.yaml` when `cloud.yaml` is not at the project root.

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
python -m arnold.pipelines.megaplan cloud init
```

2. Edit `cloud.yaml` for repo, provider, mode, secrets, and optional toolchains.

   See [docs/configuration.md](configuration.md) for where local config files, provider keys, cloud secrets, and database-mode environment variables are read from.

3. Export the local secrets named under `secrets:`:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...        # optional, but recommended for push/private clone
export ANTHROPIC_API_KEY=...   # optional
```

4. Build and deploy:

```bash
python -m arnold.pipelines.megaplan cloud build
python -m arnold.pipelines.megaplan cloud deploy
```

5. Start work remotely:

```bash
python -m arnold.pipelines.megaplan cloud bootstrap .megaplan/briefs/tiny-plan.md
python -m arnold.pipelines.megaplan cloud chain .megaplan/briefs/my-epic/chain.yaml
```

6. Inspect and connect:

```bash
python -m arnold.pipelines.megaplan cloud status
python -m arnold.pipelines.megaplan cloud status --chain
python -m arnold.pipelines.megaplan cloud logs
python -m arnold.pipelines.megaplan cloud attach
```

## `cloud.yaml` Reference

### Top-level fields

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `provider` | no | `railway` | One of `railway`, `local`, or `ssh`. |
| `mode` | no | `idle` | Runner mode: `auto`, `chain`, or `idle`. |
| `secrets` | no | `[]` | Local env var names uploaded during `python -m arnold.pipelines.megaplan cloud deploy` and redacted from cloud log output where possible. |
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
| `megaplan.codex_auth` | no | `chatgpt` | `chatgpt` forces the ChatGPT-subscription OAuth (`preferred_auth_method=chatgpt`; codex uses `chatgpt.com/backend-api/codex` even when `OPENAI_API_KEY` is set) and seeds your local `~/.codex`/`~/.hermes` OAuth onto the volume. `apikey` opts into standard API-key billing. See the "Codex auth" section in the cloud skill. |

> **Codex auth gotcha:** without `codex_auth=chatgpt`, a stray `OPENAI_API_KEY` makes the codex CLI use API-key mode → `api.openai.com` billing → `ERROR: Quota exceeded. Check your plan and billing details.` even with a working ChatGPT subscription.

### `auto`

Used only when `mode: auto`.

| Field | Required in `auto` mode | Default | Meaning |
|---|---|---:|---|
| `auto.plan_name` | yes | none | Remote plan name for boot-time `python -m arnold.pipelines.megaplan auto --plan ...`. |
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

### `python -m arnold.pipelines.megaplan cloud bootstrap <idea-file>`

`cloud bootstrap` uploads a local idea file to `<repo.workspace>/idea.txt`, then runs:

```bash
python -m arnold.pipelines.megaplan init --project-dir <workspace> --idea-file <workspace>/idea.txt --auto-start --robustness <level>
```

`--plan-name` is optional. If omitted, cloud does **not** pass `--name`; core megaplan chooses the default slug from the idea text.

### `python -m arnold.pipelines.megaplan cloud chain <spec> [--idea-dir <dir>]`

`cloud chain` is the preferred path for remote chain runs. It:

1. Parses the local chain spec with core `megaplan.chain.load_spec(...)`.
2. Resolves each milestone idea file from `--idea-dir` or, by default, the local spec's parent directory.
3. Uploads each idea file to the remote path named in the chain spec.
4. Uploads the chain spec to `<repo.workspace>/chain.yaml`.
5. Starts remote `python -m arnold.pipelines.megaplan chain start --spec <repo.workspace>/chain.yaml` in tmux session `megaplan-chain`, logging to `<repo.workspace>/.megaplan/cloud-chain.log`.

After upload + dispatch, cloud writes a provider-independent marker:

```text
~/.megaplan/cloud/markers/<sha256(abs_path_of_cloud.yaml)[:16]>/last_chain.json
```

That marker survives Railway's ephemeral deploy dir and is used by `cloud status --chain`.

### `python -m arnold.pipelines.megaplan cloud status --chain`

`cloud status --chain` fetches remote `chain_state.json`, then reuses core chain status formatting. Remote spec resolution precedence is:

1. `--remote-spec <path>`
2. `~/.megaplan/cloud/markers/<sha>/last_chain.json`
3. `spec.chain.spec` from `cloud.yaml` when `mode: chain`
4. Otherwise `missing_remote_spec`

The command prints the structured payload on stdout and the same human-readable chain summary block that local `python -m arnold.pipelines.megaplan chain status --spec ...` prints on stderr.

### `python -m arnold.pipelines.megaplan cloud status`

Without `--chain`, `cloud status` still runs remote `python -m arnold.pipelines.megaplan status` and prints that JSON payload unchanged.

### `python -m arnold.pipelines.megaplan cloud supervise --chain`

`cloud supervise --chain` runs a **one-shot supervisor tick** against the remote chain. It observes the chain, refreshes branch/PR sync state, and makes safe progress decisions. It never invents approvals, bypasses quality gates, or runs destructive git operations.

#### One-shot tick behavior

Each invocation is a single observation + decision cycle:

1. Read remote chain status via the same path as `cloud status --chain`.
2. Refresh branch/PR sync by running `_capture_sync_state` remotely.
3. Re-read chain status after the refresh.
4. Map the refreshed `effective_status` to a safe action.
5. Execute at most one safe mutation (tmux restart, one-shot chain tick).
6. Emit a structured JSON report on **stdout** and a human-readable summary on **stderr**.

#### JSON stdout

The tick report on stdout includes these fields:

| Field | Type | Meaning |
|---|---|---|
| `success` | bool | Whether the tick completed without error. |
| `event` | string | Event label: `supervisor_tick`, `supervisor_blocked`, `supervisor_advanced`, `supervisor_restarted`, or `supervisor_error`. |
| `spec` | string | Resolved remote chain spec path. |
| `effective_status` | string | Classified chain status after sync refresh. |
| `next_action` | string | Decision: `noop`, `done`, `blocked`, `advance`, `restart`, or `none`. |
| `acted` | bool | Whether the supervisor executed a mutation this tick. |
| `refused_reason` | string\|null | Human-readable explanation when the supervisor declined to act. |
| `runner` | object | Runner liveness and session info. |
| `sync` | object | Branch/PR sync state fields. |
| `pr` | object | PR number, state, and head. |
| `logs` | object | Remote log paths and best-effort mtime/size. |

#### Stderr summary

A single line is written to stderr:

```text
supervisor tick: <event> | acted=<bool> | next_action=<action> [| refused_reason=<reason>]
```

#### Remote spec precedence

Same resolution order as `cloud status --chain`:

1. `--remote-spec <path>`
2. `~/.megaplan/cloud/markers/<sha>/last_chain.json`
3. `spec.chain.spec` from `cloud.yaml` when `mode: chain`
4. Otherwise `missing_remote_spec`

#### Canonical session

The supervisor targets the same `megaplan-chain` tmux session used by `cloud chain`. All mutations use the canonical `MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold.pipelines.megaplan chain start --spec <path> --one` command, appending to `<workspace>/.megaplan/cloud-chain.log`.

#### Safe actions

The supervisor will **only** perform these mutations:

- **Restart a dead runner**: When `effective_status` is `stale_bookkeeping` and the `megaplan-chain` tmux session is dead or missing, the supervisor kills any stale session and starts a fresh one-shot tick.
- **Advance past a merged PR**: When `effective_status` is `awaiting_pr_merge` and the PR has been merged (confirmed via `gh pr view --json state`), the supervisor advances the chain with a one-shot tick.

#### Refusal cases (no mutation)

The supervisor **refuses to act** and returns `acted: false` with a `refused_reason` for:

| effective_status | Behavior |
|---|---|
| `running` | Chain is running; nothing to do. |
| `complete` | All milestones processed; chain is done. |
| `human_prerequisite` | Prerequisite policy is `required` and unmet; requires human operator resolution via `python -m arnold.pipelines.megaplan user-action resolve` or `python -m arnold.pipelines.megaplan chain override`. |
| `quality_gate` | Validation policy is `required` and quality gate is failing; requires human operator resolution. |
| `awaiting_pr_merge` (PR unmerged) | PR is still open; supervisor will not advance until merged. |
| `stale_bookkeeping` (runner alive) | Bookkeeping is stale but runner is alive; supervisor will not force-restart a live runner. |
| Provider lacks `ssh_exec` | Cannot probe or mutate the remote runner. |

#### Not a destructive repair tool

The supervisor is **not** a destructive repair tool and does **not** replace:

- **Human approval** of prerequisites — use `python -m arnold.pipelines.megaplan user-action resolve` or `python -m arnold.pipelines.megaplan chain override`.
- **PR review** — the supervisor only advances when the PR is already merged.
- **Quality-gate resolution** — failing gates must be resolved by a human operator.

The supervisor never produces force-push, reset, branch-deletion, or any other destructive git commands. Its only mutations are tmux session management and `chain start --one`.

## Boot-Time Runner Modes

`mode: auto` and `mode: chain` still control what the long-running remote `agent` session launches on boot. Those boot paths expect the referenced remote files to already exist on the workspace volume.

Use `cloud bootstrap` and `cloud chain` when you want cloud to stage the local input files for you. If you set `mode: auto` or `mode: chain` directly in `cloud.yaml`, make sure the referenced remote files already exist before restart.

## Logs, Redaction, And Attach

`python -m arnold.pipelines.megaplan cloud logs` redacts:

- literal values for secret names listed under `secrets:` when those values are present locally
- `NAME=value` and `NAME: value` patterns for those secret names
- known token shapes such as `sk-...`, `ghp_...`, and `xoxb-...`

This redaction applies to:

- `python -m arnold.pipelines.megaplan cloud logs`
- `python -m arnold.pipelines.megaplan cloud exec`
- wrapper-dispatched output from `cloud bootstrap`, `cloud chain`, and `cloud resume`

`python -m arnold.pipelines.megaplan cloud attach` is different. It opens a raw interactive PTY, so line-buffered redaction is not applied there. Treat attach sessions as trusted terminals.

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
- Config & environment map: [docs/configuration.md](configuration.md)

## Related Runbooks And Design Notes

- **Cloud chain smoke**: [docs/ops/cloud-chain-smoke.md](ops/cloud-chain-smoke.md) — end-to-end smoke tests for cloud chain operations.
- **Recovery runbooks**: [docs/ops/recovery-runbooks.md](ops/recovery-runbooks.md) — operational procedures for recovering cloud deployments.
- **Cloud prerequisite resolution**: Active milestone briefs live under [.megaplan/briefs/cloud-prerequisite-resolution/](../.megaplan/briefs/cloud-prerequisite-resolution/) — these are the source of truth for structured prerequisite/quality resolution metadata, auto recovery, chain policy/status, cloud supervision, and slot-first watchdog hardening.
- **Slot-first watchdog**: The watchdog operates from the assigned slot/workspace first, verifies provider and session consistency, lists available human-verification actions, and only restarts or wakes chains when the status payload shows the chain is recoverable. Continuous branch and PR synchronization is required after stops and recoveries so status reflects what code reviewers and operators see.

## Migration From `reigh-megaplan-dev`

The historical migration runbook is archived at [docs/archive/cloud-migration-from-reigh.md](archive/cloud-migration-from-reigh.md). The important rule is: write `MIGRATED.md` first, then remove siblings while preserving that pointer file.
