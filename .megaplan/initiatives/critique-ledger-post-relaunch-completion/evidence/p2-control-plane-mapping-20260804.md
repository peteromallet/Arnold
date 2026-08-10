# P2 control-plane findings mapped to this epic — 2026-08-04

Source: `evidence/critique-ledger-recovery/p2-to-post-relaunch-epic-mapping-20260804.md`

The source digest at capture time was
`99ebcc33b5cec141431d106d3e0d8e48dc017d301dbc7d9fd2b3759c76f0aaca`.
This initiative-local copy is the durable planning input; the source tree is
not staged wholesale because it also contains runtime output and preserved
worktrees.

The follow-up is intentionally post-canary. It must not create a parallel
authority ledger or bypass the safe-v3 T6.2 handoff. The current chain is
expected to remain launch-blocked until that independently accepted,
content-addressed handoff and its committed acceptance evidence exist.

## F1 — owner, storage and recovery acceptance

- VJ9/VJ8 contract separation: exact idempotent retry deduplicates; divergent
  same-key retry raises a typed conflict; store and outbox use one canonical
  serializer.
- Every failure, receipt, phase result and recovery mutation carries
  attempt/occurrence/fingerprint/generation; stale artifacts cannot clear a
  newer failure.
- Runtime/source/worktree/interpreter/test identity is bound to the repair
  receipt; changed imports or test hashes fail before mutation.
- Custody-issued occurrence IDs, Run Authority monotonic consumed grants/CAS,
  exact wrapper handoff and WBC notification intent/outcome evidence remain
  outside caller-writable projections.
- Snapshot/projection corruption, storage failure and notification replay are
  explicit and fail closed.

## F2 — admission, model, effect and release acceptance

- Every launch/resume/override/adoption entry point presents one non-bearer
  canonical action-envelope receipt. Direct `cloud exec`, `force-proceed`, unsafe `adopt-execution`,
  bootstrap, epic-chain refresh and AgentBox replay are denied or break-glass.
- Provider route/capability attestation is role-scoped (`orchestration`, `task`, `validation`),
  resolved by one canonical resolver, and verified before lease/resource
  acquisition and on resume.
- Lease/process/source/runtime identity is part of installed-parity and hostile
  fault testing; no marker/tmux/PID-only `executing` state is accepted.
- Snapshot-first status, bounded live fallback, attempt/generation correlation
  and durable incident dedupe are included in installed conformance.
- Cross-entry-point inventory proves exactly one authoritative writer and no
  bypass.

The occurrence-specific subset is a prerequisite only through the independently
accepted r5 quarantine/migrated-child and T6.2 handoff. Cross-entry-point
generalization remains F1/F2 follow-up and must not hold the bounded canary
hostage; unproven surfaces stay denied. Neither layer may weaken a safe-v3
canary launch precondition.

## Incident-specific amendment

The relaunch evidence also produced an explicit amendment,
[`incident-specific-control-amendment-20260804.md`](incident-specific-control-amendment-20260804.md),
with acceptance ID `incident-specific-control-amendment.v1`. It closes the
remaining implicit edges: P1 containment of every cloud/replay entry point;
one non-bearer WBC + Run Authority + Custody action-envelope receipt; exact
occurrence/generation stale rejection; shared credential bootstrap and
role-scoped pre-lease authentication; configured `runtime_python` use in all
generated commands; snapshot-first status and durable notification dedupe;
projection-cursor reconciliation; and legacy-session classification with
human-gated takeover. These are required F1/F2 acceptance evidence, not a
reason to bypass the current canary boundary.
