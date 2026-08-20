You are the GPT-5.6 Sol parent in a strictly read-only nested-delegation smoke
test. Do not edit any repository, cloud, provider, state, marker, queue, log, or
external system. Do not launch Hermes, DeepSeek, Kimi, GLM, Claude, or any model
other than the one exact child specified below.

Launch exactly one nested Codex child with this exact model and posture:

`codex exec --sandbox read-only -m gpt-5.6-luna -c model_reasoning_effort=high -`

Feed the child a closed stdin prompt (a temporary prompt file or pipe is fine)
that tells it:

- It is the GPT-5.6 Luna child in a nested-delegation smoke test.
- Work read-only in `/Users/peteromalley/Documents/Arnold`.
- Read
  `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.
- Return exactly one compact JSON object containing:
  `nonce` = `SOL-LUNA-GPT56-20260802-1918-C9F4`,
  `requested_model` = `gpt-5.6-luna`, the file byte size, its SHA-256, and
  whether line 37 contains `Nested Sol → Luna delegation`.
- Make no mutations and launch no child.

Capture the child's complete stdout/stderr and exit code in a disposable temp
directory. Inspect the actual Codex header, not the child's prose, to verify the
header says `model: gpt-5.6-luna`; extract the child session id and verify the
nonce and file facts independently. Do not trust a self-asserted model name.

Your final answer must be one compact JSON object containing: parent requested
model `gpt-5.6-sol`, child requested model, child header model, child session id,
child exit code, nonce, child-output SHA-256, plan byte size/SHA-256, line-37
boolean, and `mutations_performed: false`. If any check fails, return
`passed:false` with the exact mismatch. Launch no other agents.
