# Batch-2 attempt-4 canonical evidence seal

Sealed at `2026-08-30T21:36:53Z` and finalized after independent hash,
stream, process, and custody verification.

## Authority and disposition boundary

This document is an evidence-integrity seal for Batch-2 attempt 4. It binds the
original Luna execution evidence, the v2 evidence correction, and the v3
receipt correction into one canonical chain. It is not a review, Oracle
adjudication, `PASS_BATCH_2`, `ACCEPTED_ISSUES`, a commit authorization, or
permission to start Batch 3.

The evidence chain is complete and internally reconciled. The stale manifest
paragraph in the immutable v2 receipt is historical only; the v3 correction is
the controlling receipt for the final v2 evidence-manifest identity.

No production source, tests, frozen document, status, history, custody,
tasklist, North Star, plan, goal, or git-index content was changed while
producing this seal. No model, reviewer, test, commit, stage, push, merge,
reset, or Batch-3 action was run.

## Canonical artifact chain

| Artifact | SHA-256 | Role |
|---|---|---|
| `.oracle/rework/batch-2-attempt-4.md` | `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` | frozen attempt-4 packet |
| `.oracle/briefs/execution-batch-2-attempt-4-luna.md` | `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` | original execution brief |
| `.oracle/findings/execution-batch-2-attempt-4-luna.md` | `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda` | original executor finding |
| `.oracle/receipts/execution-batch-2-attempt-4-luna.md` | `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502` | original executor receipt |
| `.oracle/receipts/execution-batch-2-attempt-4-evidence-gap.md` | `fff19e2b4f45ce7a3238cb4848fcd95373a08475c60a9a88b4a5a442bc12c760` | initial three-gap audit |
| `.oracle/briefs/execution-batch-2-attempt-4-v2-luna.md` | `8ecf052ebe3dc608f029021d2268fac68a16186f48b6f53e10f3784928607431` | evidence-correction brief |
| `.oracle/findings/execution-batch-2-attempt-4-v2-luna.md` | `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff` | corrected raw/baseline finding |
| `.oracle/receipts/execution-batch-2-attempt-4-v2-luna.md` | `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831` | historical receipt with stale manifest paragraph |
| `.oracle/receipts/execution-batch-2-attempt-4-v2-final-seal-gap.md` | `7a1d548d73808a317847f5ae25fe236fb4d93b646836f72fcefcc95efdf28299` | stale-paragraph audit |
| `.oracle/briefs/execution-batch-2-attempt-4-v3-luna.md` | `97019e384815b95a4c96f873b63f87329a8268d74889aafc970c9e4798d8a804` | receipt-only correction brief |
| `.oracle/findings/execution-batch-2-attempt-4-v3-luna.md` | `5c87675363343bddbbaf43e5c7520cf3a6012ae65863151dddbdfcf398571b29` | receipt-correction finding |
| `.oracle/receipts/execution-batch-2-attempt-4-v3-luna.md` | `2e462d5532577fb348443461bf4369cdec512af0b4f535eefdfee73f6b5ace9e` | controlling corrected receipt |

The accepted attempt-3 Sol adjudication that commissioned attempt 4 remains
bound as check-in
`f48bffe73211a01ec8a95acb1a1cde99fc9ce6276165d64fac32b302609a27ad`
and receipt
`4dad76f10aaf0a3407ecaff7948ec09d1f07457bf2d04afb683a076cef719759`.
The review-policy override remains
`1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc`.

## Original attempt-4 validation evidence

Evidence root: `/tmp/arnold-b2-attempt4-luna-evidence/`.

All 30 JSON command records parsed. Every record's paired stdout/stderr byte
count and SHA-256 matched its retained stream; mismatch count was zero. The
root contains 90 regular files. An independent canonical in-memory inventory
over all 90 files—`<sha256><two spaces><relative POSIX path><newline>`, sorted
bytewise by relative path—was 7899 bytes with SHA-256
`a05b77ae34a5464cd161c5763f5b27caa78ec65f196c4939f538837287f8fc86`.
The earlier unreproducible claimed root digest is not used by this seal.

| Captured command | Exit | stdout SHA-256 | Result |
|---|---:|---|---|
| R3-NATIVE-001 focused | 0 | `d07a1be384f84d9d95b6d48bfc797264bdf209a84dca560c1775e944c8887ef5` | 4 passed |
| R3-TERM-002 focused | 0 | `3de0922879cc7b6509a3ad1ea40ed1f93b71bfe1a47df2a0588277d5be9a14dd` | 5 passed |
| R3-LIFE-003 focused | 0 | `5c9258a0de83f38243aa16ddbdf4932629810a56e692fb8852a52f3a6f665024` | 5 passed |
| R3-AUTH-004 focused | 0 | `bba54d0d911e4f4b3ff7099be56f23a579126dd0cbb36d88eb246b10ef320d5b` | 5 passed |
| authority full module | 0 | `da19776f28c1d566682bf8257b6879a72a4ccf5caa24bff0c678991f96a3bb16` | 14 passed |
| preserved command 1 | 0 | `16fd66e8725a47f4e13b9f2756c1cbf43df83ba1cd247170daf16004601c1102` | 59 passed |
| preserved command 2 | 0 | `89bb8a17243781f072bd93286127e374f77a0118bad47dec5c7b836a85c2b16c` | 53 passed |
| preserved command 3 | 0 | `e8e7512bc6d609785e712b176bac3bc6602c533ad6f0e19d5f879df42234e96f` | 90 passed |
| preserved command 4 | 0 | `7de2705dd0aa804ddef0b0a64440eec5a1023df15248c21732fe0318b725a2fd` | 74 passed |
| frozen NBF-02 initial | 1 | `63d44d4b18d52cb4a235d339b7d0d1efa5f1686e501e3d061f02ff8d821d0cd7` | 254 passed, 3 pre-existing incompatible assertions |
| frozen NBF-02 corrected rerun | 0 | `6e2c89136aad208ce1257bf041f973a48847437294d81af7198eaf21061cbe0e` | 257 passed |
| frozen NBF-03 | 1 | `02cb9731768e9b95f63acaab44ed16ca5cbd439bc28c269ca20cd1753a2a13ff` | 60 passed, exactly 4 babysitter baseline failures |
| baseline preservation diff | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | clean |
| baseline preservation hashes | 0 | `c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8` | exact parent hashes |
| checker `--check` | 0 | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | `ok: true`, empty diagnostics |
| compileall | 0 | empty-stream SHA | success |
| diff check | 0 | empty-stream SHA | success |

All captured original stderr streams were empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The parent and current-HEAD renderer-absence checks also exited 0 with empty
streams.

## V2 correction evidence and canonical raw manifest

Evidence root:
`/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe/`.

All 12 v2 JSON records parsed. Their exact argv/body, cwd, UTC interval, exit,
paired stream byte counts and SHA-256 values, and associated script byte counts
and SHA-256 values matched the retained files with zero mismatches.

The canonical `manifest.sha256` is final and independently verified:

- 70 captured files excluding the manifest; 71 regular files including it;
- 70 lines and 6213 bytes;
- SHA-256
  `7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`;
- final newline present;
- `shasum -a 256 -c manifest.sha256`: exit 0, 70 `OK`, zero failures.

The v2 receipt's older 65-file / 5760-byte /
`70fc93c723420d9ea4ab54123411dd6ea11d492ea56763cd964cfaaffadf54e0`
paragraph is stale. V3 finding `5c8767…` and controlling receipt `2e462d…`
explicitly supersede it and corroborate the 70-file identity above.

### Literal forbidden-symbol shell gate

`raw-symbol.sh` contains the packet-required literal `rg` shell body and hashes
to `75b76d539959b07133a151c9f59776f8cdf5a76e182af7bea58d386ff25807c4`.
`raw-symbol.json` records `[/bin/bash, -c, <exact script bytes>]`, repository
cwd, UTC interval, and exit 0. stdout and stderr are empty with the empty-stream
SHA. This is the required no-forbidden-symbol result.

### Fresh clean-checkpoint baseline

The exact archive command extracted checkpoint
`19deab5bb407273e7e82d40a66fc06d17af93ad4` into the fresh root
`/tmp/arnold-b2-attempt4-v2-clean.KonB2t/`. The sole v2 test command was:

```text
cd "$CLEAN_ROOT" && PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py
```

It exited 1 with empty stderr and stdout SHA-256
`996b9e599b8f534c1256841e7ea0b4ca7a32eb0144ced37591e37db21fb8d588`.
The exact result was 4 failed, 12 passed, with these four identities:

1. `tests/cloud/test_babysitter_routing.py::test_babysitter_routing_defaults_to_legacy_deepseek`
2. `tests/cloud/test_babysitter_routing.py::test_legacy_managed_spec_keeps_hermes_controller`
3. `tests/cloud/test_babysitter_goal.py::test_renderer_requires_single_flash_orchestrator_contract`
4. `tests/cloud/test_babysitter_goal.py::test_renderer_cli_mentions_single_flash_contract`

The fresh stdout differs from historical stdout SHA
`f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`;
the difference was disclosed and the complete fresh stream is retained.

### Parent preservation

The exact parent diff exited 0 with empty streams. The exact three-file hash
command exited 0 with stdout SHA
`c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8`
and reported:

- `285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`
  — `arnold_pipelines/megaplan/cloud/babysitter/routing.py`;
- `ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`
  — `tests/cloud/test_babysitter_routing.py`;
- `4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`
  — `tests/cloud/test_babysitter_goal.py`.

Parent and current-HEAD renderer-absence checks both exited 0 with empty
streams.

## V3 correction verification

The v3 controlling receipt independently rebuilt the v2 manifest and obtained
the same 70-file / 6213-byte / `7cd41d…` identity, byte-identical to the
preserved manifest. Its independent `shasum -c` exited 0 with 70 `OK`, zero
failures; stdout was 1873 bytes with SHA
`2f203c4e0a0337078578131158a72b16158ea51436471fdc12924fede99ea95c`
and stderr was empty.

The v3 canonical North Star comparison was byte-identical: 1515 bytes, final
newline present, SHA
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

The v3 post-write porcelain is 5465 bytes with SHA
`ccf14b9e953d4556ca1c508f1028513d8337a9a50c377deb2ea98fd04c9bddb2`.
Independent final audit reproduced that exact byte count and digest. Both
pre- and post-write index checks exited 0 with no staged names.

## Candidate and frozen custody

| Binding | Final identity |
|---|---|
| repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf` / `megado-nbf-guard-0826` |
| HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| candidate implementation | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| parent / tree | `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| full source/test diff | 153829 bytes; `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` |
| production-only diff | 109379 bytes; `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| frozen tasklist | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| frozen North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| frozen goal | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| frozen custody | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| git index | clean; zero staged paths |

The source/test inventory remains 21 modified tracked paths and zero untracked
paths under `arnold_pipelines`, `scripts`, or `tests`. Existing unrelated dirty
and untracked repository artifacts were preserved.

## Process and cardinality proof

- Original attempt-4 wrapper interval:
  `2026-08-30T20:28:46.225811Z`–`2026-08-30T20:58:58.224344Z`;
  launcher PID 87452; exit 0. Wrapper meta/stdout/stderr SHA-256 values:
  `60bbe0e2442238db58819c9ffdcd69c1708488abebc6384c1120639a9cf2235d`,
  `3305f093810a7ad0d686178e98ded3f5d80878c1da5dc11c9c91f696ae3271a0`,
  `3bae769be3ce31ff2eba509988b31942827e05a5a1b6aa70f0aea730725033da`.
- V2 used exactly one launcher/Luna chain: PID 16753 / 16782,
  `openai-codex/gpt-5.6-luna --thinking high --no-session`, timeout 1800,
  repository cwd. No nested or duplicate NBF model was observed; the chain
  exited before final audit.
- V3 used exactly one launcher/Luna chain: PID 32300 / 32323,
  `openai-codex/gpt-5.6-luna --thinking high --no-session`, timeout 900,
  repository cwd. No nested or duplicate NBF model was observed; the chain
  exited before this seal.
- No attempt-4, v2, or v3 launcher/model process remained alive at sealing.

## Seal conclusion

The three gaps recorded after the original execution are closed by immutable,
append-only evidence:

1. the exact literal raw-symbol shell command is captured;
2. the clean checkpoint reproduction records the exact unchanged 12/4
   babysitter baseline identities and parent-preservation proofs;
3. the final evidence manifest is canonical, preserved, independently
   reproducible, and correctly bound by the v3 receipt.

The original validation streams, corrected evidence streams, artifact hashes,
candidate diffs, frozen documents, index, and process cardinality agree. This
seal is therefore clean for consumption by a later authorized review gate. It
does not itself decide Batch 2.
