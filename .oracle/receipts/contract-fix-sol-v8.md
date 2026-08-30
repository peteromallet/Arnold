# Contract-fix receipt — Sol v8

- Model: `gpt-5.6-sol`
- Reasoning effort: `high`
- Scope: oracle-artifact contract corrections only; no source or test implementation
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Agent goal SHA-256: `cc9d45214a38312fb652ca216d1fbc1964b1d5d7e7b94f26b05b7b6a26c1b032`
- Custody SHA-256: `29f7ad58cfa9057ccc02006d70fede01ab5f4a38a3e351acd762a545ed3ae608`
- Sol v7 BLOCKED review SHA-256: `f29f375e3341425d4970377096f91505972fb1a4b8805ccb3674cbfb3be3ef9d`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Archived plan v7 path: `.oracle/findings/plan-v7-pre-v8.md`
- Archived plan v7 raw SHA-256: `3e76fc3c9eeb8fbd6580d1217db341c1c3e9f16a4be3552eadddbef2ccd9276f`
- Archived tasklist v7 path: `.oracle/findings/tasklist-v7-pre-v8.md`
- Archived tasklist v7 raw SHA-256: `70165356577b13f9d4a7841aaa33322839cd7f150db0bf0da2aa3c456e8bf039`
- Plan v8 path: `.oracle/plan.md`
- Plan v8 raw SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Tasklist v8 path: `.oracle/tasklist.md`
- Tasklist v8 raw SHA-256: `88adb2e2e849285c7f83c924ef32c4fab12f1d05d3d4820dab0813f40c445e43`
- Tasklist state: `PROPOSED v8`
- Frozen: `false`
- Execution authorized: `false`
- Push authorized: `false`
- Merge to main authorized: `false`

## Corrections recorded

1. A fresh complete GPT-5.6 Luna v7/v8 sense-check bound to the final plan-v8 and tasklist-v8 digests is mandatory before a separate fresh GPT-5.6 Sol freeze decision on the same digests.
2. Batch 3 may retain only an explicitly provisional, non-authoritative local inventory artifact digest; NBF-07 alone records the authoritative external inventory SHA-256 after exact final candidate-SHA freeze.
3. `tests/arnold_pipelines/megaplan/test_worker_disposition.py` is restored to NBF-06 owned and focused regression coverage.
4. Clean proof is clean tracked working-tree/index state plus the exact hash-verified protected-untracked allowlist, not a blanket no-untracked assertion.

The v8 artifacts preserve the seven tasks, five natural batches, Luna executors, historical temporary Sol authorization bookkeeping, candidate-branch-only delivery, and the prohibition on merging to `main` without explicit user approval. This receipt records the correction only; the tasklist remains PROPOSED pending the mandatory Luna-then-Sol freeze sequence.
