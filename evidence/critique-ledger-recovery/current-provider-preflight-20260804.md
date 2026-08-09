# Current r5 provider/launch evidence — 2026-08-04

## Observed failure

The first same-session cloud resume was launched with the pinned interpreter but
without sourcing `/workspace/.cloud-hot-env`. The pinned runtime therefore saw
no provider environment and failed before dispatch with:

```text
provider_credentials_missing
Hermes provider 'deepseek' cannot run model 'deepseek-v4-pro': no API credential found
Set one of: DEEPSEEK_API_KEY
```

This was not evidence that the cloud key was absent. A redacted remote probe
after sourcing the hot-env reported `DEEPSEEK_API_KEY`, `ZHIPU_API_KEY`,
`ZAI_API_KEY`, `GLM_API_KEY`, and `FIREWORKS_API_KEY` present.

## Corrective action

The local cloud `resume` adapter now performs the same environment bootstrap as
the cloud chain launcher, then invokes the absolute pinned runtime:

```text
if [ -f /workspace/.cloud-hot-env ]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;
cd <workspace> && <absolute-runtime> -P -m arnold_pipelines.megaplan <phase-command>
```

Focused cloud tests pass. The unchanged r5 session was retried once. It acquired
a live PID under the pinned runtime and emitted fresh heartbeats, so this retry
is a real execution rather than a marker-only claim.

## Remaining control-plane finding

The persisted plan says `execute=hermes:zhipu:glm-5.2`, while its current active
step metadata can still show a DeepSeek orchestration model. Batch receipts are
the authoritative source for the actual task model; future hardening must make
the resolved phase route and every batch route explicit in one execution
envelope and reject disagreement before dispatch. This is the provider-authority
item in the Sol/Luna plan, not a reason to create a replacement chain.
