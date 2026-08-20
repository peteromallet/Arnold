---
type: anchor
anchor_type: north_star
slug: runtime-convergence-promotion
title: 'North Star: Runtime Convergence Promotion'
created_at: '2026-08-20T09:08:24.349167+00:00'
---

# North Star: Runtime Convergence Promotion

## End State

Both active epics execute the same certified Arnold revision from two distinct,
immutable, per-epic runtime roots. Their runtime manifests, chain bindings,
markers, launch seeds, live imports, and dependency-generation proofs agree.
The prior Astrid `4ef83c15d9` and maintenance `d38c3980a6` generations remain
available for verified rollback.

## Non-Negotiables

- Canonicalize exact SHAs, never mutable branch names.
- Never edit or fast-forward a live runtime root in place.
- Never share one active source root between epics.
- Do not cut over Astrid during an active phase or with incoherent marker,
  lease, PID, chain, or import evidence.
- Dependency compatibility requires equal frozen-spec and venv digests; path
  equality is not proof.
- Use CAS-guarded manifest, chain, and marker operations with rollback receipts.
- Do not treat provider HTTP 402 as product evidence or retry it blindly.
- A non-empty equal-mode reconcile selection is a release blocker.

## Explicit Non-Goals

- Garbage-collecting old runtime roots or receipts.
- Cleaning unrelated dirty maintenance documentation, ledgers, or tickets.
- Resuming provider-billing failures merely to make the chain look active.
- Replacing the runtime-manifest or launch-attestation architecture.

## Allowed Temporary Bridges

- Maintenance may remain blocked while its new runtime is attested and observed.
- Astrid may remain on `4ef83c15d9` until a genuine between-milestone seam.
- The old and new dependency generations may coexist until both promotions are
  verified.

## Drift Signals

- Any proposal to mutate `/workspace/runtime-candidates/astrid-first` or
  `/workspace/runtime-candidates/arnold-4a830c6ac9a0` in place.
- Any reliance on a branch label without recording its resolved commit.
- Any claim that the shared venv is compatible without recomputing its digest.
- Any cutover while Astrid has an active worker or stale lease/marker mismatch.
- Any cleanup or deletion before both epics pass the post-cutover audit.
