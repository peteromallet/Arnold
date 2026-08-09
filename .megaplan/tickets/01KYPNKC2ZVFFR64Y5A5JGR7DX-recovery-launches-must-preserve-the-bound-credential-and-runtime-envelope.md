---
id: 01KYPNKC2ZVFFR64Y5A5JGR7DX
title: Recovery launches must preserve the bound credential and runtime envelope
status: open
source: human
tags:
- bug
- recovery
- credentials
- runtime-provenance
- managed-recovery-custody
- immediate-residual
codebase_id: null
created_at: '2026-07-29T10:09:24.064192+00:00'
last_edited_at: '2026-07-31T05:24:50+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
---

Recovery must preserve the bound runtime, provider routing, and approved credential channel without reconstructing secrets manually. Direct retries used the pinned editable interpreter but depended on copying the environment from a hard-coded resident PID. During the 13:39Z recovery that resident had restarted from PID 3304356 to PID 3411953, making the retry launcher fail before execution. Persist a non-secret launch-envelope reference bound to the current resident generation or a stable credential broker, resolve it dynamically at launch, and fail with a typed stale-envelope error rather than a missing procfs path. Acceptance: rotate or restart the resident between failure and recovery, then prove the canonical managed relaunch uses the same approved credentials and editable runtime without PID-specific configuration or secret output.

The 2026-07-30 M11 recovery exposed the same class through two additional
envelope fields. A direct pinned-interpreter `critique` launch omitted
`MEGAPLAN_TRUSTED_CONTAINER=1`, so its read-only Codex critics attempted
bubblewrap inside the already-sandboxing Docker container and every repository
inspection failed with `bwrap: No permissions to create new namespace`. A
direct `gate` launch also omitted the approved provider credential channel, so
the persisted DeepSeek route failed before judgment with
`Provider 'deepseek' ... no API key was found`. Changing only the interpreter
therefore does not preserve the runtime envelope.

Extend the fix so every canonical operator, chain, resident, fixer, and recovery
launch is produced by one launch-envelope resolver that atomically binds:

- pinned interpreter and editable source identity;
- `MEGAPLAN_TRUSTED_CONTAINER=1` (or an equivalent attested outer-sandbox
  decision);
- approved non-secret credential-channel reference and provider route;
- `.cloud-hot-env`/resident-generation identity where applicable;
- project/plan roots and the exact command.

Before spawning a model worker, preflight the selected provider through that
resolved channel and emit a typed `credential_channel_unavailable` or
`trusted_container_envelope_missing` failure. Do not let critique complete with
high-complexity checks marked unverifiable after an operational sandbox
failure, and do not let gate fall through to an uncredentialed configured
provider. Acceptance must reproduce both 2026-07-30 cases, prove the canonical
relaunch uses the same envelope as the cloud wrapper without reading a
hard-coded PID or printing a secret, and prove a provider-route override is
durably recorded when the bound provider is intentionally changed.

## 2026-07-31 runtime bootstrap evidence

The cloud image now includes a pinned Railway CLI for application deployment
from the runner. Its entire `~/.railway` directory is backed by
`/workspace/.creds/railway`, so Railway's atomic config rewrites and
`railway login --browserless` survive container replacement. A legacy
`/workspace/.creds/railway-config.json` is imported only when no durable config
exists. No token or config content is rendered into the image, `cloud.yaml`, or
logs.

This closes the Railway bootstrap/persistence subcase only. Keep this ticket
open: the canonical recovery launch-envelope resolver and its resident
rotation, trusted-container, and provider-preflight acceptance cases remain
outstanding.

The finalized Platformization epic is not the resolver for these cloud-launch
semantics; it consumes prior credential/runtime substrate rather than replacing
it. Keep this as an immediate release residual. Native Parity is associated
only because its recovery/control cutover must preserve the resulting envelope
contract and fixtures.

## 2026-07-31 pinned repair-route evidence

The post-M11 recovery wrappers now prefer `MEGAPLAN_RUNTIME_SRC` when selecting
sibling repair launchers, preserve the dedicated `editible-install` branch as
the fallback source, and pass the selected runtime into repair children through
`ARNOLD_REPAIR_RUNTIME_SRC`. Watchdog dispatch and regenerated chain relaunches
also carry the same repair queue root, marker directory, session, and run kind.
Focused wrapper tests cover pinned-source selection and route-context
propagation.

This closes the sibling-wrapper/source-selection subcase only. Keep this ticket
open: the single canonical launch-envelope resolver, credential-channel
preflight, resident-generation rotation fixture, and provider-route acceptance
proof remain outstanding.

## 2026-07-31 container-boot source closure

Release preflight found that the generated cloud entrypoint still launched
`arnold-heartbeat` and `arnold-watchdog` from the literal mutable
`/workspace/arnold` checkout. On the live Hetzner box that checkout is dirty,
while the selected runtime is a separate content-addressed candidate. A normal
container replacement could therefore boot recovery authority from unrelated
dirty source before the host-side ensure timer intervened. The resident also
used `/workspace/arnold` as its tmux working directory even when its executable
and import source were selected elsewhere.

Commit `98056ca183` closes this boot-source subcase. The generated entrypoint now
loads the persistent hot environment and resolves heartbeat, watchdog, and
resident source through the same precedence:
`MEGAPLAN_RUNTIME_SRC`, then `CLOUD_WATCHDOG_ARNOLD_SRC`, then the legacy
`/workspace/arnold` fallback. Each process changes to the selected source and
executes its wrapper from that quoted path; the resident starts from neutral
`/workspace` and then changes to the selected source. Focused rendering tests
reject hard-coded wrapper paths and the dirty-checkout tmux cwd, assert all
three consumers share the selector, and run `bash -n` over the rendered
entrypoint. Validation: `14 passed` in `tests/cloud/test_ssh_deploy.py`,
the two host ensure selector tests passed, Ruff passed, compileall passed, and
`git diff --check` passed.

Keep this ticket open. The broader canonical launch-envelope resolver,
credential-channel preflight, resident-generation rotation fixture, and
provider-route acceptance proof remain outstanding. The live
`.cloud-hot-env` and `resident-runtime.env` selectors are intentionally not
rewritten by this code commit; final-SHA cutover must replace their duplicated
and contradictory runtime assignments with one CAS/checkpointed canonical
block and produce a fresh runtime/canary receipt.
