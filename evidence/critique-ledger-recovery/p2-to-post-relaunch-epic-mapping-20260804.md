# P2 findings mapped to the new critique follow-up epic — 2026-08-04

The relevant follow-up is:

`.megaplan/initiatives/critique-ledger-post-relaunch-completion/`

Its chain is deliberately post-canary. Read-only chain status currently fails
the first launch precondition because
`handoff/safe-v3-canary-completion-manifest.json` is missing. This is expected
to block launch; it must not be bypassed.

## Recommendation

Do not create another epic or add a new parallel authority ledger. Amend F1/F2
and the unfinished-work custody ledger with the concrete P2 findings below.

### F1 — owner/storage/recovery

Make these explicit acceptance items:

- VJ9/VJ8 contract separation: exact idempotent retry deduplicates; divergent
  same-key retry raises a typed conflict; store and outbox use one canonical
  serializer.
- Every failure, receipt, phase result, and recovery mutation carries
  attempt/occurrence/fingerprint/generation; stale artifacts cannot clear a
  newer failure.
- Runtime/source/worktree/interpreter/test identity is bound to the repair
  receipt; changed imports or test hashes fail before mutation.
- Owner-issued occurrence IDs, monotonic consumed grants, exact wrapper handoff,
  notification dedupe, and no-redispatch semantics remain outside caller-
  writable projections.
- Snapshot/projection corruption, storage failure, and notification replay are
  explicit and fail closed.

### F2 — admission/model/effect/release

Make these explicit acceptance items:

- Every launch/resume/override/adoption entry point presents one admission token;
  direct `cloud exec`, `force-proceed`, unsafe `adopt-execution`, bootstrap,
  epic-chain refresh, and AgentBox replay are denied or break-glass.
- Provider authority is role-scoped (`orchestration`, `task`, `validation`),
  resolved by one canonical resolver, and verified before lease/resource
  acquisition and on resume.
- Lease/process/source/runtime identity is part of installed parity and hostile
  fault testing; no marker/tmux/PID-only `executing` state.
- Snapshot-first status, bounded live fallback, attempt/generation correlation,
  and durable incident dedupe are included in installed conformance.
- Cross-entry-point inventory proves exactly one authoritative writer and no
  bypass.

## Boundary

These amendments are follow-up hardening. They must not become prerequisites for
the bounded current-run recovery beyond its existing VJ9/source/runtime/lease
gates, and they must not be used to bypass the safe-v3 canary preconditions.
