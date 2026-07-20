You are the sole synthesis/delivery owner for recovering the live custody-control-plane-20260714 epic and fixing the Superfixer failure class that stranded it after M5a.

Authorized outcome: get the original custody-control-plane-20260714 chain genuinely moving again, while repairing the first broken Superfixer layer and the backstop above it so this exact stale-goal/no-PR terminal-transition failure cannot silently spin again. This is execution work, not a read-only diagnosis.

Known evidence to verify, not assume:
- M5a reached terminal done/approved with local integration and intentionally no PR metadata.
- The chain emitted `PR #None closed during milestone completion; stopping chain`, leaving current_milestone_index=2, no current_plan_name, no live runner, and M6 uninitialized.
- Automatic repair remained bound to an older blocker/commit requirement, produced repeated no-verdict/stale-goal attempts, exhausted roughly 55 attempts, and did not retarget to terminal reconciliation.
- Current resident status around 2026-07-16 12:03 UTC classified the session as attention, not actively repairing.

Use the superfixer-debug methodology and the canonical Megaplan cloud/on-box operations. Inspect all six custody sources: process, marker JSON, chain JSON, plan state.json, log tail, and external git/PR/runtime state. Inspect actual repair-data, repair goals, L1 repair logs, L2/meta-repair evidence, and L3 auditor evidence. Separate evidence, inference, and missing telemetry.

Execution requirements:
1. Identify the first broken layer/axis and why the layer above failed to catch it. Confirm whether the cause is frozen blocker identity/cursor, no-PR completion semantics, token/dispatch drift, or a combination.
2. Fix the fixer rather than merely hand-advancing the epic. Patch the canonical resident/runtime source in an isolated worktree and feature branch based on the verified pinned clean attached runtime target. Preserve all dirty/concurrent work. Hunt sibling paths across L1/L2/L3.
3. Add regression tests for: a valid local/no-push terminal completion must advance rather than become “PR #None closed”; a terminal plan transition must supersede/retarget stale repair goals; repeated identical deterministic repair failures must circuit-break/escalate with the real current blocker; the auditor must detect stranded between-milestone state and stale repair-data.
4. Run proportional focused tests plus required wrapper/superfixer tests. Review the full diff. Commit and locally integrate to the verified target branch if unambiguous, recording base, target, commit SHA, clean isolated worktree, and ancestry proof.
5. Because the user’s explicit priority is to get the live chain moving, perform the established supported on-box activation/restart/retrigger operations that are necessary and safe for this Superfixer/watchdog path. Reconcile installed runtime revision exactly. Do not use broad pkill/killall/tmux cleanup; use supported scoped operations. Push only if the established Superfixer deployment policy requires the canonical runtime branch and exact target/revision reconciliation proves it is authorized; otherwise stop at the precise approval gate without claiming activation.
6. Re-trigger the fixed ordinary repair/reconciliation path on the original custody-control-plane-20260714 session. Do not count a launch receipt, PID, or repair prose as recovery. Verify durable chain evidence that M6 is initialized and has a live/progressing runner (or a later milestone), and verify the stale repair claim is superseded/closed.
7. Perform the retroactive L3 test: demonstrate the auditor would now detect and correctly route this failure class.

Do not weaken completion guards and do not fabricate PR metadata. Do not declare success unless the original chain durably advances. If an actual approval gate or conflicting writable target prevents the final action, report the exact gate and all completed evidence; otherwise continue through recovery. Deliver one concise Discord-facing completion with root cause, why 55 attempts were ineffective, exact fixes, commit/runtime receipts, and observed chain advancement.
