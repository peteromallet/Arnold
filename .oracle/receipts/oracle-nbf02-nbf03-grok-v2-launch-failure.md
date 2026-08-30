# Batch-2 Grok v2 launch-failure receipt

Append-only orchestration evidence. This is not an Oracle review, executor
evidence, or Batch-2 verdict. It records the authorized Grok 4.6 wrapper
attempt that failed before any reviewer could be commissioned.

## Immutable launch bindings

- Repository/CWD: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Candidate HEAD: `5da26ec5be4d13559948fe4256a114ad7626482b`
- Candidate parent: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Candidate tree: `e3d0376482154c4f95d2ec5809d630c4a0c32e69`
- Grok v2 brief: `.oracle/briefs/oracle-nbf02-nbf03-grok-v2.md`
- Grok v2 brief SHA-256: `e770f5bb556c81a6238e4dffce517662c1624d3c312e5147532f073aaf89762a`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Frozen plan SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen agent-goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Frozen custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Candidate production-plus-focused-test digest: `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`

## Exact authorized invocation and result

The wrapper command was:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf02-nbf03-grok-v2.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

- Model selector: `grok-4.6` (the required Oracle provider).
- Wrapper process observed by the command harness: process ID `17854`.
- Start: `2026-08-30T08:54:16.974Z`.
- End: `2026-08-30T08:54:21.266Z`.
- Duration: `4.291411167s` (harness-reported).
- Exit: `1`.
- Provider response, verbatim:

```text
402 This request requires more credits, or fewer max_tokens. You requested up to 16384 tokens, but can only afford 388. To increase, visit https://openrouter.ai/settings/credits and add more credits
```

Captured wrapper stdout was 296 bytes (including its final newline) with
SHA-256 `559a1227c6289e21c3e853d5bf48ded7aaafbfe111ac10d7ba4875bd6ca97fac`.
It consisted of the launcher model/CWD line, `Working...`, and the exact 402
response above. Captured stderr was 0 bytes with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Stop and artifact audit

The provider rejected the request before Grok began judging and before any
Luna reviewer commission. A post-return process audit at
`2026-08-30T08:54:29.864Z` found no NBF Grok, Luna, or reviewer process. None
of the four required v2 gate artifacts existed:

- `.oracle/checkins/batch-2-grok-v2.md`
- `.oracle/receipts/oracle-nbf02-nbf03-grok-v2.md`
- `.oracle/checkins/batch-2-luna.md`
- `.oracle/receipts/oracle-nbf02-nbf03-luna.md`

No fallback, Sol switch, second reviewer, nested harness, source/test edit,
frozen-artifact edit, status/history mutation, test run, stage, commit, push,
or Batch-3 action followed this failure. The stop condition is provider credit
availability: retry this same Grok v2 brief only after credits/token capacity
are restored, or await explicit user approval to change Oracle. The candidate
commit remains implementation identity only and is not a valid Batch-2 PASS.
