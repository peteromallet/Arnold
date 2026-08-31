# Batch 3 NBF-04 — attempt 5 Luna integration packet

## Binding and scope

This packet binds the cumulative candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` on
`reconcile/nbf-attempt4-2297`. It supersedes attempt 4
(`.oracle/rework/batch-3-nbf04-attempt-4.md`). Scope is NBF-04 only;
NBF-05 shell work, NBF-06 provider resilience, unrelated fixture migration,
status/execution-log mutation, commit, push, merge, and deploy remain excluded.

Frozen identity hashes:

* plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
* tasklist `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
* North Star `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
* agent goal `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
* custody `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
* execution brief `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`

## Attempt-5 blocker closure

Native timeout/stall supervision now resolves the WBC-bound controlled-launch
authority's explicit immediate-timeout path. The path validates the admitted
worker identity and current process-start identity, records TERM and KILL
dispositions before their physical callbacks, and appends one terminal only
after observing death. Native callback wrappers resolve the same bound authority
through their signal implementation; no second authority or reservation is
created.

Structured ladder results are no longer coerced by object truthiness: only
`killed` and `already_dead` count as handled. Pending/refused/unresolved results
remain hard failures at the native boundary.

The immediate path carries explicit durable authorization evidence
(`native-immediate-timeout`, timeout source, and `explicit-timeout-v1`) rather
than pretending to have a sustained two-scan confirmation. Replay checks use
deterministic TERM/KILL disposition IDs, never resend an existing signal claim,
and reconstruct the terminal after a crash between KILL and terminal projection.
PID-start identity is reread before TERM, between TERM and KILL, and the
terminal is linked to the accepted launch marker. Existing stale/reused
confirmation cases remain covered by the NBF-04 ladder tests.

## Validation

Completed focused subsets:

* disposition/lifecycle, inventory, launcher, and no-bare gate: **24 passed**;
* native/controlled/ladders/no-bare regression set: **19 passed**;
* resident-only recovery/reconcile-down: **29 passed**;
* resident provider/launcher subset: **71 passed, 3 stale fixture failures**.
* targeted compileall and `git diff --check`: passed.

The three resident failures are known baseline/contract fixtures, not candidate
regressions: missing unrelated runtime-attestation seed in the Discord-origin
test; stale `HERMES_RESIDENT_OK` expectation for an OMP fixture now returning
`OMP_RESIDENT_OK`; and the old provider-timeout expectation of 124 where the
current cleanup-hold contract returns 75. A larger aggregate worker/WBC command
exceeded the local command-output window before emitting its final summary; no
failure output appeared, so its result is not claimed as a separate pass count.

Direct probes passed for `/bin/sleep` native timeout through the real
ControlledFinalLaunch/WBC callback, TERM-ignoring escalation with distinct TERM
and KILL records, child reaping, one-terminal replay after simulated
crash-after-KILL, and dynamic PID-start rejection. The intended path leaves no
live child; a physical callback failure remains explicitly unresolved and
fail-closed for later custody reconciliation.

## Candidate manifest and identity

The exact sorted tracked+untracked source/test manifest contains **25 paths**.
It excludes quarantined Oracle artifacts and the unrelated generated evidence
file. Manifest SHA-256 (newline-terminated sorted paths):

`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`

Diff SHA-256 (concatenated `git diff --binary` per path, `/dev/null` diffs for
untracked tests):

`04d0517706652d7e324aee4837a684bb0c5139c5e638d0bb21d38bfc15a1247c`

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

No commit, push, merge, deploy, main checkout change, or NBF-05 work was
performed. This is an integration packet awaiting independent Luna review and
the permitted final Sol oracle review.
