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
candidate `b38460e4d3f2605b341fa117dc838c6e51a1d3c8`. In
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

## Verified live checkpoint (2026-08-04 01:17 UTC)

This section supersedes the earlier 18b/31d2/daa2/a5d candidate references for
all remaining actions. Those identities remain historical evidence only.

- Host: `159.69.51.216`
- Runner container:
  `782c6da82a8f988646747e8e57d51ca7f69d336d21920e3adebd9fb556e00117`
- Resident container:
  `911d8a74727524e5d118c197c795b6d1fcd485689c615c6d692748d8000decff`
- Resident epoch: `critique-attempt9-b384-20260804-0115`; status
  `healthy/discord_ready`, `listener_only=true`, restart policy `no`.
- Session: `critique-ledger-accountability-v3-r5-20260803`
- Workspace: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- Spec: `$WORKSPACE/.megaplan/initiatives/critique-ledger/chain.yaml`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain-state file: `$WORKSPACE/.megaplan/plans/.chains/chain-a5c760402ea2.json`
- Plan state: `gated`; current milestone index `0`; no completed milestones;
  no active step, no runner, and marker `should_run=false`.
- Product checkout: HEAD `b9add7e867`,
  milestone branch `megaplan/critique-ledger-accountability-v3-r5/cl2-ledger-replay`.
- The supported same-profile refresh has completed. It binds selected source
  `project`, effective digest
  `2c1dabb0cab708f7131d14221f79e4ba1be8dc6a311546be2318f348d8ab548c`,
  `profile=partnered-5-glm`, `finalize=codex:gpt-5.6-sol:high`, and every
  Execute tier 1–10 to direct Zhipu GLM 5.2, Fireworks GLM 5p2, then direct
  Zhipu GLM 5.2. The previous project overlay's DeepSeek Execute routes are no
  longer current authority.
- Attempt 8 exact custody:
  - phase WBC attempt `8fe6ab70-45c0-573e-9a26-32721b06047e`
  - invocation `21d5c8322f2148a5`
  - active-step run `c9cb6a4d-ec3c-4634-a08f-db273f0d96a7`
  - ordinal `8`, phase `finalize`
  - WBC is now exactly `STARTED(1) → CANCELLED(2)`; active custody is absent.
  - The six frozen PID/start-tick identities were retired with exact guards;
    no r5 tmux or Finalize/Codex process remains.
- Legacy marker migration completed with migration ID `98569aa853…` and run ID
  `7692b167-d533-5e76-99b3-098a2a3fd40c`; no marker hand edit was used.
- Final runtime root:
  `/workspace/runtime-candidates/arnold-b38460e4d3f2605b341fa117dc838c6e51a1d3c8`.
- Final runtime commit/tree:
  `b38460e4d3f2605b341fa117dc838c6e51a1d3c8` /
  `f0acc45ff8f726d38e67fa665179b65353bac336`.
- Final isolated interpreter:
  `/workspace/runtime-venvs/arnold-b38460e4d3f2605b341fa117dc838c6e51a1d3c8/bin/python`.
- Final runtime identity digest:
  `21ff19b6bd117b18f85643781b999167c4b8eb882601a5e77d9b3c9858eff476`.
- Chain and marker both bind that exact identity; marker relaunch is generated
  for branch `runtime-b38460e4d3`; marker remains non-runnable.
- Recovered attempt-7 candidate:
  `af6149befd0e0a60700678999adbf10f425afa26f356a545b1e6246269bbe9a5`,
  72,328 bytes, 28 tasks, 28 sense checks, 29 critique-coverage rows, one user
  action; manifest status `RECOVERED_CANDIDATE_NOT_ADOPTED`.
- Final root-fix gate on exact code `b38460e4d3f2605b341fa117dc838c6e51a1d3c8`
  is GO for cutover: 261 orchestration/worker WBC tests, 118 combined incident
  tests, and 118 critical tests in the isolated cloud runtime passed. The
  candidate adds lifecycle-safe legacy custody migration plus fresh parallel
  Critique phase/worker WBC and terminal child-manifest binding.
- Integrated launch contract locks Finalize to a one-shot direct
  phase invocation and maps Execute's coordinator and every complexity tier
  1–10 to GLM-family routes. DeepSeek remains available only outside Execute;
  GPT-5.6 Sol high remains exclusive to Finalize.
- No attempt 9 exists yet. No Finalize completion, chain resume, Execute start,
  `/whats-cooking` success, or live notification-dedupe success is claimed by
  this checkpoint.

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
CUTOVER_ENGINE=/workspace/runtime-candidates/arnold-b38460e4d3f2605b341fa117dc838c6e51a1d3c8
CUTOVER_PYTHON=/workspace/runtime-venvs/arnold-b38460e4d3f2605b341fa117dc838c6e51a1d3c8/bin/python
CUTOVER_COMMIT=b38460e4d3f2605b341fa117dc838c6e51a1d3c8
CUTOVER_TREE=f0acc45ff8f726d38e67fa665179b65353bac336
CUTOVER_RUNTIME_SHA=21ff19b6bd117b18f85643781b999167c4b8eb882601a5e77d9b3c9858eff476
CUTOVER_PRODUCT_COMMIT=b9add7e867
```

Before mutation, re-read and compare:

- container IDs and health;
- the exact attempt/WBC/run/ordinal tuple above;
- all six PID start ticks and command lines (or prove all are already absent);
- chain and marker runtime provenance both equal `CUTOVER_RUNTIME_SHA`;
- the deployed registry pins Finalize to Sol high and Execute's coordinator
  plus every complexity tier 1–10 to GLM-family routes; separately record the
  old persisted tier table before its supported refresh;
- recovered candidate, manifest, rollout, and output-receipt hashes still match;
- no `finalize.json` exists;
- no second r5 tmux/session/runner exists;
- the engine checkout is clean, exact-HEAD, tested, and imported only through
  `CUTOVER_PYTHON`; do not substitute `.cloud-hot-env`, `PYTHONPATH`, or a
  global interpreter.

Any mismatch is a fail-closed stop. Do not “repair” a guard by editing state.

## Cutover sequence

### 1. Quarantine obsolete sessions first — COMPLETED

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

### 2. Produce independent legacy-runtime evidence — COMPLETED

While the global interpreter still imports the 18b runtime, run its
`cloud.runtime_provenance` with `--expected-root`, `--expected-revision`,
`--identity-out`, and `--receipt-out` into a cutover evidence directory.
The legacy identity and receipt were independently verified before migration;
the marker then received its deterministic managed run/runtime identity. This
evidence is immutable migration input, not a runtime selector for any remaining
command.

### 3. Recover the resident, then retire frozen attempt 8 — COMPLETED

The commands below are retained as historical procedure only. Do not replay the
old outage epoch or old resident-container guard. Current authority is the
verified checkpoint above.

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
test "$(git -C "$CUTOVER_CONTROL_SRC" rev-parse HEAD)" = "$CUTOVER_COMMIT"
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
test -n "$CUTOVER_COMMIT"
test -n "$CUTOVER_TREE"
test -n "$NEW_EPOCH"
PYTHONPATH="$CUTOVER_CONTROL_SRC" "$CUTOVER_CONTROL_PYTHON" -P -m \
  arnold_pipelines.megaplan cloud resident-recover \
  --cloud-yaml "$CUTOVER_CLOUD_YAML" \
  --outage-epoch "$NEW_EPOCH" \
  --expected-source-container-id 277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab \
  --expected-source-image-id sha256:de249469ec93ae57eec650b743a08e5a9790dd9612755f2118b6a3ac7149db94 \
  --expected-resident-image-id sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20 \
  --expected-runtime-path "$CUTOVER_ENGINE" \
  --expected-runtime-commit "$CUTOVER_COMMIT" \
  --expected-runtime-tree "$CUTOVER_TREE" \
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

If current resident health fails before attempt 9, stop using the exact current
epoch/container guard and remain fail-closed. Admit any rollback runtime through
the same independent provenance and resident-recovery protocol; never reuse a
historical selector merely because it appears in this record.

This finite resident recovery is the explicit selector for `/whats-cooking`
and Discord during the r5 cutover. The global `.cloud-hot-env` and
`resident-runtime.env` selectors are not silently treated as updated. Keep
r5 launch decisions independent of those selectors until the follow-up epic
performs their separate atomic global promotion and attestation; r5 itself is
bound through its chain and marker runtime identities below.

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

### 4. Durably cancel attempt 8 — COMPLETED

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

### 5. Migrate the legacy marker, then cut over runtime custody — COMPLETED

Deploy exact candidate `b38460e4d3f2605b341fa117dc838c6e51a1d3c8`, which
contains the marker migration and live-chain-shape correction, but do not touch
the live marker during deployment. Run the dedicated
`cloud.legacy_marker_runtime_migration` CLI from the isolated new-engine control
venv with:

- current marker SHA (re-read after pause);
- SHA-256 of the marker's exact old relaunch-command string;
- independently attested legacy runtime root and digest;
- exact session/workspace/spec/current plan;
- exact paused chain-state path;
- independently generated legacy runtime identity and provenance receipt.

The API rejects unpaused, stale, partially bound, retired, mismatched, or
ambiguous markers. It deterministically derives `run_id` from the marker,
relaunch, chain-state, runtime-identity, and provenance-receipt hashes; it does
not use a default/random launch identity. It atomically installs the old
runtime binding and writes immutable prepared+committed migration evidence.

Then perform the ordinary two-sided runtime cutover:

1. generate and independently verify identity+receipt for the exact new engine;
2. `chain runtime-rebind` from the migration-bound legacy digest to
   `CUTOVER_RUNTIME_SHA`,
   guarded by milestone `cl2-ledger-replay` and current plan name;
3. `cloud.runtime_cutover` the marker from the same old hash to the same new
   identity, using a launcher-generated relaunch command pinned to the exact
   new root/revision (never hand-replace a path in shell text);
4. re-read both authorities and require byte-equal normalized runtime identities.

If either side fails, remain paused. If chain rebind succeeds but marker update
fails, use the ordinary guarded chain runtime rollback with the old identity
and receipt; do not resume in a split-brain state.

### 6. Migrate exact legacy custody, then launch one Finalize — IN PROGRESS

Routing refresh is complete and its exact source/digest checks passed. The
operator pause was then cleared through supported `operator_control resume
--no-start` because the direct phase command correctly rejects a durable
`paused` lifecycle. This did **not** start a runner: marker `should_run=false`,
the chain runner is stopped, lifecycle is `gated`, and active step is absent.
Preserve that non-runnable boundary until Finalize is terminal.

First create both create-once legacy-custody sidecars under the final
interpreter. The expected hashes bind the unchanged historical v1 receipt
bytes; `legacy_unbound` explicitly does not invent an unavailable producer
invocation:

```bash
"$CUTOVER_PYTHON" -P -m \
  arnold_pipelines.megaplan.orchestration.critique_custody migrate-legacy \
  --plan-dir "$CUTOVER_PLAN" \
  --iteration 1 \
  --expected-source-sha256 sha256:2429983cf5c74a0dba072153693bdffe3fdeb735feeafafc5f4703fd51b3e37b \
  --actor operator:critique-attempt9-cutover \
  --reason "Admit intact pre-v2 iteration-1 critique custody without fabricating unavailable producer provenance"

"$CUTOVER_PYTHON" -P -m \
  arnold_pipelines.megaplan.orchestration.critique_custody migrate-legacy \
  --plan-dir "$CUTOVER_PLAN" \
  --iteration 2 \
  --expected-source-sha256 sha256:204d893956c435515faa558886c153dae6d75505893ac08827cfcbe6d6abcaf1 \
  --actor operator:critique-attempt9-cutover \
  --reason "Admit intact pre-v2 iteration-2 critique custody without fabricating unavailable producer provenance"
```

Require sidecars `critique_custody_legacy_migration_v1.json` and
`critique_custody_legacy_migration_v2.json`, exact unchanged source hashes,
`legacy_unbound` authority, complete artifact/gate/clearance lineage, and no
attempt-9 WBC row before launch. Regenerated clearance may change under its
ordinary lifecycle; the migration sidecar must remain create-once and retain
its migration-time evidence.

Any missing receipt, stale-state CAS failure, custody change, non-GLM Execute
tier, or pre-existing ordinal 9 is a fail-closed stop. Never hand-edit
`state.json`, either v1 receipt, or the WBC ledger.

From the runtime-attested exact new engine checkout, with the r5 workspace as
the current directory, invoke exactly once:

```bash
"$CUTOVER_PYTHON" -P -m arnold_pipelines.megaplan finalize \
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
explicit terminal/manual-review projection). Keep the runner stopped and
marker non-runnable. Diagnose before any new operator action; do not create
attempt 10.

### 7. Resume the same r5 chain into Execute

Invoke `cloud.operator_control resume` directly from the exact new engine with
the exact spec/workspace/session/marker and `--no-push`. Do not use
`cloud resume` (the legacy path selected the wrong `arnold` CLI family), do not
use `--fresh`, and do not run `init`.

```bash
"$CUTOVER_PYTHON" -P -m \
  arnold_pipelines.megaplan.cloud.operator_control resume \
  --spec "$CUTOVER_SPEC" \
  --workspace "$CUTOVER_WORKSPACE" \
  --session "$CUTOVER_SESSION" \
  --marker "$CUTOVER_MARKER" \
  --actor operator \
  --no-push
```

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

## Live completion record — intentionally pending

Do not check an item from model narrative or process presence alone. Attach the
canonical artifact path, immutable identity, and observation timestamp.

- [ ] **Legacy custody migration:** both sidecars exist; iteration-1 and
  iteration-2 source receipt hashes remain exact; clearance regeneration and
  custody validation pass. Evidence: `PENDING`.
- [ ] **Attempt 9 terminal:** exactly one ordinal-9 Finalize WBC exists and is
  `STARTED → COMPLETED`; attempt 8 remains cancelled; no ordinal 10 exists;
  state is `finalized/execute`. Evidence: `PENDING`.
- [ ] **Same-chain resume:** supported operator resume launched exactly one r5
  runner from the b384 marker command; no old session became runnable and no
  earlier phase replayed. Evidence: `PENDING`.
- [ ] **GLM Execute proof:** first Execute dispatch/provider receipt identifies
  Zhipu GLM 5.2 or its declared Fireworks GLM 5p2 fallback; no Execute receipt
  identifies DeepSeek or Codex. Evidence: `PENDING`.
- [ ] **`/whats-cooking` UX:** ordinary resident command responds within the
  interaction deadline and reports exactly one current r5 chain using canonical
  liveness. Evidence: `PENDING`.
- [ ] **Notification dedupe:** two unchanged ordinary polls plus the 200-effect
  evaluation show a stable effect identity, at most one provider attempt, no
  direct fallback, and no old-v2 alert resurrection. Evidence: `PENDING`.
- [ ] **Global selector follow-up (MP-094):** after Execute is healthy, atomically
  promote and attest watchdog/auditor/supervisor roots; prove no mixed-runtime
  service topology remains. Evidence: `PENDING — follow-up epic, not relaunch
  gate`.

## Rollback / fail-closed rules

- Before resume, every failure leaves the runner stopped and marker
  `should_run=false`; never use chain resume from `gated` to manufacture
  attempt 9.
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

## Attempt 10 authoritative cutover state — supersedes the relaunch checklist

The preceding Attempt-9 procedure is retained only as an audit trail. Its live
checklist, including the requirement that no ordinal 10 exist, is superseded.
Attempt 10 was launched once under the later exact runtime and terminated with
a typed quota failure. Do not execute the earlier Attempt-9 launch or b384
resume instructions.

### Admitted engine and resident

The cloud-validated repair train is:

1. `4ab819d7913352f797d8a01a5ea3b00f17e2236f` — exact authenticated response
   candidate reaches semantic repair; terminal `-o` evidence binds the last
   assistant message and canonical invocation occurrence, with mismatches
   failing closed.
2. `4cf84138de029ca8c2ec654f5a70d58d50cf6b81` — the controlled lifecycle
   projection may append current bound history without weakening immutable
   accepted legacy lineage.
3. `fdbdfb72cb32a1d7c42bc9a0d5f19eba023d5a30` — durable marker stop intent
   projects `paused` rather than synthetic `running`/`attention`; tmux/process
   facts remain orthogonal diagnostics.
4. `938a06797718dd95ef7d6bf9d9a2b1f3d97261be` — typed hard-quota guidance
   preserves `quota_exceeded`, forbids immediate retry, and directs the
   operator to restore credits/capacity or wait for the provider reset before
   retrying the same Codex step exactly once. Transient rate-limit handling is
   unchanged.

Exact deployed identity:

- commit `fdbdfb72cb32a1d7c42bc9a0d5f19eba023d5a30`;
- tree `05a77aa883d06df09d745b01047e64d1f75e8267`;
- runtime digest
  `d1f9cd20568f3fe325ea384c7adf7df8d9bba61de651ef95011e51361bf71a7b`;
- launch-seed `content_sha256`
  `7cd0f51f2ec028418209bb0511e4c70b3791b0ad2b8c070766f56ef6130f7504`;
- resident epoch `critique-attempt10-fdb-live-20260804-0149`, container
  `8be0aa325b119a00f8c62e7e4a4b2e0cb5e499999759cca4384201469f361430`,
  image
  `sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20`,
  health `healthy/discord_ready`, `listener_only=true`.

An isolated runtime venv is launch-authoritative only when created with
`python -m venv --copies` and the launch seed/receipt attests the copied venv
interpreter's exact path and digest. Attesting only the base interpreter or a
symlink-resolved identity is insufficient and must fail closed.

### Current post-Attempt-10 deployment

The active launch authority now supersedes the fdb deployment above:

- commit `938a06797718dd95ef7d6bf9d9a2b1f3d97261be`;
- tree `1491779cff3d48cf3ce8c16dfcf3656623da115e`;
- runtime digest
  `ac583f5a3832a330968d7113e88e38320f3534879e79cd8235a4056f90d9e169`;
- launch-seed `content_sha256`
  `d8d5a9575cae4e39660e6ca88b4c10ebbcda7e314e1ce837c2f977495a81bc3b`;
- resident epoch `critique-attempt10-quota-938-live-20260804-0204`, container
  `085976dfe61c388c96326cbef2d1b4bb9770493bc8d9df618e930d31bfd69bf9`;
- 219 cloud tests passed.

This was a code/runtime hardening deployment only. It did not invoke Finalize,
create ordinal 11, or resume r5. The chain remains paused/gated with Attempt 10
terminal `quota_exceeded`. Every future capacity preflight and sole retry must
attest this 938 identity and launch seed, not the historical fdb deployment.

### Immutable Attempt 10 result

- phase-WBC attempt: `646ab9ed-2706-5be8-a249-7b52e49ac102`;
- ordinal: `10`; invocation: `b437b9ee2a8b4c37`; run:
  `cl2-wbc-backed-ledger-20260803-1357`; step: `finalize`;
- worker-WBC attempt: `b0e96460-a8d7-5577-9b5f-4ed080e18c71`;
- occurrence:
  `de3040a3c789bdaa92330e08c5f8ade7cbda3136d8015194e02141d4608678ce`;
- repair-0 receipt:
  `sha256:6fa1eac08c732ade7116a3fa30160b807cdc3562388de150156a5bcb582051f4`;
- terminal event: `FAILED`; outcome: `indeterminate`; typed error:
  `quota_exceeded`.

This is not a completed WBC. Both the cloud and local same-model Sol probes
hard-failed quota, displaying reset times on Aug 9 at 11:06 AM and 1:06 PM
respectively; the Codex display supplied no timezone. No alternative authorized
Sol credential exists. r5 is `gated`, active step is null, marker
`should_run=false`, and canonical status is `paused`. It must not be resumed or
redriven by `auto`, chain, watchdog, shell, or operator retry loops.

### Sole authorized forward procedure

1. Replenish or explicitly authorize Sol capacity for the same
   `codex:gpt-5.6-sol:high` route. Re-probe once; do not switch model,
   provider, credential, or reasoning level implicitly.
2. Reattest the exact 938 runtime, launch seed, and `--copies` venv interpreter.
   Re-read r5 and require `gated`, no active step, `should_run=false`, paused,
   Attempt 10 terminal `FAILED`, and no ordinal 11.
3. From that attested interpreter, invoke the direct Finalize phase exactly once
   against the same plan in the same r5. The invocation must create exactly one
   fresh ordinal 11 phase/worker occurrence. Do not wrap it in `auto`, chain
   resume, a shell retry, or a deterministic retry loop.
4. Before any resume, require ordinal 11 terminal `COMPLETED`, authenticated
   exact-response receipt, immutable Finalize publication/mutation receipts, no
   active Finalize owner, lifecycle `finalized`, and `next_step=execute`. A
   second quota/error outcome leaves r5 paused and authorizes no automatic
   ordinal 12.
5. Only then resume this same r5 once through the supported operator path.
   Require the first Execute dispatch and tiers 1–10 to be GLM-family, never
   DeepSeek or Codex. Verify `/whats-cooking` reports one current r5 from the
   fresh local snapshot builder and unchanged polls yield no duplicate Discord
   provider attempt or obsolete-session resurrection.

The cached `/workspace/.megaplan/status/cloud-status.json` is stale follow-up
work; it is not the `/whats-cooking` source, which uses a fresh builder. Repair
and attest cache generation/freshness separately so no other consumer can treat
stale cache as canonical. Nothing in this section claims ordinal 11, Execute,
the Critique epic, or the follow-up epic is complete.

## Final live-run addendum — 2026-08-04

The sole ordinal-11 procedure above completed successfully with Sol high and is
now closed. Subsequent resume-path fixes were deployed in `eac97bd5bf`,
`93ca6b69e7`, `c9239cfe79`, and `4ed98585fd`. Current launch authority is
runtime
`5572d914c38da76fa1f6f800a50ae7b1573ea451b9faf6a2b222ffe7612709d5`,
seed `933fce9e4ad2197513df715971bc2ff04ebac58ac3fd4d0aadac750b248b90a9`,
and healthy resident `critique-4ed-pause-live-20260804-1246` /
`e0740d2fcb36b36a2eb691c9a09829fb68283aa985132bcfd00508b863c64850`.

r5 has resumed. VJ2 is durably deferred (evidence hash prefix `b87f`), and
Execute run `4cc63054…` is active through `hermes:zhipu:glm-5.2`; WBC attempt
`88c958d3…` is `STARTED`. Preserve this live occurrence. Do not replay
Finalize or restart Execute to investigate the remaining M7 cursor mismatch,
the broad Finalize 414-selector/900s baseline, or the Hermes `openrouter`
provider label versus selected `zhipu` route-spec discrepancy.
