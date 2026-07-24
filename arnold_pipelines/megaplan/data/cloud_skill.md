---
name: megaplan-cloud
description: Run megaplan plans and chains on the Hetzner agentbox via the ssh provider, with a persistent workspace volume. Use when the run needs to outlast a local terminal session, span multiple repos, or share a long-lived dev box across concurrent chains. Covers `cloud.yaml` fields, `extra_repos[]` + `chain_session` multi-tenancy, the operator loop, the direct-`chain-start` recipe for the ssh box, and the gotchas that wedge fresh runs.
---

# Megaplan Cloud

`megaplan cloud` runs a plan inside a provider-managed container with a persistent workspace volume, so the run survives the user's terminal session. For this environment, use **`provider: ssh`** against the Hetzner agentbox. Do not launch Megaplan work on other cloud providers unless the user explicitly asks for legacy-provider debugging. `local` is scaffolded; the ssh provider is the working path. See **SSH provider — Hetzner agentbox** below.

Reach for cloud mode when at least one of these is true:

- The plan is long-running and would outlast a local terminal session.
- The work spans multiple repos that all need to be mounted side-by-side (`extra_repos:`).
- The user wants an isolated persistent sandbox separate from their laptop.
- A chain needs to keep running while the laptop is asleep or on the move.

Skip cloud mode when the plan finishes in a sitting, the work fits in one repo, and a local `megaplan run` would do the same job.

## SSH provider — Hetzner agentbox (the working on-prem path)

`provider: ssh` targets a remote box (host/user/port/identity_file in `cloud.yaml` under `ssh:`) that runs the megaplan worker in a docker container. The working on-prem setup is a Hetzner VM with a long-lived `megaplan-cloud-agent` container + a persistent `/workspace` volume; an `arnold-watchdog` (tmux session `watchdog`) keeps chains alive and a meta-loop supervises it (see `docs/hetzner-watchdog-meta-loop.md`).

A minimal ssh `cloud.yaml`:

```yaml
provider: ssh
repo:
  url: https://github.com/org/repo.git
  branch: <base-branch>
  workspace: /workspace/<unique-per-chain>     # unique — the box runs concurrent chains
mode: chain
chain_session: <unique-per-chain>              # unique tmux session on the box
chain:
  spec: /workspace/<unique-per-chain>/<path-to-chain.yaml>
megaplan:
  ref: main
  codex_auth: chatgpt                          # any codex phases bill to ChatGPT subscription
ssh:
  host: <box-ip>
  user: root
  port: 22
  remote_dir: /opt/megaplan-cloud/deploy
  workspace_dir: /opt/megaplan-cloud/workspace
  container: megaplan-cloud-agent
secrets: []   # leave empty if pre-set on the box; listing would overwrite box values with local env
```

### Recommended launch: canonical initiative + `cloud chain`

Create one self-contained initiative first, then preflight and launch that same
initiative:

```bash
python -m arnold_pipelines.megaplan initiative new <initiative> \
  --milestone m1="First Sprint" \
  --doc research=path/to/strategy-or-audit.md \
  --cloud

python -m arnold_pipelines.megaplan cloud preflight \
  .megaplan/initiatives/<initiative>/chain.yaml \
  --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml

python -m arnold_pipelines.megaplan cloud chain \
  .megaplan/initiatives/<initiative>/chain.yaml \
  --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml \
  --fresh
```

Durable chain specs must live at `.megaplan/initiatives/<initiative>/chain.yaml`.
Milestone briefs, North Star anchors, research notes, and supporting docs belong under
`.megaplan/initiatives/`; tickets and ideas stay under `.megaplan/tickets/` or `.megaplan/ideas/`. Runtime state
stays under `.megaplan/plans/` and `.megaplan/epics/`.

`initiative new --cloud` creates a cloud-shaped template, but generated
placeholders are treated as unsafe defaults. `cloud preflight` and `cloud chain`
fail if fields such as `TODO_REPO_URL`, `TODO_SSH_HOST`, or
`TODO_INITIATIVE_DESCRIPTION` remain. Passing
`--allow-template-placeholders` is the required explicit override for deliberate
dry runs against an unedited template.

Cloud chains are also treated as unattended by default. `cloud preflight` and
`cloud chain` fail when `chain.yaml` contains human-gated policy
(`merge_policy: review`/`manual` or `driver.auto_approve: false`) unless the
operator passes `--allow-human-gates`. Use that override only when the chain is
supposed to pause for human PR merges, prep clarifications, or verification
records. For normal cloud epics, keep `merge_policy: auto` and
`driver.auto_approve: true`.

Use `--doc kind=path` during initiative creation to seed starting documents for
specific parts of the run. Supported kinds are `research`, `decisions`, `notes`,
`assets`, and `handoff`. The files are copied under the initiative and uploaded
with the durable inputs; cite them from milestone briefs instead of relying on
local `.codex/`, Downloads, or scratch files that the cloud runner cannot see.

`cloud chain` is the normal launcher. It validates the North Star, `chain.yaml`,
and every milestone brief before it uploads anything. It syncs the launching
Arnold checkout to `editible-install`, starts tmux, writes the watchdog marker,
and verifies that the marker's `remote_spec` resolves on the box. If that
verification fails, the command fails instead of leaving an orphaned chain.
`cloud launch-epic` remains a compatibility/materialization helper for older
brief directories; prefer `initiative new` plus `cloud chain` for new work.

When already inside the target agentbox/container, add `--on-box` to that
canonical `cloud chain` command. It bypasses SSH transport only: canonical
validation, workspace/session setup, tmux launch, watchdog registration, and
launch verification still run. Do not substitute a raw `chain start` command.

Canonical chain layout on the box:

```text
/workspace/<initiative>-<identity-digest>/<repo-name>/.megaplan/initiatives/<initiative>/chain.yaml
/workspace/<initiative>-<identity-digest>/<repo-name>/.megaplan/initiatives/<initiative>/NORTHSTAR.md
/workspace/<initiative>-<identity-digest>/<repo-name>/.megaplan/initiatives/<initiative>/briefs/<milestone>.md
```

The watchdog marker must point `remote_spec` to that real `chain.yaml`, never to
`<workspace>/chain.yaml` or another guessed path.

Observe first with `megaplan cloud status --all --cloud-yaml cloud.<chain>.yaml`.
It lists all known shared-runner sessions with human names, `should_run=yes/no`,
tmux/process liveness, current plan state, chain policy, watchdog status, and an
operator-facing `operator=... reason=... next=...` classification. Trust this
over raw `tmux ls`: a supervised chain can have no live tmux session while it is
blocked on user action, and a live repair/relaunch can briefly obscure a human
gate. `operator=blocked_prep_clarification` means the watchdog will not resume
until clarification is answered or the run is relaunched as unattended. Use
`tmux ls` and per-chain logs under
`<workspace>/.megaplan/cloud-chain-<session>.log` only as follow-up evidence;
milestone state lives under `.megaplan/plans/<plan>/state.json` + `events.ndjson`.
For "what changed recently?" use
`megaplan cloud status --all --compact --since 12h --cloud-yaml <active-cloud.yaml>`.
`--since` filters on real plan `state.json` activity when available, not
watchdog health mtimes, because watchdog reports can be rewritten after a chain
has already completed.

For lower-level launches or when preparing a shared cloud checkout manually,
seed durable planning state before `cloud chain`:

```bash
megaplan cloud sync-megaplan .megaplan/initiatives/<initiative>/chain.yaml --clean
megaplan cloud chain .megaplan/initiatives/<initiative>/chain.yaml
```

`sync-megaplan` uploads `.megaplan/initiatives/`, `.megaplan/tickets/`, and
`.megaplan/ideas/` as one archive to the target workspace. It deliberately does
not upload generated plans, epics, locks, logs, telemetry, or verification
state.

### Gotchas specific to the ssh/Hetzner path (learned the hard way)

1. **Chain spec requires a `north_star` anchor** — `cloud preflight` / `cloud chain` reject the setup without `anchors: north_star: NORTHSTAR.md` and a real `NORTHSTAR.md` next to the canonical `chain.yaml`.
2. **Anchor paths are chain.yaml-dir-relative.** Put `NORTHSTAR.md` next to `.megaplan/initiatives/<initiative>/chain.yaml` and set `anchors.north_star: NORTHSTAR.md`.
3. **Durable `.megaplan` inputs must be synced or committed.** The cloud runner ignores generated state, but it needs the durable source artifacts. Use `megaplan cloud sync-megaplan <chain.yaml> --clean` to upload `.megaplan/initiatives/`, `.megaplan/tickets/`, and `.megaplan/ideas/` to the exact derived workspace before launch.
4. **The base-branch refresh fetches but does NOT fast-forward the box clone's local branch.** If the clone's `<base-branch>` is already checked out, `git checkout <base-branch>` is a no-op and the clone stays at the old commit. Force it: `git fetch origin <base-branch> && git reset --hard origin/<base-branch>` before launching (or after any push to the base branch).
5. **Do not bypass `cloud chain` for normal initiatives.** Direct tmux/`chain start` launches can drift out of the canonical marker contract and fall outside watchdog supervision. `launch-epic` is only for older brief directories that still need materialization.
6. **Missing specs/workspaces are watchdog issues.** A marker whose `workspace` or `remote_spec` does not resolve is reported as `workspace_missing` or `spec_missing`, not hidden as a benign skip.
7. **The editable arnold `.pth` can get disabled mid-run** (renamed `*.pth.disabled`) by a cloud-chain editable-install-sync side-effect, breaking `import arnold`/`import arnold_pipelines` locally + any local tooling that uses it. Re-enable: `mv <site-packages>/_editable_impl_arnold.pth.disabled <site-packages>/_editable_impl_arnold.pth`. (Also: keep the local venv on an editable install of `~/Documents/Arnold` — a stale non-editable copy shadows the live code and lags the path migration.)
8. **arnold path migration: `arnold.pipelines.megaplan` → `arnold_pipelines.megaplan`.** Live arnold moved megaplan to the top-level `arnold_pipelines` package and dropped `arnold.pipelines.megaplan`. Older tooling (e.g. the hermes subagent launcher, watchdog scripts) may still use the old dotted path and depend on a stale site-packages copy as a bridge. When you editable-install live arnold, update those tools to `arnold_pipelines.megaplan` too, or they break.
9. **Use a unique `workspace` + `chain_session` per chain.** The box runs multiple chains concurrently; sharing a workspace or tmux session name collides.

## Subcommands

`init`, `build`, `deploy`, `preflight`, `chain`, `sync-megaplan`, `launch-epic`, `epic-chain`, `status`, `attach`, `logs`, `exec`, `resume`, `down`, `destroy`.

Typical flow:

1. `megaplan cloud init` scaffolds a `cloud.yaml` at the project root.
2. Edit it (set the provider, primary `repo:`, any `extra_repos:`, the secret names, etc.).
3. Export the secret values into your local env (the names listed under `secrets:` in `cloud.yaml`).
4. `megaplan cloud deploy` to build the image and start the runner.
5. `python -m arnold_pipelines.megaplan initiative new <initiative> --milestone m1="First Sprint" --cloud` to create the canonical initiative. Add `--doc research=...`, `--doc decisions=...`, etc. for starting docs that should travel with the cloud run.
6. Edit `.megaplan/initiatives/<initiative>/README.md`, `NORTHSTAR.md`, `briefs/*.md`, `chain.yaml`, and `cloud.yaml`. Do not leave `TODO_*` placeholders unless this is an intentional dry run.
7. `megaplan cloud preflight .megaplan/initiatives/<initiative>/chain.yaml --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml` to check the canonical spec, North Star, placeholder status, resolved profile routing, local secrets, worker import path, and remote command availability.
8. `megaplan cloud chain .megaplan/initiatives/<initiative>/chain.yaml --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml --fresh` for the normal multi-milestone launch. Use `launch-epic` only for older brief directories that still need materialization.
7. Use `status`, `logs`, `attach` to observe; `down` to pause, `destroy` to tear the volume.

See `docs/cloud.md` for the full reference, including `cloud.yaml` fields, mode behavior (`auto`/`chain`/`idle`), and provider-specific troubleshooting.

## Claude auth: subscription via refresh token (no metered API, no human)

When Claude phases run on the cloud worker, you want them billed against your Claude **subscription** (Max/Pro), not metered API. The entrypoint supports two auth modes with clear precedence:

1. **`CLAUDE_CODE_REFRESH_TOKEN`** *(preferred — programmatic, no expiry)*. Set this once on the cloud worker. On every boot, the entrypoint installs:
   - `/usr/local/bin/claude.real` — copy of the actual claude binary.
   - `/usr/local/bin/claude-key-helper` — refreshes the OAuth access token against `https://api.anthropic.com/v1/oauth/token` using the refresh token, caches the result on the volume (`/workspace/.claude-creds/`), and rotates the refresh token per use.
   - `/usr/local/bin/claude` — shim that calls the helper, exports `ANTHROPIC_API_KEY`, and `exec`s the real binary.

   First-time setup runs on your laptop where you're already logged in to claude:

   ```bash
   bash scripts/refresh-cloud-claude-key.sh
   ```

   That extracts the refresh token from your macOS Keychain (service `"Claude Code-credentials"`), validates it against the OAuth endpoint, and writes the rotated value to the worker as `CLAUDE_CODE_REFRESH_TOKEN`. No browser, no recurring human action. Re-run only if you `claude /logout` everywhere or the refresh token gets revoked.

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

A minimal multi-repo Hetzner `cloud.yaml`:

```yaml
provider: ssh

repo:
  url: https://github.com/org/app.git
  branch: main
  workspace: /workspace/my-chain/app

extra_repos:
  - url: https://github.com/org/worker.git
    branch: main
    workspace: /workspace/my-chain/worker
  - url: https://github.com/org/agent.git
    branch: main
    workspace: /workspace/my-chain/agent

chain_session: my-chain    # per-chain tmux session

mode: idle                 # box stays up; chain launches its own session

megaplan:
  ref: main                # or a SHA on a feature branch

resources:
  volume: my-volume
  port: 8080

ssh:
  host: <box-ip>
  user: root
  port: 22
  remote_dir: /opt/megaplan-cloud/deploy
  workspace_dir: /opt/megaplan-cloud/workspace
  container: megaplan-cloud-agent

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
- auto-merge and advance a milestone PR when the chain declares `merge_policy: auto`, or advance a chain past a PR that was already merged by a human;
- commit and push after each completed milestone when the user asked for push-after-sprint behavior.

For an operator loop to progress a chain autonomously, the chain spec must set
`merge_policy: auto` and `driver.auto_approve: true`. This should be the default
for cloud epics unless the user explicitly wants human review on every milestone
PR or prep/verification halt. With `review`/`manual`, the chain opens each
milestone PR and halts at `awaiting_pr_merge` until a human merges it. With
`driver.auto_approve: false`, prep clarification and human-verification gates
halt at `awaiting_human_verify`; watchdog/repair reports
`blocked_prep_clarification` or `blocked_human_verification` and does not
silently answer those questions.

An operator loop should **not** silently decide product or architecture questions, resolve merge conflicts, accept destructive cleanup, or ignore failing tests. Those are implementation decisions, not supervision. Surface them to the user or write a clear ticket unless the plan already contains an explicit settled decision that covers the case.

### Built-in cloud supervision (automated operator loop)

Two always-on supervisors run the recovery loop; the operator watches *them*, not the chain.

**1h watchdog** (`/usr/local/bin/arnold-watchdog`, `megaplan-watchdog-ensure.timer` keep-alive): syncs the editable install; per session treats any unintended nonterminal condition — stopped/flap/`retrying_failure`, missing workspace/spec, chain-health failures, and `progress_stall` — as repairable and **background-dispatches Kimi→Codex repair**, falling back to **direct relaunch** only when repair is unavailable or already failed. It auto-merges `awaiting_pr_merge` milestone PRs only when the chain declares `merge_policy: auto`; expected manual/review PR waits remain passive. Report: `/workspace/watchdog-report.json` (archived `/workspace/watchdog-reports/`). Repair dispatch requires `ARNOLD_REPAIR_TRIGGER_ENABLED=1`.

**6h progress auditor** (`/usr/local/bin/arnold-progress-auditor`, `megaplan-progress-audit.timer`): reviews the last 6h per plan and the watchdog report. If a session has been in an unintended stop/stall for >1h with no active or recent repair attempt, that is a **superfixer failure**: dispatch **Codex** (may deploy DeepSeek) to fix the watchdog/repair trigger/auditor on `editible-install`, push, refresh, and let the watchdog relaunch. Otherwise, genuine plan deadlock/inefficiency → **fix + push to `editible-install`**; expected manual/product decisions → document. Verdicts `FIXED <sha>` / `PASSIVE`. Report: `/workspace/audit-reports/`.

Recovery path: watchdog fixes hard stops; auditor fixes inefficiency/deadlocks the liveness check can't see. Operator job = **meta-loop** (hourly): watchdog alive + reporting, plan progressing, `blocked_recovery_not_resolved` not climbing, auditor verdicts landing. See `docs/hetzner-watchdog-meta-loop.md`.

## Gotchas (learned the hard way)

1. **`chain_state.json` committed in the project repo poisons fresh chains.** The chain runner derives state from `<chain.yaml dir>/chain_state.json`. If a prior chain committed that file, every `git clone` on the worker re-seeds stale state (`completed: [...prior milestones]`, `current_milestone_index: N`); the new chain skips early milestones and crashes at a later `git checkout main` against leftover working-tree dirt. Fix: `rm` it on the worker after clone. Durable fix: `git rm chain_state.json` + add to `.gitignore` on the branch. Don't trust `git checkout -- .` as cleanup — it restores tracked files including this one.

2. **Profile-name gap between the decision skill and the loaded registry.** The decision skill documents `basic`/`led`/`thoughtful`/`premium`/`super-premium`. The registry only loads `solo`/`directed`/`partnered`/`premium`/`apex`, with `basic`→`solo` and `led`→`directed` as legacy aliases — `thoughtful` and `super-premium` are **not** aliased. Chain specs need canonical names or chain start fails preflight with "Unknown profile".

3. **Run `cloud preflight` before launch when changing profiles.** It resolves milestone-level `profile`, `phase_model`, `vendor`, `depth`, `critic`, and provider settings the same way launch does, then reports whether the worker needs Codex-only setup or mixed Claude/Codex support.

4. **`megaplan` CLI may use a separate Python venv** from `pip install --user`. After upgrading megaplan from a branch SHA, run `head -1 $(which megaplan)` to find which interpreter and `python -m pip install` into that one specifically — otherwise local `cloud chain` runs against the old code while the remote pulls the new SHA.

5. **`secrets:` in `cloud.yaml` drives an upload from local env at deploy time.** If values are already set on the Hetzner box/container, leave `secrets: []` in the `cloud.yaml` — otherwise `megaplan cloud deploy` reads the names from your local env and may fail or overwrite the worker values with empty strings. List the names in a comment for reference.

6. **Credit-balance failures look like `internal_error`.** When a phase exits as "internal_error" with no useful stderr, read `plan_v<n>_raw.txt` in the plan directory. Anthropic/OpenAI quota errors arrive there as `"text":"Credit balance is too low"` from the agent CLI wrapper. For Claude, the real fix is the refresh-token shim (see "Claude auth" above) — it bills against your subscription, never depletes. For OpenAI, top up the console balance or switch to a profile with credit headroom — **but for a `codex` phase it's usually the API-key fallback, not a real balance issue; see gotcha #9.**

7. **`secrets` can be overwritten by deploy-time sync.** `megaplan cloud deploy` pushes every declared secret found in the local environment. Pre-existing worker values are overwritten when the local env has the same key set. To preserve worker-side values, either unset them locally before deploy or empty the `secrets:` list.

8. **Volume size and disk pressure.** A multi-repo chain with `node_modules` and `.venv` directories across sibling repos can fill the worker volume quickly; `git clean -fdx` and `npm cache clean --force` on the worker free space, but ultimately expand the Hetzner volume if disk-pressure errors become routine.

9. **Codex `Quota exceeded. Check your plan and billing details.` is the API-key fallback, not a real cap.** megaplan runs codex via `codex exec`, which silently uses **API-key mode** when `OPENAI_API_KEY` is present — so plan/critique/etc. hit `api.openai.com` with that (often dead) key and quota-fail, even though you have a working ChatGPT subscription. This is the codex-specific case of gotcha #6, and "top up the console balance" is the *wrong* fix. Right fix: `megaplan.codex_auth: chatgpt` (the default) forces `preferred_auth_method=chatgpt` so codex uses the subscription OAuth (`chatgpt.com/backend-api/codex`) regardless of `OPENAI_API_KEY`. If you see this error, confirm `/root/.codex/config.toml` has `preferred_auth_method = "chatgpt"` and `~/.codex/auth.json` has `auth_mode: chatgpt`, and that the OAuth seed landed (`/workspace/.creds/codex-auth.json`). See "Codex auth" above.

10. **Stalled `chain_state` makes a relaunch resume a dead plan (session alive, milestone stuck at "none").** An aborted run leaves `.megaplan/plans/.chains/<spec>-<digest>.json` with `last_state: "stalled"`; the next `cloud chain` resumes it and never starts the milestone. `cloud chain` now auto-clears a stalled-with-no-progress state on fresh launch; if you hit it on an older worker, `rm -rf .megaplan/plans/.chains/* .megaplan/plans/<milestone>-*` (only the stalled ones) and relaunch.

## Quick Reference: Hetzner Agentbox Workflow

For users running multiple chains across many repos on the shared Hetzner agentbox:

1. **One-time setup**:
   - Ensure the remote box has the long-lived `megaplan-cloud-agent` container.
   - Ensure the persistent workspace volume is mounted at `/workspace`.
   - Set worker secrets once (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `FIREWORKS_API_KEY`, `GITHUB_TOKEN`, `MEGAPLAN_TRUSTED_CONTAINER=1`).

2. **Per chain**:
   - Write `cloud.<chain>.yaml` with `provider: ssh`, `repo:` + any `extra_repos:` + `chain_session: <chain-name>` + `mode: idle`.
   - `megaplan cloud deploy --cloud-yaml cloud.<chain>.yaml` only when adding new repos or bumping `megaplan.ref` (the entrypoint is baked in at build time).
   - `megaplan cloud preflight --cloud-yaml .megaplan/initiatives/<chain>/cloud.yaml .megaplan/initiatives/<chain>/chain.yaml`
   - `megaplan cloud chain --cloud-yaml .megaplan/initiatives/<chain>/cloud.yaml .megaplan/initiatives/<chain>/chain.yaml --fresh` to validate, upload, launch, and watchdog-verify.

3. **Observing**:
   - `megaplan cloud status --all --cloud-yaml cloud.<chain>.yaml` first.
   - `megaplan cloud status --all --compact --since 12h --cloud-yaml cloud.<chain>.yaml` for a compact recent-activity handoff.
   - `megaplan cloud status --chain` for one chain's detailed summary.
   - `megaplan cloud logs --no-follow` for build / boot logs.
   - SSH-tail the per-chain log: `ssh root@<box-ip> 'docker exec megaplan-cloud-agent tail -f /workspace/<repo>/.megaplan/cloud-chain-<chain-session>.log'`.
   - `tmux ls` only shows live runner processes.
