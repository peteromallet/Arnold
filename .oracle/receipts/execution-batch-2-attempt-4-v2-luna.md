# Batch-2 attempt-4 v2 Luna evidence correction receipt

## Receipt type and authority

Executor evidence correction only. This receipt is not implementation, review,
Oracle adjudication, or a batch verdict. It addresses only the three gaps in
`.oracle/receipts/execution-batch-2-attempt-4-evidence-gap.md`, SHA-256
`fff19e2b4f45ce7a3238cb4848fcd95373a08475c60a9a88b4a5a442bc12c760`.

The candidate was not changed. No source, test, frozen document, status,
history, custody, tasklist, North Star, plan, goal, or git-index mutation
occurred. No nested model or reviewer ran. No commit, stage, push, merge, reset,
verdict, or Batch-3 action occurred. The only repository files created by this
correction are this receipt and its paired finding:

- `.oracle/receipts/execution-batch-2-attempt-4-v2-luna.md`
- `.oracle/findings/execution-batch-2-attempt-4-v2-luna.md`

## Binding ledger

| Binding | SHA-256 / identity |
|---|---|
| branch / HEAD | `megado-nbf-guard-0826` / `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| candidate / parent / tree | `5da26ec5be4d13559948fe4256a114ad7626482b` / `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| full source/test diff | 153829 bytes; `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` |
| production-only diff | 109379 bytes; `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| packet | `.oracle/rework/batch-2-attempt-4.md`; `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` |
| attempt-4 brief | `.oracle/briefs/execution-batch-2-attempt-4-luna.md`; `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` |
| attempt-4 finding / receipt | `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda` / `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502` |
| tasklist / North Star | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| plan / goal / custody | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` / `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

Pre-correction identity command records are `identity-pre.json` plus streams.
The final post-correction identity command record, after both v2 artifacts were
written, is `identity-final.json` plus streams; `identity-post.json` is also
preserved as an intermediate capture. Each records branch, HEAD, source base,
candidate parent/tree, both diff digests and byte counts, index state, frozen
hashes, and tracked-path inventory. The pre-correction tracked inventory digest
is `b3b97fa54870fa5507f4b2a2f81d7c855a89d24e07f2cdf3542a0ad85cdfa4a7`, and
the final identity stdout is byte-identical to the pre-correction stdout.

## Fresh evidence root and manifest

All correction captures are preserved under:

`/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe/`

Final manifest: `manifest.sha256`.

- Algorithm: for every regular file except the manifest, invoke
  `shasum -a 256` from the evidence root, rewrite the result as
  `<sha256><two spaces><evidence-root-relative POSIX path><newline>`, sort
  complete lines bytewise by relative path, write a final newline, then hash
  the exact manifest bytes with SHA-256.
- Captured-file count: `65` (66 regular files exist including the manifest).
- Manifest byte count: `5760`.
- Manifest SHA-256: `70fc93c723420d9ea4ab54123411dd6ea11d492ea56763cd964cfaaffadf54e0`.
- Independent recomputation returned the same digest, 65 lines, and 5760 bytes.

The initial builder and final independent recomputation command records are
`manifest-build.json` and `manifest-recompute.json`; their bodies are
`manifest-build.sh` (103 bytes, SHA-256
`c070206635e8f365de8b5dd909c2b6e4275eb5d089ebbf9d061cb38db972b576`) and
`manifest-recompute.sh` (260 bytes, SHA-256
`02b1863a9973fe59a09ebfd6e1a6c41119f0082a271cb1f595094e5b8b02def0`).

## Correction command records

Every record contains literal argv/body bytes, cwd, UTC start/end, exit code,
separate stream bytes and SHA-256, pre/post porcelain, and changed-path hashes.
All empty streams use SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| record | UTC interval | exit | stdout bytes / SHA-256 |
|---|---|---:|---|
| `raw-symbol.json` | `21:12:09.146337Z–21:12:09.458301Z` | 0 | 0 / empty SHA |
| `clean-archive.json` | `21:12:32.492985Z–21:12:39.396734Z` | 0 | 0 / empty SHA |
| `clean-pytest.json` | `21:12:52.768817Z–21:13:10.653060Z` | 1 | 7033 / `996b9e599b8f534c1256841e7ea0b4ca7a32eb0144ced37591e37db21fb8d588` |
| `parent-diff.json` | `21:13:34.526550Z–21:13:34.837852Z` | 0 | 0 / empty SHA |
| `parent-hashes.json` | `21:13:39.859517Z–21:13:40.167216Z` | 0 | 327 / `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8` |
| `parent-renderer.json` | `21:13:44.464504Z–21:13:44.762916Z` | 0 | 0 / empty SHA |
| `head-renderer.json` | `21:13:48.331680Z–21:13:48.632427Z` | 0 | 0 / empty SHA |
| `identity-pre.json` | `21:14:11.394602Z–21:14:12.604487Z` | 0 | 1661 / `2181b38c7dc4508ac131bd7bee33ebfacb7c333ed36df61b2ddceaf798adc9b8` |
| `identity-post.json` | `21:17:54.973739Z–21:17:55.721162Z` | 0 | 1661 / `2181b38c7dc4508ac131bd7bee33ebfacb7c333ed36df61b2ddceaf798adc9b8` |
| `identity-final.json` | `21:20:21.373590Z–21:20:22.307911Z` | 0 | 1661 / `2181b38c7dc4508ac131bd7bee33ebfacb7c333ed36df61b2ddceaf798adc9b8` |
| `manifest-build.json` | `21:15:24.120709Z–21:15:26.458484Z` | 0 | 102 / `3e82b680e8d3a75ceef383ca8e12b0c3281cf3475fc32c08a2b8c2c1fea3d6da` |
| `manifest-recompute.json` | `21:19:32.762280Z–21:19:34.940793Z` | 0 | 313 / `5ebbaeb36a38c231de542d660f68be645ad5f7ec5f09d19a9fd9a4fc198c991d` |

The raw-symbol body is exact and exits 0 with empty stdout/stderr. The clean
archive body is exact and created the fresh nonexistent root
`/tmp/arnold-b2-attempt4-v2-clean.KonB2t/`. The exact two-module pytest body
was the sole test command in this pass and exits 1 with exactly `12 passed, 4
failed`. Complete output is retained in `clean-pytest.stdout`; the four failure
identities are the four named in the gap receipt and packet. Its fresh stdout
SHA differs from the historical accepted clean stdout SHA
`f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`: fresh
`996b9e599b8f534c1256841e7ea0b4ca7a32eb0144ced37591e37db21fb8d588`.

Parent preservation results: exact parent diff exit 0; exact three-file hash
output SHA `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8`;
parent and HEAD renderer absence checks both exit 0 with empty output. Their
literal shell bodies and complete streams are retained under the corresponding
record names.

## Final custody statement

The required North Star block was rehashed before and after and remains exactly
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`, including
its final newline. Candidate HEAD, branch, source base, full source/test diff,
production diff, frozen tasklist, North Star, plan, goal, custody, index, and
tracked path inventory remain bound to the identities above. Existing candidate
dirt was preserved. The v2 finding and this v2 receipt are evidence corrections
only; no implementation or test content was changed, and no disposition is
issued.
