# Batch-2 attempt-3 Luna timeout receipt

## Executor evidence (not an Oracle review or verdict)

This append-only receipt records the failed attempt-3 execution launch.  It is
not acceptance evidence and does not authorize source/test edits, a review,
staging, commit, push, merge, Batch 3, or mutation of frozen inputs/history.
The attempt produced no finding or executor receipt.  A later leaf continuation
must treat the current partial tree as untrusted work to audit.

## Frozen launch and wrapper evidence

Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`.

Authorized command (the outer wrapper invocation):

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-3-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=7200
```

The wrapper capture is `/private/tmp/oracle-b2-rework3-luna`:

| Evidence | Bytes | SHA-256 | Observed content/meaning |
|---|---:|---|---|
| `meta.txt` | 172 | `f5b6129e409c75095bc6518a513e8b944b0d4986a13de7ad222296cffdc2f3c8` | `START_UTC=2026-08-30T16:11:47.508527000Z`; `BRIEF_SHA=7ef4af5b06937e5f32e3a09aeb96084f2f79864dbc9926166799d7b7cf90c516`; `PID=28308`; `END_UTC=2026-08-30T18:11:48.015364000Z`; `EXIT=0` |
| `stdout.txt` | 4 | `ca2ebdf97d7469496b1f4b78958f9dc8447efdcb623953fee7b6996b762f6fff` | Exactly `124\n`; this is the nested process status surfaced by the wrapper |
| `stderr.txt` | 461 | `b24906aa424c1ab49a8497431c4a533df4bbc02a6f63d6504ac3fac4e315b593` | Model resolution/high setting, cwd, and `error: omp process exceeded --timeout=7200s` |

The outer Python wrapper therefore exited `0` after reporting the inner OMP
status `124`; it was not a successful Luna execution.  Outer wall time from
the authoritative meta capture is 7200.506837 seconds.  The wrapper stderr
also states that the selected model resolved to `openai-codex/gpt-5.6-luna`,
with `thinking=high`, and that its cwd was the repository above.

## Nested process and termination evidence

The wrapper delegated to OMP despite the leaf brief's direct-execution
boundary.  The wrapper itself says: `omp gives the full toolset (Bash, Read,
Edit, web, …)`.  The nested OMP log identifies PID `28330`, provider
`openai-codex`, and model `gpt-5.6-luna`:

* `/Users/peteromalley/.omp/logs/omp.2026-08-30.28330.log`: 10,639 bytes,
  final SHA `02b5786b81a4569d6bcd88f7796cb056c5151d2d8bfb998b72c9648f50568769`.
  Its first runtime record is `2026-08-30T18:11:49.505+02:00`
  (`2026-08-30T16:11:49.505Z`); its final records are
  `2026-08-30T20:11:28.719+02:00` / `.720+02:00`
  (`2026-08-30T18:11:28.719Z` / `.720Z`).
* The final record has `stopReason:"error"`, `provider:"openai-codex"`,
  `model:"gpt-5.6-luna"`, `hasText:false`; the following record reports
  `The socket connection was closed unexpectedly` with error id `135168`.
* Observer audit `/Users/peteromalley/.omp/logs/.omp.28330-audit.json` is 405
  bytes, SHA
  `6d72b8b0c135e79e2a74649360756690bc276abbc7f24a44e57e763f759dc063` and
  records an earlier nested-log hash
  `246448f387bb494bdb9514e742d3873b25035ee11f474bcd1f5ba359ead06c07`.
  The differing final log hash is retained as evidence that the log continued
  after that observer snapshot.

This is a concrete nested delegation violation: the intended executor was
launched through `launch_hermes_agent.py`, which started OMP and a model
process.  No second independent reviewer or fanout is evidenced.  The outer
capture contains no literal SIGTERM record, and the nested log contains no
signal/kill record; consequently no SIGTERM is asserted here.  The only
recoverable termination evidence is the OMP timeout status `124`, the wrapper's
`--timeout=7200s` error, and the provider socket-close error.  Any launcher
implementation-level SIGTERM, if sent internally, was not captured by the
authoritative artifacts and must not be fabricated as observed fact.

## Missing outputs and partial tree

Neither required attempt-3 output exists:

* `.oracle/findings/execution-batch-2-attempt-3-luna.md` — absent.
* `.oracle/receipts/execution-batch-2-attempt-3-luna.md` — absent.

Immediately after the timeout, the current source/test diff against candidate
`5da26ec5be4d13559948fe4256a114ad7626482b` was captured as:

* all `arnold_pipelines scripts tests`: SHA
  `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec`;
* production-only `arnold_pipelines` diff: SHA
  `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549`;
* 18 changed paths:

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

The independently rerun production-only measurement is the binding above. No untracked
source/test paths were observed.  The next executor must audit all 18 paths,
restore accidental expansion, and preserve only justified R3 work.

## Identity bindings

| Item | SHA / identity |
|---|---|
| Branch | `megado-nbf-guard-0826` |
| Current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate / parent / tree | `5da26ec5be4d13559948fe4256a114ad7626482b` / `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Candidate canonical production+focused diff | `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0` |
| Attempt-2 execution packet / triage receipt | `cba6d2236a7bae5bd12f38f38ad775ca800ed19dc3ba79c14ac6e00d3d78ff83` / `4d1d9bde6740897e84e99ac34d050055eb7f7c12a4823f65fe2cb7e04e007ed3` |
| Attempt-2 finding / receipt | `f1e3b9521bd15e932a87be921325af901c78e9dde06fd2729d7bf502c722e7d4` / `ea9723a96c8e6d7e9cb7b68a3352d6dc34b03b81dfd47011d0599db6a7844425` |
| Attempt-3 packet / triage receipt / execution brief | `ff19d01688124ef3b77dba28ab24c28da71b395838c645a3a34f7b580c24c1e2` / `5d08b2b2f31a8a85f602c449311bd05a775711f298db963a8bc611f81abfab38` / `7ef4af5b06937e5f32e3a09aeb96084f2f79864dbc9926166799d7b7cf90c516` |
| Frozen tasklist | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Frozen agent goal | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Frozen custody | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

The frozen hashes were rechecked after the timeout and were unchanged.  This
receipt is the complete recovered timeout record; it makes no claim that the
timed-out executor implemented or validated any R3 item.
