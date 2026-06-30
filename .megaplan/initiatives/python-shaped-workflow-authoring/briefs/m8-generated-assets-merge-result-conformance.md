# M8: Generated Assets And Merge-Result Conformance

## Outcome

Run the post-authoring final conformance pass that the cleanup chain could not perform once M5/M7 had already advanced. All generated assets should now reflect Python-shaped workflow authoring as the product-facing surface.

## Source Material

- M1-M7 outputs.
- Cleanup chain M5 generated-assets and merge-result conformance brief.
- Current docs, skills, CLI snapshots, examples, package ledgers, and manifest identity ledgers.

## Scope

Regenerate and verify:

- Docs and user-facing examples.
- Generated skills/assets.
- Pipeline registries/catalogs or derived metadata.
- CLI help/snapshot output.
- Package inclusion ledgers.
- Manifest identity ledgers derived from authored workflow source.
- Merge-result conformance from an integrated checkout.

Run final gates:

- Chain done gate.
- Purge/deleted-surface gate.
- Source/wheel/sdist builds.
- Installed-wheel positive and negative tests.
- Dynamic import tracing.
- `sys.modules` deleted-prefix audit.
- Python-shaped authoring check/compile/inspect/explain smoke tests.

## Constraints

- Do not certify stale explicit DSL fixtures as the final source of truth.
- Generated catalogs are derived artifacts only.

## Done Criteria

- The repository’s shipped state presents Python-shaped workflow files as the main authoring interface.
- Generated assets and package artifacts agree with the new source of truth.
- Merge-result conformance passes on the integrated result.
