You are the GPT-5.6 Sol parent in a strictly read-only nested-delegation smoke
test, retry 2. Launch exactly one child using exactly:

`codex exec --sandbox read-only -m gpt-5.6-luna -c model_reasoning_effort=high -`

No other agents/models. No repository, cloud, provider, state, marker, queue,
log, or external mutation. Capture child stdout/stderr and exit in a disposable
temp directory.

Child task: work read-only in `/Users/peteromalley/Documents/Arnold`; read
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`;
compute byte size and SHA-256; read the full 1-indexed line 37; set
`line_37_contains_nested_delegation` by evaluating the substring expression
`"Nested Sol → Luna delegation" in line_37` (not whole-line equality); and
return one compact JSON object with nonce
`SOL-LUNA-GPT56-20260802-1924-E71B`, requested model `gpt-5.6-luna`, byte size,
SHA-256, and that boolean. Child launches no child and performs no mutation.

Parent independently recomputes every value and inspects the actual child Codex
header for `model: gpt-5.6-luna` plus child session id; do not trust child prose.
Return exactly one compact JSON object with `passed`, parent requested model,
child requested/header model, child session id/exit code, nonce, stdout/stderr
SHA-256, plan size/SHA-256, line boolean, and `mutations_performed:false`.
Overall `passed` is true only if all values match, exit is zero, header is exact,
nonce is exact, and boolean is true.
