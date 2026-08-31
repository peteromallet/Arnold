# Batch 3 NBF-04 attempt 3 — Luna reconciliation packet

## Binding and scope

This attempt reconciles the cumulative candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`. It binds attempt2 packet
`.oracle/rework/batch-3-nbf04-attempt-2.md` (SHA `61d85b9f6d6d8fde4069df9d63c89f9c728d5562ba1e80e04dc7c76a0d901ece`),
attempt2 review brief `.oracle/briefs/review-batch-3-nbf04-attempt-2-luna.md`
(SHA `cf87109c74dd37074fece2c3fb618df9fe07a53ab70053bfa0e1100c265383cb`),
and the Batch3 execution brief (SHA
`1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`).

Frozen plan/tasklist/North Star/agent-goal/custody hashes remain respectively
`0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`,
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`,
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`,
`2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`, and
`94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.

Scope is NBF-04 only: signal ladder, durable confirmations, identity/incarnation,
terminal reconciliation, launcher/resident integration, and audit coverage.
No NBF05/06 work, status/log/frozen mutation, commit, merge, push, or deploy was
performed. Child certification continues to reuse the existing WBC attempt.

## Reconciliation

No production redesign was required. The cumulative implementation was verified
through the actual native, OMP, managed, handler, WBC, launcher, fan, resident,
operator, orphan, and timeout paths. The prior mechanical native WBC adapter
remains intact. The current cumulative diff additionally contains custody export
and watchdog identity helper edits from the parallel integration; they are
included in the manifest below.

## Validation

* Core ladder/stage confirmation/replay/terminal/incarnation/reconciliation:
  **71 passed, 1 skipped**.
* Spawned certification/WBC/lifecycle/native physical/OMP/managed doors:
  **99 passed**.
* Launcher/fan/resident/managed/operator/orphan-adjacent chunk:
  **93 passed, 2 failed**.
* Exhaustive Python signal inventory: **5 passed**.
* Identity helper/PID-reuse/admission chunk: **94 passed, 1 failed**.
* Authority checker: `ok: true`, zero diagnostics, three configured doors.
* `git diff --check`: passed.
* Targeted changed-module compilation: passed.

The two resident failures are the previously documented OMP fake output
(`HERMES_RESIDENT_OK` versus `OMP_RESIDENT_OK`) and a timing-sensitive Codex
fixture whose call marker is absent when the canonical process-group termination
occurs. The identity chunk's one failure is the existing watchdog manifest-order
fixture. The separate no-bare-subprocess guard reports three unledgered existing
surface violations: canonical generic `os.killpg` in `incident/disposition.py`
and launcher `subprocess.Popen` in `fan.py` and `launch_omp_agent.py`. No frozen
deferral ledger was changed. These are recorded as remaining review risks, not
silently waived.

## Candidate hashes

Full tracked+untracked source/test path manifest SHA-256:
`13ac3bdb09658124a526bc3d9100257cab54a0dbcca6a53e5d577607c74443e3`

Full binary tracked+untracked source/test diff SHA-256:
`0d54a97670986c4f298090c53755f1b2fd348fd643013cc84078d34dda3fda12`

The manifest contains the 19 changed production paths:

```
arnold_pipelines/megaplan/auto.py
arnold_pipelines/megaplan/cloud/controlled_final_launch.py
arnold_pipelines/megaplan/cloud/operator_control.py
arnold_pipelines/megaplan/cloud/worker_dispatch.py
arnold_pipelines/megaplan/custody/__init__.py
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
arnold_pipelines/megaplan/watchdog/worker_identity.py
arnold_pipelines/megaplan/workers/_impl.py
```

and the four untracked NBF-04 tests:

```
tests/arnold_pipelines/megaplan/test_managed_signal_contract.py
tests/arnold_pipelines/megaplan/test_nbf04_ladder.py
tests/arnold_pipelines/megaplan/test_python_signal_inventory.py
tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py
```

Worktree is intentionally uncommitted; frozen files, status, and execution log
are untouched.
