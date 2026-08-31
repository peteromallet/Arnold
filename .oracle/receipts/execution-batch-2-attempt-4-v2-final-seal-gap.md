# Batch-2 attempt-4 v2 final-seal evidence gap

Audit start: `2026-08-30T21:22:51Z`.

This is an independent evidence-integrity receipt, not executor evidence, a
review, an Oracle adjudication, or a Batch-2 verdict. No production source,
tests, frozen documents, status, history, custody, tasklist, North Star, plan,
goal, or git-index content was changed. No model, reviewer, test, commit,
stage, push, merge, reset, or Batch-3 action was run.

## Disposition

The final attempt-4 seal is **not clean**. No
`.oracle/evidence/batch-2-attempt-4-sealed.md` was created.

The v2 finding and raw external evidence identify the final canonical manifest
as 70 captured files, 6213 bytes, SHA-256
`7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`.
The paired immutable v2 receipt instead identifies its purported final
manifest as 65 captured files, 5760 bytes, SHA-256
`70fc93c723420d9ea4ab54123411dd6ea11d492ea56763cd964cfaaffadf54e0` and
states that an independent recomputation returned that stale identity. Those
claims cannot both describe the final manifest.

The conflicting immutable artifacts are:

- `.oracle/findings/execution-batch-2-attempt-4-v2-luna.md`, SHA-256
  `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff`;
  final-manifest statement at lines 135-138.
- `.oracle/receipts/execution-batch-2-attempt-4-v2-luna.md`, SHA-256
  `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831`;
  stale-manifest statement at lines 56-59.

This is a receipt-integrity defect, not a candidate-code or test defect.

## Independently verified final manifest

Evidence root:
`/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe/`.

- `manifest.sha256`: 70 lines, 6213 bytes.
- `manifest.sha256` SHA-256:
  `7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`.
- Regular files excluding the manifest: 70; including it: 71.
- `shasum -a 256 -c manifest.sha256`: 70 `OK`, zero failures.
- The manifest excludes itself and binds every currently preserved v2 capture.

Thus the finding's final identity is correct and the paired receipt's identity
is stale.

## Other v2 correction evidence verified

All 12 v2 JSON command records parsed. Their literal argv/body, cwd, UTC
interval, exit, paired stdout/stderr byte counts and SHA-256 values, and script
byte counts/SHA-256 values matched the preserved files with zero mismatches.

### Literal raw-symbol terminal capture

- `raw-symbol.sh` is the exact required shell body and hashes to
  `75b76d539959b07133a151c9f59776f8cdf5a76e182af7bea58d386ff25807c4`.
- `raw-symbol.json` records argv `[/bin/bash, -c, <exact script bytes>]`, the
  repository cwd, UTC interval, and exit `0`.
- stdout and stderr are each zero bytes with SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### Fresh clean-checkpoint baseline

- Archive command uses checkpoint
  `19deab5bb407273e7e82d40a66fc06d17af93ad4` and created
  `/tmp/arnold-b2-attempt4-v2-clean.KonB2t/`.
- The sole v2 test command was exactly:
  `cd "$CLEAN_ROOT" && PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py`.
- Exit `1`; stderr empty; stdout 7033 bytes with SHA-256
  `996b9e599b8f534c1256841e7ea0b4ca7a32eb0144ced37591e37db21fb8d588`;
  exact summary `4 failed, 12 passed`.
- Exact failures:
  1. `tests/cloud/test_babysitter_routing.py::test_babysitter_routing_defaults_to_legacy_deepseek`
  2. `tests/cloud/test_babysitter_routing.py::test_legacy_managed_spec_keeps_hermes_controller`
  3. `tests/cloud/test_babysitter_goal.py::test_renderer_requires_single_flash_orchestrator_contract`
  4. `tests/cloud/test_babysitter_goal.py::test_renderer_cli_mentions_single_flash_contract`
- The fresh stdout differs from the historical accepted stdout SHA
  `f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`;
  that difference is disclosed and the complete fresh stream is retained.

### Parent preservation

- Exact parent diff command: exit `0`, empty streams.
- Exact three-file hash command: exit `0`; stdout SHA-256
  `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8`.
- Preserved file hashes:
  - `285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`
    — `arnold_pipelines/megaplan/cloud/babysitter/routing.py`
  - `ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`
    — `tests/cloud/test_babysitter_routing.py`
  - `4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`
    — `tests/cloud/test_babysitter_goal.py`
- Parent and current-HEAD renderer-absence commands both exited `0` with
  empty streams.

## Original attempt-4 evidence retained and checked

- Original finding SHA-256:
  `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda`.
- Original receipt SHA-256:
  `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502`.
- All 30 original JSON records under
  `/tmp/arnold-b2-attempt4-luna-evidence/` parsed; every paired stream byte
  count and SHA-256 matched, with zero mismatches.
- Recorded results remain: focused roots `4/5/5/5`; authority `14`;
  preserved suites `59/53/90/74`; initial NBF-02 `254 passed, 3 failed`;
  corrected NBF-02 `257 passed`; NBF-03 `60 passed, 4 failed`; checker,
  compile, and diff-check exit `0`.
- The original post-exit gap receipt remains immutable at SHA-256
  `fff19e2b4f45ce7a3238cb4848fcd95373a08475c60a9a88b4a5a442bc12c760`.

## Candidate custody

- Branch / HEAD: `megado-nbf-guard-0826` /
  `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`.
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Candidate implementation: `5da26ec5be4d13559948fe4256a114ad7626482b`.
- Full source/test diff: 153829 bytes, SHA-256
  `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.
- Production-only diff: 109379 bytes, SHA-256
  `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
- Git index was clean.
- Frozen tasklist / North Star:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` /
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
- Frozen plan / goal / custody:
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` /
  `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` /
  `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.
- No attempt-4-v2 launcher/model remained alive at final audit, and no nested
  or duplicate NBF model was observed during the authorized execution.

## Closure condition

Do not seal or launch the attempt-4 review gate until a new append-only executor
evidence-correction receipt explicitly supersedes the stale manifest paragraph
and binds the verified final identity: 70 captured files, 6213 bytes, SHA-256
`7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`.
The existing finding, receipt, raw evidence, and this gap receipt must remain
immutable.
