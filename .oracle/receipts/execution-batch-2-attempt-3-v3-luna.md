# Executor receipt — Batch 2 attempt 3 v3 Luna

**Status: executor evidence recorded; correction only.** This is not an Oracle
review, gate, verdict, or acceptance token. It does not authorize source/test
changes or any later batch.

## Immutable bindings

```text
repository /Users/peteromalley/Documents/Arnold-oracle-nbf
branch megado-nbf-guard-0826
HEAD 2297fb330cdb375b4e5bd048f0d5c37d0e06db30
source_base origin/main@798c50619204010ed3f4297fbb57988fe9381924
candidate 5da26ec5be4d13559948fe4256a114ad7626482b
candidate_parent 19deab5bb407273e7e82d40a66fc06d17af93ad4
candidate_tree e3d0376482154c4f95d2ec5809d630c4a0c32e69
candidate_source_test_diff acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec
candidate_source_test_diff_bytes 126804
candidate_production_only_diff f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549
attempt3_packet ff19d01688124ef3b77dba28ab24c28da71b395838c645a3a34f7b580c24c1e2
attempt3_triage_receipt 5d08b2b2f31a8a85f602c449311bd05a775711f298db963a8bc611f81abfab38
timeout_receipt 678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df
prior_v2_brief 5de88060bc2b2045ccf34ff86b08624ccc95e6f9ba909039706a31a7e8f12539
prior_v2_finding 7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f
prior_v2_receipt 58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b
frozen_tasklist 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
frozen_northstar d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
frozen_plan 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
frozen_goal 2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864
frozen_custody 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0
```

The listed v2 hashes were rechecked from the current immutable files. The
North Star was also read byte-for-byte and matched its fixed digest. Full
finding detail is in
[the corrected finding](../findings/execution-batch-2-attempt-3-v3-luna.md).

## Prior v2 artifact recheck

| File | Current SHA-256 |
|---|---|
| `.oracle/briefs/execution-batch-2-attempt-3-v2-luna.md` | `5de88060bc2b2045ccf34ff86b08624ccc95e6f9ba909039706a31a7e8f12539` |
| `.oracle/findings/execution-batch-2-attempt-3-v2-luna.md` | `7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f` |
| `.oracle/receipts/execution-batch-2-attempt-3-v2-luna.md` | `58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b` |
| `.oracle/receipts/execution-batch-2-attempt-3-timeout.md` | `678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |

## Corrected commands 07–10

The prior v2 finding's raw claim is preserved here exactly:

> `PASS — preserved babysitter paths differ from parent`

That claim's interpretation was wrong. For `git diff --quiet <base> -- <paths>`,
exit `0` means no differences and exit `1` means a difference exists. Thus the
prior command 07 exit `0` means the selected paths were preserved unchanged
relative to its parent. The v2 files were not rewritten.

| # / role | Literal prior argv | UTC start → end | Exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---:|---|---|---:|---|---|
| 07 preservation | `[/bin/bash, -lc, "git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- arnold_pipelines/megaplan/cloud/babysitter/routing.py skills/babysitter/scripts/render_babysitter_goal.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py"]` | `2026-08-30T18:39:30.251717+00:00` → `2026-08-30T18:39:30.313251+00:00` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 08 three-file shasum | `[/bin/bash, -lc, "shasum -a 256 arnold_pipelines/megaplan/cloud/babysitter/routing.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py"]` | `2026-08-30T18:39:30.607384+00:00` → `2026-08-30T18:39:30.666866+00:00` | 0 | 327 / `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 09 authority checker | `[/bin/bash, -lc, "PYTHONDONTWRITEBYTECODE=1 python -B scripts/check_worker_admission_authority.py --check"]` | `2026-08-30T18:39:30.863377+00:00` → `2026-08-30T18:39:44.856107+00:00` | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 10 forbidden-symbol raw scan | Recorded argv was `[`specialized functions.grep`, `refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch`]`; recorded command field was the `if rg -n ...; then exit 1; fi` form | `2026-08-30T18:40:01.959465+00:00` → `2026-08-30T18:40:01.959757+00:00` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Prior command 10 was not a literal shell `rg` invocation. It used the
specialized repository grep tool; the fresh literal shell command below is the
required correction.

## Fresh literal raw-shell transcript

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

Literal argv: `[/bin/bash, -lc, <command above>]`.

- Start/end UTC: `2026-08-30T18:57:29Z` / `2026-08-30T18:57:29Z`
- Exit: `0`
- stdout: `0` bytes; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- stderr: `0` bytes; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Command-text SHA-256: `75b76d539959b07133a151c9f59776f8cdf5a76e182af7bea58d386ff25807c4`

The empty match is the expected success. This evidence does not substitute for
the static authority checker.

## Frozen identity transcript

The commands below were run exactly, in this order, with literal argv
`[/bin/bash, -lc, <command>]`:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/main
git show -s --format='%H%n%P%n%T' 5da26ec5be4d13559948fe4256a114ad7626482b
git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests | shasum -a 256
git diff --name-status 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests
git ls-files --others --exclude-standard -- arnold_pipelines scripts tests
```

| # | Command | UTC start → end | Exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---:|---|---|---:|---|---|
| 1 | `git rev-parse --abbrev-ref HEAD` | `2026-08-30T18:57:49Z` → `2026-08-30T18:57:49Z` | 0 | 22 / `d16a4b7e75934804a550403f7aeaede152310ae73b9091d09b5a60599bed7333` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 2 | `git rev-parse HEAD` | `2026-08-30T18:57:49Z` → `2026-08-30T18:57:49Z` | 0 | 41 / `ea3a3bb36ec3ae1a30dd542056944359cdc5c18f208eb7c352b9c8190cdaa056` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 3 | `git rev-parse origin/main` | `2026-08-30T18:57:49Z` → `2026-08-30T18:57:49Z` | 0 | 41 / `9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 4 | `git show -s --format='%H%n%P%n%T' 5da26ec5be4d13559948fe4256a114ad7626482b` | `2026-08-30T18:57:49Z` → `2026-08-30T18:57:49Z` | 0 | 123 / `b740fd69703d0377e6d0c0a993933dda9c7831a6fc2e5261308d3ee37ae7e742` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 5 | candidate diff piped to `shasum -a 256` | `2026-08-30T18:57:49Z` → `2026-08-30T18:57:49Z` | 0 | 68 / `214d396aeb581c9960051374c84d6b5d8da5900a5b1c4641552b50fc5562067` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 6 | `git diff --name-status 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests` | `2026-08-30T18:57:50Z` → `2026-08-30T18:57:50Z` | 0 | 889 / `3936e0f053ea7e36d9e58e416fce7177e0d1104fcecd757645f440c01e1a1451` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 7 | `git ls-files --others --exclude-standard -- arnold_pipelines scripts tests` | `2026-08-30T18:57:50Z` → `2026-08-30T18:57:50Z` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The candidate diff hash stdout was exactly:

```text
acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec  -
```

The identity stdout values establish:

```text
megado-nbf-guard-0826
2297fb330cdb375b4e5bd048f0d5c37d0e06db30
798c50619204010ed3f4297fbb57988fe9381924
5da26ec5be4d13559948fe4256a114ad7626482b
19deab5bb407273e7e82d40a66fc06d17af93ad4
e3d0376482154c4f95d2ec5809d630c4a0c32e69
```

The name-status stdout was exactly:

```text
M	arnold_pipelines/megaplan/auto.py
M	arnold_pipelines/megaplan/cloud/babysitter/launch.py
M	arnold_pipelines/megaplan/cloud/controlled_final_launch.py
M	arnold_pipelines/megaplan/cloud/worker_dispatch.py
M	arnold_pipelines/megaplan/incident/ledger.py
M	arnold_pipelines/megaplan/incident/schema.py
M	arnold_pipelines/megaplan/workers/_impl.py
M	arnold_pipelines/megaplan/workers/omp.py
M	scripts/check_worker_admission_authority.py
M	tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
M	tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
M	tests/cloud/dispatch_test_helpers.py
M	tests/cloud/test_controlled_final_launch.py
M	tests/cloud/test_dispatch_reconciliation.py
M	tests/cloud/test_dispatch_with_admission.py
M	tests/cloud/test_worker_admission_authority.py
M	tests/cloud/test_worker_dispatch_admission.py
M	tests/cloud/test_worker_dispatch_spy.py
```

The untracked-path stdout was empty.

## Byte, path, and hash status

A raw external capture of
`git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests`
produced exactly `126804` stdout bytes before hashing, SHA-256
`acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec`, exit
`0`; stderr was `0` bytes with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The name-status transcript contains exactly 18 `M` paths, all the candidate
source/test paths; the untracked-path transcript is empty. Their current SHA-256
values are:

```text
5c19b32ebba4a1427dd7f8af4769a4dab1996a3b0cbb04dc3b516754cd5d0ec0  arnold_pipelines/megaplan/auto.py
ee17fe049cbf34bfc5a6288ef3ac9849bdcf8eb51e03650a3a24b4101a63bcdb  arnold_pipelines/megaplan/cloud/babysitter/launch.py
56e95131d86637a6ff0a64ddb894314e80c4cd1460747e8129e7af7e3424b474  arnold_pipelines/megaplan/cloud/controlled_final_launch.py
0928ad9bd5ae9ce7c9e94d08c4650a8ee5c571b8b95b8400031773343ad853b3  arnold_pipelines/megaplan/cloud/worker_dispatch.py
20238728afdccce52177cf8f136ea1a03cac74d8f8b427fa93f9b9dc30c57b4b  arnold_pipelines/megaplan/incident/ledger.py
56f81b72de0ee22e7d86a1d18b18faeef47b5c4eaecb0c12f33db89941d4f328  arnold_pipelines/megaplan/incident/schema.py
09a2938e966808b32d043362eb1e3801f0eff1fe3b33a5c0eff7dd58a429063a  arnold_pipelines/megaplan/workers/_impl.py
220738cff08b34216f0ff5233a5536d8904cf6db5c58bded7a4ea11f807bbbf1  arnold_pipelines/megaplan/workers/omp.py
12d276d30dc28c6776cd8b75463befedb62dfc3798dcb06ddec8523c80b1a665  scripts/check_worker_admission_authority.py
272e1bc3a7360f4566fbe6f3a079eb71497b75291aba0d93ea296004d3bfcac5  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
a7d727c47434a541b4632f5eea73bb15ec8d677faccb79f34eeccd2bfc9c73a2  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py
e4338c4fea624082e1d8876b02bb32fcd2074a09544c509bd449c8783c5cb770  tests/cloud/dispatch_test_helpers.py
a10beccdef6ca329131759f5f6e8d8c0577af9d7218c2ba7a1329d1b43be3d04  tests/cloud/test_controlled_final_launch.py
61b692a3ab38060e1145c82f454ec1ace48dd7296729adb42aa35ac0b6b36d0a  tests/cloud/test_dispatch_reconciliation.py
f6bac8f37c80bee50161d2795d30c4d7bc1c89ed034235866e5b7dfaf1e8cf19  tests/cloud/test_dispatch_with_admission.py
f13a20df1c3f248f863f7baf56c07cb85b789ee089e264f9019cc606f0f7f0e2  tests/cloud/test_worker_admission_authority.py
f399b6b1c10339f253243518fdd04132c0368a23e602080336d1a8d29082ec51  tests/cloud/test_worker_dispatch_admission.py
74b11a527c90f5a04ef8f29d5a4503ce2e74e70a4d2ee7979a8e2c3962da0dca  tests/cloud/test_worker_dispatch_spy.py
```

## External stream digest ledger

External evidence root: `/tmp/nbf-batch2-attempt3-v3-luna-evidence`.
All listed captures used separate stdout and stderr files. The command-text
SHA is included where recorded.

| Capture | Start → end UTC | Exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 | command-text SHA-256 |
|---|---|---:|---|---|---|
| literal raw `rg` | `18:57:29Z` → `18:57:29Z` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `75b76d539959b07133a151c9f59776f8cdf5a76e182af7bea58d386ff25807c4` |
| identity 1–4 | `18:57:49Z` → `18:57:49Z` | 0 each | `22 / d16a4b7e75934804a550403f7aeaede152310ae73b9091d09b5a60599bed7333`; `41 / ea3a3bb36ec3ae1a30dd542056944359cdc5c18f208eb7c352b9c8190cdaa056`; `41 / 9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430`; `123 / b740fd69703d0377e6d0c0a993933dda9c7831a6fc2e5261308d3ee37ae7e742` | 0 / empty SHA each | individually recorded in `02`–`05-meta.txt` |
| identity 5 | `18:57:49Z` → `18:57:49Z` | 0 | 68 / `214d396aeb581c9960051374c84d6b5d8da5900a5b1c4641552b50fc5562067` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e8adf405ed04b7f4ebe464316f93b7551eb01487042b7111f78fe33900dbf8a3` |
| identity 6 | `18:57:50Z` → `18:57:50Z` | 0 | 889 / `3936e0f053ea7e36d9e58e416fce7177e0d1104fcecd757645f440c01e1a1451` | 0 / empty SHA | `7de3b4b0400d3fea1c91355c246c0de1b70f42d51a322312ac9238418fb9f61e` |
| identity 7 | `18:57:50Z` → `18:57:50Z` | 0 | 0 / empty SHA | 0 / empty SHA | `de38a9082ba42df172cdccd20014832e04b4339c08f58b4e6c94ec7bd08aa30a` |
| raw candidate diff | `18:58:30Z` → `18:58:30Z` | 0 | 126804 / `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` | 0 / empty SHA | `17864f2e6ea4631c04f844e61cee87b228ec79427334ef1122f20d1d227adb3c` |
| fresh preservation | `18:58:58Z` → `18:58:58Z` | 0 | 0 / empty SHA | 0 / empty SHA | `ca23f638a82c19026e5c45517086243142294438973bd5ece6ca86ca12e46b35` |
| fresh three-file shasum | `18:58:58Z` → `18:58:58Z` | 0 | 327 / `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8` | 0 / empty SHA | `87bf6f8c66c29204a0e16816cca4d335484a1891890ef0fbac32143013fa4793` |
| fresh authority checker | `18:58:59Z` → `18:59:08Z` | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | 0 / empty SHA | `dd3313f1d9e7db9ec5c148a6a1e5c0180b427489dcdc8b2d8dc1ff6229a76527` |
| path hashes | `18:59:24Z` → `18:59:24Z` | 0 | 2041 / `f54f6cbe47d6920527397969feb5359578de19db19505455bf45b598b06f5d73` | 0 / empty SHA | `db54aa952c40c0767c560a061cff41c770d6c453f1a5b7cea72b0cc655fd0ced` |
| artifact hash recheck | `19:00:05Z` → `19:00:05Z` | 0 | 573 / `861c8601b4bda2573911d6eacfd0e123f0d2b83338ea1dd0400782e0cf23b833` | 0 / empty SHA | `6e12ea420b1b0ed8eb18b00ca207ba9effb9d957cfae9c405e962dfaeb67b5ab` |

For every `empty SHA` entry, the value is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Boundary and non-decision statement

No source/test/frozen-document/status/custody/goal/tasklist/history/index
mutation occurred. No review, nested model, delegation, OMP, Megado, Megaplan,
reviewer, fallback, commit, stage, push, merge, or Batch-3 action occurred.
Only this receipt and the paired finding were created, after evidence capture.
This correction records executor evidence, corrects the `git diff --quiet`
meaning, and does not issue an Oracle judgment, verdict, or acceptance token.
