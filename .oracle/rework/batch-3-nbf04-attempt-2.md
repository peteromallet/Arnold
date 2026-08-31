# Batch 3 NBF-04 attempt 2 — Luna integration packet

## Binding and scope

This packet records the NBF-04 attempt-2 integration on cumulative checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.  It is bound to the Batch 3
execution brief (`.oracle/briefs/execution-batch-3-luna.md`, SHA-256
`1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`), the
attempt-1 packet (`.oracle/rework/batch-3-nbf04-attempt-1.md`,
`b1d84fc21d6dbf56e47c6813373eb1f1476c1b4ba5ba532ec1da66d58d3fed59`), and
the attempt-1 Luna review brief (`.oracle/briefs/review-batch-3-nbf04-luna.md`,
`cf0bf486da547414b2fa11e68fcc52795df39faed304b838765560b81cdf9835`).

Frozen inputs were unchanged: plan
`0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`, tasklist
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`,
North Star `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`,
agent goal `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`,
and custody `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.

Scope is NBF-04 only: durable signal disposition, TERM/KILL confirmation,
same-incarnation evidence, replay/idempotence, terminal reconciliation, and
inventory/audit integration. No NBF-05/06 source, generated inventory, shell
wrapper, status, execution-log, frozen-file, commit, or deployment change was
made.

## Integration change

The only new mechanical integration fix was in
`arnold_pipelines/megaplan/workers/_impl.py`: native WBC invocation now selects
the established `run(dispatch, context=...)` or legacy `run(dispatch)` call
shape by inspecting the adapter signature. This avoids retrying admission after
a signature `TypeError` while retaining legacy WBC test/adapter compatibility.
The transient direct Codex resident process group uses the canonical generic
`signal_process_group` primitive; managed workers retain the strict typed
worker-disposition door.

## Exact validation

Passed:

* NBF-04 ladder/core/disposition/terminal/confirmation/incarnation/reconciliation
  chunk: **64 passed, 1 skipped**.
* Spawned certification/WBC/ControlledFinalLaunch/native physical/handler chunk:
  **129 passed**.
* Native/OMP/managed physical doors plus handler/context: **89 passed**.
* Launcher/fan/resident/managed/operator/orphan-adjacent chunk: **92 passed**.
* `git diff --check`: passed.
* Targeted `py_compile` for changed worker, resident, incident, and WBC modules:
  passed.

The adjacent resident chunk also had two failures. The OMP resident assertion
expects `HERMES_RESIDENT_OK` while its fake launcher returns
`OMP_RESIDENT_OK`; this is the attempt-1 documented fixture mismatch. The Codex
timeout assertion did not observe its call marker after canonical process-group
termination (the marker was absent before the assertion); this remains an
environment/timing-sensitive resident fixture issue and is not an NBF-04
ledger or worker-door failure. The requested exhaustive inventory test and
broader resident suite were not started after the timebox; they remain pending.

## Candidate manifest and hashes

Source/test path manifest SHA-256:
`b785c2e5f048614f05f5462430ea22905e867c8300e1bca324aa04854857320d`

Full binary tracked+untracked source/test diff SHA-256:
`140104caf75bb6aa1137b0df35c7dc434986ff6efe00f71a33ac584f55ba45d7`

Manifest paths are the 17 changed production files and four new tests:

```
arnold_pipelines/megaplan/auto.py
arnold_pipelines/megaplan/cloud/controlled_final_launch.py
arnold_pipelines/megaplan/cloud/operator_control.py
arnold_pipelines/megaplan/cloud/worker_dispatch.py
arnold_pipelines/megaplan/custody/common_worker_dispatch.py
arnold_pipelines/megaplan/custody/wbc_runtime.py
arnold_pipelines/megaplan/incident/disposition.py
arnold_pipelines/megaplan/incident/ledger.py
arnold_pipelines/megaplan/incident/schema.py
arnold_pipelines/megaplan/managed_agent.py
arnold_pipelines/megaplan/resident/agent_loop.py
arnold_pipelines/megaplan/resident/subagent.py
arnold_pipelines/megaplan/skills/subagent-launcher/fan.py
arnold_pipelines/megaplan/skills/subagent-launcher/fan_kill.py
arnold_pipelines/megaplan/skills/subagent-launcher/fan_process.py
arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py
arnold_pipelines/megaplan/workers/_impl.py
tests/arnold_pipelines/megaplan/test_managed_signal_contract.py
tests/arnold_pipelines/megaplan/test_nbf04_ladder.py
tests/arnold_pipelines/megaplan/test_python_signal_inventory.py
tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py
```

Worktree remains intentionally uncommitted and includes pre-existing Oracle
evidence artifacts. No frozen/status/log files were modified.
