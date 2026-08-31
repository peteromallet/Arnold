# Batch-2 attempt-3 v2 post-exit evidence-gap receipt

## Orchestration disposition

This is an orchestration integrity receipt, not executor evidence, an Oracle
review, or an acceptance verdict. The Luna-produced finding and receipt exist,
but they are not complete enough to seal as a canonical evidence manifest.
Accordingly, no file was created under `.oracle/evidence/`, and this receipt
does not authorize review, staging, commit, delivery, or Batch 3.

Audit time: `2026-08-30T18:50:33Z` through `2026-08-30T18:57:00Z`.

## Wrapper completion

The authorized v2 wrapper and all descendants had exited before the audit.
The wrapper capture root is `/private/tmp/oracle-b2-rework3-luna-v2`.

| Capture | Bytes | SHA-256 | Meaning |
|---|---:|---|---|
| `meta.txt` | 217 | `776c75c1171d1389989f14a098e588f6f69022e3a01a480c87fc60dafaf21b01` | Start `2026-08-30T18:23:25.733340000Z`, end `2026-08-30T18:49:43.433571000Z`, launcher PID `4800`, wrapper `EXIT=0` |
| `stdout.txt` | 1118 | `04c36c6075ed98884423adc8aef41f5bc865f4a20b205c857b419115490f0068` | Luna completion summary followed by launcher result `0` |
| `stderr.txt` | 464 | `f5de77c20708635ad3152c11a24573df5ec0728c0524d80f5d40a5755ba760aa` | Resolved `openai-codex/gpt-5.6-luna`, `thinking=high`, repository cwd, `done in 1577.2s (exit=0)` |

The deterministic aggregate of those three `shasum -a 256` lines is
`696bdc05dba9b63b4edacb3d1c27e4b3e363f699b6ddd9362329e74a024a703e`.
There is no separate `exit.txt`; the exact outer exit is recorded by
`meta.txt`, stdout, and stderr.

## Luna artifacts inspected

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `.oracle/findings/execution-batch-2-attempt-3-v2-luna.md` | 8619 | `7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f` |
| `.oracle/receipts/execution-batch-2-attempt-3-v2-luna.md` | 8323 | `58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b` |

Both artifacts correctly disclaim Oracle authority, bind the current candidate
and frozen identities, disclose the four frozen NBF-03 failures, and preserve
the 18 source/test paths. Their recorded per-path hashes were independently
recomputed with zero mismatches.

## Candidate and frozen identities

```text
branch megado-nbf-guard-0826
HEAD 2297fb330cdb375b4e5bd048f0d5c37d0e06db30
origin/main 798c50619204010ed3f4297fbb57988fe9381924
candidate 5da26ec5be4d13559948fe4256a114ad7626482b
candidate_parent 19deab5bb407273e7e82d40a66fc06d17af93ad4
candidate_tree e3d0376482154c4f95d2ec5809d630c4a0c32e69
source_test_diff_sha256 acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec
source_test_diff_bytes 126804
source_test_diffstat 18 paths; 1567 insertions; 75 deletions
production_diff_scope arnold_pipelines scripts
production_diff_sha256 f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549
production_diff_bytes 84905
northstar d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
tasklist 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
plan 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
agent_goal 2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864
custody 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0
execution_brief 5de88060bc2b2045ccf34ff86b08624ccc95e6f9ba909039706a31a7e8f12539
```

No untracked source/test path exists. The changed source/test inventory is:

```text
arnold_pipelines/megaplan/auto.py
arnold_pipelines/megaplan/cloud/babysitter/launch.py
arnold_pipelines/megaplan/cloud/controlled_final_launch.py
arnold_pipelines/megaplan/cloud/worker_dispatch.py
arnold_pipelines/megaplan/incident/ledger.py
arnold_pipelines/megaplan/incident/schema.py
arnold_pipelines/megaplan/workers/_impl.py
arnold_pipelines/megaplan/workers/omp.py
scripts/check_worker_admission_authority.py
tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
tests/cloud/dispatch_test_helpers.py
tests/cloud/test_controlled_final_launch.py
tests/cloud/test_dispatch_reconciliation.py
tests/cloud/test_dispatch_with_admission.py
tests/cloud/test_worker_admission_authority.py
tests/cloud/test_worker_dispatch_admission.py
tests/cloud/test_worker_dispatch_spy.py
```

## Validation evidence verified

The frozen evidence root contains 16 JSON records. Its deterministic lexical
file-manifest digest is
`3a5731511d27d75c598820596c54cf8332c482874b241770ea64ef24daeadf3a`.
The R3 evidence root contains 9 JSON records. Its corresponding digest is
`8405ad04406ba6c6a0caeb8e7d7a988e6a972c6fc2151c2088bde04693e34024`.
All 25 JSON records parse. Recomputing every embedded stdout/stderr byte count
and SHA-256 produced zero mismatches.

Observed substantive results are truthful: R3 focused/broad results were
`4/113`, `5/67`, `5/18`, and `5/13` passed, and the authority checker exited
zero. Frozen commands 1-5 passed `56`, `53`, `90`, `74`, and `254` tests.
Frozen command 6 exited one with `59 passed, 4 failed`; the artifacts disclose
that failure. The final compile and diff-check records exited zero.

## Reasons a canonical evidence manifest was refused

1. The execution brief required the literal command
   `if rg -n 'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' ...; then exit 1; fi`
   with literal argv and separate captured streams. It was not executed.
   `10-specialized-grep.json` instead records a synthetic specialized-tool
   invocation with argv `specialized functions.grep`; its stdout/stderr values
   are null. Disclosure of this substitution is truthful, but it does not
   satisfy the exact-command evidence contract.
2. The brief required every command/result/transcript digest and exact ordered
   execution. The Luna tables omit the preserved initial misordered captures
   `07.json`, `08.json`, `09.json`, and `10.json` and do not bind their JSON-file
   digests. Corrected records exist, but omitted intermediate execution remains
   part of the immutable evidence history.
3. The brief separately required captured transcripts for the exact identity
   commands (`git rev-parse`, `git show`, diff digest/name-status, untracked
   inventory, and frozen-document hashes). The Luna artifacts state their
   results but the two evidence roots contain no dedicated command records or
   transcript digests for that identity-command block.
4. The findings table describes the successful `git diff --quiet` result as
   “preserved babysitter paths differ from parent.” Exit zero proves the
   opposite: those paths are byte-identical to candidate parent
   `19deab5bb407273e7e82d40a66fc06d17af93ad4`. Later prose mostly uses the
   correct unchanged-from-parent interpretation, but the contradictory table
   statement prevents an unqualified truth seal.

These are evidence-contract defects, not an Oracle judgment about the source
implementation. The Luna artifacts remain inspectable executor material, but
must not be represented as canonically sealed by this audit.

## Mutation boundary

This audit ran only read-only hash/status/process checks and added this receipt.
It did not alter source, tests, frozen documents, prior artifacts, status,
history, staging, commits, delivery state, or Batch 3 material. No model or
reviewer was launched.
