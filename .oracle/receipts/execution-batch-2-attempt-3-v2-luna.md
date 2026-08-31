# Executor receipt — Batch 2 attempt 3 v2 Luna

Status: executor evidence recorded; not an Oracle review or verdict.

## Immutable binding

```text
branch megado-nbf-guard-0826
HEAD 2297fb330cdb375b4e5bd048f0d5c37d0e06db30
origin/main 798c50619204010ed3f4297fbb57988fe9381924
candidate 5da26ec5be4d13559948fe4256a114ad7626482b
candidate_parent 19deab5bb407273e7e82d40a66fc06d17af93ad4
candidate_tree e3d0376482154c4f95d2ec5809d630c4a0c32e69
candidate_source_test_diff acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec
final_production_diff f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549
northstar d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e
tasklist 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589
plan 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1
agent_goal 2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864
custody 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0
```

All four rework slices passed their focused and broad suites. Existing partial source/test work was preserved; this continuation made no source/test edits. The full findings and rationale are in [the findings artifact](../findings/execution-batch-2-attempt-3-v2-luna.md).

## R3 command evidence

All commands used literal argv `[/bin/bash, -lc, <command>]`, UTC timestamps, separate stream byte counts/SHA-256, and post-command porcelain capture in `/tmp/nbf-batch2-attempt3-v2-luna-r3-evidence`.

| Command | UTC start | UTC end | exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---|---|---|---:|---|---|
| native focused | 2026-08-30T18:41:42.904252+00:00 | 2026-08-30T18:41:45.813605+00:00 | 0 | 98 / `44091516c6f7d278c9900d796163d45f95d1ad1819370ffeeaf887bc704f2e38` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| native broad | 2026-08-30T18:41:45.920372+00:00 | 2026-08-30T18:42:59.416849+00:00 | 0 | 191 / `8d65225305adc8e95ccfa4247a29cbfc4ba63e3c0f1958a70fc19df68a353eca` | 0 / same empty-stream SHA |
| terminal focused | 2026-08-30T18:42:59.544965+00:00 | 2026-08-30T18:43:03.099329+00:00 | 0 | 98 / `a86fbc1eaf8fe3346837ab279229e9eb1b6170e862c47dae08b324a37c72100c` | 0 / same empty-stream SHA |
| terminal broad | 2026-08-30T18:43:03.219861+00:00 | 2026-08-30T18:43:21.081917+00:00 | 0 | 100 / `d5105a2a2a31b25f0783d20632c0e7c26f3c81b6ba8f51bb092303067a8d0afd` | 0 / same empty-stream SHA |
| lifecycle focused | 2026-08-30T18:43:21.175776+00:00 | 2026-08-30T18:43:23.734375+00:00 | 0 | 98 / `5c9258a0de83f38243aa16ddbdf4932629810a56e692fb8852a52f3a6f665024` | 0 / same empty-stream SHA |
| lifecycle broad | 2026-08-30T18:43:23.824692+00:00 | 2026-08-30T18:43:26.415396+00:00 | 0 | 99 / `4fbfe0b2c326209cdd318cb4bc315f4ff4bc437d80e9898c1ae537c63f35375d` | 0 / same empty-stream SHA |
| authority focused | 2026-08-30T18:43:26.500522+00:00 | 2026-08-30T18:44:33.390359+00:00 | 0 | 109 / `0407c81f58a87403f115aa0196e1c68d7be7a22d330f09eabf4c946a853e91ff` | 0 / same empty-stream SHA |
| authority broad | 2026-08-30T18:44:33.493496+00:00 | 2026-08-30T18:46:35.804659+00:00 | 0 | 111 / `489cd4744986b1a46608752c592c91f6f46125cfc871ea7ba364743cd32906aa` | 0 / same empty-stream SHA |
| authority script | 2026-08-30T18:46:35.935561+00:00 | 2026-08-30T18:46:46.860356+00:00 | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | 0 / same empty-stream SHA |

## Frozen command evidence

Fresh root: `/tmp/nbf-batch2-attempt3-v2-luna-evidence`. Each JSON record contains the literal command, UTC start/end, argv, exit code, stream counts/digests, pre/post porcelain, and hashes for all 18 changed source/test paths.

| # | UTC start | UTC end | exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---:|---|---|---:|---|---|
| 1 | 2026-08-30T18:32:32.005660+00:00 | 2026-08-30T18:33:05.374214+00:00 | 0 | 100 / `6ce6d7abe3234c2938579445b8632691407810ca9e9e4a05b15779c356214628` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 2 | 2026-08-30T18:33:05.574313+00:00 | 2026-08-30T18:33:12.374995+00:00 | 0 | 99 / `b1d5100ae101808494b1abe3ecb9366c9f5d61fea7960e5d2f1e78b6c9632b88` | 0 / same empty-stream SHA |
| 3 | 2026-08-30T18:33:12.618195+00:00 | 2026-08-30T18:34:02.715148+00:00 | 0 | 180 / `9c001d8b22cff0472ed4c03ce27f0999b42e85607cb6aa354026fc409c8f606d` | 0 / same empty-stream SHA |
| 4 | 2026-08-30T18:34:02.916279+00:00 | 2026-08-30T18:34:06.234560+00:00 | 0 | 179 / `79f8afeb3e812347d4d6f9ebe94697f1de19ae26a98d7b296d7fe5517ed1cb09` | 0 / same empty-stream SHA |
| 5 | 2026-08-30T18:34:06.434416+00:00 | 2026-08-30T18:35:36.756201+00:00 | 0 | 351 / `6236aee318b79882976d9015f9333c3ad326fb902c98cd2ea3a0aacd6ac1eea6` | 0 / same empty-stream SHA |
| 6 | 2026-08-30T18:35:36.955884+00:00 | 2026-08-30T18:38:06.426509+00:00 | 1 | 7044 / `d393b85f46c796ea6488d7ac096cd642870f43d2d7bfcdaef52c7bd07efb02d2` | 0 / same empty-stream SHA |
| 7 | 2026-08-30T18:39:30.251717+00:00 | 2026-08-30T18:39:30.313251+00:00 | 0 | 0 / empty-stream SHA | 0 / empty-stream SHA |
| 8 | 2026-08-30T18:39:30.607384+00:00 | 2026-08-30T18:39:30.666866+00:00 | 0 | 327 / `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8` | 0 / same empty-stream SHA |
| 9 | 2026-08-30T18:39:30.863377+00:00 | 2026-08-30T18:39:44.856107+00:00 | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | 0 / same empty-stream SHA |
| 10 | 2026-08-30T18:40:01.959465+00:00 | 2026-08-30T18:40:01.959757+00:00 | 0 | 0 / empty-stream SHA | 0 / empty-stream SHA |
| 11 | 2026-08-30T18:40:24.748343+00:00 | 2026-08-30T18:40:24.964903+00:00 | 0 | 0 / empty-stream SHA | 0 / empty-stream SHA |
| 12 | 2026-08-30T18:40:25.180497+00:00 | 2026-08-30T18:40:25.244871+00:00 | 0 | 0 / empty-stream SHA | 0 / empty-stream SHA |

Command 6: `4 failed, 59 passed`. Failures are the two pre-existing babysitter routing expectations and two pre-existing single-flash renderer expectations. Commands 7–12 passed. The command 10 shell `rg` was represented by the required specialized grep tool; no forbidden symbols matched. This deviation is explicit.

## Final source/test path hashes

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

No commits, staging, pushes, merges, frozen-artifact mutations, or Batch 3 actions were performed.
