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

## Gotchas (learned the hard way)

1. **`chain_state.json` committed in the project repo poisons fresh chains.** The chain runner derives state from `<chain.yaml dir>/chain_state.json`. If a prior chain committed that file, every `git clone` on the worker re-seeds stale state (`completed: [...prior milestones]`, `current_milestone_index: N`); the new chain skips early milestones and crashes at a later `git checkout main` against leftover working-tree dirt. Fix: `rm` it on the worker after clone. Durable fix: `git rm chain_state.json` + add to `.gitignore` on the branch. Don't trust `git checkout -- .` as cleanup — it restores tracked files including this one.

2. **Profile-name gap between the decision skill and the loaded registry.** The decision skill documents `basic`/`led`/`thoughtful`/`premium`/`super-premium`. The registry only loads `solo`/`directed`/`partnered`/`premium`/`apex`, with `basic`→`solo` and `led`→`directed` as legacy aliases — `thoughtful` and `super-premium` are **not** aliased. Chain specs need canonical names or chain start fails preflight with "Unknown profile".

3. **The `cloud preflight` resolver ignores milestone-level `vendor`/`depth`/`critic`.** `megaplan/cloud/preflight.py:_expanded_phase_models` hardcodes `vendor=None`, `depth=None`, `critic=None`. The local preflight will misreport phase routing for chains that override vendor per milestone — but the **runtime** phase invoker in `chain.py:_init_plan` DOES forward those fields, so the actual run uses the correct routing. Treat preflight's `resolved_phase_map` as advisory until that gap closes.

4. **`megaplan` CLI may use a separate Python venv** from `pip install --user`. After upgrading megaplan from a branch SHA, run `head -1 $(which megaplan)` to find which interpreter and `python -m pip install` into that one specifically — otherwise local `cloud chain` runs against the old code while the remote pulls the new SHA.

5. **`secrets:` in `cloud.yaml` drives an upload from local env at deploy time.** If you pre-set values directly on the Railway service (e.g. copied from another service), leave `secrets: []` in the `cloud.yaml` — otherwise `megaplan cloud deploy` reads the names from your local env, finds them missing, and either fails the deploy or overwrites the Railway values with empty strings. List the names in a comment for reference.

6. **Credit-balance failures look like `internal_error`.** When a phase exits as "internal_error" with no useful stderr, read `plan_v<n>_raw.txt` in the plan directory. Anthropic/OpenAI quota errors arrive there as `"text":"Credit balance is too low"` from the agent CLI wrapper. For Claude, the real fix is the refresh-token shim (see "Claude auth" above) — it bills against your subscription, never depletes. For OpenAI, top up the console balance or switch to a profile with credit headroom.

7. **`secrets` get baked into the image-build context, not just runtime env.** `megaplan cloud deploy` runs `railway variables --set NAME=VALUE` for every secret in the local environment that matches a declared name, then `railway up`. Pre-existing values on the service are overwritten when the local env has the same key set. To preserve service-side values, either unset them locally before deploy or empty the `secrets:` list.

8. **Volume size and disk pressure.** The default Railway volume is 5 GB. A multi-repo chain with `node_modules` and `.venv` directories across sibling repos can fill it quickly; `git clean -fdx` and `npm cache clean --force` on the worker free space, but ultimately bump the volume in the Railway UI if you're routinely seeing disk-pressure errors.

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
