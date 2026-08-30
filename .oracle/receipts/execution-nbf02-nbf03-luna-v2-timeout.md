# NBF-02/NBF-03 Luna v2 timeout receipt

This append-only receipt records executor-wrapper evidence. It is not an
implementation finding, review, Oracle gate, or verdict, and it does not
rewrite the first execution artifacts.

## Authoritative wrapper record

The v2 continuation was invoked with this exact command (including the lack of
an explicit `:high` suffix and lack of an explicit timeout flag):

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-nbf02-nbf03-luna-v2.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf
```

- Model requested: `codex:gpt-5.6-luna` (no explicit `:high`)
- CWD: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Launcher PID: `74894`; OMP child PID: `74917`
- Wrapper session: `88209`
- Start: `2026-08-30T07:03:47.953Z`
- End: `2026-08-30T07:33:48.346Z`
- Duration: `1800.370992084s`
- Effective launcher timeout: default `1800.0s` (no `--timeout` was supplied)
- Wrapper result: exit `124`
- Exact timeout output: `error: omp process exceeded --timeout=1800.0s`
- The launcher process itself returned an outer command result of `0` while
  its emitted terminal status was `124`; the authoritative continuation
  outcome is timeout/exit `124`, not successful completion.

Captured launcher streams, extracted byte-for-byte from the authoritative
session record:

| stream | bytes | SHA-256 |
|---|---:|---|
| stdout | 426 | `eedd27d97bdba9b1fa681a9605a1a9b3c1be5aebf7c98ed5694152e61089efe8` |
| stderr | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Timeout outcome and preserved state

- `.oracle/findings/execution-nbf02-nbf03-luna-v2.md`: absent.
- `.oracle/receipts/execution-nbf02-nbf03-luna-v2.md`: absent.
- No v2 finding, receipt, review, verdict, commit, stage, push, or Batch-3
  action was produced by this timed-out continuation.
- Final observed HEAD at timeout: `19deab5bb407273e7e82d40a66fc06d17af93ad4`.
- Final observed worktree diff digest from the audit:
  `e945526a223f4c03f866d892d4ab5be70c189d7fbcfb9c70552f06bf68b3f6fd`.
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

The audit reported that v2 added the previously missing NBF-02/NBF-03 test
files and changed production/tests, including large changes/deletions in
`tests/arnold_pipelines/megaplan/test_phase_result_classify.py` and
`tests/arnold_pipelines/megaplan/test_plan_circuit.py`; those changes require
necessity and loss-audit review in the v3 continuation. The audit also recorded
the provenance defects: no explicit high-reasoning selector, abbreviated or
incorrect historical bindings, and timeout before evidence sealing.

The first execution artifacts and all frozen planning/status/goal/custody
files remain historical and untouched by this receipt.
