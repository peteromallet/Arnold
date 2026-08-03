# Critique r5: exact attempt-9 cutover runbook

## Decision

Continue the existing r5 session, workspace, chain cursor, plan, and accepted
planning artifacts. Do **not** restart Prep and do **not** resume attempt 8.

The recovery boundary is:

1. durably pause every obsolete Critique marker;
2. replace the old resident-only listener with one attested to the exact new
   candidate, proving `/whats-cooking` and notification delivery load the new
   code before the failure state can change;
3. terminate only the frozen attempt-8 process incarnation;
4. durably cancel attempt 8 in its WBC ledger;
5. bind the legacy r5 marker to its proven old runtime, then cut both chain and
   marker runtime custody to the exact deployed engine;
6. while still paused, reapply `partnered-5-glm` through the supported control
   route and prove the persisted Execute coordinator and tiers 1–10 are all
   GLM-family routes;
7. while the chain remains paused and the plan lifecycle remains `gated`, invoke
   exactly one direct Finalize command under that exact new runtime;
8. verify the new Finalize WBC is ordinal 9 and completes with lifecycle state
   `finalized` and `next_step=execute`;
9. only then explicitly resume the same chain with `--no-push` into GLM-family
   Execute.

This ordering is the integrated launch contract in
`docs/arnold/critique-attempt9-launch-contract.md`, present in exact release
candidate `daa2c850645532dffb697182203284c5b965a563`. In
particular, resuming the chain from `gated` is forbidden: chain resume must not
be used to create attempt 9.

Do not directly adopt the recovered attempt-7 candidate. It passed model
schema, semantic, critique-coverage, and feasibility checks, but it is only the
model-authored payload. No existing public adoption transition also performs
the harness-owned baseline selection, validation-job compilation, critique
custody binding, `finalize.json` publication receipt, phase WBC terminal,
`phase_result.json`, and state transition. Use it as recovery evidence and
prompt precedent; rerun one new Finalize occurrence through the fixed
file-receipt protocol.

## Verified live facts (read-only, 2026-08-03)

- Host: `159.69.51.216`
- Runner container:
  `782c6da82a8f988646747e8e57d51ca7f69d336d21920e3adebd9fb556e00117`
- Resident container:
  `a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a`
- Session: `critique-ledger-accountability-v3-r5-20260803`
- Workspace: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- Spec: `$WORKSPACE/.megaplan/initiatives/critique-ledger/chain.yaml`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain-state file: `$WORKSPACE/.megaplan/plans/.chains/chain-a5c760402ea2.json`
- Plan state: `gated`; current milestone index `0`; no completed milestones.
- Product checkout: HEAD `07dc708074f2b887f86af3484759080713ace636`,
  milestone branch `megaplan/critique-ledger-accountability-v3-r5/cl2-ledger-replay`.
- The profile name and Execute coordinator are persisted as
  `profile=partnered-5-glm`,
  `finalize=codex:gpt-5.6-sol:high`, and
  `execute=hermes:zhipu:glm-5.2`, but the existing plan's persisted tier table
  is from the old registry: tiers 1–2 are DeepSeek flash, tiers 3–6 are
  DeepSeek pro, and only tiers 7–10 are GLM. Deploying a new profile registry
  does not rewrite existing plan state; the supported same-profile refresh is
  therefore a mandatory cutover step.
- Attempt 8 exact custody:
  - phase WBC attempt `8fe6ab70-45c0-573e-9a26-32721b06047e`
  - invocation `21d5c8322f2148a5`
  - active-step run `c9cb6a4d-ec3c-4634-a08f-db273f0d96a7`
  - ordinal `8`, phase `finalize`
  - WBC has exactly one event: sequence 1, `STARTED`.
- Frozen process identities (container PID / start ticks):
  - tmux server `151724 / 25944913`; raw cmdline SHA-256
    `692946e7ea42f486e0bdd084bc9a6b19416c7d126c4f3963f7d48b29e7614039`
  - tmux pane bash `151725 / 25944914`
  - chain runner `152041 / 25945230`
  - Codex node wrapper `160047 / 26116032`
  - Codex binary `160061 / 26116035`
  - code-mode host `160240 / 26117045`
- Old runtime root/revision:
  `/workspace/runtime-candidates/arnold-18b279f5ef-live` /
  `18b279f5ef6d2a4db693586a59de8d87d7b45ab5`.
- A fresh in-memory provenance observation of that runtime is healthy and
  exactly equals the chain runtime binding:
  `cb6afb8017532b1dd744e2e24cd3e02cb01f479814d2b4b7548429ebefaed49b`.
- The r5 marker is legacy: it has no `runtime_binding`, no
  `editable_source_head`, and no `run_id`; its relaunch command still names
  the 18b runtime. This is why ordinary runtime-cutover CAS could not be used
  directly.
- Recovered attempt-7 candidate:
  `af6149befd0e0a60700678999adbf10f425afa26f356a545b1e6246269bbe9a5`,
  72,328 bytes, 28 tasks, 28 sense checks, 29 critique-coverage rows, one user
  action; manifest status `RECOVERED_CANDIDATE_NOT_ADOPTED`.
- Final adversarial gate on exact code
  `daa2c850645532dffb697182203284c5b965a563` is GO: 530 combined tests, 622
  prior broad tests, 40 combined resident/notification/profile/control tests,
  and 17 latest resident-recovery tests passed; modified production Python
  compiles, donor Ruff and `git diff --check` pass. The fresh-clone resident
  capability probe remains clean (old code created 61 ignored bytecode paths).
- Integrated launch contract locks Finalize to a one-shot direct
  phase invocation and maps Execute's coordinator and every complexity tier
  1–10 to GLM-family routes. DeepSeek remains available only outside Execute;
  GPT-5.6 Sol high remains exclusive to Finalize.

## Preconditions — all must pass

Use task-specific variables; never use `--fresh` or delete plan/chain state.

```bash
CUTOVER_HOST=159.69.51.216
CUTOVER_RUNNER=782c6da82a8f988646747e8e57d51ca7f69d336d21920e3adebd9fb556e00117
CUTOVER_SESSION=critique-ledger-accountability-v3-r5-20260803
CUTOVER_WORKSPACE=/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold
CUTOVER_SPEC=$CUTOVER_WORKSPACE/.megaplan/initiatives/critique-ledger/chain.yaml
CUTOVER_PLAN=$CUTOVER_WORKSPACE/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357
CUTOVER_CHAIN_STATE=$CUTOVER_WORKSPACE/.megaplan/plans/.chains/chain-a5c760402ea2.json
CUTOVER_MARKER=/workspace/.megaplan/cloud-sessions/$CUTOVER_SESSION.json
CUTOVER_OLD_ENGINE=/workspace/runtime-candidates/arnold-18b279f5ef-live
CUTOVER_OLD_RUNTIME_SHA=cb6afb8017532b1dd744e2e24cd3e02cb01f479814d2b4b7548429ebefaed49b
```

Before mutation, re-read and compare:

- container IDs and health;
- the exact attempt/WBC/run/ordinal tuple above;
- all six PID start ticks and command lines (or prove all are already absent);
- old runtime provenance still equals `CUTOVER_OLD_RUNTIME_SHA`;
- the deployed registry pins Finalize to Sol high and Execute's coordinator
  plus every complexity tier 1–10 to GLM-family routes; separately record the
  old persisted tier table before its supported refresh;
- recovered candidate, manifest, rollout, and output-receipt hashes still match;
- no `finalize.json` exists;
- no second r5 tmux/session/runner exists;
- the new engine checkout is clean, exact-HEAD, tested, and installed only into
  an isolated control venv at this point. Do not replace the global old-runtime
  interpreter until its provenance receipt has been generated and verified.

Any mismatch is a fail-closed stop. Do not “repair” a guard by editing state.

## Cutover sequence

### 1. Quarantine obsolete sessions first

The v2, v3, and r4 markers are already durably paused. r2 and r3 were verified
with `should_run=true` and no pause, so they remain watchdog-relaunchable.
Using the exact deployed control engine, call
`arnold_pipelines.megaplan.cloud.operator_control pause` separately for r2 and
r3 with their own marker/spec/workspace/session and reason
`superseded by canonical r5 recovery`. Do not hand-edit the markers.

Postcondition: every `critique-ledger-*` marker except r5 has
`should_run=false` plus active operator-pause authority, and no matching tmux,
repair loop, or meta-repair process. Repeat this scan immediately before r5
resume. These durable pauses keep old rows out of active status. After r5
completes, use the completion-manifest-gated retirement command for formal
tombstones; do not unpause an old attempt.

### 2. Produce independent old-runtime evidence

While the global interpreter still imports the 18b runtime, run its
`cloud.runtime_provenance` with `--expected-root`, `--expected-revision`,
`--identity-out`, and `--receipt-out` into a cutover evidence directory.
Verify the identity digest is exactly `CUTOVER_OLD_RUNTIME_SHA` and the receipt
reports no errors. The migration control process must run from a separate
new-engine venv, so receipt verification is independent.

### 3. Recover the resident, then retire frozen attempt 8

Before changing attempt custody, replace the resident-only listener through the
supported recovery surface. The existing resident is already running the
reviewed seven-commit listener-recovery donor, so it can be stopped with exact
custody. The new candidate includes that same recovery series plus the durable
notification owner.

From the attested new-candidate control environment, first call
`cloud resident-down` for epoch `discord-enospc-20260803-r7`, guarded by:

- source container
  `277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab`;
- source image
  `sha256:de249469ec93ae57eec650b743a08e5a9790dd9612755f2118b6a3ac7149db94`;
- resident image
  `sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20`;
- resident container
  `a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a`.

Use the exact final source checkout as the local control plane and prove its
import before either command:

```bash
CUTOVER_CONTROL_SRC=/absolute/path/to/exact-final-Arnold-checkout
CUTOVER_CONTROL_PYTHON=python3
CUTOVER_CLOUD_YAML=$CUTOVER_CONTROL_SRC/.megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml
NEW_RUNTIME=/workspace/runtime-candidates/arnold-$NEW_COMMIT
test "$(git -C "$CUTOVER_CONTROL_SRC" rev-parse HEAD)" = "$NEW_COMMIT"
test -z "$(git -C "$CUTOVER_CONTROL_SRC" status --porcelain)"
CUTOVER_CONTROL_SRC="$CUTOVER_CONTROL_SRC" PYTHONPATH="$CUTOVER_CONTROL_SRC" \
  "$CUTOVER_CONTROL_PYTHON" -P -c \
  'import os,pathlib,arnold_pipelines; assert pathlib.Path(arnold_pipelines.__file__).resolve().is_relative_to(pathlib.Path(os.environ["CUTOVER_CONTROL_SRC"]).resolve())'

PYTHONPATH="$CUTOVER_CONTROL_SRC" "$CUTOVER_CONTROL_PYTHON" -P -m \
  arnold_pipelines.megaplan cloud resident-down \
  --cloud-yaml "$CUTOVER_CLOUD_YAML" \
  --outage-epoch discord-enospc-20260803-r7 \
  --expected-source-container-id 277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab \
  --expected-source-image-id sha256:de249469ec93ae57eec650b743a08e5a9790dd9612755f2118b6a3ac7149db94 \
  --expected-resident-image-id sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20 \
  --expected-resident-container-id a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a
```

Then call `cloud resident-recover` under a fresh, never-reused outage epoch with
the same source identities, the independently admitted compatible resident
image, and exact new runtime path/commit/tree. Guard the interpreter as
`/root/.pyenv/versions/3.11.11/bin/python3.11` with SHA-256
`2575448bc13e2a87f48b65eeaa6d72de75e250616340b377a8989a80317a0ec5`.
Use
`.megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml` for both
commands. Never print or copy the resident secret environment.

```bash
test -n "$NEW_COMMIT"
test -n "$NEW_TREE"
test -n "$NEW_EPOCH"
PYTHONPATH="$CUTOVER_CONTROL_SRC" "$CUTOVER_CONTROL_PYTHON" -P -m \
  arnold_pipelines.megaplan cloud resident-recover \
  --cloud-yaml "$CUTOVER_CLOUD_YAML" \
  --outage-epoch "$NEW_EPOCH" \
  --expected-source-container-id 277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab \
  --expected-source-image-id sha256:de249469ec93ae57eec650b743a08e5a9790dd9612755f2118b6a3ac7149db94 \
  --expected-resident-image-id sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20 \
  --expected-runtime-path "$NEW_RUNTIME" \
  --expected-runtime-commit "$NEW_COMMIT" \
  --expected-runtime-tree "$NEW_TREE" \
  --expected-runtime-python-path /root/.pyenv/versions/3.11.11/bin/python3.11 \
  --expected-runtime-python-sha256 2575448bc13e2a87f48b65eeaa6d72de75e250616340b377a8989a80317a0ec5 \
  --health-timeout-seconds 45
```

Required postconditions are: top status `healthy`, reason `discord_ready`,
`listener_only=true`, `resident_running=true`; singleton container name
`megaplan-cloud-agent-resident-only`; restart policy `no`; start receipt bound
to the exact candidate path/commit/tree/interpreter; custody runtime and seed
mounted read-only; workspace mounted read-write; and logs after `started_at`
contain the readiness line with `listener_only=True`. Run unchanged completion
and subagent notification tests before deployment; do not synthesize an
outbound event against the production Discord resident. Live validation is
read-only: require the durable delivery-effect store to initialize, compare
its rows and provider-attempt count across two ordinary unchanged resident
polls, and require no duplicate attempt for any effect identity. Confirm
`/whats-cooking` through the ordinary command only after readiness.

If new health fails, call `resident-down` with the new epoch and exact new
resident ID, then recover under another fresh rollback epoch using old runtime
`/workspace/runtime-candidates/arnold-31d2e052104a57eb48e782dce8bdf678e6731caf`,
commit `31d2e052104a57eb48e782dce8bdf678e6731caf`, tree
`4a6c152c3e898c7bd379f1566ec2f1f11091fd4f`, and the same old resident image.
Keep r5 frozen; do not continue the cutover.

This finite resident recovery is the explicit selector for `/whats-cooking`
and Discord during the r5 cutover. The global `.cloud-hot-env` and
`resident-runtime.env` selectors are not silently treated as updated. Keep
their watchdog/auditor/supervisor consumers inactive until the follow-up epic
performs the separate atomic global promotion; r5 itself is bound through its
chain and marker runtime identities below.

After the resident is proven healthy, retire the frozen attempt-8 process
incarnation.

The r5 plan lock is held by the frozen Finalize call, so the normal durable
pause cannot commit until that exact owner is gone. First verify watchdog,
auditor, and repair-trigger services are inactive (as observed) or temporarily
stop only those supervisors and record which were active for later restoration.

In one guarded operator script, re-read `/proc/<pid>/stat` and command lines,
require every extant PID to match the PID/start-ticks/command identity above,
and require the exact tmux session to resolve to PID `151724`. Parse
`/proc/<pid>/stat` after the closing `)` because the tmux server comm contains a
space. First invoke `tmux kill-session -t
critique-ledger-accountability-v3-r5-20260803`. Then reconcile all six known
PIDs: missing means the clean session termination retired it; present with the
same start ticks and command identity may receive guarded `TERM`, followed by
`KILL` if it remains; any mismatched incarnation is an abort and must never be
signalled. Never signal by a broad pattern, unresolved variable, or
container-wide kill.

Postconditions:

- none of those PID incarnations exists;
- no process command contains the r5 workspace plus Finalize/Codex invocation;
- the r5 tmux session is absent;
- `.plan.lock` and `.auto-driver.lock` are acquirable;
- state and WBC are otherwise unchanged (attempt 8 still STARTED until the
  explicit cancellation below).

Immediately call `operator_control pause` for exact r5. It must persist both
chain- and plan-side operator-pause authority and set marker
`should_run=false`. If pause fails, keep all supervisors stopped and do not
launch anything.

### 4. Durably cancel attempt 8

From the exact new engine, invoke:

```python
cancel_active_phase_wbc_attempt(
    plan_dir=Path("/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357"),
    step="finalize",
    expected_attempt_id="8fe6ab70-45c0-573e-9a26-32721b06047e",
    expected_invocation_id="21d5c8322f2148a5",
    expected_run_id="c9cb6a4d-ec3c-4634-a08f-db273f0d96a7",
    expected_attempt_ordinal=8,
    agent="operator",
    reason="superseded by immutable attempt 9 after runtime cutover",
)
```

Postconditions:

- attempt-8 WBC events are exactly `STARTED(1), CANCELLED(2)`;
- state history has one cancellation row carrying attempt/WBC/invocation/run;
- `active_step` is absent;
- plan and chain remain durably paused;
- repeated exact cancellation is idempotent and cannot add another terminal.

This cancellation history is what makes the next Finalize owner ordinal 9.

### 5. Migrate the legacy marker, then cut over runtime custody

Deploy exact candidate `daa2c850645532dffb697182203284c5b965a563`, which
contains the marker migration and live-chain-shape correction, but do not touch
the live marker during deployment. Run the dedicated
`cloud.legacy_marker_runtime_migration` CLI from the isolated new-engine control
venv with:

- current marker SHA (re-read after pause);
- SHA-256 of the marker's exact old relaunch-command string;
- old runtime root and `CUTOVER_OLD_RUNTIME_SHA`;
- exact session/workspace/spec/current plan;
- exact paused chain-state path;
- independently generated old runtime identity and provenance receipt.

The API rejects unpaused, stale, partially bound, retired, mismatched, or
ambiguous markers. It deterministically derives `run_id` from the marker,
relaunch, chain-state, runtime-identity, and provenance-receipt hashes; it does
not use a default/random launch identity. It atomically installs the old
runtime binding and writes immutable prepared+committed migration evidence.

Then perform the ordinary two-sided runtime cutover:

1. generate and independently verify identity+receipt for the exact new engine;
2. `chain runtime-rebind` from `CUTOVER_OLD_RUNTIME_SHA` to the new runtime hash,
   guarded by milestone `cl2-ledger-replay` and current plan name;
3. `cloud.runtime_cutover` the marker from the same old hash to the same new
   identity, using a launcher-generated relaunch command pinned to the exact
   new root/revision (never hand-replace a path in shell text);
4. re-read both authorities and require byte-equal normalized runtime identities.

If either side fails, remain paused. If chain rebind succeeds but marker update
fails, use the ordinary guarded chain runtime rollback with the old identity
and receipt; do not resume in a split-brain state.

### 6. Refresh persisted routing, then launch exactly one Finalize while paused

Keep the chain runner stopped, both operator-pause authorities present, and the
r5 marker at `should_run=false`. The plan lifecycle state itself remains
`gated`; the direct `finalize` phase command accepts `gated` and would reject a
durable plan lifecycle state of `paused`.

From the runtime-attested exact new engine, first reapply the same profile
through the ordinary control-routed override:

```bash
python -P -m arnold_pipelines.megaplan override set-profile \
  --plan cl2-wbc-backed-ledger-20260803-1357 \
  --profile partnered-5-glm \
  --reason "refresh persisted routing after attested GLM-only registry cutover"
```

Require a durable `profile_refresh_receipt` with `same_profile_refresh=true`
and exact before/after routing hashes. Reread state and require:

- lifecycle remains `gated` and both operator pauses remain active;
- attempt-8 cancellation history and all phase-WBC bytes are unchanged;
- `phase_model` keeps Finalize on GPT-5.6 Sol high and Execute on GLM;
- every persisted `tier_models.execute` entry 1–10 contains only direct Zhipu
  GLM 5.2 and Fireworks GLM 5p2 routes;
- the chain-state bytes are unchanged.

Any missing receipt, stale-state CAS failure, custody change, or non-GLM
Execute tier is a fail-closed stop. Never hand-edit `state.json`.

From the runtime-attested exact new engine checkout, with the r5 workspace as
the current directory, invoke exactly once:

```bash
python -P -m arnold_pipelines.megaplan finalize \
  --plan cl2-wbc-backed-ledger-20260803-1357
```

Do not wrap this command in `auto`, `chain`, a shell retry, or a deterministic
three-attempt loop. Do not resume the chain from `gated`. The direct phase
command is the sole authorized creator of immutable Finalize attempt 9.

Before any resume, reread state and the WBC ledger and require:

- exactly one new Finalize WBC stream with ordinal 9;
- attempt 9 is `STARTED -> COMPLETED`, with no active Finalize owner;
- attempt 8 remains `STARTED -> CANCELLED`;
- lifecycle state is `finalized` and `next_step=execute`;
- `finalize.json` and its immutable publication/mutation receipts exist and
  match the completed attempt.

If the direct command fails, require exactly one terminal attempt-9 stream, no
attempt 10, no active Finalize owner, and lifecycle state still `gated` (or its
explicit terminal/manual-review projection). Keep the runner stopped and both
pause authorities intact. Diagnose before any new operator action.

### 7. Resume the same r5 chain into Execute

Invoke `cloud.operator_control resume` directly from the exact new engine with
the exact spec/workspace/session/marker and `--no-push`. Do not use
`cloud resume` (the legacy path selected the wrong `arnold` CLI family), do not
use `--fresh`, and do not run `init`.

`--no-push` preserves the existing milestone checkout and its plan artifacts;
the relaunch command must be the marker's newly attested command. Resume is
authorized only from the verified `finalized` / `next_step=execute` state; it
must clear both pause authorities, set only r5 `should_run=true`, and launch one
r5 tmux runner. The resumed chain must enter Execute and cannot redispatch
Finalize.

## Launch canaries and success criteria

Check Finalize completion before resume, then check immediately after resume
and again after 10–15 minutes:

1. Exactly one active Critique session: r5. All older markers remain paused.
2. Same chain state, milestone 0, same plan; no Prep/Plan/Critique replay.
3. The direct paused-state Finalize invocation created exactly one ordinal-9
   WBC with a new run/WBC/invocation ID, `codex:gpt-5.6-sol:high`, no
   relationship to attempt-8 PIDs, and terminal `COMPLETED` status before chain
   resume.
4. Attempt 8 stays `CANCELLED`; attempt 7 stays failed/indeterminate. Neither is
   rewritten as success.
5. Local-strict Sol output uses the fresh authorized candidate path plus exact
   SHA/byte-count receipt. One WBC Finalize occurrence may use its single
   internal structural repair, but deterministic local-contract failure must
   not create an outer attempt 10.
6. Successful Finalize publishes `finalize.json` through sole Finalize
   authority with immutable mutation receipt, then writes phase/WBC success and
   advances state to `finalized`.
7. After operator-controlled resume from `finalized`, Execute starts through a
   GLM-family route; its coordinator and every complexity tier 1–10 exclude
   DeepSeek and Codex. The preferred route is direct Zhipu GLM 5.2, followed by
   Fireworks GLM 5p2 and then direct Zhipu retry.
8. `/whats-cooking` responds and shows one current r5 chain. Raw tmux/PID facts
   are diagnostic only; canonical current-target liveness is authoritative.
9. Poll unchanged stopped/healthy status repeatedly (including 200 notification
   effect evaluations): no duplicate Discord delivery, no direct fallback send,
   and no resurrection of v2/r2/r3/r4.

The relaunch gate is passed only after criteria 1–7. The recovery is proven
durable after criteria 8–9 also pass.

## Rollback / fail-closed rules

- Before resume, every failure leaves the chain paused and `should_run=false`;
  never resume from `gated` or use resume to manufacture attempt 9.
- Never restore attempt 8 to STARTED or delete its terminal evidence.
- Never copy the recovered candidate over `finalize.json` manually.
- Never run a second driver, `--fresh`, broad workspace cleanup, or global
  process kill.
- Runtime rollback must use the same chain+marker CAS APIs and independently
  verified old identity; no marker/state hand edits.
- After attempt 9 starts, a new failure is a new immutable occurrence: pause,
  diagnose its typed receipt, and repair forward. Do not relabel history.
- Restore any supervisor temporarily stopped for the process cutover only after
  marker/chain runtime identities agree and r5 has a single attested runner.
