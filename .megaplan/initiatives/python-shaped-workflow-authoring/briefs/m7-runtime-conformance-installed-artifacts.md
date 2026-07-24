# M7: Runtime Conformance And Installed Artifacts

## Outcome

Prove that Python-shaped authoring is behaviorally equivalent to the manifest runtime path in source, editable checkout, wheel, and sdist installs.

## Source Material

- M1-M6 outputs.
- Existing runtime conformance, installed-wheel, dynamic-import, source/wheel/sdist, and purge gates.
- Current Megaplan golden behavior fixtures.

## Scope

Prove:

- Authored source -> DSL -> manifest -> runtime execution equivalence.
- Manifest identity and provenance stability.
- Event journals, artifact refs, resume cursors, suspension, loop/retry behavior, and review/rework semantics match the previous canonical runtime.
- Wheel/sdist installs include workflow source, prompt resources, component metadata, and required package data.
- Deleted legacy surfaces remain absent from source, wheel, sdist, dynamic imports, and `sys.modules`.
- Failure cases remain deterministic and diagnosable.

## Constraints

- Topology parity alone is insufficient.
- No permanent compatibility shims may be added to make tests pass.

## Done Criteria

- Runtime equivalence is proven by tests and ledgers.
- Installed artifacts work without repo-relative assumptions.
- Legacy runtime/authoring surfaces stay deleted.
