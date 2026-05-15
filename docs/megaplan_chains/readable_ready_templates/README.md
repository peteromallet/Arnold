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

Required local environment before deploy/start:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...
export ANTHROPIC_API_KEY=...
export DEEPSEEK_API_KEY=...
```

The chain spec sets `vendor: codex` for premium phases and
`deepseek_provider: direct` for DeepSeek phases. Do not switch DeepSeek traffic
to Fireworks for this chain.

Start from the repository root:

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud build --cloud-yaml cloud.yaml
PYENV_VERSION=3.11.11 python -m megaplan cloud deploy --cloud-yaml cloud.yaml
PYENV_VERSION=3.11.11 python -m megaplan cloud chain docs/megaplan_chains/readable_ready_templates/chain.yaml \
  --idea-dir docs/megaplan_chains/readable_ready_templates \
  --cloud-yaml cloud.yaml
```

Start the operator loop in a second tmux session after `cloud chain` launches:

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud exec --cloud-yaml cloud.yaml \
  "cd /workspace/app && tmux new-session -d -s megaplan-operator './scripts/megaplan_cloud_operator_loop.sh /workspace/app/docs/megaplan_chains/readable_ready_templates/chain.yaml megaplan/production-parity-templates'"
```

Observe:

```bash
PYENV_VERSION=3.11.11 python -m megaplan cloud status --cloud-yaml cloud.yaml --chain
PYENV_VERSION=3.11.11 python -m megaplan cloud logs --cloud-yaml cloud.yaml
PYENV_VERSION=3.11.11 python -m megaplan cloud attach --cloud-yaml cloud.yaml
```

## Local Dry Checks

This does not execute the chain:

```bash
PYENV_VERSION=3.11.11 python -m megaplan chain status --spec docs/megaplan_chains/readable_ready_templates/chain.yaml
```

The `cloud chain` command starts remote execution, so use it only when ready.
