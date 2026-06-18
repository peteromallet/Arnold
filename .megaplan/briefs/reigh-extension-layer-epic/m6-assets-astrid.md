# M6: Asset Metadata, Parser Contributions, Astrid Loop

## Outcome

Add sanctioned asset metadata and parser contributions, then prove the local-first extension loop against Astrid persistence.

## Execution Posture

Assets are shared project memory. Parser/output extensions should enrich and export deterministically without turning metadata into an uncontrolled database or treating untrusted media input as safe.

## Scope

IN:
- Add namespaced `AssetRegistryEntry.metadata`.
- Define `AssetParserContribution`.
- Invoke parsers during asset ingestion and merge approved registry metadata.
- Add search facets or minimal asset filtering for metadata.
- Add host-owned asset detail sections for metadata/provenance/enrichment/search-index/related-materials, plus search result source badges and enrichment claim detail surfaces.
- Add compile-only `OutputFormatContribution` for formats that only read timeline/assets and do not invoke render providers.
- Register compile-only output formats through the M5 provider-scoped registry infrastructure and export UI/command integration.
- Add an EXIF/GPS or integrity-hash example parser.
- Add consent/provenance metadata vocabulary for asset and dataset workflows: source, rights/consent note, generated/derived-from references, capture/import timestamp, and extension-owned confidence/embedding metadata.
- Add deferred enrichment record lifecycle vocabulary and a bounded `SearchProviderContribution` shape for host-owned asset/material search surfaces.
- Add one compile-only export example such as EDL/XML/metadata JSON/project archive.
- Add disabled/reserved render-dependent output format declarations in the export UI when an extension declares them before M12; they must explain that execution is unavailable until render planning activates the route.
- Prove local extension authoring with Astrid: read assets/timeline, apply patch/proposal, save, reload, preserve result.
- Add parser input-safety rules for user-uploaded files: bounded reads, explicit accepted MIME/extensions, failure diagnostics, and no network/process side effects.

OUT:
- Full asset database migration beyond needed schema additions.
- Remote marketplace pack resources.
- Local persistence for extension source code.
- Agent runtime.

## Locked Decisions

- Parsers can mutate only blessed registry fields and namespaced metadata.
- Parsers are trusted extension code but asset inputs are untrusted user data; parser contributions must validate input size/type and fail closed into diagnostics.
- Unknown top-level mutations are rejected.
- Astrid remains a local data provider for timeline/assets, not an extension source store.
- Asset metadata lives under `AssetRegistryEntry.metadata`, with extension-owned data namespaced by extension ID.
- Parser profiles are not a general persistence surface in this milestone; only registry metadata that survives schema validation is persisted.
- Compile-only output formats declare `requiresRender: false` and return a `RenderArtifact`/bundle without entering the render pipeline.
- The Astrid test fixture is a minimal local project containing `assembly.json`, `registry.json`, and at least one asset; it proves extension mutation persists through the existing Astrid bridge.
- `OutputFormatContribution` is added to the reserved manifest surface and activated only for `requiresRender: false` formats in this milestone.
- Asset ingestion threads provider-scoped parsers through upload/extraction paths explicitly; parsers run in deterministic registration order.
- Parser results shallow-merge blessed registry fields and deep-merge metadata by namespace. Unknown top-level fields are rejected with diagnostics.
- `validateAssetMetadata()` validates known shapes such as GPS/integrity and preserves namespaced extension data.
- `validateAssetMetadata()` validates known shapes such as GPS/integrity/consent/provenance and preserves namespaced extension data.
- Minimal asset search UI is a text filter in the asset panel. It calls parser `search.matches` where provided and hides when no searchable fields exist.
- Metadata facets are declared through descriptors with field path, display name, value kind, sort/order, and aggregation posture. The host renders facets; extensions provide metadata and descriptors.
- Asset detail sections are named slots inside the asset panel, not whole replacement panels. The host owns section placement, empty/error states, search result badges, and provenance-chain rendering.
- Semantic search/embedding metadata is treated as a known namespaced pattern: parsers may persist compact embedding references or tags, but local inference/model loading remains outside M6 unless routed through later agent/process contracts.
- Parsers that need ML inference may emit deferred enrichment records: asset reference, enrichment kind, input parameters, status, and owning extension. The record shape includes the state machine `pending`, `claimed`, `resolving`, `resolved`, `failed`, `expired`; M6 persists and displays the shape, while M10/M12 activate claim/resolve execution through agent/process contracts.
- `SearchProviderContribution` is bounded to host query/result integration, not ranking ownership: providers return scored asset/material refs with excerpts/source kind/provider ID; extensions own indexing, model choice, and refresh.

## Constraints

- Existing asset ingestion must remain compatible.
- Parser failure must not block asset upload unless the parser marks itself required.
- Metadata shape should not force future migrations for common EXIF/GPS/integrity use cases.

## Done Criteria

- Asset parser example enriches uploaded assets.
- Metadata is persisted and readable through `ctx.assets`.
- Asset search/filter can use at least one contributed metadata field.
- Astrid local-first demo/test proves extension mutation and persistence.
- Compile-only export appears in export UI/command surface and produces a deterministic artifact.
- Render-dependent output formats declared early appear disabled with planner-compatible diagnostics rather than disappearing or executing.
- One end-to-end test registers parser + compile-only export, ingests an asset, persists metadata through Astrid reload, and exports an artifact containing that metadata.
- Tests cover parser rejection for unsupported MIME/type, oversized input where applicable, and attempted unknown top-level metadata mutation.
- Tests cover consent/provenance metadata persistence and export into a sidecar/metadata artifact.
- Tests cover a deferred enrichment record round-trip through asset metadata without running inference.
- Tests cover enrichment status persistence and asset-panel/search-surface display of pending/failed counts, plus a stub search provider result merge without a built-in vector database.
- Tests cover metadata facet rendering, search result badges with provider/source labels, enrichment claim detail display, asset detail sections, and provenance chain rendering.

## Touchpoints

- Asset registry types
- Asset ingestion/upload utilities
- Asset panel filtering/search
- Astrid bridge data provider
- SDK asset types
