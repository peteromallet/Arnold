# Cloud Chain Smoke

Evidence id: `OPS-CLOUD-CHAIN-3-SPRINT-SMOKE`

This is the credentialed live procedure for release signoff when provider access is available. Local tests cover wrapper dispatch and image build behavior without requiring cloud credentials.

## Scope

- Build or deploy a fresh cloud worker image from the current checkout.
- Run one chain with exactly three sprint milestones through `megaplan cloud chain`.
- Confirm the remote command includes `MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec ...`.

## Three-Sprint Fixture

Create `cloud-chain-smoke.yaml`:

```yaml
base_branch: main
milestones:
  - label: sprint-1
    idea: /workspace/app/ideas/sprint-1.md
  - label: sprint-2
    idea: /workspace/app/ideas/sprint-2.md
  - label: sprint-3
    idea: /workspace/app/ideas/sprint-3.md
```

Create matching local files under the `--idea-dir` used for upload:

```bash
mkdir -p smoke-ideas/ideas
printf 'Sprint 1 smoke\n' > smoke-ideas/ideas/sprint-1.md
printf 'Sprint 2 smoke\n' > smoke-ideas/ideas/sprint-2.md
printf 'Sprint 3 smoke\n' > smoke-ideas/ideas/sprint-3.md
```

## Live Procedure

1. Confirm credentials and provider access are present.
2. Build and deploy the worker:

```bash
megaplan cloud build --cloud-yaml cloud.yaml
megaplan cloud deploy --cloud-yaml cloud.yaml
```

3. Start the three-sprint chain:

```bash
megaplan cloud chain cloud-chain-smoke.yaml --idea-dir smoke-ideas --cloud-yaml cloud.yaml
```

4. Follow logs and status:

```bash
megaplan cloud logs --cloud-yaml cloud.yaml --follow
megaplan cloud status --cloud-yaml cloud.yaml --chain
```

5. Run the supervisor tick after the chain has settled (or stalled):

```bash
megaplan cloud supervise --chain --cloud-yaml cloud.yaml
```

The supervisor emits a JSON report on stdout and a human-readable summary on stderr. If the chain is running it reports `noop`; if stalled with a dead runner it may restart the tmux session; if blocked on prerequisites, quality gates, or unmerged PRs it refuses to act and explains why.

**Important**: The supervisor is **not** a destructive repair tool. It does not replace human approval, PR review, or quality-gate resolution. See `docs/cloud.md` for the full refusal-case table.

Record the supervisor report as evidence (save stderr and stdout).

## Evidence Template

Record the following:

- Evidence id: `OPS-CLOUD-CHAIN-3-SPRINT-SMOKE`
- Date/time:
- Provider and region:
- Worker image digest or deployment id:
- `cloud.yaml` path and commit SHA:
- Chain spec path:
- Remote command line showing `MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec`:
- Uploaded milestone files:
- Final status:
- Log excerpt proving all three sprint milestones completed or the failure reason:
- Supervisor tick report (JSON stdout + stderr summary) from step 5:

## Local Validation

Run:

```bash
pytest tests/test_cloud_chain_wrapper.py tests/test_cloud_docker_build.py
```

The wrapper test asserts the trusted container dispatch command. Docker build coverage is skipped automatically when Docker is unavailable.
