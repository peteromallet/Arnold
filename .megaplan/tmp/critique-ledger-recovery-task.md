Act as the internal recovery owner for the live Megaplan session `critique-ledger-bigbang-20260716`, current plan `cl1-contract-ownership-and-m6-20260716-2157`, in `/workspace/critique-ledger-bigbang-20260716/Arnold`.

Objective: get this exact chain durably moving from `awaiting_human_verify` without weakening correctness or inventing human approval. Establish why preparation emitted this state, identify the supported state-machine action or missing verification step, perform all execution that is already authorized and safe, and verify the original session advances into real work. If there is a genuine approval decision that cannot be made from existing policy/evidence, do not bypass it: produce the exact narrow approval question and evidence. Treat a PID, command start, or prose claim as insufficient.

Required method and evidence:
- Start with `megaplan introspect`, then trace/doctor as needed; use `now_utc`, exact state events, configuration, and chain/plan records.
- Inspect the live process, marker, chain JSON, plan state, log/event tail, and relevant git/runtime state. Separate evidence, inference, and missing telemetry.
- Determine whether this is an expected human verification gate, an accidental merge/verify policy, a token/dispatcher mismatch, or another mechanism.
- Use only supported Megaplan/chain operations. Do not force-proceed unless the recorded policy and artifacts establish that no human judgment is required.
- Preserve concurrent work. For any git-backed fix, use an isolated worktree/feature branch based on the verified target; commit, test, revalidate the target, and locally integrate only when unambiguous. Do not push remotely.
- Verify recovery by observing the original session leave `awaiting_human_verify`, a live step with progressing liveness, and subsequent durable state/event activity. If blocked by a real approval gate, record why and the exact requested decision instead.
- Write a durable result with commands, timestamps, state transitions, tests, reviewed diff/commit/base/target/clean-worktree evidence for any mutation, and any raw artifact paths needed by the synthesis owner.

Do not send the user-facing completion. Report only to the synthesis/delivery owner in this delegation group.
