# M2: Canonical Side Effects And Public Surface

## Outcome

Importing `arnold_pipelines.megaplan` is enough to establish all supported Megaplan import-time behavior. Import order with any temporary legacy shim cannot change content-type registration, model adapter installation, normalizer registration, public exports, or registry behavior.

## Scope

In:

- Identify and migrate load-bearing import side effects from legacy implementation modules to canonical modules.
- Add import-order subprocess tests covering canonical-only, legacy-only if still present, canonical-then-legacy, and legacy-then-canonical.
- Make adapter/content-type/model normalizer setup idempotent through an explicit canonical initializer.
- Reconcile public exports: either move supported symbols to canonical APIs or record deliberate removals with tests and docs.
- Update any aspirational tests that currently describe a future state so they match the actual milestone contract.

Out:

- Do not delete the legacy package yet.
- Do not create a final canonical `_pipeline` namespace.
- Do not preserve removed public names just to keep historical compatibility if the project has decided to clean-break them.

## Locked Decisions

- Canonical side effects live under `arnold_pipelines.megaplan`.
- Any temporary legacy import path delegates to canonical initialization.
- Import-order determinism is a release gate, not a nice-to-have.

## Done Criteria

- Import-order matrix tests pass in clean subprocesses.
- `arnold_pipelines.megaplan` does not need `arnold.pipelines.megaplan` for initialization side effects.
- Public export decisions are documented and enforced by tests.
- No shim points at a missing target.
