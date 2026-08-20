# T1.1 raw-evidence admission — bounded GPT-5.6 Sol-high repair pass 2

This is Stage-A critical and 🔥 VERY HARD. Work only in
`/private/tmp/arnold-critique-recovery-t1-1-admission-20260802` from exact clean
HARD-FAIL candidate `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`, tree
`f6c83fca884e9631c7518810ee521d75389815b3`, parent `6787d636...`.

Read the independent report:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-independent-review-pass1-sol-result.md`

Full-file SHA-256:
`1b7a9c7d94f3bfdf5b5ab92b01cda1d8ec1576a45029b54f814ffe9513642d1d`.

Fix exactly the four reproduced ordinary-path blockers. Do not perform a
wholesale revisioned ChainState migration, generic platform redesign, arbitrary
interpreter defense, or unrelated non-Megaplan cleanup.

## 1. Remove caller-mintable hermetic authority

- Ordinary shipped/installed production APIs must not accept a boolean,
  caller-selected backend, predicate deriver/allowlist, verifier key, launch
  grant or local authority initializer as admission authority.
- Separately package the hermetic backend or guard it with a non-forgeable,
  test-only capability unavailable to normal source/wheel callers. Production
  composition uses a fixed owner-installed endpoint/trust root and fails closed
  when absent.
- Rewrite positive tests to obtain preinstalled conformance authority without
  demonstrating the production exploit composition.

## 2. Root milestones require explicit owner policy

- Absence of `depends_on` and default `prerequisite_policy` must never silently
  authorize materialization for the incident v3 route.
- A root milestone may be generic only through an explicit owner-allowlisted
  no-prerequisite contract bound to exact spec/milestone/brief/source identity.
  The v3 Stage-A spec requires raw CL1 admission.

## 3. Bind protected target identity across every init path

- Direct `handle_init`, shared `_init_plan`, control adapters, workflow-canary
  helpers, installed entrypoints and ordinary wrappers must determine whether
  the requested brief/spec is an owner-gated milestone before any plan directory,
  state, subprocess or other mutation.
- A matching protected target must reserve/reconcile through the fixed owner;
  callers cannot discard its identity by entering outside chain start.
- Unrelated genuinely generic plans remain available only under the explicit
  no-prerequisite policy above.

## 4. Missing marker/projection rollback must consult owner truth

- Marker loss, rolled-back metadata and renamed/replaced plan directories must
  not downgrade an admitted target to generic.
- Resolve intended plan/protected target from immutable owner/index identity
  independent of directory name and mutable projection. Missing/corrupt/unknown
  owner lookup fails closed with zero mutation.
- Add the exact `restored-plan`, missing marker, empty metadata, owner-spy probe;
  owner must be queried and the unverified mutation rejected.

## Preserve accepted behavior

Keep the exact eight-role raw derivation, duplicate/extra/corrupt/symlink/tamper
rejection, deterministic reservation/CAS/replay/response-loss behavior,
materialization claim/completion interlock, handler mutation checks,
installed/source parity and T0.2 negative fixture.

## Finite validation

- committed hostile regressions for all four blockers across direct, legacy,
  supervisor, auto, control and installed entrypoints;
- existing 57 focused tests plus relevant chain/init/control dependency closure;
- two/200 concurrency, crash/response-loss and marker/projection replacement;
- source/wheel/materialized parity with production owner absence fail-closed;
- ruff/compile/diff/static inventory checks.

Large suites single-flight. Do not touch cloud/provider/production owner state,
markers, plans, checklist or git outside this worktree. Commit scoped code/tests,
leave clean, and write exact commit/tree/tests/limitations to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-repair-pass2-sol-result.md`

No formal completion without a new independent Sol-high review, clean-lineage
integration and installed production owner receipts.
