You are the sole synthesis/delivery owner for fixing the resident-managed successor queue so future authorized tasks can be queued reliably.

Current user request: "Can you fix this issue so we can queue tasks from now on."

Observed durable evidence:
- Queue successor subagent-20260715-211742-c2dd4b4a terminated dependency_failed with attention=invalid_dependency_contract because predecessor subagent-20260715-203137-46254c64 was resolved as status unknown.
- Existing repair run subagent-20260715-210357-6b134a2c is still reported running and already owns implementation of the cross-request custody/queue seam. Another repair run subagent-20260715-210435-dfad9559 completed, but its attempted successor still failed.
- A recent runtime revision added queue support, but end-to-end queue creation/transition is not proven.

Ownership and boundaries:
1. Reconcile the existing repair owner's current durable result/log/state first. Do not create overlapping edits. If it is genuinely active and making progress, consolidate/adopt its verified work; if stale or superseded, record that evidence and take over safely.
2. Inspect both the dirty project checkout and the pinned resident runtime. Discover and record the actual writable target; never infer literal main. Use an isolated worktree/feature branch for mutation.
3. Root-cause and fix the queue contract, including cross-request same-user custody/provenance, predecessor lookup/status normalization, success gating, cycle/cancellation/failure behavior, and bounded retries. Preserve fail-closed behavior for genuinely unauthorized or ambiguous provenance.
4. Add regression tests reproducing the exact unknown-predecessor/invalid_dependency_contract failure plus ordinary linear success-only queueing. Run proportional focused tests and the relevant resident suite.
5. Review the diff, commit it, revalidate the target ref, and locally integrate only into the verified unambiguous non-main/pinned runtime target according to repository policy. Do not push or mutate a remote default branch without explicit authorization.
6. Activation is authorized because the user asked to make queueing work from now on. If activation needs a Discord resident restart, use only `agentbox services restart agentbox-discord-resident`; record its supported receipt, installed/runtime revision reconciliation, service health, and outcome probe. The current turn may be interrupted; detached agents/chains must remain preserved.
7. Prove end to end with a harmless, bounded real queue probe: create a success-gated successor against a known valid predecessor (or a purpose-built no-op predecessor), observe durable queued state, predecessor completion, successor launch exactly once, and terminal result/delivery semantics. Clean up only disposable probe artifacts where supported; do not destructively alter unrelated runs.
8. Record exact base/target revisions, commit SHA, clean isolated worktree, tests, ancestry evidence for local integration, restart receipt if used, active runtime revision, and queue probe run IDs/state transitions.
9. Deliver one concise Discord-facing completion to the current request only after durable proof. If blocked by a true approval gate, state the exact gate and evidence; do not claim success from a PID, acknowledgement, patch, or agent prose.

Expected outcome: future authorized resident tasks can be queued linearly and success-gated, with the exact prior failure covered by tests and a live durable queue probe proving activation.
