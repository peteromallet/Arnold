# Megaplan Cloud

`python -m arnold_pipelines.megaplan cloud` keeps cloud orchestration thin. Core megaplan owns plan, auto, and chain behavior; cloud subcommands stage files, pick a transport, and run the core commands remotely.

Examples below use `python -m arnold_pipelines.megaplan ...`; reuse that verified module launcher for every cloud command. Add `--cloud-yaml /path/to/cloud.yaml` when `cloud.yaml` is not at the project root.

## Providers

| Provider | Use case | Notes |
|---|---|---|
| `local` | Fast local iteration and CI-friendly smoke tests | Uses `docker compose` from a persistent deploy dir under `~/.megaplan/cloud/<compose_project>/`. |
| `ssh` | Shared remote runner, including the Hetzner agentbox | Syncs the deploy dir to `ssh.remote_dir` with `rsync`, or `scp -r` when `rsync` is unavailable. |

`provider: fly` remains reserved for a future release.

## Quick Start

1. Scaffold:

```bash
python -m arnold_pipelines.megaplan cloud init
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
python -m arnold_pipelines.megaplan cloud build
python -m arnold_pipelines.megaplan cloud deploy
```

5. Start work remotely:

```bash
python -m arnold_pipelines.megaplan cloud bootstrap .megaplan/initiatives/tiny-plan/briefs/tiny-plan.md
python -m arnold_pipelines.megaplan cloud preflight .megaplan/initiatives/my-epic/chain.yaml
python -m arnold_pipelines.megaplan cloud sync-megaplan .megaplan/initiatives/my-epic/chain.yaml --clean
python -m arnold_pipelines.megaplan cloud launch-epic .megaplan/initiatives/my-epic --fresh
```

Durable chain specs are expected at `.megaplan/initiatives/<initiative>/chain.yaml`.
Milestone briefs, north-star anchors, research notes, and related durable
planning inputs belong in the same initiative directory. Runtime state stays
under `.megaplan/plans/` and `.megaplan/epics/` and is not uploaded as planning
source. Epic chain specs require `anchors.north_star`, with paths resolved
relative to the `chain.yaml` directory.

`cloud preflight` validates the canonical spec layout, North Star, milestone
brief paths, resolved cloud routing, configured secrets, required remote
commands, and the worker's modern `arnold_pipelines.megaplan` import. Its JSON
output includes the derived workspace, session, and canonical `remote_spec` that
`launch-epic` will use.

To seed a cloud checkout with the local durable planning state before or after a
chain launch:

```bash
python -m arnold_pipelines.megaplan cloud sync-megaplan .megaplan/initiatives/my-epic/chain.yaml --clean
```

When a chain spec is supplied, `sync-megaplan` uses the same derived per-chain
workspace as `cloud chain`, then uploads `.megaplan/initiatives/`, `.megaplan/tickets/`,
and `.megaplan/ideas/`. It deliberately does not upload generated plans, epics,
locks, logs, telemetry, verification state, `.DS_Store`, or macOS AppleDouble
`._*` files.

6. Inspect and connect:

```bash
python -m arnold_pipelines.megaplan cloud status --all
python -m arnold_pipelines.megaplan cloud status --all --compact --since 12h
python -m arnold_pipelines.megaplan cloud status
python -m arnold_pipelines.megaplan cloud status --chain
python -m arnold_pipelines.megaplan cloud logs
python -m arnold_pipelines.megaplan cloud attach
```

On a shared runner, use `cloud status --all` first. It lists all known cloud
sessions with human names, `should_run=yes/no`, liveness, current plan state,
and any watchdog repair/escalation status. Use `tmux ls` only for "which runner
processes are alive right now"; `/workspace/watchdog-report.json` is only the
last watchdog scan and can be stale.

For operator handoffs and "what changed recently?" checks, prefer:

```bash
python -m arnold_pipelines.megaplan cloud status --all --compact --since 12h \
  --cloud-yaml .megaplan/initiatives/<active-initiative>/cloud.yaml
```

`--compact` prints one row per relevant session. `--since` accepts durations
such as `30m`, `12h`, or `2d`, or an ISO timestamp. The filter uses the newest
real plan `state.json` timestamp when available, not watchdog health mtimes,
because watchdog reports can be rewritten after a chain has already completed.
The JSON payload is filtered to the same sessions and includes
`unfiltered_session_count` plus `since` for auditability.

## `cloud.yaml` Reference

### Top-level fields

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `provider` | no | `ssh` | One of `ssh` or `local`. |
| `mode` | no | `idle` | Runner mode: `auto`, `chain`, or `idle`. |
| `secrets` | no | `[]` | Local env var names uploaded during `python -m arnold_pipelines.megaplan cloud deploy` and redacted from cloud log output where possible. |
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
| `codex.model` | no | `gpt-5.6-sol` | Written into `/root/.codex/config.toml` on boot. |
| `codex.reasoning` | no | `medium` | Reasoning level (`minimal` through `max`) written into `/root/.codex/config.toml` on boot. |
| `megaplan.codex_auth` | no | `chatgpt` | `chatgpt` forces the ChatGPT-subscription OAuth (`preferred_auth_method=chatgpt`; codex uses `chatgpt.com/backend-api/codex` even when `OPENAI_API_KEY` is set) and seeds your local `~/.codex`/`~/.hermes` OAuth onto the volume. `apikey` opts into standard API-key billing. See the "Codex auth" section in the cloud skill. |

> **Codex auth gotcha:** without `codex_auth=chatgpt`, a stray `OPENAI_API_KEY` makes the codex CLI use API-key mode → `api.openai.com` billing → `ERROR: Quota exceeded. Check your plan and billing details.` even with a working ChatGPT subscription.

### `auto`

Used only when `mode: auto`.

| Field | Required in `auto` mode | Default | Meaning |
|---|---|---:|---|
| `auto.plan_name` | yes | none | Remote plan name for boot-time `python -m arnold_pipelines.megaplan auto --plan ...`. |
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

### `python -m arnold_pipelines.megaplan cloud bootstrap <idea-file>`

`cloud bootstrap` uploads a local idea file to `<repo.workspace>/idea.txt`, then runs:

```bash
python -m arnold_pipelines.megaplan init --project-dir <workspace> --idea-file <workspace>/idea.txt --auto-start --robustness <level>
```

`--plan-name` is optional. If omitted, cloud does **not** pass `--name`; core megaplan chooses the default slug from the idea text.

### `python -m arnold_pipelines.megaplan cloud chain <spec> [--idea-dir <dir>]`

`cloud chain` is the preferred path for remote chain runs. It:

1. Parses the local chain spec with core `megaplan.chain.load_spec(...)`.
2. Requires the spec to live at `.megaplan/initiatives/<initiative>/chain.yaml` unless
   `--allow-loose-chain-spec` is passed for a temporary compatibility launch.
3. Derives an isolated workspace and tmux session from the chain identity when
   `repo.workspace` and `chain_session` are omitted from `cloud.yaml`.
4. Resolves each milestone idea file from `--idea-dir` or, by default, the local spec's parent directory.
5. Uploads each idea file to the remote path named in the chain spec.
6. Uploads the chain spec to the matching repo-relative path in the remote workspace.
7. Starts remote `python -m arnold_pipelines.megaplan chain start --spec <remote-spec>` in the derived tmux session, logging to `<workspace>/.megaplan/cloud-chain-<session>.log`.

If the remote Arnold editable checkout is dirty from a previous failed repair,
retry with `--force-clean-editable-install`. This is opt-in and only resets and
cleans `megaplan.src_path` before refreshing from `editible-install`; it does not
reset the application workspace.

After upload + dispatch, cloud writes a provider-independent marker:

```text
~/.megaplan/cloud/markers/<sha256(abs_path_of_cloud.yaml)[:16]>/last_chain.json
```

That marker survives deploy-dir refreshes and is used by `cloud status --chain`.

### `python -m arnold_pipelines.megaplan cloud status --chain`

`cloud status --chain` fetches remote `chain_state.json`, then reuses core chain status formatting. Remote spec resolution precedence is:

1. `--remote-spec <path>`
2. `~/.megaplan/cloud/markers/<sha>/last_chain.json`
3. `spec.chain.spec` from `cloud.yaml` when `mode: chain`
4. Otherwise `missing_remote_spec`

The command prints the structured payload on stdout and the same human-readable chain summary block that local `python -m arnold_pipelines.megaplan chain status --spec ...` prints on stderr.

### `python -m arnold_pipelines.megaplan cloud status`

Without `--chain`, `cloud status` still runs remote `python -m arnold_pipelines.megaplan status` and prints that JSON payload unchanged.

Status payloads keep the durable lifecycle value in `plan_state` (or the
legacy-compatible `state`) and expose presentation separately through
`active_phase`, `execution_state`, and `display_state`. In particular, a live
execute step is displayed as `executing` while its correct durable
`plan_state` remains `finalized`. Progress remains a projection: 30% for work
through finalize plus 70% apportioned by completed finalized-task complexity.

### `python -m arnold_pipelines.megaplan cloud supervise --chain`

`cloud supervise --chain` runs a **one-shot supervisor tick** against the remote chain. It observes the chain, refreshes branch/PR sync state, and makes safe progress decisions. It never invents approvals, bypasses quality gates, or runs destructive git operations.

### Resident cloud watchdog

Every cloud container starts `/usr/local/bin/arnold-watchdog` in a dedicated
tmux session named `watchdog`. The watchdog scans
`/workspace/.megaplan/cloud-sessions/*.json` once per hour, treats each marker
as an active chain that should be supervised, and leaves live tmux sessions
alone. If a marked chain session has stopped, the watchdog first invokes
`arnold-kimi-goal-operator`: a Kimi Code agent that inspects run state/logs,
uses Codex for root-cause fixes in the Arnold editable install when needed,
validates, commits/pushes, refreshes the install, and tries to unblock the
current run. The watchdog then falls back to relaunching the chain as a
one-shot `chain start --one` under `arnold-supervise` if needed. Every scan also
writes a structured report and logs a single-line JSON summary; set a webhook
URL to receive that report remotely.

Useful environment variables:

| Variable | Default | Meaning |
|---|---:|---|
| `CLOUD_WATCHDOG_INTERVAL_SECS` | `3600` | Seconds between scans. |
| `CLOUD_WATCHDOG_LOG` | `/workspace/watchdog.log` | Watchdog log path. |
| `CLOUD_WATCHDOG_REPORT_PATH` | `/workspace/watchdog-report.json` | Latest structured scan report. |
| `CLOUD_WATCHDOG_REPORT_WEBHOOK` | unset | Optional HTTP endpoint that receives the full report JSON after each scan. |
| `ARNOLD_REPAIR_TRIGGER_ENABLED` | `0` | Set to `1` to let the watchdog dispatch repair loops for unintended stops and run editable-install repair when import checks fail. |
| `CLOUD_WATCHDOG_PUSH_REPAIRS` | `0` | Set to `1` to push watchdog repair commits after a successful Codex repair. |
| `CLOUD_WATCHDOG_ARNOLD_SRC` | `/workspace/arnold` | Arnold source checkout used for Codex repair. |
| `CLOUD_WATCHDOG_SYNC_ENABLED` | `1` | Set to `0` to disable the hourly editable-install source sync. |
| `CLOUD_WATCHDOG_SYNC_BRANCH` | `editible-install` | Branch the watchdog keeps synced in the editable source checkout. Do not point this at the active workflow branch except for a deliberate one-off debug run. |
| `CLOUD_WATCHDOG_SYNC_REPO` | `MEGAPLAN_REPO` or the primary workspace origin | Git repo URL used if the editable source checkout must be cloned. |
| `CLOUD_WATCHDOG_CODEX_TIMEOUT_SECS` | `1800` | Timeout for a Codex repair attempt. |
| `KIMI_API_KEY` | unset | Required for `arnold-kimi-goal-operator`. |
| `KIMI_GOAL_MODEL` | `kimi-k2.7-code` | Kimi model used by the goal operator. |
| `KIMI_GOAL_TIMEOUT_SECS` | `3600` | Timeout for one Kimi diagnosis/repair goal attempt. |

Run one scan manually inside the container:

```bash
/usr/local/bin/arnold-watchdog --once
```

At the start of every scan, the watchdog also maintains a separate editable
Arnold source checkout, defaulting to `/workspace/arnold`. It clones the
configured repo if missing, fetches and fast-forwards the sync branch,
regenerates generated docs/skills when `scripts/generate_arnold_docs.py` is
present, runs `sync-skills.sh` when present, commits/pushes any resulting drift,
and refreshes the installed Arnold package from `/workspace/arnold`. If that
source checkout is unavailable, it falls back to `/usr/local/bin/mp-refresh-megaplan`
with `MEGAPLAN_REF` pinned to the sync branch. It does not force-push, reset, or
mutate the active chain workspace to perform this sync.

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

The supervisor targets the same `megaplan-chain` tmux session used by `cloud chain`. All mutations use the canonical `MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold_pipelines.megaplan chain start --spec <path> --one` command, appending to `<workspace>/.megaplan/cloud-chain.log`.

#### Safe actions

The supervisor will **only** perform these mutations:

- **Restart a dead runner**: When `effective_status` is `stale_bookkeeping` and the `megaplan-chain` tmux session is dead or missing, the supervisor kills any stale session and starts a fresh one-shot tick.
- **Auto-merge or advance a milestone PR**: When `effective_status` is `awaiting_pr_merge`, the supervisor may auto-merge only if the chain declares `merge_policy: auto`; once the PR is merged (by policy or by a human), it advances the chain with a one-shot tick.

#### Refusal cases (no mutation)

The supervisor **refuses to act** and returns `acted: false` with a `refused_reason` for:

| effective_status | Behavior |
|---|---|
| `running` | Chain is running; nothing to do. |
| `complete` | All milestones processed; chain is done. |
| `human_prerequisite` | Prerequisite policy is `required` and unmet; requires human operator resolution via `python -m arnold_pipelines.megaplan user-action resolve` or `python -m arnold_pipelines.megaplan chain override`. |
| `quality_gate` | Validation policy is `required` and quality gate is failing; requires human operator resolution. |
| `awaiting_pr_merge` (PR unmerged, `merge_policy: review`/`manual`) | PR is still open; supervisor will not advance until merged by a human. |
| `stale_bookkeeping` (runner alive) | Bookkeeping is stale but runner is alive; supervisor will not force-restart a live runner. |
| Provider lacks `ssh_exec` | Cannot probe or mutate the remote runner. |

#### Not a destructive repair tool

The supervisor is **not** a destructive repair tool and does **not** replace:

- **Human approval** of prerequisites — use `python -m arnold_pipelines.megaplan user-action resolve` or `python -m arnold_pipelines.megaplan chain override`.
- **PR review** — the supervisor only advances when the PR is already merged.
- **Quality-gate resolution** — failing gates must be resolved by a human operator.

The supervisor never produces force-push, reset, branch-deletion, or any other destructive git commands. Its only mutations are tmux session management and `chain start --one`.

## Boot-Time Runner Modes

`mode: auto` and `mode: chain` still control what the long-running remote `agent` session launches on boot. Those boot paths expect the referenced remote files to already exist on the workspace volume.

Use `cloud bootstrap` and `cloud chain` when you want cloud to stage the local input files for you. If you set `mode: auto` or `mode: chain` directly in `cloud.yaml`, make sure the referenced remote files already exist before restart.

## Logs, Redaction, And Attach

`python -m arnold_pipelines.megaplan cloud logs` redacts:

- literal values for secret names listed under `secrets:` when those values are present locally
- `NAME=value` and `NAME: value` patterns for those secret names
- known token shapes such as `sk-...`, `ghp_...`, and `xoxb-...`

This redaction applies to:

- `python -m arnold_pipelines.megaplan cloud logs`
- `python -m arnold_pipelines.megaplan cloud exec`
- wrapper-dispatched output from `cloud bootstrap`, `cloud chain`, and `cloud resume`

`python -m arnold_pipelines.megaplan cloud attach` is different. It opens a raw interactive PTY, so line-buffered redaction is not applied there. Treat attach sessions as trusted terminals.

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

## Runtime Requirements

- Docker install docs: https://docs.docker.com/get-docker/
- OpenSSH project/docs: https://www.openssh.com/
- Config & environment map: [docs/configuration.md](configuration.md)

## M1 Cloud-Safe Repair Substrate

The M1 substrate wraps the existing watchdog, repair loop, auditor, and Discord
dispatch with observe-only resolver evidence, shared repair locking, canonical
redaction, and feature flags.  All behaviour-changing paths are disabled by
default; the resolver and redaction are on.

### Quick Reference

| Topic | See |
|---|---|
| Rollback, preflight, flags, wrapper refresh, lock inspection, watchdog restart, validation | [docs/ops/recovery-runbooks.md](ops/recovery-runbooks.md) — `OPS-M1-REPAIR-ROLLBACK` |
| Feature flag env vars and defaults | `arnold_pipelines/megaplan/cloud/feature_flags.py` |
| Repair lock dir (`<marker_dir>/<session>.repair-loop.lock/`) | `arnold_pipelines/megaplan/cloud/repair_lock.py` |
| Sidecar compatibility (needs-human, repair-data) | `arnold_pipelines/megaplan/cloud/repair_contract.py` |
| Redaction API | `arnold_pipelines/megaplan/cloud/redact.py` |
| Implementation plan (sprints, stages, policy decisions) | [docs/ops/tiered-repair-implementation-plan.md](ops/tiered-repair-implementation-plan.md) |

### Key env vars

| Variable | M1 Default | Behaviour |
|---|---|---|
| `ARNOLD_RESOLVER_OBSERVE` | `1` | Capture resolver evidence (additive, non-authoritative). |
| `ARNOLD_RESOLVER_ENFORCEMENT` | `0` | Make resolver authoritative for target selection. |
| `ARNOLD_ESCALATION_LEDGER` | `0` | Enable append-only escalation ledger. |
| `ARNOLD_AUTONOMY` | `0` | Enable autonomous trigger/meta/auditor actions. |
| `ARNOLD_REDACTION_ENABLED` | `1` | Redact secrets in persisted and outbound artifacts. |

All flags accept `0`/`false`/`no`/`off` to disable.  Unset uses the M1 default.

### Wrapper deployment note

The editable-install sync updates the Python package but does **not** refresh
`/usr/local/bin` wrappers.  After every merge that changes wrapper scripts or
shared cloud Python modules, re-copy wrappers manually:

```bash
cd /workspace/arnold
for w in arnold-repair-loop arnold-watchdog arnold-progress-auditor arnold-discord-dm; do
  cp "arnold_pipelines/megaplan/cloud/wrappers/$w" "/usr/local/bin/$w"
  chmod +x "/usr/local/bin/$w"
done
```

## Related Runbooks And Design Notes

- **Cloud chain smoke**: [docs/ops/cloud-chain-smoke.md](ops/cloud-chain-smoke.md) — end-to-end smoke tests for cloud chain operations.
- **Recovery runbooks**: [docs/ops/recovery-runbooks.md](ops/recovery-runbooks.md) — operational procedures for recovering cloud deployments, including the M1 rollback/preflight runbook (`OPS-M1-REPAIR-ROLLBACK`).
- **Cloud prerequisite resolution**: Active milestone briefs live under `.megaplan/initiatives/<initiative>/briefs/` — these are the source of truth for structured prerequisite/quality resolution metadata, auto recovery, chain policy/status, cloud supervision, and slot-first watchdog hardening.
- **Slot-first watchdog**: The watchdog operates from the assigned slot/workspace first, verifies provider and session consistency, lists available human-verification actions, and only restarts or wakes chains when the status payload shows the chain is recoverable. Continuous branch and PR synchronization is required after stops and recoveries so status reflects what code reviewers and operators see.

## Migration From `reigh-megaplan-dev`

The historical migration runbook is archived at [docs/archive/cloud-migration-from-reigh.md](archive/cloud-migration-from-reigh.md). The important rule is: write `MIGRATED.md` first, then remove siblings while preserving that pointer file.
