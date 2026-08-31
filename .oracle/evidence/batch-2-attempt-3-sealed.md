# Batch 2 Attempt 3 — Canonical Evidence Seal

Sealed at: `2026-08-30T19:10:03Z`

This is an evidence-integrity seal for the Batch 2 attempt-3 Luna execution. It
is not an Oracle review, does not assert `PASS_BATCH_2`, and does not accept or
reject any implementation issue. No source, test, frozen document, status,
index, or history mutation was performed while producing this seal.

## Disposition

The post-exit v3 evidence is complete and internally consistent. The launcher
and resolved GPT-5.6 Luna/high model both completed successfully, all captured
command and stream hashes match their metadata, the literal shell `rg` gate is
present, the initial misordered command records remain preserved, the corrected
`git diff --quiet` interpretation is truthful, and the candidate and frozen
identities remain unchanged.

This seal supersedes only the earlier orchestration statement that the v2
evidence gap was still open. It does not rewrite or invalidate the immutable v2
gap receipt.

## Wrapper and Model Completion

Evidence root: `/private/tmp/oracle-b2-rework3-luna-v3`

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `meta.txt` | 374 | `5b852fb79d1da03f03d7be5c1a172e5dc26f9dae1ab3759e6189b1358e5d3f21` |
| `stdout.txt` | 1272 | `9c32622901d4575b1d333399289aed12e99f01327fc258a01e716cb57f6ee597` |
| `stderr.txt` | 463 | `0618f08c37d054823cb3c2702e93ae91be4f82a0b91d58f2e3dac3d834496613` |

The deterministic SHA-256 of the three lexical `shasum -a 256` lines above is
`59dc8dde74cf1a1d04360cf26c5d96425af9f5576201d40057a1e2ea43ab957e`.

- Wrapper start: `2026-08-30T18:55:56.847840000Z`
- Wrapper end: `2026-08-30T19:05:30.957165000Z`
- Launcher PID recorded by wrapper: `23486`
- Wrapper exit: `0`
- Resolved model: `openai-codex/gpt-5.6-luna`
- Thinking level: `high`
- Model duration: `573.7s`
- Model exit: `0`
- Working directory: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- All v3 wrapper, launcher, and model processes were absent at sealing time.

There is no separate `exit.txt`; the exact successful exit is recorded in the
complete `meta.txt`, `stdout.txt`, and `stderr.txt` capture set.

## Bound Executor Artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `.oracle/briefs/execution-batch-2-attempt-3-v3-luna.md` | — | `b5cbe8cadfce9ed0ddba64cd4432fefaf3422eac66914354346ec254b37bb7af` |
| `.oracle/findings/execution-batch-2-attempt-3-v3-luna.md` | 16578 | `c216fc39fcdec21cf81f8a3bb43656b7dca5ef949a050a85ac1a81b0523569ee` |
| `.oracle/receipts/execution-batch-2-attempt-3-v3-luna.md` | 16163 | `cca7987c9f23eab5ec6c2a4cf80ceb1af84fd1d5e2503bc20421ef2685cb0bcf` |

The finding and receipt are truthful executor evidence. They explicitly avoid
an Oracle verdict and accurately disclose the earlier command-order and literal
shell-capture defects together with their corrections.

Prior immutable artifacts remain bound as follows:

| Artifact | SHA-256 |
|---|---|
| `.oracle/briefs/execution-batch-2-attempt-3-v2-luna.md` | `5de88060bc2b2045ccf34ff86b08624ccc95e6f9ba909039706a31a7e8f12539` |
| `.oracle/findings/execution-batch-2-attempt-3-v2-luna.md` | `7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f` |
| `.oracle/receipts/execution-batch-2-attempt-3-v2-luna.md` | `58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b` |
| `.oracle/receipts/execution-batch-2-attempt-3-timeout.md` | `678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df` |
| `.oracle/receipts/execution-batch-2-attempt-3-v2-evidence-gap.md` | `048fa29c50add4230a7049af2e038a2fbd5f8339c1d04f8ad5271e26670ff778` |

## Repository and Candidate Identity

| Identity | Value |
|---|---|
| Branch | `megado-nbf-guard-0826` |
| Current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate checkpoint | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate parent | `19deab5bb407273e7e82d40a66fc06d17af93ad4` |
| Candidate tree | `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Source/test diff command | `git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests` |
| Source/test diff SHA-256 | `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| Source/test diff bytes | `126804` |
| Source/test diff stats | `18 files; 1567 insertions; 75 deletions` |
| Production-only diff SHA-256 (`arnold_pipelines scripts`) | `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549` |
| Production-only diff bytes | `84905` |

There were no untracked files under `arnold_pipelines`, `scripts`, or `tests`.
The following 18 candidate paths and their content hashes matched the sealed v3
path-hash capture exactly:

1. `arnold_pipelines/megaplan/auto.py`
2. `arnold_pipelines/megaplan/cloud/babysitter/launch.py`
3. `arnold_pipelines/megaplan/cloud/controlled_final_launch.py`
4. `arnold_pipelines/megaplan/cloud/worker_dispatch.py`
5. `arnold_pipelines/megaplan/incident/ledger.py`
6. `arnold_pipelines/megaplan/incident/schema.py`
7. `arnold_pipelines/megaplan/workers/_impl.py`
8. `arnold_pipelines/megaplan/workers/omp.py`
9. `scripts/check_worker_admission_authority.py`
10. `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
11. `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
12. `tests/cloud/dispatch_test_helpers.py`
13. `tests/cloud/test_controlled_final_launch.py`
14. `tests/cloud/test_dispatch_reconciliation.py`
15. `tests/cloud/test_dispatch_with_admission.py`
16. `tests/cloud/test_worker_admission_authority.py`
17. `tests/cloud/test_worker_dispatch_admission.py`
18. `tests/cloud/test_worker_dispatch_spy.py`

## Frozen Identity

| Artifact | SHA-256 |
|---|---|
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

## V3 Capture Inventory and Integrity Audit

| Evidence root | Files | Lexical manifest SHA-256 |
|---|---:|---|
| `/private/tmp/nbf-batch2-attempt3-v3-luna-evidence` | 56 | `ea42d7db641b06399ab0d51754b40f3fc77cf154a987981221447a2414cdd893` |
| `/private/tmp/nbf-batch2-attempt3-v2-luna-evidence` | 16 | `3a5731511d27d75c598820596c54cf8332c482874b241770ea64ef24daeadf3a` |
| `/private/tmp/nbf-batch2-attempt3-v2-luna-r3-evidence` | 9 | `8405ad04406ba6c6a0caeb8e7d7a988e6a972c6fc2151c2088bde04693e34024` |

The lexical manifest hash is the SHA-256 of the sorted, relative-path
`shasum -a 256` lines for every regular file in the named root.

Post-exit integrity checks produced:

- `META_MISMATCH_COUNT=0` across the complete v3 capture set.
- `STREAM_MISMATCH_COUNT=0` across all 25 prior JSON validation records.
- Every command-text SHA, exit code, stdout byte count/hash, and stderr byte
  count/hash matched its metadata.
- All 18 current candidate path hashes matched `13-path-hashes-stdout`.
- All prior v2 executor artifact hashes matched `14-artifact-hashes-stdout`.
- All 25 prior JSON validation records parsed successfully.

## Exact Literal Shell `rg` Gate

Command file:
`/private/tmp/nbf-batch2-attempt3-v3-luna-evidence/01-raw-rg-command.txt`

Command-file bytes/SHA-256: `263` /
`75b76d539959b07133a151c9f59776f8cdf5a76e182af7bea58d386ff25807c4`

The literal command executed through `/bin/bash -lc` was:

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

Result: start/end `2026-08-30T18:57:29Z`, exit `0`, stdout `0` bytes with
SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
stderr `0` bytes with the same empty-stream SHA-256. Metadata SHA-256:
`b34250474d228632cb3f52f8e67940201ba8c4556a8a1ac1ac680dd539b7bf80`.

## Exact Identity Transcript

Each command exited `0` with empty stderr. The transcript ran from
`2026-08-30T18:57:49Z` through `2026-08-30T18:57:50Z`.

| Step | Result | Command-text SHA-256 | Stdout bytes / SHA-256 |
|---:|---|---|---|
| 1 | `megado-nbf-guard-0826` | `edd02ec3bd1b0a6e587a36a91c34e91d1f11b3825a2991e527c345d55a32fcc3` | 22 / `d16a4b7e75934804a550403f7aeaede152310ae73b9091d09b5a60599bed7333` |
| 2 | HEAD `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` | `4efde96313ab618b31843815582cd27c102485c5ee9a4c9c66e907855a202017` | 41 / `ea3a3bb36ec3ae1a30dd542056944359cdc5c18f208eb7c352b9c8190cdaa056` |
| 3 | `origin/main` `798c50619204010ed3f4297fbb57988fe9381924` | `af9d314e9ea299e91d417e88156af9c63eb18d919bbf26412509208ca345e0e0` | 41 / `9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430` |
| 4 | Candidate commit/parent/tree identity | `3338424fa49af71516acd2f1bf7e1cd4482a5c8047579529d2a2e75b96dcefe6` | 123 / `b740fd69703d0377e6d0c0a993933dda9c7831a6fc2e5261308d3ee37ae7e742` |
| 5 | `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec  -` | `e8adf405ed04b7f4ebe464316f93b7551eb01487042b7111f78fe33900dbf8a3` | 68 / `214d396aeb581c9960051374c84d6b5d8da5900a5b1c4641552b50fc5562067b` |
| 6 | Exact 18-path name-status inventory | `7de3b4b0400d3fea1c91355c246c0de1b70f42d51a322312ac9238418fb9f61e` | 889 / `3936e0f053ea7e36d9e58e416fce7177e0d1104fcecd757645f440c01e1a1451` |
| 7 | No untracked source/test paths | `de38a9082ba42df172cdccd20014832e04b4339c08f58b4e6c94ec7bd08aa30a` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The raw candidate-diff capture used command-text SHA-256
`17864f2e6ea4631c04f844e61cee87b228ec79427334ef1122f20d1d227adb3c`,
exited `0`, emitted `126804` stdout bytes with SHA-256
`acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec`,
and empty stderr. Its metadata SHA-256 is
`f108b4b48751d78c6736c59234b9bef36a8776a57e3340ca2e63aa6444ba929a`.

## Misordered Records and Corrected Semantics

The initial evidence was preserved immutably rather than overwritten:

| Initial record | Actual command/result | Record SHA-256 |
|---|---|---|
| `07.json` | three-file `shasum`, exit 0 | `366da30f9a7a62e42c4d4520e2f380afbe542f31a875f2146eae68d8497ed40f` |
| `08.json` | authority checker, exit 0 | `9921737957afa986b5214170e040712c1c50a5ffe4f500609ef598756650178f` |
| `09.json` | `compileall`, exit 0 | `11c822a569d77f8f2282063a62953d54c4290ff4cc2b83f379dd9b02ad6cafb7` |
| `10.json` | `git diff --check`, exit 0 | `f8665dfc282e2f5a20cd7b6b2a277db92255d4c8746ec57c1363828608e7bce8` |

Corrected/additional records:

| Record | Result | Record SHA-256 |
|---|---|---|
| `07-correct.json` | packet command 07, `git diff --quiet`, exit 0 | `a67bf9cb0326dc27e04c3ee007337f67ea8122f8b4124680d1b88e89c454e5d3` |
| `08-correct.json` | packet command 08, three-file `shasum`, exit 0 | `7168d0d1450a6f7244f0706d04a4274f379494eb270a68f01384f92cc5ecc907` |
| `09-correct.json` | packet command 09, authority checker, exit 0 | `442a7559dc7ae2228d39773e6f2124869da8caf6be4484b401e0b72cc5c4b27a` |
| `10-specialized-grep.json` | earlier specialized non-literal grep substitution, exit 0 | `07932088013c5d8e22618aad24a813106987994675d307b61a1ba10ce5068dc2` |

The exact preservation command was rerun in v3:

```text
git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- arnold_pipelines/megaplan/cloud/babysitter/routing.py skills/babysitter/scripts/render_babysitter_goal.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py
```

It exited `0` with empty stdout and stderr. The correct semantics are that the
selected preservation paths are byte-identical to the named base; the prior
statement that exit `0` meant “paths differ” was false and is corrected by the
v3 artifacts.

## Prior Validation Results Preserved and Revalidated

Frozen command results:

| Gate | Result | Stdout SHA-256 |
|---:|---|---|
| 1 | 56 passed | `6ce6d7abe3234c2938579445b8632691407810ca9e9e4a05b15779c356214628` |
| 2 | 53 passed | `b1d5100ae101808494b1abe3ecb9366c9f5d61fea7960e5d2f1e78b6c9632b88` |
| 3 | 90 passed | `9c001d8b22cff0472ed4c03ce27f0999b42e85607cb6aa354026fc409c8f606d` |
| 4 | 74 passed | `79f8afeb3e812347d4d6f9ebe94697f1de19ae26a98d7b296d7fe5517ed1cb09` |
| 5 | 254 passed | `6236aee318b79882976d9015f9333c3ad326fb902c98cd2ea3a0aacd6ac1eea6` |
| 6 | exit 1; 59 passed and 4 known baseline failures | `d393b85f46c796ea6488d7ac096cd642870f43d2d7bfcdaef52c7bd07efb02d2` |
| corrected 07 | preservation diff quiet, exit 0 | empty stdout |
| corrected 08 | three-file SHA check, exit 0 | captured |
| corrected 09 | authority checker, exit 0 | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` |
| final compile | exit 0 | captured |
| final diff check | exit 0 | captured |

The four command-6 failures were reproduced as baseline-relevant known failures;
the v3 work did not silently waive or relabel them as passes.

Fresh r3 focused/broad results preserved in the 9-record evidence root:

| Area | Focused | Broad | Stdout SHA-256 (focused / broad) |
|---|---|---|---|
| Native dispatch | 4 passed | 113 passed | `44091516c6f7d278c9900d796163d45f95d1ad1819370ffeeaf887bc704f2e38` / `8d65225305adc8e95ccfa4247a29cbfc4ba63e3c0f1958a70fc19df68a353eca` |
| Terminal launch | 5 passed | 67 passed | `a86fbc1eaf8fe3346837ab279229e9eb1b6170e862c47dae08b324a37c72100c` / `d5105a2a2a31b25f0783d20632c0e7c26f3c81b6ba8f51bb092303067a8d0afd` |
| Lifecycle | 5 passed | 18 passed | `5c9258a0de83f38243aa16ddbdf4932629810a56e692fb8852a52f3a6f665024` / `4fbfe0b2c326209cdd318cb4bc315f4ff4bc437d80e9898c1ae537c63f35375d` |
| Authority | 5 passed | 13 passed | `0407c81f58a87403f115aa0196e1c68d7be7a22d330f09eabf4c946a853e91ff` / `489cd4744986b1a46608752c592c91f6f46125cfc871ea7ba364743cd32906aa` |
| Authority checker | — | exit 0 | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` |

The complete command argv, start/end timestamps, exit codes, stdout/stderr byte
counts, and full hashes remain authoritative in the JSON records and the v3
finding/receipt. The post-exit audit rehashed their embedded streams and found
zero mismatches.

## Seal Boundary

- No implementation or test file was edited.
- No frozen `.oracle` document was edited.
- `.oracle/status.md`, the git index, and history were not modified.
- No tests, model, reviewer, or Oracle gate were launched by the sealer.
- No commit, stage, push, merge, or Batch 3 action was performed.
- The only repository write made by the sealer is this new immutable evidence
  manifest.

The candidate is therefore ready for an independently authorized Oracle gate to
evaluate. This statement concerns evidence readiness only and is not a verdict.
