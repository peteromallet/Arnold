# Post-M11 consolidation release evidence

Status: **in progress**. Evidence cut:
`87ef026ba7bfced7906f27cb0d965b2b62c3884a`.

This is the human-readable projection of
[`post-m11-release-evidence-20260731.json`](post-m11-release-evidence-20260731.json).
The JSON record is authoritative for this evidence cut. It deliberately does
not call the release done: final integrated validation, the reviewed PR, the
main merge and tag, runtime promotion, canary, and Critique launch are still
pending.

## Authority

- Plan: `docs/megaplan/post-m11-loose-work-consolidation-release-plan-2026-07-29.md`
- Published plan commit:
  `f1c0b7384752ee96ea74eaee0f6c8d5d06c301d4`
- Exact plan blob: `8b8a157ae0e2ad89209dd1cde61791856997585b`
- Origin base containing that plan:
  `96127731661b4aeec7e049b8a7b59170a9506b06`
- Consolidation evidence cut:
  `87ef026ba7bfced7906f27cb0d965b2b62c3884a`

The original dirty checkout is preserved, not normalized. Its encrypted
payload and preservation bundle each have a local copy and a hash-matched
cloud copy. Paths in the JSON use `$LOCAL_CHECKPOINT_ROOT` and
`$CLOUD_WORKSPACE` intentionally; credentials and operator-specific absolute
paths do not belong in Git.

## What has landed by this cut

The first-parent lineage records eleven integration steps:

1. completed Custody control-plane M5-M11 lineage;
2. bounded supervision and atomic phase handoff;
3. immediate stability and authority closure fixes;
4. the finalized Native Parity and Platformization program;
5. provider recovery edge cases;
6. chain-completion reconciliation invariants;
7. context-budget and persistent Railway runtime fixes;
8. post-M11 ticket reconciliation;
9. repair publication and runtime custody containment;
10. explicit human-wait custody; and
11. canonical fixer-occurrence custody.

Every `LAND` source in the JSON names both its immutable source SHA and the
integration commit that contains it. The two dirty-work checkpoint branches
remain `KEEP_CHECKPOINT`; their existence is evidence preservation, not a claim
that all checkpoint contents should land.

## Validation interpretation

The recorded test counts are historical observations at their stated branch or
pre-integration scope. They are useful regression evidence, but none is a
substitute for the still-pending final integrated validation:

- 283 passed in the focused Custody conflict-resolution run;
- the first broader run found seven real integration failures after 275 passes;
- 289 passed and one skipped on the immediate-stability branch; and
- 488 passed on the bounded-supervision compatibility scope.

The seven-failure run remains in the record because failure history must not be
laundered by later fixes. A final green run must be bound to the final release
candidate SHA before this journal can be completed.

## Protected cloud custody

The completed Custody checkout and existing runtime candidate are protected
until final acceptance. The authoritative Critique checkout is also protected
and must not launch until its runtime binding points at the released main
runtime. The paused predecessor Critique epic is audit-only and must never be
resumed. The two divergent dirty Arnold cloud workspaces remain protected until
classified; this record authorizes no deletion.

## Remaining completion gates

- Freeze and execute the final integrated validation inventory.
- Open and review the release PR; do not push the consolidation directly to
  main.
- Record the exact main merge SHA and annotated tag.
- Build and promote a content-addressed runtime from that exact main SHA.
- Prove resident, watchdog, three-hour fixer, `/whats-cooking`, ten-minute
  canary, and recurring-cycle health.
- Rebind the unchanged authoritative Critique initiative to that runtime,
  launch it through the supported cloud-chain path, and observe durable
  progress.
- Perform cleanup deletions only after per-item user approval.

Until those receipts exist, the correct label is **in progress**, not done.
