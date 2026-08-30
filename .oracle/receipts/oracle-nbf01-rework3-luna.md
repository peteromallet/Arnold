# Immutable receipt — Luna independent review NBF-01 / Batch 1 rework 3

- Reviewer count: exactly one
- Reviewer: GPT-5.6 Luna
- Reviewed candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Candidate branch: `megado-nbf-guard-0826`
- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Source/base/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Owned production diff SHA-256: `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- `incident/disposition.py` SHA-256: `2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a`; git blob `291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Attempt-3 rework tasklist SHA-256: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- Attempt-3 executor finding SHA-256: `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f`
- Attempt-3 executor receipt SHA-256: `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f`
- Review check-in path: `.oracle/checkins/batch-1-rework3-luna.md`
- Review check-in SHA-256 after write: `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd`
- Isolated transcript root: `/tmp/oracle-nbf01-rework3-luna/`

## Candidate and owned-file binding

All supplied owned production/test SHA-256 and git-blob identities were independently reproduced. The unchanged `tests/arnold_pipelines/megaplan/test_incident_ledger.py` remains blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`. Identity capture reproduced HEAD, origin/main, and merge-base above. The candidate contains pre-existing dirty `.oracle` noise; this receipt does not claim a clean worktree.

## Test-command transcript digests

Every row has a JSON transcript under the isolated root containing the exact argv, cwd, exit status, verbatim stdout, verbatim stderr, and full SHA-256 for each stream.

| Transcript | Exit | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|
| `focused.json` | 0 | `b295944369c7307eae526dbb7f26489f657782bc8f7f7f104a1a5613ebfaaac3` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `legacy.json` | 0 | `6bf9fdef28e576401171fa27f28aed01180b01cf2c0864567bc6bc54d21d4f7b` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tx_subset.json` | 0 | `a64d95de6a86d87df3375b0a5fdac47745385bc5dd0622308e19fcdee85dba09` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider_subset.json` | 0 | `808c3d14219287627b518671c7308d76b836ed617dc7d6e8e463ef82c4169e47` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `confirmation_subset.json` | 0 | `35c11cc3672b8bda3b90af5b09f81b95192b96e163255ff89c7c355117ee769d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `compile.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `diff_check.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `broad.json` | 2 | `602e26d1aaada829260638a8e5c880caa4b0efa7366c8968a7c7df1e489fa096` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `collect_new.json` | 0 | `97d1c095a2cdb9587407637a79e5d35baf21a9dc0d1cffd3c742a5016b655c9d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `collect_unchanged.json` | 0 | `208afccf84501ad8455173d54844085406ca307fdd52686e935328bd860c9b3` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |


## Independent probe transcript digests

- `independent_probes.json`: exit 0; stdout `62fa6b24fdf1db5c4e2e098b757c227384d137d0a3384528c0769835f4e115c1`; stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `recovery_probes.json`: exit 0; stdout `89baff32ef176c411763c002b13d1740906510040c68f78013218c1cc9ec43b2`; stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The probe transcripts are full subprocess records with exact argv/cwd and both stream hashes. All temporary ledgers and probe files are beneath the isolated root.

## Independent CLI transcript digests

Each `cli2_*.json` records its full subprocess argv, cwd, exit status, verbatim streams, and both stream hashes. The status cases are:

- status 0 consumed matching confirmation: stdout `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9`, stderr empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- status 5 same-identity replay: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `7fe9e01d6cba7af6c48aff7b6a459cfc1116a9bfbc742574a8da501cc954e208`.
- status 2 malformed: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a`.
- status 2 schema-invalid: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee`.
- status 3 valid-location append failure: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `6429e423ada8619a78f87e9f17b5fb6960164ca1c9d1f527a426a579909dc2ec`.
- status 4 invalid ledger location: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f`.
- status 5 missing confirmation: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9`.
- status 5 expired confirmation: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93`.
- status 5 differently-bound consumed replay: stdout empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, stderr `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655`.

## Preservation and mutation statement

Historical evidence remains historical: 52→61 start-gate mutation, unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`, failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`, attempt-1 `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`, and attempt-2 `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d` were not rewritten. I did not implement, repair, stage, commit, push, merge, rebase, reset, clean, edit production/tests/plans/frozen tasklists/North Star/custody/historical evidence, start Batch 2, fan out another review, or issue `PASS_BATCH_1`. After capturing the candidate and transcript digests and writing the review, I did not mutate the candidate; only the two authorized review output files were written in the worktree.

## Recommendation

RECOMMEND_ACCEPTED_ISSUES
