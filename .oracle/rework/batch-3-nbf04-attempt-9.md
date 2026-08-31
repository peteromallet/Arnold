# Batch 3 NBF-04 — attempt 9 integration packet

## Binding and scope

This packet binds the cumulative candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` on
`reconcile/nbf-attempt4-2297`. It supersedes the attempt-5 packet and records
the attempt-6 through attempt-9 custody fixes. Scope is NBF-04 only: canonical
signal disposition, typed confirmation, PID/start incarnation safety, WBC
handoff custody, terminal reconciliation, and the live Python inventory. NBF-05,
provider resilience, status/execution-log mutation, commit, push, merge, and
deploy remain excluded.

Frozen identity hashes:

* plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
* tasklist `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
* North Star `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
* agent goal `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
* custody `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
* execution brief `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`

## Attempt history and reconciled fixes

1. Attempts 1–4 established the canonical disposition/confirmation ladder,
   one WBC and one lifecycle authority, dynamic PID/start checks, resident
   cleanup holds, and explicit inventory/no-bare classifications.
2. Attempt 5 closed native timeout blockers: explicit plan-authorized
   immediate timeout, record-before-TERM/KILL, distinct deterministic signal
   identities, crash-after-KILL replay, and already-dead observation linkage.
   The frozen plan explicitly permits an immediate-timeout path when its
   authorization is explicit; it does not claim sustained two-scan proof.
3. Attempt 6 linked pre-timeout already-dead children to one canonical
   observation and ordinary terminal without signal attribution.
4. Attempt 7 added durable identity-bound spawn cleanup handoff and typed
   natural-death/permanent-hold reconciliation.
5. Attempt 8 made permanent holds replay-idempotent, retained lawful parent
   handles, and separated accepted natural-death terminalization from
   pre-acceptance permanent custody holds.
6. Attempt 9 fixed wrapper unwrapping of `SpawnCleanupHold.process`, preserved
   serializable hold metadata, returned canonical handoff/event references,
   normalized replayed JSON tuple/list shapes, propagated typed
   `unresolved_launch`, and classified the new `os.kill(pid, 0)` liveness probe.

The pre-acceptance rule is deliberate: a child that dies before an accepted
launch marker has no lawful worker terminal attribution. It remains a durable
hold with no inferred success, failure, or signal disposition. Accepted
natural death records exactly one observation and ordinary terminal, and only
an available parent-owned handle may reap.

## Focused gate evidence

The existing cumulative gate contains **218 passing checks** across the NBF-04
ladder, disposition/lifecycle, controlled/native, WBC, managed, launcher,
resident, authority, inventory, and no-bare evidence sets. The attempt-9
control-side rerun passed **51 tests**, including the complete focused
controlled launch, common WBC, managed signal, and Python inventory suites.
Additional handoff/unresolved tests passed **8 tests**.

Targeted compileall and `git diff --check` passed. Direct `/bin/sleep`
probes covered wrapper handoff and retained handle, accepted natural death
with and without a restart-style Popen handle, duplicate natural-death replay,
pre-acceptance death hold, PID reuse hold without signaling, and typed
`unresolved_launch` propagation. No signal was emitted by any custody test.

Known stale/baseline classifications remain explicit: unrelated runtime
attestation seed absence; the OMP fixture's `OMP_RESIDENT_OK` versus stale
`HERMES_RESIDENT_OK` assertion; and the old provider-timeout `124` expectation
versus the current cleanup-hold `75` contract. These are not candidate
regressions and are outside this NBF-04 control-side packet.

## Exact candidate identity

The sorted tracked+untracked source/test manifest contains **25 paths**. It
excludes all quarantined Oracle artifacts and unrelated generated evidence.

Manifest SHA-256 (newline-terminated sorted paths):
`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`

Diff SHA-256 (concatenated `git diff --binary` bytes per path, `/dev/null`
diffs for untracked tests):
`1c4087c1ab54e275e881895aa9e5219d3e52dc02d3308e8d0600d405f46067dd`

```text
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
tests/arnold_pipelines/megaplan/test_managed_signal_contract.py
tests/arnold_pipelines/megaplan/test_nbf04_ladder.py
tests/arnold_pipelines/megaplan/test_python_signal_inventory.py
tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py
tests/cloud/test_controlled_final_launch.py
tests/test_no_bare_subprocess.py
```

Worktree remains intentionally uncommitted. This packet is ready for fresh
Luna semantic review and the permitted final Sol oracle review; it does not
authorize execution, merge, deployment, or epic launch.
