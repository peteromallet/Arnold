# Megaplan Cloud

`megaplan cloud` packages the existing Railway runner pattern into the main CLI for the narrow sprint-1 scope: one provider (`railway`), one persistent volume, manual upload of runtime input files, and parity with `reigh-megaplan-dev`.

Examples below use `megaplan ...`; in this repo run `./.venv/bin/python -m megaplan ...`, and add `--cloud-yaml /path/to/cloud.yaml` when `cloud.yaml` is not at the project root.

## Quick Start

1. Scaffold:

```bash
megaplan cloud init
```

2. Edit `cloud.yaml` for repo, mode, secrets, and Railway settings.

3. Export the local secrets named under `secrets:`:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...        # optional, but recommended for push/private clone
export ANTHROPIC_API_KEY=...   # optional
```

4. Deploy:

```bash
megaplan cloud deploy
```

5. Check status, logs, and SSH:

```bash
megaplan cloud status
megaplan cloud logs
megaplan cloud attach
```

## `cloud.yaml` Reference
### Top-level fields
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `provider` | no | `railway` | Sprint 1 provider; only `railway`. |
| `mode` | no | `idle` | Runner mode: `auto`, `chain`, or `idle`. |
| `secrets` | no | `[]` | Local env var names uploaded during `megaplan cloud deploy` before boot. |
### `repo`
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `repo.url` | yes | none | Git URL cloned into the persistent workspace volume on first boot. |
| `repo.branch` | no | `main` | Branch checked out on clone. |
| `repo.workspace` | no | `/workspace/app` | Absolute in-container repo path for clone, tmux, git safe.directory, and remote `cd`. |
### `agents`
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `agents.default` | no | `codex` | Default megaplan agent for routed steps. |
| `agents.<step>` | no | inherits `default` | Optional per-step override; valid keys match routed steps such as `plan`, `review`, `execute`, and `loop_execute`. |
Boot rewrites these as `megaplan config set agents.<step> <agent>`.
### `codex`
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `codex.model` | no | `gpt-5.4` | Value written into `/root/.codex/config.toml` on boot. |
| `codex.reasoning` | no | `high` | Reasoning level written into `/root/.codex/config.toml` on boot. |
### `auto`
Used only when `mode: auto`.
| Field | Required in `auto` mode | Default | Meaning |
|---|---|---:|---|
| `auto.plan_name` | yes | none | Plan name for `megaplan auto --plan ...` and first-boot `megaplan init`. |
| `auto.idea_file` | yes | none | Absolute in-container path to the uploaded idea text. |
| `auto.robustness` | no | `standard` | Robustness for the boot-time `megaplan init` fallback. |
### `chain`
Used only when `mode: chain`.
| Field | Required in `chain` mode | Default | Meaning |
|---|---|---:|---|
| `chain.spec` | yes | none | Absolute in-container path to the uploaded chain spec for `megaplan chain --spec ...`. |
### `megaplan`
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `megaplan.ref` | no | `main` | Branch, tag, or SHA installed on boot via `pip install --upgrade git+...@<ref>`. |
### `resources`
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `resources.volume` | no | none | Persistent Railway volume name. `megaplan cloud destroy` deletes it only when set; `cloud.yaml.tmpl` scaffolds `agent-volume` as an example. |
| `resources.port` | no | `8080` | Health server port exposed by the container. |
### `railway`
| Field | Required | Default | Meaning |
|---|---|---:|---|
| `railway.service` | no | `agent` | Railway service name for `deploy`, `logs`, and `down`. |
| `railway.session` | no | `agent` | Railway SSH session for `attach` and `ssh_exec`. |
| `railway.project` | no | unset | Optional Railway project ID/name for `railway link --project ...` before deploy. |
### Mode Behavior
| `mode` | What the `agent` tmux session launches | Required fields | Missing-file behavior |
|---|---|---|---|
| `auto` | If the named plan directory does not exist, bootstraps it with `megaplan init --project-dir <workspace> --name <plan> --auto-approve --robustness <level> "$IDEA"`, then runs `mp-supervise auto-<plan> megaplan auto --plan <plan>` | `auto.plan_name`, `auto.idea_file` | Missing `auto.idea_file`: logs `WARN: idea file missing, dropping to idle` and starts `bash -l` instead of crashing. |
| `chain` | Runs `mp-supervise chain mp-chain <chain.spec>` | `chain.spec` | Missing `chain.spec`: logs `WARN: chain spec missing, dropping to idle` and starts `bash -l`. |
| `idle` | Starts `bash -l` | none | Not applicable. |
Heartbeat tmux and the health server always start.

## Environment Variables And Secrets
`megaplan cloud deploy` reads each name listed under `secrets:` from the local environment and uploads it to Railway before `railway up`. Missing required secrets fail the deploy before any Railway command runs.
Keep `REPO_URL`, `REPO_BRANCH`, and `MEGAPLAN_REF` in `cloud.yaml` unless you need a runtime override.
| Variable | Required | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | usually yes | Used for Codex auth inside the container. If `/root/.codex/auth.json` is absent, entrypoint runs `codex login --with-api-key`. |
| `ANTHROPIC_API_KEY` | optional | If present, entrypoint attempts non-interactive Claude auth with `printf '%s\n' \"$ANTHROPIC_API_KEY\" \| claude setup-token`. Failure is a warning, not a deploy blocker. |
| `GITHUB_TOKEN` | optional | Configures git credentials for clone/push. Recommended for private repos or when the agent should push branches. |
| `GIT_EMAIL` | optional | Overrides the git commit author email. Default: `codex-agent@example.com`. |
| `GIT_NAME` | optional | Overrides the git commit author name. Default: `Codex Agent`. |
| `REPO_URL` | optional | Runtime override for `repo.url`. |
| `REPO_BRANCH` | optional | Runtime override for `repo.branch`. |
| `MEGAPLAN_REF` | optional | Runtime override for `megaplan.ref`. |

Railway CLI install docs: https://docs.railway.app/develop/cli

## Manual Upload Workflow For `auto.idea_file` And `chain.spec`
Sprint 1 keeps reigh parity by not uploading `auto.idea_file` or `chain.spec`: deploy uploads environment variables only. If either file is missing, boot warns, the `agent` tmux session falls back to `bash -l`, and you can upload the file, restart, and continue.
### Upload an idea file for `mode: auto`
```bash
cat idea.txt | megaplan cloud exec "cat > /workspace/idea.txt"
megaplan cloud down
megaplan cloud deploy
```
If your `cloud.yaml` uses a different `auto.idea_file` path, change the target path in the one-liner to match it exactly.
### Upload a chain spec for `mode: chain`
```bash
cat chain.yaml | megaplan cloud exec "cat > /workspace/chain.yaml"
megaplan cloud down
megaplan cloud deploy
```
If the chain spec references additional files (for example idea files under `/workspace/ideas/`), upload those too before restarting.

## Command Notes
### `megaplan cloud status`
Runs remote `megaplan status` through Railway SSH and prints the JSON payload unchanged. If you omit `--plan`, megaplan's own status auto-discovery is used.
### `megaplan cloud exec`
`megaplan cloud exec` does **not** auto-`cd` into `repo.workspace`. It runs the exact command string you give it.
Recommended pattern:
```bash
megaplan cloud exec "cd /workspace/app && megaplan status"
```
That is also the right pattern for ad hoc `git`, `ls`, or `megaplan override` operations inside the repo.
### `megaplan cloud destroy`
`destroy` is a full teardown:
1. `railway down --service <service>`
2. if `resources.volume` is set, `railway volume delete <volume>`
The command prompts interactively unless you pass `--yes`.

## Claude Auth Behavior
Sprint 1 treats Claude auth as best-effort: `printf '%s\n' "$ANTHROPIC_API_KEY" | claude setup-token`. If it fails, boot logs `WARN: Claude token auth failed; continuing without Claude auth`; deploy still succeeds.

## Bundled `chain.yaml.example`
Start from:
```text
megaplan/cloud/templates/chain.yaml.example
```
It expects the sprint-1 volume-backed `/workspace` layout and is the right starting point for the file you upload to `chain.spec`.

## Symptom → Cause → Fix

| Symptom | Likely cause | Fix |
|---|---|---|
| `megaplan cloud exec` or `megaplan cloud attach` hangs/errors | Container is redeploying | Wait ~30s, then retry. Use `megaplan cloud logs --no-follow` for recent output. |
| Codex reports `model_not_found` | Bad `codex.model` in `cloud.yaml` or a broken manual config edit in the container | Fix `cloud.yaml` and redeploy. The entrypoint rewrites `/root/.codex/config.toml` on every boot. |
| `megaplan cloud status` reports no such plan after restart | Wrong plan name or plan never initialized on disk | Use the exact plan name under `<repo.workspace>/.megaplan/plans/`, or rerun `auto` mode after uploading the idea file. |
| Plan shows an `active_step` but nothing is happening | The worker process died while plan state remained on disk | Run `megaplan cloud resume [--plan <name>]`. |
| `git push` fails inside the container | `GITHUB_TOKEN` missing, expired, or too limited | Rotate the token locally, export it, and redeploy so Railway variables are updated. |
| Container restarts repeatedly | Health server never came up or entrypoint exited before idling | Check `megaplan cloud logs` for startup errors. |
| Auto/chain mode never starts after deploy | `auto.idea_file` or `chain.spec` is missing on the volume | Upload the missing file with `megaplan cloud exec "cat > /workspace/..."`, then restart with `megaplan cloud down` + `megaplan cloud deploy`. |

## Secret Rotation And Cost Monitoring

### Rotate secrets after unattended runs

- OpenAI API keys: https://platform.openai.com/api-keys
- GitHub tokens: https://github.com/settings/tokens
- Anthropic keys: rotate in the Anthropic console used for your account/org

Because Railway variables are plaintext to project members, rotate long-lived keys after high-trust or shared-environment runs.

### Monitor cost

- Railway compute/storage/runtime/deployments/volume usage: Railway dashboard for the linked project/service
- OpenAI usage: https://platform.openai.com/settings/organization/usage
- OpenAI limits/caps: https://platform.openai.com/settings/organization/limits

## Sprint 2 Follow-Ups

Sprint 2 is expected to add:

- additional providers (`fly`, `ssh`, `local`)
- `megaplan cloud init-plan`
- automated upload/materialization for `auto.idea_file` and `chain.spec`
- reigh-parity validation runbook
