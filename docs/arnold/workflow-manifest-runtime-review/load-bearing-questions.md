# Load-Bearing Questions For Workflow Manifest Runtime

Date: 2026-06-21

These are the decisions the plan rests on. If one answer changes, multiple milestones need to change.

## 1. What is the canonical runtime source of truth?

Answer: The compiled `WorkflowManifest` plus append-only event journal and content-addressed artifacts. Python DSL objects, old native programs, generator frames, mutable state files, package discovery manifests, and generated docs are not runtime authority.

## 2. What is the canonical authoring source?

Answer: Explicit-node Python data via `arnold.workflow.Pipeline` and pure `arnold.patterns` constructors. `build_pipeline()` returns `workflow.Pipeline`; `WorkflowManifest` is compiler output. Restricted Python/generator syntax remains private or future sugar, not the migration target.

## 3. Where is the neutral/product boundary?

Answer: `arnold.kernel`, `arnold.workflow`, `arnold.patterns`, `arnold.execution`, and any surviving neutral `arnold.agent`/`arnold.control` surfaces define neutral contracts. Product packages such as `arnold_pipelines.megaplan` and standalone `arnold_pipelines/<name>` packages register prompts, policies, reducers, capabilities, control meanings, and content types through protocol registries. Neutral runtime never imports product modules directly or by resolving manifest strings at runtime. Any `TYPE_CHECKING` cross-boundary exception must be explicit and scanner-enforced.

## 4. How do pipeline identity and version alignment work?

Answer: `workflow.Pipeline.id` is the stable human alias. `Pipeline.version` is authoring metadata unless explicitly promoted by the M1 identity contract; `manifest_hash` is the runtime identity discriminator. The compiler computes `WorkflowManifest.manifest_hash` over the normalized manifest. Registries, discovery manifests, trust/tenant derivation, generated artifacts, CLI fixtures, and resume cursors derive from `id + manifest_hash`; final M6 evidence recompiles every surviving `build_pipeline()` from the final tree and proves every reference matches.

## 5. How is behavior parity proven?

Answer: By locked golden normalization, shadow/dual-run characterization traces, a canonical manifest fixture matrix, semantic manifest diffs, fake-run/replay/resume gates, live-backed smoke across meaningful scenarios, installed-wheel CLI/operator parity, and refusal to update goldens for migration convenience.

## 6. How are old `.megaplan` state and resume handled?

Answer: The event journal becomes authority. Old state is migrated, projected read-only with a sunset, archived outside the active tree, deleted, or quarantined with operator-visible rationale. Surviving suspended runs get manifest-coordinate aliases or explicit quarantine. No surviving runtime/operator path may depend on old `state.json` authority after M6.

## 7. How are dynamic topology, control, override, fallback, and supervisor behavior represented?

Answer: Planned topology variants such as robustness level and feedback phase compile to distinct manifests. Runtime overlays are control-transition events projected into views, not manifest mutations. Megaplan owns concrete meanings for override, fallback, escalation, compensation, supervisor promotion, and tiebreaker policy through startup protocol registries; kernel/execution owns event envelopes, ordering, idempotency, and fail-closed dispatch.

## 8. What happens to shipped pipelines, examples, templates, and generated skills?

Answer: Public shipped pipelines migrate to `workflow.Pipeline` under final `arnold_pipelines` locations or are deleted. Whitelist is only for zero-public-surface internal coverage with owner, expiry, independent review, and no old-native teaching surface. Generated skills/docs/scaffolds are teaching surfaces and must be regenerated, provenance-stamped, semantically scanned, and fake-run where they contain examples.

## 9. What makes the clean break real?

Answer: M6 is not complete until deleted surfaces are absent from source, tests, scripts, generators, docs, generated artifacts, wheel, sdist, entrypoint metadata, type stubs, bytecode caches, runtime import traces, and filesystem read traces. The final proof runs from a clean installed wheel/sdist and from the post-merge checkout, not only from editable source.

## 10. How do downstream discoveries change earlier decisions?

Answer: Any downstream discovery that requires manifest/kernel/runtime contract changes must go through the amendment protocol, update M1/M2/M3 contract tests, refresh affected fixtures/artifacts, and block downstream milestones until the plan and tests line up. Post-merge conformance rechecks the integrated result so branch merge order cannot reintroduce stale contracts or deleted surfaces.
