# F5 — Accept, build and deploy the Critique Ledger product

## Outcome

Accept and merge the completed successor implementation, build an exact
content-addressed product generation, and deploy it through the product Release
Authority with old product writers and effects fenced.

## Scope

Implements T7.1, T7.2 and T7.3.

## Locked decisions

- Ordinary publication custody owns PR acceptance and merge.
- The generation binds implementation source, migrations, config, runtime,
  contract bundle, fixtures, rollback/forward-fix and target environment.
- Product deployment requires an explicit installed Release Authority
  command/API, contract/help digest, rollback token and stop capability—or an
  independently proven accepted T3 generation transaction that owns this exact
  product subject.
- Epic completion, merge or process liveness does not authorize deployment.

## Open questions

- Does the accepted platform generation transaction cover the exact product
  deployment subject, or is a product-specific owner transaction required?

## Constraints

No generic deployment script, mutable-latest artifact, silent migration,
unfenced old writer or unverified runtime/source mixture.

## Done criteria

- Successor PR is accepted and merged with exact WBC receipts.
- Product generation manifest is content-addressed and independently recomputed.
- Backup, rollback or forward-fix and stop capability are proven before cutover.
- Exact installed vector is attested after deployment; old writers reject.

## Touchpoints

Critique Ledger product code, migration/config, release owner, cloud generation,
deployment selector and `evidence/critique-ledger-recovery/T7.1-T7.3/`.

## Anti-scope

Do not broaden rollout or close the incident before production acceptance.
