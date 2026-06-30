# Readable Ready Templates Megaplan Chain

This chain executes the roadmap in `docs/templates/readable_ready_template_cleanup_plan.md`
as a cloud-capable sequence of sprint-sized megaplan runs.

## Single Branch Policy

All work runs on one branch:

```text
main
```

Do not add `branch:` fields to the milestones. The current megaplan chain PR
mode is milestone-branch oriented; omitting milestone branches keeps the cloud
workspace on the single branch configured in this directory's `cloud.yaml` and
in `chain.yaml`.
The final `publish-shared-branch` milestone is responsible for committing and
pushing the accumulated changes to that one branch.

For push-after-sprint behavior, run the chain alongside
`scripts/megaplan_cloud_operator_loop.sh` in a second cloud tmux session. The
operator watches chain progress and commits/pushes the shared branch after each
completed milestone. It must not resolve product questions, merge conflicts, or
failing tests.

## Files

- `chain.yaml` - ordered chain spec for cloud or local execution.
- `ideas/*.md` - one idea file per sprint plus the final publish milestone.
- `../../readable_ready_template_cleanup_plan.md` - the authoritative roadmap.

## Cloud Setup

`cloud.yaml` in this directory is configured for the shared branch and a
Hetzner ssh runner.

Before cloud deploy/status works, confirm `ssh.host` and `ssh.container` in this directory's `cloud.yaml` point at the intended Hetzner agentbox:

```bash
python -m megaplan cloud status --cloud-yaml docs/megaplan_chains/readable_ready_templates/cloud.yaml
```

Required cloud secrets before deploy/start:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...
export ANTHROPIC_API_KEY=...
export DEEPSEEK_API_KEY=...
```

The chain spec currently uses `profile: all-codex` and `vendor: codex` for every
milestone. The explicit vendor is required because Megaplan's default vendor is
Claude and can otherwise rewrite premium Codex slots back to Claude during
profile expansion. This is an operator override from the earlier `all-claude`
routing: Claude Code v2.1.143 opens successfully in the Hetzner ssh root container,
but the Shannon tmux bridge does not reliably submit the initial prompt into
Claude's transcript. Keep the profile and vendor consistent across new
milestones unless the operator explicitly changes the chain routing again after
validating the runner.

The Hetzner ssh container runs as root, so Claude Code rejects
`--dangerously-skip-permissions`. The operator and recovery loops run
`scripts/patch_shannon_unattended_root.sh` before launching the chain; this
keeps Shannon's long-turn fixes, strips root-rejected dangerous flags, maps
Megaplan's `bypassPermissions` request to Claude's root-safe `dontAsk`
permission mode, and makes the Megaplan Shannon parser tolerate a short prose
prefix before the required JSON payload.

Codex premium phases should use the same Codex allocation as the operator's
normal Codex CLI login. If the cloud runner only has API-key auth, `gpt-5.5`
can fail with `insufficient_quota` even when the Codex CLI account has
available allocation. Before launch, verify the cloud runner has a usable
`/root/.codex/auth.json` and that it reports `auth_mode=chatgpt` when the
intended allocation is the Codex/ChatGPT account rather than a raw OpenAI API
key. Do not print token contents in logs.

Build and deploy from the repository root:

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud build --cloud-yaml docs/megaplan_chains/readable_ready_templates/cloud.yaml
PYENV_VERSION=3.11.11 python -m megaplan cloud deploy --cloud-yaml docs/megaplan_chains/readable_ready_templates/cloud.yaml
```

Launch the chain on the cloud runner from an SSH session. Use `--no-push`
because the operator loop owns same-branch commits/pushes:

```bash
ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/vibecomfy-readable-ready-templates && tmux new-session -d -s megaplan-chain \
  "MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec /workspace/vibecomfy-readable-ready-templates/docs/megaplan_chains/readable_ready_templates/chain.yaml --no-push >> /workspace/vibecomfy-readable-ready-templates/.megaplan/cloud-chain.log 2>&1"'
```

The higher-level `cloud chain` wrapper is convenient, but confirm its resolved
phase map before using it for this chain. At the time this chain was created,
the wrapper could still resolve DeepSeek through Fireworks even when the
milestone spec requested `deepseek_provider: direct`.

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud chain docs/megaplan_chains/readable_ready_templates/chain.yaml \
  --idea-dir docs/megaplan_chains/readable_ready_templates \
  --cloud-yaml docs/megaplan_chains/readable_ready_templates/cloud.yaml
```

Start the lightweight operator loop in a second tmux session after the chain
launches. This loop handles process restarts and push-after-completed-sprint:

```bash
ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  "cd /workspace/vibecomfy-readable-ready-templates && tmux new-session -d -s megaplan-operator './scripts/megaplan_cloud_operator_loop.sh /workspace/vibecomfy-readable-ready-templates/docs/megaplan_chains/readable_ready_templates/chain.yaml main'"
```

For unattended end-to-end execution, also start the recovery loop. It wakes
hourly, detects terminal `blocked` / `worker_blocked` milestones, backs up any
dirty diff, runs a Codex repair pass against the current milestone artifacts,
commits/pushes a recovery commit to the same branch, advances the chain state
when the branch moves, and restarts the chain:

```bash
ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  "cd /workspace/vibecomfy-readable-ready-templates && tmux new-session -d -s megaplan-recovery './scripts/megaplan_cloud_recovery_loop.sh /workspace/vibecomfy-readable-ready-templates/docs/megaplan_chains/readable_ready_templates/chain.yaml main'"
```

Optional tuning:

```bash
RECOVERY_INTERVAL_SECONDS=3600
RECOVERY_CODEX_MODEL=gpt-5.5
RECOVERY_MAX_REPAIR_SECONDS=3300
```

Observe:

```bash
ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/vibecomfy-readable-ready-templates && tmux ls && megaplan chain status --spec /workspace/vibecomfy-readable-ready-templates/docs/megaplan_chains/readable_ready_templates/chain.yaml'

ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/vibecomfy-readable-ready-templates && tail -n 120 .megaplan/cloud-chain.log && tail -n 80 .megaplan/cloud-operator-loop.log'

ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/vibecomfy-readable-ready-templates && tail -n 120 .megaplan/cloud-recovery-loop.log && tail -n 120 .megaplan/recovery-prompts/recovery-agent.log'
```

For an active milestone, the freshest progress is usually in the plan state
file rather than the chain log:

```bash
ssh root@159.69.51.216 -- docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/vibecomfy-readable-ready-templates && python - <<'"'"'PY'"'"'
import json
from pathlib import Path

state = next(Path(".megaplan/plans").glob("*/state.json"))
data = json.loads(state.read_text())
active = data.get("active_step") or {}
print("plan=", data.get("name"))
print("state=", data.get("current_state"))
print("active_step=", active.get("step"))
print("agent=", active.get("agent"))
print("last_activity_at=", active.get("last_activity_at"))
PY'
```

## Local Dry Checks

This does not execute the chain:

```bash
PYENV_VERSION=3.11.11 python -m megaplan chain status --spec docs/megaplan_chains/readable_ready_templates/chain.yaml
```

The `cloud chain` command starts remote execution, so use it only when ready.
