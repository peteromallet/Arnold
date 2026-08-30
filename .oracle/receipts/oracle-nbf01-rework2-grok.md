# Immutable receipt — Grok 4.6 Oracle NBF-01 Batch 1 rework-2 gate

- Oracle: Grok 4.6 (manager/validator only; no implementation)
- Date: 2026-08-30
- Role: attempt-2 hard gate after frozen supplemental tasklist `.oracle/rework/batch-1-attempt-2.md`
- Implementation / commit / push / merge / Batch 2 / custody edit / historical-receipt rewrite: **none**
- Reviewers commissioned: **one** (GPT-5.6 Luna)

## Bound identities

| Artifact | SHA-256 / git identity |
| --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Attempt-2 rework tasklist | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-1 rework tasklist | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Executor receipt `.oracle/receipts/execution-nbf01-rework2-luna.md` | `d03d259725484d4eac22cae1e2582288a85a2d2dbfbbfbba7a2b0878b9b02e51` |
| Executor finding `.oracle/findings/execution-nbf01-rework2-luna.md` | `896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb` |
| Luna review brief | `b4647bc377366ef4e2f6eeeb8bfc24f480bc0dbe2de21858873bcad372cde456` |
| Luna review `.oracle/checkins/batch-1-rework2-luna.md` | `bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a` |
| Luna review receipt `.oracle/receipts/oracle-nbf01-rework2-luna.md` | `53a69d3e8a4a232c63e7f25fcda279b0059162087a7d45244ba0bf8d271f6f2e` |
| Oracle check-in `.oracle/checkins/batch-1-rework2-grok.md` | `5ceb712841cb02a0abeb5142864b08107f86695020c872861dc1d1b8bc940455` |
| Current `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Custody receipt | `48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base | `798c50619204010ed3f4297fbb57988fe9381924` |
| Owned production diff | `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d` |

## Independent Luna command transcripts

All under `/tmp/oracle-nbf01-rework2-luna/`. Empty-stdout SHA-256 is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| Transcript | Exit | stdout SHA-256 |
| --- | ---: | --- |
| `focused.json` | 0 | `1996f644e0e8cea7e6cc65ae3b0b8215b9a139b9996049bcb91160cc25f85292` |
| `legacy.json` | 0 | `a96ce9348b20653cb0c42b3ca9a255dd7cad88327a9c7506d2017b889095c310` |
| `transactions_subset.json` | 0 | `ac1b5f4cee6d37390bb37b3914c5289695e19fbebfbc62d1660d7d64140b7d66` |
| `provider_subset.json` | 0 | `79993755e5d9f5e2813be8e4549013ef9294fb0405ef72f4101c82496b487e30` |
| `confirmation_subset.json` | 0 | `fd14cdc4324f99c94e1c223a45b4157339986c37c6aa682625e9d58908d92420` |
| `py_compile.json` | 0 | empty |
| `diff_check.json` | 0 | empty |
| `cli_status_0b.json` | 0 | `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` |
| `cli_status_2b_malformed.json` | 2 | empty |
| `cli_status_2b_schema.json` | 2 | empty |
| `cli_status_3b.json` | 3 | empty |
| `cli_status_4b.json` | 4 | empty |
| `cli_status_5b_missing.json` | 5 | empty |
| `cli_status_5c_consumed_mismatch.json` | 5 | empty |
| `manual_source_probes.json` | 0 | `574ed0ec9494696307c4a8b22b95647e9e8b12bc6ffd68d73bd0e4824c8435ab` |
| `manual_provider_applicable_key_probe.json` | 0 | `4fd3032dac94068518c07362b7f2500813aa46d4b25d6e9b3e8917da2b7e6b81` |

Focused observation: `101 passed in 14.11s`. Legacy observation: `78 passed in 1.52s`. Counts are observations, not targets.

## Disposition summary

C03–C06, C08, C12, C15–C18, C22, C25, C26 shape, C29 order, C30/C31 matching/rekey-at-one, C35, CP01 pytest, CP04 journal count, CP05 increment rule, CP09 type/state, CP10, RW-CUSTODY: **MET**.

C01 partial, C02, C09–C11, C13, C14, C19–C21, C23, C24, C27, C28, C32–C34, C36–C41, CP02/CP03/CP06–CP08/CP11, RW2-01..RW2-04: **NOT_MET**.

North Star one-door / deaths-speak / anti-patterns: **NOT_MET** for the Batch 1 primitive. Scope/YAGNI/later-batch absence: **MET**. KISS quality and ceremonial validation: **NOT_MET**.

Custody/history: `f8725af…` remains historical; `798c506…` remains current; 52→61, `4aee815d…`, `50c86490…`, attempt-1 `e060f650…` remain historical observations.

## Integrity statement

This Oracle read the required North Star, agent goal, frozen tasklist, freeze receipt, both rework tasklists, both triage receipts, original and rework-1 Batch 1 check-ins, model-policy receipt, and attempt-2 executor receipt/finding before dispatching the single Luna review. After that review, Oracle independently re-hashed frozen identities, the owned production diff, and owned untracked files; re-read the cited ledger/schema/phase_result symbols; and confirmed Luna’s source and provider probes. This turn wrote only the Luna review brief plus the two Oracle output files. The candidate source/test tree was not mutated.

## Terminal decision

```text
ACCEPTED_ISSUES
```
