# Batch 3 NBF-04 attempt 4 — Luna integration packet

## Binding and scope

This packet binds the cumulative candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` on
`reconcile/nbf-attempt4-2297`. It supersedes the attempt-3 packet
`.oracle/rework/batch-3-nbf04-attempt-3.md` (SHA
`9155e9a44a0c66ab3fac056f389dd147994fb17f8922eab1ac7483103b1d595e`) and its
review brief (SHA
`fefd6b667a49ac6589303ad81ca702f890390f64b13e2820065132faadfdd133`).

Frozen plan/tasklist/North Star/agent-goal/custody hashes remain respectively:

* `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
* `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
* `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
* `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
* `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`

The execution brief SHA is
`1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`.
Scope is NBF-04 only. NBF-05 shell work, NBF-06 provider resilience, status or
execution-log mutation, commit, push, merge, and deploy are excluded.

## Attempt-3 findings reconciled

All three attempt-3 review findings were closed:

1. Native timeout/guard/first-byte paths now map to typed CauseKind values
   (`timeout` or `stall`); invalid legacy labels fail closed.
2. Process-start identity is normalized and reread at ladder time. The
   controlled-launch callback no longer returns a captured token, and TERM and
   KILL confirmations carry distinct stage and signal identities.
3. The resident managed timeout/exception path honors a refused or missing
   signal result by writing `cleanup_hold` and returning without `wait()`.
   It waits only after an authorized signal or typed already-dead result.
4. The no-bare guard has explicit, reviewed ledger entries for the canonical
   disposition `killpg` and the two launcher `Popen` seams. The entries are
   not used to authorize any additional signal path.

Native child registration remains additive evidence on the existing WBC
attempt: it creates no second reservation, STARTED marker, admission, or
authority. Native `_impl.py` signal requests flow through
`_native_signal_ladder` → `SpawnedChildControl` → the controlled-launch
ladder → `signal_worker_ladder`.

The four `runtime/batch.py` `Process.terminate/kill` sites are the neutral
validation-shard substrate. Live AST discovery classifies them as
`validation-shard`, and the inventory regression proves the classification is
stable. They have no managed worker execution context and are retained as a
narrow NBF-05/transitive inventory follow-up, not silently treated as worker
authority.

## Validation evidence

Focused changed-contract and adjacent WBC suites:

* **97 passed** across the Python inventory, NBF-04 ladder, managed signal,
  launcher, no-bare, worker disposition, WBC runtime, common dispatch, and
  physical-door tests.
* Resident/controlled-launch/supervision suites: **72 passed, 2 failures**.
  The failures are baseline/stale fixtures: one test requires the unrelated
  runtime-attestation seed, and one expects the stale `HERMES_RESIDENT_OK`
  output from an OMP fixture that emits `OMP_RESIDENT_OK`. Neither is caused
  by this candidate.
* Live AST discovery: **83 sites, 0 unclassified**, including the four
  explicitly reviewed validation-shard sites; no `workers/_impl.py` direct
  signal primitive remains.
* `tests/test_no_bare_subprocess.py`: passed; all current violations are
  accounted for by the frozen ledger.
* Targeted changed-module `compileall`: passed.
* `git diff --check`: passed.

Direct probes also passed for: missing-context zero-signal behavior; refused
resident cleanup with no wait; distinct TERM/KILL proof enforcement;
record-before-signal; crash recovery from a disposition without a claim;
already-dead replay with exactly one physical TERM and one terminal; dynamic
PID-reuse rejection; and typed native cause mapping.

## Candidate identity

The source/test manifest below contains 19 changed production paths, the four
new NBF-04 tests, and the changed no-bare guard (24 paths total). It excludes
the unrelated generated `evidence/m11-recovery-topology-surfaces.json` and
quarantined Oracle capture directories.

Manifest SHA-256 (sorted paths, newline-terminated):
`6ffd29fbc503d77fd830af0638e1ebdd7698bdf0082a6d5e2265759ee70b2034`

Diff SHA-256 (concatenated `git diff --binary` per manifest path, using
`/dev/null` diffs for untracked tests):
`b1e6ea8d25b30e5b016949291626b7147739b5be6291c570faefa1a01bf74087`

Paths:

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
tests/test_no_bare_subprocess.py
```

Worktree remains intentionally uncommitted. This is a Luna integration packet,
not a Batch-3 acceptance verdict; it is ready for the configured Luna review
fan and the single permitted Batch-3 Sol oracle review.
