# M4: Evidence And Drift Gates

## Outcome

Prove the epic end state from a clean checkout. Add durable gates that keep trust claims, migrated composition authority, and export readiness from drifting apart again.

## Execution Posture

This milestone is about earning the claims. Do not broaden product scope. Tighten evidence, clean stale docs, and make the quality surface deterministic.

## Scope

IN:
- Re-run the relevant quality/test suite from a clean checkout or clean cloud workspace.
- Add or strengthen drift gates for forbidden extension trust claims.
- Add or strengthen drift gates for direct legacy reads in migrated shader/ref readiness paths.
- Add or strengthen tests proving user-facing export blockers originate from planner readiness.
- Reconcile docs matrices and supported/deferred language after the first three milestones.
- Produce a final completion note that maps North Star proof requirements to concrete files/tests.

OUT:
- New architecture beyond what M1-M3 implemented.
- Real untrusted-extension sandboxing.
- Additional composition fact-family migrations.
- Cosmetic docs rewrites unrelated to trust/composition/export convergence.

## Constraints

- Do not suppress failing tests without either fixing the behavior or documenting a precise deferred requirement outside release claims.
- Do not accept a dirty or stale evidence state as proof.
- Do not let docs claim future composition-spine or export capabilities as current support.
- Preserve generated runtime state and user work; do not use destructive git cleanup.

## Done Criteria

- Relevant extension, planner/export, SDK/schema, and docs quality checks pass from a clean base.
- A final proof note lists each North Star required proof item and the exact test, script, or document that proves it.
- Docs supported/deferred matrices agree with code and tests.
- Gates fail on each of these regressions:
  - UI/docs imply runtime permission enforcement or sandboxing.
  - migrated shader/ref readiness reads raw legacy timeline fields as authority.
  - user-facing export blocks bypass planner blockers.
- The epic can be handed off with no unresolved blocker hidden behind "supported" language.

## Touchpoints

- `package.json`
- `scripts/**`
- `docs/extensions/**`
- `src/sdk/**`
- `src/tools/video-editor/rendering/**`
- `src/tools/video-editor/runtime/composition/**`
- `.megaplan/initiatives/extension-reality-convergence-epic/**`

