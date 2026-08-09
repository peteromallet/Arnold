# Sol final plan request — control-plane hardening and safe restart

Read only these two evidence files:

- `evidence/critique-ledger-recovery/sol-broader-review-compact-brief-20260804.md`
- `evidence/critique-ledger-recovery/luna-synthesis-20260804.md`

Do not inspect the repository, delegate, or edit. Produce the final implementation plan for this user goal: make the current critique session resume safely on the cloud and remove the broader class of failures across all cloud megaplan pipelines. Take firm positions and order the work. Separate:

1. The minimum repair required before touching the current session.
2. The exact safe steps to resume the existing plan, including how U1/quality blockers remain authoritative.
3. The shared control-plane changes that must ship next (runtime identity, lease/liveness, evidence ordering, lineage, provider preflight, observer bounds).
4. What can run in parallel, what is a very-hard/high-risk judgement call, and what must remain human-gated.
5. A conformance/rollback test matrix proving the fix generalizes.

State explicitly whether the combined work prevents recurrence or only improves detection/recovery, and name any residual risk. Keep under 1400 words.
