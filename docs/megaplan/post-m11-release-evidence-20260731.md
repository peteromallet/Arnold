# Post-M11 consolidation release evidence

Status: **in progress**. Evidence cut:
`20644b23a7e041caad15684ddba07e703ca1c5af`, tree
`3518bd92e7ef7a1af6883879c41c179d1ff46d9c`.

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
  `20644b23a7e041caad15684ddba07e703ca1c5af`
- Exact evidence-cut tree:
  `3518bd92e7ef7a1af6883879c41c179d1ff46d9c`

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
11. canonical fixer-occurrence custody; and
12. reconciliation of five stale cloud-supervisor test modules with the
    post-M11 contracts; and
13. repair of M11 validation node-ID accounting, recovering all 208 omitted
    node IDs and closing ticket `01KYV57FAPY2H0ZRQMM8MJ29EM`; and
14. resolution of the three packaging release-contract blockers;
15. durable inclusion of the post-M11 evidence ledger; and
16. canonicalization of four normative initiative artifacts, with obsolete
    paths removed and references updated.

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
- 650 passed across the five-file cloud-supervisor reconciliation matrix at
  commit `5642cdd1ac5749aaf206bccdc5723613493e6db3`.
- A pinned-runtime subset collected and passed 431 of 431 tests at that same
  commit. The ledger binds its command, dependency freeze, composite runtime,
  and log hashes.
- The node-ID repair's focused suites passed 74 tests and recovered the 208
  IDs the old parser had silently omitted.

Two attempted full no-debt validations are retained as failure history, not
acceptance. The first exposed the node-ID defect at `5642cdd1ac`; the second
was a seeded run at `bf5449ae0e` that was aborted and superseded. Neither may
be promoted into a final green receipt.

Packaging evidence is also partial:

- the earlier 132-pass run identified three concrete packaging blockers under
  the framework-managed Python 3.12 runtime;
- commit `81a44fd930` resolved all three, after which focused and expanded
  matrices passed 17 and 110 tests respectively;
- four fresh non-editable installation smoke tests passed;
- all 47 cloud-template tests passed under that runtime;
- rebuilt wheel and sdist hashes are recorded in the JSON; and
- the packaging **code gate is complete**, but the cloud image build remains
  pending because the Docker daemon was unavailable during the local attempt.

The fresh-wheel evidence log hash is
`384cb2f6325a2bde92a625db9cace86117f89be76e05a53011788e55ed9bfdc5`;
it supersedes the incorrectly recorded earlier value.

The first full no-debt attempt at `cd7c6ac0ee` reached shard 002 and failed nine
conformance tests. Its immutable receipt, custody, terminal, and failure-list
hashes are retained in the JSON as superseded failure evidence. The underlying
issue was real: four normative initiative artifacts occupied noncanonical
locations and an obsolete legacy-reference exception remained. Commit
`3ca68e0e3b` moved the artifacts into `validation/`, `research/`, `decisions/`,
and `evidence/`, removed the obsolete locations, and passed 275 adjacent plus
55 focused conformance tests. That fixes the observed defect but does not turn
the failed shard into acceptance; a fresh full no-debt run is still required.

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

- Freeze and execute the final integrated and no-debt validation inventories.
- Run the cloud-image build against an available Docker daemon and bind it to
  the final release candidate.
- Promote the exact validated commit through the authorized ordinary
  fast-forward compare-and-swap push in
  `post-m11-direct-promotion-policy-override-20260731.md`; no PR or force push.
- Record the exact main merge SHA and annotated tag.
- Build and promote a content-addressed runtime from that exact main SHA.
- Prove resident, watchdog, three-hour fixer, `/whats-cooking`, ten-minute
  canary, and recurring-cycle health.
- Rebind the unchanged authoritative Critique initiative to that runtime,
  launch it through the supported cloud-chain path, and observe durable
  progress.
- Perform cleanup deletions only after per-item user approval.

Until those receipts exist, the correct label is **in progress**, not done.
