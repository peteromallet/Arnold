# F2 — Generalize admission, model, effect and release closure

## Outcome

Extend the Stage-A route-scoped protections to every shipped production route
and effect family, then issue the zero-debt release decision required before v3
ordinary execution/publication authority expands.

## Scope

Complete platform generalization of T1.1-T1.4; migrate all production effects
under T1.6; finish T2.2, full T2.4, all configured T2.5 routes and T2.6; run broad
T3.5 canaries; produce the launch-critical T3.6 release-authority receipt but
leave its two administrative ticket closures to F7. Consume the frozen T6.2
incident replay as input evidence only; F7 alone owns T8.3's permanent replay
gate and publication.
Add provider/server-attested backend-model identity and close the evidence
vocabulary across requested CLI model, sealed CLI-local turn context,
server-attested execution model and billing model.

## Locked decisions

- Every physical model attempt has owner-bound transport evidence and typed
  health; only `SUCCEEDED` may yield a semantic result.
- Requested model, `codex_cli_turn_context`, server-attested model and billing
  model are distinct typed fields. No field is promoted into another by name
  equality or prose.
- Model-identity evidence binds dispatch ID, phase, source, target, freshness
  and replay status. Providers without authoritative attestation return sticky
  `UNKNOWN` and cannot satisfy a gate that requires backend identity.
- Raw target-bound evidence, not a projection, grants admission.
- Every external effect has a WBC occurrence, durable pre-effect intent, exact
  reconciliation and sticky UNKNOWN/no-redispatch behavior.
- Unavailable routes and effect families remain hard-denied until proven; no
  dynamic fallback or caller-minted authority.
- Offline evidence is not deploy authority. Release acceptance binds the exact
  integrated and installed generation.

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
- Every supported provider proves requested/CLI-local/server-attested/billing
  identity separation, freshness and replay binding. Missing or contradictory
  attestation fails closed as `UNKNOWN`; no client rollout is labelled
  `provider_observed`.
- T2.6 zero-debt decision and the exact T3.6 release-authority receipt are
  accepted; the two administrative ticket closures remain explicitly pending
  for F7.
- The frozen T6.2 replay is consumed as immutable input without modifying or
  claiming T8.3 completion.

## Touchpoints

Run Authority admission, contract bundles, critic attempt ledger, graph repair,
WBC, route registry, release evidence, installed generation and evidence for
T1.1-T1.4/T1.6/T2.2/T2.4-T2.6/T3.5 and the release-authority subeffect of T3.6.

## Anti-scope

Do not execute CL2 feature work, publish its PR, deploy the product, or close the
incident.
