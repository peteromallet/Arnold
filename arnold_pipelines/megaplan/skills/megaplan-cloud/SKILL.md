---
name: megaplan-cloud
description: Run megaplan plans and chains inside a provider-managed container (today, Railway) with a persistent workspace volume. Use when the run needs to outlast a local terminal session, span multiple repos, or share a long-lived dev box across concurrent chains. Covers `cloud.yaml` fields, `extra_repos[]` + `chain_session` multi-tenancy, the operator loop, and the gotchas that wedge fresh runs.
---

# Megaplan Cloud

`megaplan cloud` runs a plan inside a provider-managed container with a persistent workspace volume, so the run survives the user's terminal session. Today only the `railway` provider is shipped end-to-end; `ssh` and `local` are scaffolded for future use.

Reach for cloud mode when at least one of these is true:

- The plan is long-running and would outlast a local terminal session.
- The work spans multiple repos that all need to be mounted side-by-side (`extra_repos:`).
- The user wants an isolated persistent sandbox separate from their laptop.
- A chain needs to keep running while the laptop is asleep or on the move.

Skip cloud mode when the plan finishes in a sitting, the work fits in one repo, and a local `megaplan run` would do the same job.

## Subcommands

`init`, `build`, `deploy`, `chain`, `status`, `attach`, `logs`, `exec`, `resume`, `down`, `destroy`.

Typical flow:

1. `megaplan cloud init` scaffolds a `cloud.yaml` at the project root.
2. Edit it (set the provider, primary `repo:`, any `extra_repos:`, the secret names, etc.).
3. Export the secret values into your local env (the names listed under `secrets:` in `cloud.yaml`).
4. `megaplan cloud deploy` to build the image and start the runner.
5. `megaplan cloud chain <chain.yaml>` for a multi-milestone run, or `megaplan cloud bootstrap <idea.md>` for a single plan.
6. Use `status`, `logs`, `attach` to observe; `down` to pause, `destroy` to tear the volume.

See `docs/cloud.md` for the full reference, including `cloud.yaml` fields, mode behavior (`auto`/`chain`/`idle`), and provider-specific troubleshooting.

## Claude auth: subscription via refresh token (no metered API, no human)

When Claude phases run on the cloud worker, you want them billed against your Claude **subscription** (Max/Pro), not metered API. The entrypoint supports two auth modes with clear precedence:

1. **`CLAUDE_CODE_REFRESH_TOKEN`** *(preferred — programmatic, no expiry)*. Set this once on the Railway service. On every boot, the entrypoint installs:
   - `/usr/local/bin/claude.real` — copy of the actual claude binary.
   - `/usr/local/bin/claude-key-helper` — refreshes the OAuth access token against `https://api.anthropic.com/v1/oauth/token` using the refresh token, caches the result on the volume (`/workspace/.claude-creds/`), and rotates the refresh token per use.
   - `/usr/local/bin/claude` — shim that calls the helper, exports `ANTHROPIC_API_KEY`, and `exec`s the real binary.

   First-time setup runs on your laptop where you're already logged in to claude:

   ```bash
   bash scripts/refresh-cloud-claude-key.sh
   ```

   That extracts the refresh token from your macOS Keychain (service `"Claude Code-credentials"`), validates it against the OAuth endpoint, and pushes the (rotated) value to Railway as `CLAUDE_CODE_REFRESH_TOKEN`. No browser, no recurring human action. Re-run only if you `claude /logout` everywhere or the refresh token gets revoked.

   The OAuth client ID is `9d1c250a-e61b-44d9-88ed-5944d1962f5e` (Claude Code's public client, discovered from the binary). Override with `CLAUDE_CODE_OAUTH_CLIENT_ID` on the service if needed.

2. **`ANTHROPIC_API_KEY`** *(legacy / metered)*. If `CLAUDE_CODE_REFRESH_TOKEN` is unset, the entrypoint expects a real API key here. `claude --bare` reads it directly; no shim installed. Billed per-call against the Anthropic Console org.

If neither is set the entrypoint warns and continues — Claude phases will then fail at first invocation. Codex/DeepSeek/Kimi/Fireworks phases are unaffected.

**Why a shim rather than `claude setup-token`**: `setup-token` generates a long-lived `sk-ant-api03-...` key but requires an interactive browser OAuth approval — incompatible with headless cloud-worker boot. The refresh-token flow uses credentials you already authorized when you ran `claude /login` on your laptop, and rotates them indefinitely without further consent.

**Why a shim rather than `apiKeyHelper` in `--settings`**: shannon/megaplan invoke `claude --bare` without an explicit `--settings` flag. Wrapping the binary is the only way to inject auth without patching megaplan.

## Codex auth: ChatGPT subscription OAuth (not the metered API key)

When codex (GPT-5.x) phases run on the worker, megaplan invokes the `codex exec` CLI. The codex CLI **defaults to API-key auth whenever `OPENAI_API_KEY` is in the environment** — routing to `api.openai.com` standard billing, which fails with `ERROR: Quota exceeded. Check your plan and billing details.` the moment that key is dead or out of credits. A stray `OPENAI_API_KEY` on the service silently hijacks codex onto metered billing even when you intend to use your ChatGPT subscription.

**Default (`megaplan.codex_auth: chatgpt`)** forces the subscription path:

- The entrypoint writes `preferred_auth_method = "chatgpt"` (and `forced_login_method = "chatgpt"`) into `~/.codex/config.toml`, so codex uses the ChatGPT-subscription endpoint (`chatgpt.com/backend-api/codex`) **even when `OPENAI_API_KEY` is set**.
- `seed_codex_oauth()` (run on `cloud deploy` and before each `cloud chain`) copies your local `~/.codex/auth.json` and `~/.hermes/auth.json` OAuth bundles to `/workspace/.creds/` (persistent volume) and `/root`; the entrypoint re-seeds from the volume on every boot, so a container restart restores the credential automatically (`/root` is ephemeral).

**Seeding / refresh:** seed once from a machine where you're logged in (`codex login` → `~/.codex/auth.json` with `auth_mode: chatgpt`). Codex auto-refreshes the OAuth bundle during use and writes it back; a session only goes stale after ~8 days idle. Re-run `cloud deploy` (or the seed) to re-push if it goes stale or the chain breaks. **Rotation caveat:** the same OAuth refresh token can't be used concurrently by your laptop *and* the box without invalidating one — let the box own the session, or (ChatGPT Business/Enterprise) use a **Codex Access Token** (`CODEX_ACCESS_TOKEN`, 7/30/60/90-day) instead.

**Opt out** with `megaplan.codex_auth: apikey` to use standard API-key billing — the entrypoint then runs `codex login --with-api-key` from `OPENAI_API_KEY` and skips the OAuth seed.

**Verify** which path is live: `RUST_LOG=debug codex exec --sandbox read-only --skip-git-repo-check "ok" 2>&1 | grep -iE 'chatgpt.com/backend-api/codex|api.openai.com'` — you want the chatgpt backend, not `api.openai.com`.

## Multi-repo and multi-tenant chains

Two `cloud.yaml` fields let one shared worker host many sibling repos and several concurrent chains:

- **`extra_repos:`** — list of `{url, branch, workspace}` cloned as siblings of the primary `repo:` on every container boot. Each workspace must be a unique absolute POSIX path. Use for chains that span multiple repos (e.g. an app + worker + sibling agent repos). The entrypoint baked into the cloud image clones-if-missing, so adding an `extra_repos` entry requires `megaplan cloud deploy` to re-render the entrypoint — not just `cloud chain` again.
- **`chain_session:`** — tmux session name `megaplan cloud chain` uses on the worker. Default `megaplan-chain`. Override per `cloud.<chain>.yaml` (e.g. `chain_session: slot-first`) so two concurrent chains on the same shared worker don't collide. Non-default sessions write their log to `.megaplan/cloud-chain-<session>.log` instead of `.megaplan/cloud-chain.log`.

The dev pattern is one long-lived `mode: idle` cloud service plus a `cloud.<chain>.yaml` per chain. The box stays up; each `megaplan cloud chain` invocation creates its own tmux session and writes plan state under `<workspace>/.megaplan/plans/`. Concurrent chains targeting the same primary repo will collide on the workspace path — give them distinct workspace prefixes (e.g. `/workspace/<chain-name>/<repo>/`) or run them sequentially.

A minimal multi-repo `cloud.yaml`:

```yaml
provider: railway

repo:
  url: https://github.com/org/app.git
  branch: main
  workspace: /workspace/app

extra_repos:
  - url: https://github.com/org/worker.git
    branch: main
    workspace: /workspace/worker
  - url: https://github.com/org/agent.git
    branch: main
    workspace: /workspace/agent

chain_session: my-chain    # per-chain tmux session

mode: idle                 # box stays up; chain launches its own session

megaplan:
  ref: main                # or a SHA on a feature branch

resources:
  volume: my-volume
  port: 8080

railway:
  service: megaplan-dev    # the shared service name on Railway
  session: agent           # interactive attach session — NOT the chain session

secrets: []                # leave empty if values are pre-set on the service
```

## Operator loop

For long-running cloud plans — especially chain runs — do not rely on a passive `tail` or a one-off `cloud exec` as the only supervision. Run the plan in one tmux session and a separate monitor/supervisor in another tmux session.

Recommended check cadence:

1. Check immediately after launch, to catch bad branches, missing secrets, bad provider config, or command syntax.
2. Check again after 10–15 minutes, because most cloud setup and first model-call failures surface early.
3. Check hourly after that for long execution, review, or chain progress.

Use separate cloud workspaces for unrelated mutating tasks. If `/workspace/<repo>` is already running a plan, create a sibling checkout such as `/workspace/<repo>-task-foo`, use a separate branch, separate tmux session names, and separate logs. Do not launch two mutating plans in the same checkout unless the user explicitly wants them to share branch state.

An operator loop may automatically handle infrastructure recovery:

- restart a dead tmux runner when no active phase process exists;
- rerun `megaplan auto` for states with an unambiguous valid next step;
- recover provider quota/failure by switching to an already-approved fallback model/provider for the same phase;
- continue a chain after a completed milestone;
- commit and push after each completed milestone when the user asked for push-after-sprint behavior.

An operator loop should **not** silently decide product or architecture questions, resolve merge conflicts, accept destructive cleanup, or ignore failing tests. Those are implementation decisions, not supervision. Surface them to the user or write a clear ticket unless the plan already contains an explicit settled decision that covers the case.

Today this operator loop is usually a small project-local shell script under `.megaplan/` plus tmux. Treat that as an operational shim, not the ideal abstraction. The durable Megaplan feature should be first-class cloud supervision: built-in early check, hourly tick, provider fallback policy, single-PR chain mode, and push-after-milestone support.

## Hourly editable-install sync

On SSH/Hetzner workers, the resident watchdog keeps a separate editable Arnold
source checkout synced before it inspects chain sessions. This checkout is
`/workspace/arnold` and must stay on the dedicated `editible-install` branch
unless `CLOUD_WATCHDOG_SYNC_BRANCH` is deliberately set for a one-off debug
case. It is intentionally separate from the active workflow checkout, whose
branch varies per megaplan. The sync step:

- clones the configured Arnold repo into `/workspace/arnold` if missing;
- fetches and fast-forwards the sync branch;
- regenerates generated docs/skills with `python scripts/generate_arnold_docs.py --write` when present;
- runs `./sync-skills.sh` when present so bundled skills are linked into the agent skill dirs;
- commits and pushes any resulting source drift back to the sync branch;
- refreshes the installed Arnold package from `/workspace/arnold`, falling back
  to `/usr/local/bin/mp-refresh-megaplan` with `MEGAPLAN_REF` pinned to the sync
  branch only when the source checkout is unavailable.

It does not force-push, reset, or mutate the active chain workspace. Disable
with `CLOUD_WATCHDOG_SYNC_ENABLED=0` only when deliberately debugging the
editable install.

## SSH hot-upload operations

For SSH/Hetzner workers, use `python scripts/cloud_hot_upload.py` when a
running container needs a narrow wrapper/runtime/env hotfix and rebuilding the
Docker image would be too slow. It reads the SSH host, port, container, volumes,
and remote deploy dir from `cloud.yaml`, dry-runs by default, uploads files with
`docker exec`/SSH, verifies remote `sha256sum`, and reports container/tmux
state.

Default workflow-manifest-runtime dry run:

```bash
python scripts/cloud_hot_upload.py \
  --wrapper arnold-watchdog \
  --wrapper arnold-kimi-goal-operator \
  --verify
```

Apply and restart the watchdog tmux session:

```bash
python scripts/cloud_hot_upload.py \
  --wrapper arnold-watchdog \
  --wrapper arnold-kimi-goal-operator \
  --restart-session watchdog \
  --apply
```

Use this as an operational hotfix, then make the durable repo/image-template
change too. For token/env changes that only need to affect tmux sessions
restarted through the helper, use `--env-name NAME` after exporting the local
value; it writes `/workspace/.cloud-hot-env` inside the container. For full
Docker env replacement, pass a local file outside the repo with
`--env-file /secure/path/.env --recreate-container --apply`; never commit secret
material and remember that Docker only applies env-file changes when the
container is recreated. See `docs/cloud-hot-upload.md` for examples.

## Hetzner check-in runbook

For SSH/Hetzner workers, verify the live machine directly instead of inferring
health from local state. Read the target host/container from the active
`cloud.yaml`; for the current Arnold worker this is typically:

```bash
ssh -p 22 root@159.69.51.216
docker exec -it megaplan-cloud-agent bash
```

Minimum check-in:

```bash
# Host/container resilience.
hostname
systemctl is-active megaplan-watchdog-ensure.timer 2>/dev/null || true
systemctl list-timers megaplan-watchdog-ensure.timer --no-pager 2>/dev/null || true
tail -20 /var/log/megaplan-watchdog-ensure.log 2>/dev/null || true
docker ps --filter name=megaplan-cloud-agent --format '{{.Names}} {{.Status}} {{.Image}}'
docker inspect -f 'restart={{.HostConfig.RestartPolicy.Name}}' megaplan-cloud-agent

# Inside the container.
docker exec megaplan-cloud-agent bash -lc '
  echo SESSIONS
  tmux ls 2>/dev/null || true

  echo PROCS
  pgrep -af "arnold-watchdog|arnold-supervise|arnold_pipelines.megaplan chain start" || true

  echo REPORT
  python3 -m json.tool /workspace/watchdog-report.json 2>/dev/null || true

  echo REPORT_ARCHIVES
  ls -lt /workspace/watchdog-reports 2>/dev/null | head || true

  echo WATCHDOG_LOG
  tail -80 /workspace/watchdog.log 2>/dev/null || true

  echo AGENT_PANE
  tmux capture-pane -pt agent -S -80 2>/dev/null || true

  echo RECENT_EVENTS
  find /workspace/Arnold/.megaplan/plans -name events.ndjson -print 2>/dev/null |
    sort | tail -1 | xargs -r tail -20
'
```

Interpretation:

- `watchdog` tmux session should exist and log `starting (interval=3600s ...)`.
- `agent` tmux session alone is not enough; confirm an active
  `python3 -m arnold_pipelines.megaplan chain start ...` process or fresh
  `llm_token_heartbeat` events.
- `/workspace/watchdog-report.json` is the latest report. Timestamped history
  lives under `/workspace/watchdog-reports/`.
- `issue_count: 0` means the last watchdog tick saw no actionable issue.
- If `CLOUD_WATCHDOG_REPORT_WEBHOOK` is unset, reports are stored locally only.

Always distinguish the two Arnold checkouts:

```bash
docker exec megaplan-cloud-agent bash -lc '
  echo EDITABLE_INSTALL
  cd /workspace/arnold &&
    printf "path=%s\nbranch=%s\ncommit=%s\n" "$PWD" "$(git branch --show-current)" "$(git rev-parse --short HEAD)"

  echo ACTIVE_WORKFLOW
  cd /workspace/Arnold &&
    printf "path=%s\nbranch=%s\ncommit=%s\n" "$PWD" "$(git branch --show-current)" "$(git rev-parse --short HEAD)"

  echo WATCHDOG_SYNC_BRANCH
  grep -n "^SYNC_BRANCH=" /usr/local/bin/arnold-watchdog
  grep -E "^export CLOUD_WATCHDOG_SYNC_BRANCH=" /workspace/.cloud-hot-env 2>/dev/null || true
'
```

Expected invariant:

- `/workspace/arnold` is the editable install/runtime checkout and should be on
  `editible-install`.
- `/workspace/Arnold` is the active megaplan checkout and may be on any
  per-plan or per-milestone branch.

### One-shot watchdog check/repair

The hourly watchdog can be triggered immediately with `arnold-watchdog --once`.
This is the manual "run the watchdog right now" path: it performs the same sync,
inspection, repair, relaunch, report-write, and report-archive work as the
hourly tick, then exits. Use it after hot-uploading wrapper/env/skill changes,
after moving a new chain onto the worker, or when you want to battle-test the
recovery path without waiting for the next hourly tick.

```bash
ssh -p 22 root@159.69.51.216 \
  "docker exec megaplan-cloud-agent bash -lc 'timeout 900 /usr/local/bin/arnold-watchdog --once; rc=\$?; echo WATCHDOG_RC=\$rc; python3 -m json.tool /workspace/watchdog-report.json; echo REPORT_ARCHIVE; python3 -c \"import json; print(json.load(open(\\\"/workspace/watchdog-report.json\\\"))[\\\"archive_report_path\\\"])\"'"
```

Expected success shape:

- `WATCHDOG_RC=0`;
- `/workspace/watchdog-report.json` has `issue_count: 0` or a concrete
  `issues[]` entry explaining the remaining blocker;
- `archive_report_path` points at a unique timestamped JSON file under
  `/workspace/watchdog-reports/`;
- the active chain has a tmux session and, unless complete, an active
  `arnold_pipelines.megaplan chain start` or worker process.

## Gotchas (learned the hard way)

1. **`chain_state.json` committed in the project repo poisons fresh chains.** The chain runner derives state from `<chain.yaml dir>/chain_state.json`. If a prior chain committed that file, every `git clone` on the worker re-seeds stale state (`completed: [...prior milestones]`, `current_milestone_index: N`); the new chain skips early milestones and crashes at a later `git checkout main` against leftover working-tree dirt. Fix: `rm` it on the worker after clone. Durable fix: `git rm chain_state.json` + add to `.gitignore` on the branch. Don't trust `git checkout -- .` as cleanup — it restores tracked files including this one.

2. **Profile-name gap between the decision skill and the loaded registry.** The decision skill documents `basic`/`led`/`thoughtful`/`premium`/`super-premium`. The registry only loads `solo`/`directed`/`partnered`/`premium`/`apex`, with `basic`→`solo` and `led`→`directed` as legacy aliases — `thoughtful` and `super-premium` are **not** aliased. Chain specs need canonical names or chain start fails preflight with "Unknown profile".

3. **The `cloud preflight` resolver ignores milestone-level `vendor`/`depth`/`critic`.** `megaplan/cloud/preflight.py:_expanded_phase_models` hardcodes `vendor=None`, `depth=None`, `critic=None`. The local preflight will misreport phase routing for chains that override vendor per milestone — but the **runtime** phase invoker in `chain.py:_init_plan` DOES forward those fields, so the actual run uses the correct routing. Treat preflight's `resolved_phase_map` as advisory until that gap closes.

4. **`megaplan` CLI may use a separate Python venv** from `pip install --user`. After upgrading megaplan from a branch SHA, run `head -1 $(which megaplan)` to find which interpreter and `python -m pip install` into that one specifically — otherwise local `cloud chain` runs against the old code while the remote pulls the new SHA.

5. **`secrets:` in `cloud.yaml` drives an upload from local env at deploy time.** If you pre-set values directly on the Railway service (e.g. copied from another service), leave `secrets: []` in the `cloud.yaml` — otherwise `megaplan cloud deploy` reads the names from your local env, finds them missing, and either fails the deploy or overwrites the Railway values with empty strings. List the names in a comment for reference.

6. **Credit-balance failures look like `internal_error`.** When a phase exits as "internal_error" with no useful stderr, read `plan_v<n>_raw.txt` in the plan directory. Anthropic/OpenAI quota errors arrive there as `"text":"Credit balance is too low"` from the agent CLI wrapper. For Claude, the real fix is the refresh-token shim (see "Claude auth" above) — it bills against your subscription, never depletes. For OpenAI, top up the console balance or switch to a profile with credit headroom — **but for a `codex` phase it's usually the API-key fallback, not a real balance issue; see gotcha #9.**

7. **`secrets` get baked into the image-build context, not just runtime env.** `megaplan cloud deploy` runs `railway variables --set NAME=VALUE` for every secret in the local environment that matches a declared name, then `railway up`. Pre-existing values on the service are overwritten when the local env has the same key set. To preserve service-side values, either unset them locally before deploy or empty the `secrets:` list.

8. **Volume size and disk pressure.** The default Railway volume is 5 GB. A multi-repo chain with `node_modules` and `.venv` directories across sibling repos can fill it quickly; `git clean -fdx` and `npm cache clean --force` on the worker free space, but ultimately bump the volume in the Railway UI if you're routinely seeing disk-pressure errors.

9. **Codex `Quota exceeded. Check your plan and billing details.` is the API-key fallback, not a real cap.** megaplan runs codex via `codex exec`, which silently uses **API-key mode** when `OPENAI_API_KEY` is present — so plan/critique/etc. hit `api.openai.com` with that (often dead) key and quota-fail, even though you have a working ChatGPT subscription. This is the codex-specific case of gotcha #6, and "top up the console balance" is the *wrong* fix. Right fix: `megaplan.codex_auth: chatgpt` (the default) forces `preferred_auth_method=chatgpt` so codex uses the subscription OAuth (`chatgpt.com/backend-api/codex`) regardless of `OPENAI_API_KEY`. If you see this error, confirm `/root/.codex/config.toml` has `preferred_auth_method = "chatgpt"` and `~/.codex/auth.json` has `auth_mode: chatgpt`, and that the OAuth seed landed (`/workspace/.creds/codex-auth.json`). See "Codex auth" above.

10. **Stalled `chain_state` makes a relaunch resume a dead plan (session alive, milestone stuck at "none").** An aborted run leaves `.megaplan/plans/.chains/<spec>-<digest>.json` with `last_state: "stalled"`; the next `cloud chain` resumes it and never starts the milestone. `cloud chain` now auto-clears a stalled-with-no-progress state on fresh launch; if you hit it on an older worker, `rm -rf .megaplan/plans/.chains/* .megaplan/plans/<milestone>-*` (only the stalled ones) and relaunch.

## Quick reference: shared dev-box workflow

For users running multiple chains across many repos on one Railway service:

1. **One-time setup**:
   - Create the Railway service (`railway add --service megaplan-dev`).
   - Attach a volume (`railway service megaplan-dev` then `railway volume add -m /workspace`).
   - Set project-level secrets once (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `FIREWORKS_API_KEY`, `GITHUB_TOKEN`, `MEGAPLAN_TRUSTED_CONTAINER=1`).

2. **Per chain**:
   - Write `cloud.<chain>.yaml` with `repo:` + any `extra_repos:` + `chain_session: <chain-name>` + `mode: idle`.
   - `megaplan cloud deploy --cloud-yaml cloud.<chain>.yaml` only when adding new repos or bumping `megaplan.ref` (the entrypoint is baked in at build time).
   - `megaplan cloud chain --cloud-yaml cloud.<chain>.yaml <chain.yaml>` to launch.

3. **Observing**:
   - `megaplan cloud status --chain` for the chain summary.
   - `megaplan cloud logs --no-follow` for build / boot logs.
   - SSH-tail the per-chain log: `railway ssh --service megaplan-dev -- tail -f /workspace/<repo>/.megaplan/cloud-chain-<chain-session>.log`.
   - List active chains: `railway ssh --service megaplan-dev -- tmux ls` (filter for non-default sessions).
