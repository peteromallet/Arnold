# F2 — Generalize admission, model, effect and release closure

## Outcome

Extend the Stage-A route-scoped protections to every shipped production route
and effect family, then issue the zero-debt release decision required before v3
ordinary execution/publication authority expands.

## Scope

Complete platform generalization of T1.1-T1.4; migrate all production effects
under T1.6; finish T2.2, full T2.4, all configured T2.5 routes and T2.6; run broad
T3.5 canaries; close the two administrative T3.6 release tickets; and keep the
exact incident replay as a permanent candidate gate.

## Locked decisions

- Every physical model attempt has owner-bound transport evidence and typed
  health; only `SUCCEEDED` may yield a semantic result.
- Raw target-bound evidence, not a projection, grants admission.
- Every external effect has a WBC occurrence, durable pre-effect intent, exact
  reconciliation and sticky UNKNOWN/no-redispatch behavior.
- Unavailable routes and effect families remain hard-denied until proven; no
  dynamic fallback or caller-minted authority.
- Offline evidence is not deploy authority. Release acceptance binds the exact
  integrated and installed generation.

### Architecture-fit gate

F2 must consume the canonical Custody Control Plane adoption contracts rather
than add wrappers around them. Its entry-point inventory must identify one
authoritative admission writer, one WBC evidence path, and one Custody lease /
occurrence path; every other path is denied, read-only, or explicitly expiring.
The first accepted slice is one end-to-end response-loss/restart recovery
through those owners, not a new reconciliation subsystem.

## P2 control-plane acceptance (required, not advisory)

The initiative-local mapping in
[`../evidence/p2-control-plane-mapping-20260804.md`](../evidence/p2-control-plane-mapping-20260804.md)
is a durable planning input. F2 must prove the following across every shipped
entry point and installed generation:

- Every launch, resume, override, adoption, bootstrap, epic-chain refresh and
  AgentBox replay presents one admission token. Direct `cloud exec`,
  `force-proceed`, and unsafe adoption are denied or require an explicit,
  auditable break-glass path.
- Provider authority is role-scoped (`orchestration`, `task`, `validation`),
  resolved by one canonical resolver, and verified before lease/resource
  acquisition and again on resume. No route can mint a provider authority by
  falling back to a profile alias.
- Lease/process/source/runtime identity is bound into installed-parity and
  hostile-fault evidence; marker, tmux, or PID presence alone can never produce
  an `executing` decision.
- Status is snapshot-first with a bounded live fallback; every projection is
  correlated to attempt and generation, and incident notifications are durably
  deduplicated across refresh/restart.
- A cross-entry-point inventory proves exactly one authoritative writer for
  each execution/effect state and shows no bypass path.

These obligations require dynamic inventory, source tests, installed tests,
crash/restart tests, hostile replay, and receipt-level evidence. They are
follow-up hardening and must not be used to bypass the safe-v3 canary
preconditions or to widen its bounded authority early.

## Open questions

- Which configured routes/effect families are intentionally retired rather than
  migrated? Record explicit owner decisions and absence proofs.

## Constraints

Do not re-run or widen the accepted Stage-A canary merely to collect evidence.
No broad production authority until F1 and F2 completion manifests both exist.

## Done criteria

- All admission/attempt/graph routes and effect families pass dynamic inventory,
  hostile replay/response-loss, installed parity and direct-module tests.
- Full installed fault/crash matrix and all configured live route canaries pass.
- T2.6 zero-debt decision and exact T3 release/ticket evidence are accepted.
- Permanent incident replay fails any candidate that recreates false success,
  duplicate fixer/notification, blind resend or broken fence.
- Architecture-fit receipt proves every launch/resume/replay route uses the
  existing owner contracts and that no parallel authority, watcher, queue, or
  snapshot system was introduced.

## Touchpoints

Run Authority admission, contract bundles, critic attempt ledger, graph repair,
WBC, route registry, release evidence, installed generation and evidence for
T1.1-T1.4/T1.6/T2.2/T2.4-T2.6/T3.5-T3.6/T8.3.

## Anti-scope

Do not execute CL2 feature work, publish its PR, deploy the product, or close the
incident.
