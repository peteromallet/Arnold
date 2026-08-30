# Receipt — Oracle NBF-01 Grok 4.6 rework-1 decision

- Oracle: Grok 4.6
- Role: independent Batch 1 / NBF-01 rework-1 gate (manager/validator; not implementer)
- Date: 2026-08-30
- Branch: `megado-nbf-guard-0826`
- HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Rework tasklist SHA-256: `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c`
- Owned production diff SHA-256: `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`

## Inputs

- Executor receipt: `.oracle/receipts/execution-nbf01-rework1-luna.md` (`1acba71b835c7bb2d854773d200c988f1fd344fa4ecdfab8eb64306ba7c69143`)
- Executor finding: `.oracle/findings/execution-nbf01-rework1-luna.md` (`e7607cf15818e2c05b1fc997d92a06f133fe98e12d543e6d8555ddea96192f91`)
- Custody receipt: `.oracle/receipts/rework-nbf01-custody-luna.md` (`48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9`)
- Current custody.md: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Luna review brief: `.oracle/briefs/oracle-nbf01-rework1-luna-review.md` (`01b52d04007214020485c11578bb3e107da2bdceb3539eb84305b9a5aecdd31a`)
- Luna review: `.oracle/checkins/batch-1-rework1-luna.md` (`cdc6cd9b0ecfc3097c0c2940bb9ce85b810a84ab81ceb777ead97dfdc86ec89b`)
- Luna invocation receipt: `.oracle/receipts/oracle-nbf01-rework1-luna.md` (`79a1ff3c42f97888d4faa3ab876618ae9506f7cd3f0755f015050810419e57ec`)
- Policy: `.oracle/receipts/model-policy-grok-switch.md`
- Historical Batch-1 check-ins preserved: `.oracle/checkins/batch-1-luna.md`, `.oracle/checkins/batch-1-grok.md`

Focused transcript stdout SHA-256: `9cf73370d5321101a5f60d46e4572164f52630f3338b5d41a1f8cda4fcd4a006` (`78 passed in 1.53s`)
Legacy transcript stdout SHA-256: `84f2299be394af8fc77dcda51eaca94e685326f456ebae809e5bbfd92fc18514` (`78 passed in 2.06s`)

## Decision

```text
ACCEPTED_ISSUES
```

Full evidence-cited verdict: `.oracle/checkins/batch-1-rework1-grok.md`
Verdict SHA-256: `2d82e2d09e1ff7e49ac895878a5cbabc19e19dda4d109bd528da54c83e6b79a8`

Luna recommended `RECOMMEND_ACCEPTED_ISSUES`. Oracle independently confirmed the remaining CAS-binding, schema-matrix, producer, keyed-replay, confirmation, CLI-named-test, and crash/replay blockers against the post-rework candidate. No second Luna pass was commissioned. Historical 52-versus-61 mutation and unreproducible `4aee815d...` digest remain labeled historical and were not rewritten.

## Boundaries observed

- No production or test code edited
- Frozen tasklist, plan, North Star, agent goal, and historical Batch-1 receipts/findings/check-ins not edited
- No commit, push, merge, rebase, or `main` mutation
- Batch 2 is not authorized
- Executor remains GPT-5.6 Luna; Grok 4.6 remains Oracle only
