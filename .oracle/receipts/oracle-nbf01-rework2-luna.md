# Immutable receipt — Luna independent NBF-01 rework-2 review

- Reviewer: GPT-5.6 Luna
- Date: 2026-08-30
- Review path: `.oracle/checkins/batch-1-rework2-luna.md`
- Review SHA-256 after write: `bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a`
- Candidate branch: `megado-nbf-guard-0826`
- Reviewed candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Merge-base: `798c50619204010ed3f4297fbb57988fe9381924`
- Owned production diff SHA-256: `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`
- Executor receipt: `.oracle/receipts/execution-nbf01-rework2-luna.md`
- Executor receipt SHA-256: `d03d259725484d4eac22cae1e2582288a85a2d2dbfbbba7a2b0878b9b02e51`
- Executor finding: `.oracle/findings/execution-nbf01-rework2-luna.md`
- Executor finding SHA-256: `896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Attempt-2 rework tasklist SHA-256: `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721`
- Attempt-1 rework tasklist SHA-256: `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c`
- Current custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Custody receipt SHA-256: `48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9`

## Transcript bindings

All transcript JSON files are under `/tmp/oracle-nbf01-rework2-luna/`. Each records exact argv, cwd, exit status, verbatim stdout/stderr, and byte SHA-256 values.

| Transcript | Exit | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|
| `focused.json` | 0 | `1996f644e0e8cea7e6cc65ae3b0b8215b9a139b9996049bcb91160cc25f85292` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `legacy.json` | 0 | `a96ce9348b20653cb0c42b3ca9a255dd7cad88327a9c7506d2017b889095c310` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `transactions_subset.json` | 0 | `ac1b5f4cee6d37390bb37b3914c5289695e19fbebfbc62d1660d7d64140b7d66` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider_subset.json` | 0 | `79993755e5d9f5e2813be8e4549013ef9294fb0405ef72f4101c82496b487e30` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `confirmation_subset.json` | 0 | `fd14cdc4324f99c94e1c223a45b4157339986c37c6aa682625e9d58908d92420` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `py_compile.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `diff_check.json` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `owned_production_diff_digest.json` | 0 | `119026dca76b2b52c32e14ee5ad156ea591d41bc10ead58968770c968629547d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `collect_new.json` | 0 | `f33adfde35d5a318d00ee2d4782aa70c59238e4b2530ae890f0de96e5a047b93` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `collect_legacy.json` | 0 | `1e18cabf56d9c74d0b2b716800f453d13857d2d84fbb45444c0fa231eb23580d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `cli_status_0b.json` | 0 | `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `cli_status_2b_malformed.json` | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` |
| `cli_status_2b_schema.json` | 2 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` |
| `cli_status_3b.json` | 3 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `06678ba61b7788bb53c26e0abad3c8b4898a7ef458305ee30e40e604356af7dd` |
| `cli_status_4b.json` | 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` |
| `cli_status_5b_missing.json` | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` |
| `cli_status_5c_consumed_mismatch.json` | 5 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655` |
| `manual_source_probes.json` | 0 | `574ed0ec9494696307c4a8b22b95647e9e8b12bc6ffd68d73bd0e4824c8435ab` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `manual_provider_applicable_key_probe.json` | 0 | `4fd3032dac94068518c07362b7f2500813aa46d4b25d6e9b3e8917da2b7e6b81` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |


## Binding statement

The review inspected the candidate files actually present at HEAD `922241d0bdb3e993c3b554cc69f19948adef7bc3`, including all owned production and test files. It did not implement, repair, stage, commit, push, merge, rebase, reset, clean, edit production/tests/frozen plan/tasklist/North Star/custody/historical evidence, start Batch 2, fan out a second review, or issue `PASS_BATCH_1`. After capturing the candidate revision, production diff, source-file identities, and validation transcript hashes, I mutated only the two authorized output files: the review check-in and this receipt. The candidate was not mutated after those digests.

Recommendation recorded in the review check-in:

`RECOMMEND_ACCEPTED_ISSUES`
