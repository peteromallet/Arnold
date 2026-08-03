# Critique attempt 9 launch-contract delta

The recovery is a phase-boundary continuation of the existing r5 plan, not a
new epic or plan. Preserve the workspace, plan name, history, and accepted
planning artifacts.

## One-shot Finalize

1. Keep the chain runner stopped and the session marker non-runnable. The plan
   lifecycle state itself must remain `gated`; `finalize` correctly rejects a
   durable plan state of `paused`.
2. Terminate only the exact attempt-8 process tree after revalidating its
   run/process identity.
3. Call `cancel_active_phase_wbc_attempt` with attempt 8's exact WBC attempt,
   invocation, run ID, and ordinal. Reread `state.json` and the WBC ledger:
   attempt 8 must be `STARTED -> CANCELLED`, its active owner must be absent,
   and cancellation history must retain ordinal 8.
4. From the runtime-attested engine checkout invoke exactly once:

   ```sh
   python -P -m arnold_pipelines.megaplan finalize \
     --plan cl2-wbc-backed-ledger-20260803-1357
   ```

   Do not wrap this command in `auto`, a shell retry, or a deterministic
   three-attempt loop. The direct phase command has no outer retry driver.
5. On success require exactly one new phase-WBC stream, ordinal 9, with
   `STARTED -> COMPLETED`; require lifecycle state `finalized`, no active
   Finalize owner, and `next_step=execute`. Resuming the existing chain then
   routes to Execute and cannot rerun Finalize from `finalized`.
6. On failure require exactly one attempt-9 terminal, lifecycle state still
   `gated` (or an explicit terminal/manual-review projection), no active owner,
   and no attempt 10. Keep the runner stopped and diagnose before any explicit
   new operator action.

## Execute model contract

`partnered-5-glm` resolves Execute's coordinator and every complexity tier
1–10 to GLM-family routes. Each tier prefers direct Zhipu GLM 5.2, falls back
to Fireworks GLM 5p2, then retries direct Zhipu. DeepSeek remains available for
prep/critique/gate; GPT-5.6 Sol high remains exclusive to Finalize.

