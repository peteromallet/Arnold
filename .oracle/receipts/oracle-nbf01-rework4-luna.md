# Immutable review receipt — Luna independent NBF-01 / Batch 1 rework 4

- Reviewer: GPT-5.6 Luna
- Reviewer count: exactly one
- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Reviewed candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source / origin/main / merge-base: `798c50619204010ed3f4297fbb57988fe9381924`
- Owned production diff SHA-256: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Attempt-4 packet SHA-256: `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- Attempt-4 executor finding SHA-256: `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- Attempt-4 executor receipt SHA-256: `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`
- Review check-in: `.oracle/checkins/batch-1-rework4-luna.md`
- Review check-in SHA-256 after write: `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`
- Immutable receipt path: `.oracle/receipts/oracle-nbf01-rework4-luna.md`
- Isolated transcript root: `/tmp/oracle-nbf01-rework4-luna-review/`

## Candidate and scope binding

`identity.json` recorded exact argv, cwd, timestamps, and status for the
identity capture. It reproduced HEAD, origin/main, and merge-base above.
`hashes.json` reproduced the required production diff and every owned full-file
SHA-256, including all eight new test modules and `incident/disposition.py`.
The unchanged `test_incident_ledger.py` remained the origin blob
`44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`.

The candidate worktree was dirty with unrelated `.oracle` planning/evidence
artifacts. This receipt makes no clean-tree claim. Changed production scope was
exactly the five tracked NBF modules plus `incident/disposition.py`; changed
test scope was exactly the eight named NBF modules. No later-batch path was
reviewed as an NBF-01 change.

## Actual command log and stream binding

All commands ran from
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. The capture harness wrote
verbatim streams and JSON metadata beneath the isolated root. Each table row
binds the transcript JSON SHA-256 and the separate stdout/stderr SHA-256.
The timestamps are the capture metadata timestamps; status is the subprocess
exit status.

| UTC+0200 start | Command/transcript | Exit | stdout SHA-256 | stderr SHA-256 | transcript JSON SHA-256 |
|---|---|---:|---|---|---|
| 05:14:19 | identity capture / `identity.json` | 0 | `d43a762bb188acdc307c555106146c7cfd26d481b3e21886a3389e3e27ffd4fd` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `c980f94772cb9cd77465d2f4da2208fff65df14a6570e6614527ff5f7bcf55ab` |
| 05:14:30 | required production/file hash command / `hashes.json` | 0 | `ad94c9bc260081e60e6e44657669b0607975839d989557e99fe713b854bca477` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `7f47246eba08b4c8ecfa2e9bd47c8dfa6979c8de70f7d2e0f030c8950418d628` |
| 05:16:46 | frozen focused pytest / `focused.json` | 0 | `eb007f81b56a64eda7073a78949932b1f77653d9df6ca93922045251646eba3b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e473746d417d831fe92e2a039a42cc8b79a46e288244cdf9ccb6beeb42eb511a` |
| 05:17:13 | legacy pytest / `legacy.json` | 0 | `211dfb1591ec7c1c795a37c2c284e61936f83ace4f8e319ad3fbeaf9975392a8` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `f5bb75ad6497ec6c6ef6686aa1f69d3d4e3f14f173638a10a11b6ff85177b220` |
| 05:17:25 | changed-producer subset / `changed_subset.json` | 0 | `7cb45892af5510dfff0577f6d1cdf92492b282c211bb3578d90422bc122eaeb8` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `71f8f3f8c4913284088cbe147c3148d24b5a1ca906ec0d657366a0517730bddc` |
| 05:17:35 | worker/terminal/scheduling pytest / `worker_terminal_sched.json` | 0 | `1951731dcea742817c5409fee5e5fee678088ddaf9ef8b40074a7a7f0f2d9931` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e7e129df5c77597b05f314d5da00714d7fbb9ae84e02dbc8d57e5c01bdd2f08c` |
| 05:17:59 | provider projection pytest / `provider.json` | 0 | `d015b2f31ef3fe7900d05082b66c5ec8069a2ebe988abc3a1192c3455c86b15d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `b745b33f0669e8594e7fb43b707b9916b343b7121369c8500b798e1ef7693db6` |
| 05:18:14 | transaction race/crash subset / `cross_tx.json` | 0 | `3f6c93b5bf0db5bcad8649961358aedefab718ecb84d0860a8791fb73a22884c` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `5800b75ebdd9c57d8cf0a56c08c7abdca9a365ad29ef9436fe0f1e327bb7a30a` |
| 05:18:29 | transaction full race/crash subset / `cross_tx_full.json` | 0 | `ab020e2215f61d573510338e4c5638861de5a1b8f4e17fed39cde704317f171d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `4f2514153b91a039f7ca5e0623ca0ce8bab006f2c17f4f2e82063303dfa07022` |
| 05:18:40 | provider replay/receipt subset / `provider_replay.json` | 0 | `bcaf041802b7e74be4107ad7ac76c1f1125595572458fc65d8e3a14d9c38cafb` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `12d75f14ecad4442cf7d643a9220e97217969591fdfde6d91b5bf1984044d6c6` |
| 05:18:49 | confirmation pytest / `confirmation.json` | 0 | `42317fada6dcccf66125f116d742efc2b7f7fa15372a60582b23352bdc60c64e` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `35c58c1e066c2527f0bcc055e7618f278475228e6d2ecd8e0f9d81fc1edf6358` |
| 05:18:59 | required py_compile / `py_compile.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `3c49cd2fc868f4701b178aa38357f2e103b4b5e345d7f7edb07ab19e72b876b4` |
| 05:19:02 | required `git diff --check` / `diff_check.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `b843dde49257dd319d7b9eb9c4b1f217860aae1e6dfbd220ac4720372e6d2253` |
| 05:19:05 | full megaplan sweep / `broad.json` | 2 | `fe5ee29bc0a5dc6c64b50b148a20f01128422c47042d84b06570ce0f2fee817e` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `076b5bd69bd28a81e3c2fd3b6449dadf562620aeb0d1b5a049302e6f0a5514b5` |
| 05:19:29 | broad blocker relevance proof / `broad_relevance.json` | 0 | `cd8db8718ff84e2a9432e2a859e33f5501d33df7f614cbfff1174f85ac84a901` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `edc88bb62f307f610cc6233c84217cee0a9baebf99f0d002e1c6758372e42b49` |
| 05:22:37 | independent public producer probe / `independent_probe.json` | 0 | `8072831de3b478aa9b856e8c3aa3141ca08e0b5c02bb2a228996f2e8475ecc76` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `59604b68de96e9dc39a440f1ede9898657dc970c9bc9a101a8d26c9465270b46` |
| 05:24:03 | independent wire-forgery probe / `wire_forgery_probe.json` | 0 | `4a292ceb0c1dff3ce9d26125ab82293e6bf5f2013cc8e77be48bec111aabd6aa` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `eb992fd4f35ac4c810cd45da987d55b2064f1b1f93fb75d2c5ed4d045dbf6a92` |

The command JSON-record SHA-256 inventory above was generated independently
with `shasum -a 256 /tmp/oracle-nbf01-rework4-luna-review/*.json`; its command
transcript is `bound_artifacts.json`/`all_bindings.json` context, and the
individual JSON hashes are the binding identifiers used here.

## Independent CLI records

The CLI capture harness invokes the exact module command with stdin bytes and
records complete stdin, ledger root, argv, cwd, streams, status, and stream
hashes. The following are independent subprocesses, not pytest-name claims.

| Case | Exact invocation class | Exit | stdout SHA-256 | stderr SHA-256 | JSON transcript SHA-256 |
|---|---|---:|---|---|---|
| status 0 | `python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <valid-root> --json-stdin` | 0 | `de85b9592423e61ef59c4a860ba75e55ed618dd8934da164df3f802f16b71e85` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ff4d24a2c5962c6f072dba39ab1919809d00e185440880dbc579eebfa141ff1a` |
| status 2 malformed | same command, malformed JSON stdin | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` | `fa9156725d63e8d43af249acbd26ae0b0c3a9b115371b8997456546b19662151` |
| status 2 schema | same command, schema-invalid object stdin | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb4199a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` | `b72d9557936490688d8cd706463ed69858d050aacc4c81c4cda5420cc8b205d9` |
| status 3 | same command, valid payload and `events.jsonl` directory | 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `b5f11611441f45b0b3e377f413816e00edba8f940215647376e50b72bdb6dfb7` | `02159a8fe21e9c5c38889075ec328170c23e5da3d72b44c44253d159cce0202f` |
| status 4 | same command, ledger root is a file | 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` | `28adf7ea6de7003922f4af7e4341e3564a21a5ec91f2b1a76f1f7fac6e423082` |
| status 5 missing | same command, no confirmation reference | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` | `664e9cd8bd5ba1d782a5f4d7cb4b0b2d190be7ca0b121a4ec8c9e2f788d8ce7a` |
| status 5 expired | same command, expired confirmation | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` | `3230f4b0db51a9fa9659fe4a7639a4492c9b5abc4c228cc1c8f2c2f24ce2062c` |
| status 5 same consumed replay | same command, same confirmation/disposition invoked twice | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `7fe9e01d6cba7af6c48aff7b6a459cfc1116a9bfbc742574a8da501cc954e208` | `180076526816411f7c4d0b16b6cb01a0487496f756c7dc3036bb2884e46bf596` |

Status 0 emitted one JSON acknowledgement and the helper did not signal.

## Broad-suite classification

The complete `pytest -q tests/arnold_pipelines/megaplan` stdout is retained at
`broad.stdout` with SHA-256
`fe5ee29bc0a5dc6c64b50b148a20f01128422c47042d84b06570ce0f2fee817e`; stderr
is empty with the full empty digest. Collection fails only for missing
`arnold.agent.costing.model_resource_capabilities` and
`tools.environments.singularity`. `broad_relevance.stdout` proves both are
| status 2 schema | same command, schema-invalid object stdin | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb4199a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` | `b72d9557936490688d8cd706463ed69858d050aacc4c81c4cda5420cc8b205d9` |
them (`owned_diff_reaches_blockers=no`). Classification for each is
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`; no environment repair was performed.

## Criterion and task result

The complete C01–C41, CP01–CP11, RW4, and A3 tables are in the check-in and
are bound to this receipt. The binary result is not a Batch-1 pass: C19–C21
fail at the wire/private append boundary; C02/C13 and C39 lack the mandated
full named evidence matrices. Strong prior-MET behavior remains green, but
counts do not waive those issues.

## Preservation and non-mutation statement

Historical attempt-1/2/3 artifacts, the frozen plan/tasklist, North Star,
agent goal, custody, production, and tests were not edited. No commit, push,
merge, rebase, reset, clean, Batch 2 start, second review, or
`PASS_BATCH_1` action occurred. Temporary scripts, probes, ledgers, and
transcripts live only under the isolated review root. After the candidate
identity and owned-file/diff digests were captured, no candidate production or
test content was mutated. The only authorized worktree writes were the
check-in and this receipt. This receipt binds the review result to the exact
candidate HEAD and production diff above.

## Recommendation

RECOMMEND_ACCEPTED_ISSUES
