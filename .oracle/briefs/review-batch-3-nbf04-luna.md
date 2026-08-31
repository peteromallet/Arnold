# Luna review brief — Batch 3 NBF-04 attempt 1

Perform one independent, read-only GPT-5.6 Luna review of the NBF-04 Python
signal candidate in `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4`.
Do not edit source, tests, frozen inputs, status, execution log, or prior
artifacts; do not commit, stage, push, merge, deploy, launch another agent, or
issue a Sol verdict.

## Exact custody binding

- Candidate checkpoint: `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`
- Parent checkpoint: `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Batch 3 brief SHA: `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`
- Frozen plan/tasklist/North Star/goal/custody SHAs:
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`,
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`,
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`,
  `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`,
  `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.
- Attempt packet: `.oracle/rework/batch-3-nbf04-attempt-1.md`

## Review scope

Review only NBF-04: Python timeout, TERM/KILL ladder, resident/fan/launcher
signals, managed and operator lifecycle signals, canonical disposition and
terminal linkage, worker context identity, durable confirmation, OOM/unknown
death semantics, and the live Python classification table in the bound packet.
Use the current 10 modified production paths plus
`tests/arnold_pipelines/megaplan/test_python_signal_inventory.py`.

Run focused no-cache/no-bytecode checks where safe:

```text
python scripts/check_worker_admission_authority.py --check
git diff --check
python -m pytest -p no:cacheprovider \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/resident/test_managed_provider_agent_runner.py
```

The current run is 64 passed, 1 skipped, and one documented resident fixture
baseline mismatch (`OMP_RESIDENT_OK` versus expected `HERMES_RESIDENT_OK`).
Assess whether any failure is candidate-caused; do not blanket-waive new
failures.  Confirm the full tracked+untracked source/test diff SHA
`64c6701ab1043bc596e519e95b1b8eeb475240f94f1b707567945d57deb92448` and path
manifest SHA `fb82e1b15aacb40aeafa292cd5325d750cdaa1ba430a2264358c09e6b82a83e8`.

Do not review or modify NBF-05 shell wrappers/generated inventory, NBF-06
provider resilience, or any later batch.  Report concrete evidence, every
discovered signal classification/exclusion, baseline/environment exceptions,
and a clear NBF-04 disposition without fabricating a final Batch 3 gate.
