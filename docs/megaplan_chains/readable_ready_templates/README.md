# Readable Ready Templates Megaplan Chain

This chain executes the roadmap in `docs/readable_ready_template_cleanup_plan.md`
as a cloud-capable sequence of sprint-sized megaplan runs.

## Single Branch Policy

All work runs on one branch:

```text
megaplan/production-parity-templates
```

Do not add `branch:` fields to the milestones. The current megaplan chain PR
mode is milestone-branch oriented; omitting milestone branches keeps the cloud
workspace on the single branch configured in `cloud.yaml` and in `chain.yaml`.
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

`cloud.yaml` at the repository root is configured for the shared branch and a
Railway runner.

Before cloud deploy/status works, link this checkout to the intended Railway
project or fill in `railway.project` / `railway.environment` in `cloud.yaml`:

```bash
railway link
```

Required cloud secrets before deploy/start:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...
export ANTHROPIC_API_KEY=...
export DEEPSEEK_API_KEY=...
```

The chain spec currently uses `profile: all-claude` for every milestone. Keep
that profile consistent across new milestones unless the operator explicitly
changes the chain routing again.

Codex premium phases should use the same Codex allocation as the operator's
normal Codex CLI login. If the cloud runner only has API-key auth, `gpt-5.5`
can fail with `insufficient_quota` even when the Codex CLI account has
available allocation. Before launch, verify the cloud runner has a usable
`/root/.codex/auth.json` and that it reports `auth_mode=chatgpt` when the
intended allocation is the Codex/ChatGPT account rather than a raw OpenAI API
key. Do not print token contents in logs.

Build and deploy from the repository root:

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud build --cloud-yaml cloud.yaml
PYENV_VERSION=3.11.11 python -m megaplan cloud deploy --cloud-yaml cloud.yaml
```

Launch the chain on the cloud runner from an SSH session. Use `--no-push`
because the operator loop owns same-branch commits/pushes:

```bash
railway ssh --environment production --service agent -- \
  'cd /workspace/app && tmux new-session -d -s megaplan-chain \
  "MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec /workspace/app/docs/megaplan_chains/readable_ready_templates/chain.yaml --no-push >> /workspace/app/.megaplan/cloud-chain.log 2>&1"'
```

The higher-level `cloud chain` wrapper is convenient, but confirm its resolved
phase map before using it for this chain. At the time this chain was created,
the wrapper could still resolve DeepSeek through Fireworks even when the
milestone spec requested `deepseek_provider: direct`.

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud chain docs/megaplan_chains/readable_ready_templates/chain.yaml \
  --idea-dir docs/megaplan_chains/readable_ready_templates \
  --cloud-yaml cloud.yaml
```

Start the lightweight operator loop in a second tmux session after the chain
launches. This loop handles process restarts and push-after-completed-sprint:

```bash
railway ssh --environment production --service agent -- \
  "cd /workspace/app && tmux new-session -d -s megaplan-operator './scripts/megaplan_cloud_operator_loop.sh /workspace/app/docs/megaplan_chains/readable_ready_templates/chain.yaml megaplan/production-parity-templates'"
```

For unattended end-to-end execution, also start the recovery loop. It wakes
hourly, detects terminal `blocked` / `worker_blocked` milestones, backs up any
dirty diff, runs a Codex repair pass against the current milestone artifacts,
commits/pushes a recovery commit to the same branch, advances the chain state
when the branch moves, and restarts the chain:

```bash
railway ssh --environment production --service agent -- \
  "cd /workspace/app && tmux new-session -d -s megaplan-recovery './scripts/megaplan_cloud_recovery_loop.sh /workspace/app/docs/megaplan_chains/readable_ready_templates/chain.yaml megaplan/production-parity-templates'"
```

Optional tuning:

```bash
RECOVERY_INTERVAL_SECONDS=3600
RECOVERY_CODEX_MODEL=gpt-5.5
RECOVERY_MAX_REPAIR_SECONDS=3300
```

Observe:

```bash
railway ssh --environment production --service agent -- \
  'cd /workspace/app && tmux ls && megaplan chain status --spec /workspace/app/docs/megaplan_chains/readable_ready_templates/chain.yaml'

railway ssh --environment production --service agent -- \
  'cd /workspace/app && tail -n 120 .megaplan/cloud-chain.log && tail -n 80 .megaplan/cloud-operator-loop.log'

railway ssh --environment production --service agent -- \
  'cd /workspace/app && tail -n 120 .megaplan/cloud-recovery-loop.log && tail -n 120 .megaplan/recovery-prompts/recovery-agent.log'
```

For an active milestone, the freshest progress is usually in the plan state
file rather than the chain log:

```bash
railway ssh --environment production --service agent -- \
  'cd /workspace/app && python - <<'"'"'PY'"'"'
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
