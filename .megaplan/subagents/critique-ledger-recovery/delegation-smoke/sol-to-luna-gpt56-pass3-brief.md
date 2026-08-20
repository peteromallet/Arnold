# Sol → Luna nested delegation smoke test, pass 3

You are GPT-5.6 Sol. Perform exactly one read-only nested delegation to an
explicit GPT-5.6 Luna child. This is only a transport/model-identity smoke test;
do not edit files, run cloud/provider operations, or make product changes.

Use the trusted child working directory `/Users/peteromalley/Documents/Arnold`.
Invoke a new child with explicit model `gpt-5.6-luna` and high reasoning. Give it
this exact bounded task:

> Read
> `/Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.
> Return one JSON object only with keys `nonce`, `line_37_contains`,
> `requested_model`, and `mutations_performed`. The nonce must equal
> `SOL-LUNA-GPT56-20260802-PASS3-9C42`. `line_37_contains` is true iff the text of
> line 37 contains the substring `nested delegation`. `requested_model` must be
> `gpt-5.6-luna`; `mutations_performed` must be false. Do not edit anything.

Capture the child exit code, stdout and stderr SHA-256, child session ID, and the
model shown in the child's startup header. Independently read line 37 yourself
and evaluate substring containment. Do not use whole-line equality. Do not run
from an untrusted temporary cwd. Do not delete anything.

Return one final JSON object only with keys: `passed`, `parent_requested_model`,
`child_requested_model`, `child_header_model`, `child_session_id`,
`child_exit_code`, `nonce`, `stdout_sha256`, `stderr_sha256`,
`line_37_contains_nested_delegation`, and `mutations_performed`. `passed` may be
true only if the actual Luna child ran successfully, its header/session/model
are captured, all child fields are exact, your independent substring check is
true, and neither process mutated files.
