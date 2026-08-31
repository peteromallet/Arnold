# Batch 3 NBF-04 attempt 1 — Python signal review packet

Review packet only; no Oracle acceptance verdict is issued here.  It binds the
Batch 3 execution brief and the current NBF-04 candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` on
`reconcile/nbf-attempt4-2297`.  The source base is
`origin/main@798c50619204010ed3f4297fbb57988fe9381924`.

## Immutable bindings

| artifact | SHA-256 |
|---|---|
| `.oracle/briefs/execution-batch-3-luna.md` | `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/evidence/batch-2-attempt-18-sealed.md` | `7ce34484b2db4789c8ebde59175fcb2b95dcb9f5da48020dda21792a48242c1a` |

## Candidate diff and focused evidence

The current NBF-04 candidate is 10 modified production paths plus the new
Python inventory test.  Full tracked + untracked source/test diff, using
tracked `git diff --binary` bytes and `/dev/null` diffs for untracked files, is
`64c6701ab1043bc596e519e95b1b8eeb475240f94f1b707567945d57deb92448`.
The sorted 11-path source/test manifest is
`fb82e1b15aacb40aeafa292cd5325d750cdaa1ba430a2264358c09e6b82a83e8`.

The changed paths are:

- `arnold_pipelines/megaplan/cloud/operator_control.py`
- `arnold_pipelines/megaplan/incident/disposition.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/managed_agent.py`
- `arnold_pipelines/megaplan/resident/agent_loop.py`
- `arnold_pipelines/megaplan/resident/subagent.py`
- `arnold_pipelines/megaplan/skills/subagent-launcher/fan.py`
- `arnold_pipelines/megaplan/skills/subagent-launcher/fan_kill.py`
- `arnold_pipelines/megaplan/skills/subagent-launcher/fan_process.py`
- `arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py`
- `tests/arnold_pipelines/megaplan/test_python_signal_inventory.py`

Focused NBF-04 validation: 64 passed, 1 skipped, and 1 baseline failure in
`tests/resident/test_managed_provider_agent_runner.py::test_omp_resident_runner_persists_artifacts_and_resumes_exact_session`.
The failure is the pre-existing fixture/assertion mismatch
(`OMP_RESIDENT_OK` emitted versus `HERMES_RESIDENT_OK` expected); the candidate
change in that module only replaces termination calls with the canonical signal
primitive and does not alter provider output.  It remains a documented
baseline exception, not an acceptance claim.

The authority checker returned `ok: true` with zero diagnostics and
`git diff --check` passed.  The live AST discovery below is the review input;
it is not the NBF-05 generated inventory.

## Live-discovered Python classifications

| discovered site | classification and current boundary |
|---|---|
| `incident/disposition.py` direct `os.kill`/`os.killpg` | canonical signal authority; record-before-signal helper, in scope |
| `resident/agent_loop.py` TERM/KILL helper calls | worker timeout/escalation, helper-routed, in scope |
| `resident/subagent.py` INT/TERM/KILL helper calls | worker follow-up/timeout/escalation, helper-routed, in scope |
| `skills/subagent-launcher/launch_omp_agent.py` TERM/KILL | worker ladder, helper-routed, in scope |
| `skills/subagent-launcher/fan.py`, `fan_process.py`, `fan_kill.py` | fan worker/process control, helper-routed or to be confirmed, in scope |
| `cloud/operator_control.py` TERM group | non-worker lifecycle shutdown, helper-routed, in scope |
| `managed_agent.py` TERM | managed child control, helper-routed, in scope |
| `runtime/batch.py` terminate/kill | generic batch child cleanup; current reviewed exclusion pending NBF-05 classification |
| `agent/tools/terminal_tool.py` environment terminate | external sandbox cleanup; current reviewed non-worker exclusion pending NBF-05 classification |
| `bakeoff/handlers.py` tail-process terminate | external bakeoff helper cleanup; current reviewed non-worker exclusion pending NBF-05 classification |

The following are explicit `os.kill(..., 0)` liveness probes, not signals and
must remain mechanically classified as probes: `_core/phase_runtime.py`,
`_core/state.py`, `watchdog/worker_identity.py`, `resident/runtime.py`,
`managed_agent.py`, `handlers/finalize.py`, `cloud/repair_goal.py`,
`cloud/liveness_lease.py`, `cloud/m11_live_canary.py`,
`cloud/status_snapshot.py`, `cloud/current_target.py`,
`cloud/current_target_liveness.py`, `cloud/babysitter/launch.py`,
`cloud/repair_lock.py`, `custody/contracts.py`, and
`skills/subagent-launcher/fan_kill.py`.

The three generic/non-worker exclusions are narrow compatibility boundaries,
not permission to omit live discovery.  NBF-05 must assign each one a stable
inventory row, reason, and direct regression; any new or changed real signal
must block `--check` until classified.

## NBF-04 review criteria

Review the candidate against the frozen NBF-04 contract: every Python signal is
classified; timeout and TERM→wait→KILL records precede signaling; worker
context, receipt, fingerprint, PID, and process-start identity are exact;
missing context or append failure produces zero signal; admitted accepted
worker death yields one lossless `worker_disposition` and one linked canonical
terminal outcome; non-worker/already-dead/OOM records are typed without
fabrication; durable separated confirmation handles restart, PID reuse,
progress, expiry, and incarnation changes; and existing timeout/breaker
semantics remain compatible.  Check for duplicate disposition appends,
ordinary-failure coercion, signal-before-record, or wrapper-local confirmation
authority.

This packet explicitly excludes all NBF-05 shell wrapper edits, generated
inventory files, and shell/inventory acceptance.  It also excludes NBF-06
provider resilience, fallback/degradation policy, and any Batch 4 work.  No
source, test, frozen artifact, status, execution log, commit, push, merge, or
deployment was performed while preparing this packet.
