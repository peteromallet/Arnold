# M5: Provider-Scoped Registry Foundation And Trusted Loader Lifecycle

## Outcome

Replace global render/extension registries with provider-scoped lifecycle infrastructure before public effect, transition, clip-type, shader, or catalog contributions depend on them.

## Execution Posture

Unify vocabulary before adding power. The goal is not just provider-scoped registries; it is one lifecycle, renderability, determinism, artifact, and blocker language that later contribution kinds can extend without local dialects.

## Scope

IN:
- Replace module-level effect registry mutation with provider-scoped registry context.
- Preserve built-ins, localStorage drafts, DB/resource effects, and AI-generated compiled-string resources.
- Add subscription-based registry access modeled after existing sequence component registry patterns.
- Add provenance metadata: built-in, bundled extension, external catalog, localStorage draft, DB/resource, AI generated.
- Add deterministic register/unregister lifecycle for provider mount, extension enable/disable, HMR replacement, and provider teardown.
- Add minimal trusted workspace-pack/local-loader lifecycle to test enable/disable cleanup.
- Add missing-ID behavior: loud diagnostics and export blocking, never silent fallback.
- Add renderability metadata plumbing for registry records.
- Add registry health/status surfaces for diagnostics and developer inspection.
- Export shared `RenderCapability`, `ContributionRenderability`, and `DisposeHandle` usage patterns consumed by later contribution registries.
- Define planner-compatible `CapabilityFinding`/`RenderBlocker` records used by early export-readiness scans and later consumed by the M12 planner.
- Add a minimal planner skeleton: route vocabulary, blocker aggregation, diagnostic severity mapping, extension/status UI integration, and test fixtures. It does not choose every final route yet; it prevents divergent pre-M12 export truth.
- Define shared `ArtifactBoundary`, `RenderMaterial`, and `BakeContract` vocabulary: material refs, artifact IDs, provenance, storage locators, input hashes where available, replacement of live/runtime refs, failure behavior, and hooks for capability findings.
- Add provider contract tests for registry isolation, diagnostics cleanup, duplicate IDs, HMR replacement, and extension enable/disable across fake provider instances.

OUT:
- Public `EffectContribution.component` bridge.
- Transition registry.
- Clip-type dispatch bridge.
- Shader/WebGL support.
- Marketplace, sandboxing, remote untrusted loading.

## Locked Decisions

- Provider scoping is non-negotiable.
- Registries are projections of the host-owned `ExtensionRuntime`; contribution kinds do not self-register outside runtime lifecycle.
- Global singleton registry access is legacy compatibility only and must not be the public extension path.
- All registry records carry provenance and renderability.
- Enable/disable must unregister contributions without a full page refresh.
- Renderability uses one shared route vocabulary: preview, browser export, worker export, sidecar export, and blocked reasons. M12 may enrich this into a planner report, but earlier milestones must not invent incompatible capability shapes.
- Shared vocabulary includes determinism status: deterministic, preview-only, live-unbaked, process-dependent, and unknown.
- Early feature-specific export guards must emit planner-compatible finding records. M12 replaces the decision engine, not every call site and diagnostic shape.
- `RenderMaterial` is the deterministic input object for composition, distinct from final `RenderArtifact` export outputs. Timeline state may reference `RenderMaterialRef`; material bytes live in provider/asset/artifact storage.
- Artifact/bake/materialization semantics start here as shared vocabulary; M11/M12/M13 fill in live-data, process, and shader-specific implementations.

## Locked Answers

- Legacy `effectCatalog` is adapted into the provider-scoped registry as a legacy/resource source with explicit provenance.
- Trusted local-loader lifecycle is implemented here narrowly enough to prove enable/disable/unregister cleanup before public render contribution bridges depend on it.
- Registry APIs expose snapshots through `useSyncExternalStore`-style subscription and never mutate during render.
- Registry records include owner extension ID, contribution ID, provenance, renderability, status, diagnostics, and `DisposeHandle`.
- Enabling/disabling/reloading an extension is tested as a lifecycle operation, not just a data mutation.

## Constraints

- Existing built-in, localStorage, DB, and resource effects must keep working.
- No contribution may leak across editor provider instances.
- HMR re-registration must remove stale records.

## Done Criteria

- Provider isolation tests cover two simultaneous editor instances.
- Provider contract tests prove registry behavior is shared across fake/InMemory runtime instances and does not rely on browser globals.
- HMR replacement tests prove stale components/records are removed.
- Legacy effects still render and remain editable where they were editable before.
- Missing effect IDs produce clear diagnostics and export blockers.
- Renderability metadata is available to export guards.
- Registry diagnostics are visible in the diagnostic panel/status surface.
- A host-visible canary shows a registry record, renderability status, and planner-compatible blocker/finding in the status/diagnostics surfaces.
- Minimal planner skeleton aggregates at least one registry blocker into the M2 status/diagnostics surfaces.
- Shared vocabulary docs include `RenderMaterialRef`, locator, media kind, duration/frame/sample range where relevant, producer extension/version, determinism status, replacement policy, and how material refs differ from final export artifacts.
- Calling a registry record's `DisposeHandle.dispose()` twice is safe and does not throw.
- Disabling an extension calls dispose on all records owned by that extension and removes stale registry diagnostics/status entries.

## Touchpoints

- Dynamic effect registry
- Sequence/clip registry contexts
- Runtime extension normalization
- Effect picker/validation paths
- Render router/export guard
