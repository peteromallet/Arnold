# T3.6 independent ticket closure and release receipt — Luna preparation

Verdict: **NO CLOSURE OR RELEASE CLAIM; preparation only.**

## Exact subjects

Independently recompute both open ticket contracts from their immutable ticket blobs:

- umbrella `01KYSBGRHM1S8R6RQ1DGZ7843Y` (association-only; no epic may auto-resolve it);
- deployed-canary `01KYVJ7A47TMH4BRGEV9JFTK10` (code/local proof cannot close it).

Expected release identity is supplied independently before verification and binds exact source commit/tree, pushed remote head, source/acceptance tags, wheel/sdist/RECORD, container image, installed package/runtime/interpreter/import roots/wrappers/config/schema/routes, RA revision/fence, Custody epoch, WBC generation, live process/vector and evidence-manifest digests.

## Required current evidence

Require accepted, unexpired, nonrevoked T2.2 no-debt/offline candidate, T2.3 exact installed `admit/run/verify` with four independently derived deployed proofs, T2.4 full installed replay/fault suite, T2.5 all configured routes, T2.6 deploy decision, T3.1 atomic preflight, T3.2 old-writer fence, deployment receipt, T3.4 two-observer live attestation and T3.5 recovery/rollback-or-forward-fix canaries. Recompute both ticket requirement maps against raw owner evidence; historical/superseded/rejected/narrative/checklist/marker/tag-only evidence is inadmissible. Every production-only clause must now be proved, not deferred.

## Separation and quorum

The verifier is independent of implementer, integrator, deployer, canary producer, ticket editor and Release Authority signer. Domain owners attest only their facts; Run Authority, Custody and WBC attest their stores; two live-vector observers remain separate. Closure quorum requires independent verifier PASS, every named ticket/domain owner, and Release Authority. No majority can override a missing owner, UNKNOWN or failed predicate.

## CAS closure transaction

1. Freeze expected ticket versions/status/blob hashes and current release/owner heads.
2. Recompute both proof maps and release vector twice from immutable/raw sources.
3. Release Authority records a pending dual-closure intent with idempotency key and pre-issued revoke/reopen capability.
4. CAS-close canary ticket first, binding its deployed-proof receipt; reread exact closed version.
5. CAS-close umbrella second, requiring canary closure version plus all umbrella proofs.
6. Atomically finalize one release receipt only after both exact closure versions are observed. Annotated acceptance tag/status projections follow the receipt; they are not its authority.

If the second CAS fails, do not pretend atomic success: reconcile the first closure against the pending intent and either resume exact second CAS or use the signed reopen capability. Response loss at intent, either closure, receipt, or tag is `UNKNOWN`; query the ticket/Release Authority owner by idempotency key and adopt the exact committed result. Never issue a fresh closure blindly.

## Release receipt schema

Bind schema/version; decision/intent/idempotency IDs; both ticket IDs, prior/final versions, blob hashes and closure receipts; exact release vector above; every evidence digest/query window; signer identities/keys/revocation heads/quorum; verifier code/runtime/raw-output digest; deployment/canary/rollback/live-attestation receipts; remote/tag identities; created/expires times; result; reopen/revoke capability digest; and canonical bundle hash plus owner signature. SHA-256 identifies bytes but does not authenticate ownership.

## Reopen and revoke

Any later discovered forged/missing evidence, deployed-vector drift, revoked signer, schema/route change, old writer, canary contradiction or unresolved effect triggers an append-only Release Authority revocation and CAS reopen of affected ticket(s). Never rewrite the old receipt. Umbrella cannot remain closed if the canary closure is revoked. A new revision requires full recomputation and a new receipt; ancestry cannot inherit acceptance.

## Finite negatives

Reject forged expected HEAD/tree; mixed source/runtime; local canary substituted for deployed; omitted ticket clause; association auto-close; stale ticket version; stale/revoked signer; producer=verifier; missing owner/quorum; historical receipt promotion; UNKNOWN relabeled PASS; old writer; expired T3 receipt; live-vector drift; forged remote/tag; first-close success/second-close conflict; lost response at every CAS; duplicate intent; receipt before both closures; tag before receipt; closure after evidence expiry; reopen without capability; new commit claiming inherited release.

Current closure is impossible: prerequisites are preparation/incomplete and no accepted installed production vector or owner-installed Release Authority exists. No code, Git, cloud, provider, process, owner, ticket or checklist state was mutated. This report is the sole write; SHA-256 is external.
