# Megaplan Ticket: Reigh Full Extension Extensibility

Date: 2026-06-22
Workspace: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`
Prerequisite: `.megaplan/briefs/reigh-extension-layer-foundation/chain.yaml`

## Outcome

Complete the original extension-layer ambition on top of the foundation epic. A third-party or trusted package author should be able to extend the video editor with new asset metadata, UI, settings, diagnostics, commands, proposal-backed mutations, effects, transitions, clip types, keyframes, agent tools, live data, render/export materials, and optional trusted local process or shader capabilities, without editing Reigh internals.

The result should be a coherent extension platform, not a collection of one-off plug-ins. Every supported contribution family must plug into the same foundation primitives: manifest schema, public SDK exports, provider persistence, manager UI, SchemaForm, scoped diagnostics, lifecycle cleanup, proposal policy, render planner, docs, examples, and release gates.

## Foundation Dependencies

This ticket should not start until the foundation epic has produced:

- Honest docs/schema/runtime/export drift gates.
- Provider-backed extension state/settings/proposal persistence.
- Public proposal envelope and agent proposal policy.
- Scoped extension diagnostic reporter.
- Host-owned SchemaForm.
- Lifecycle cleanup contract.
- Extension manager UI.
- Trust/security statement.
- Phase 4 readiness artifact with render planner extension contract, trust posture, and family promotion checklist.

Each new family must satisfy that promotion checklist before it can move to `supported`.

## What Complete Extensibility Means

Complete extensibility means the following families are either supported end to end or explicitly rejected/deferred with consistent diagnostics and docs:

1. **Asset parser and enrichment contributions**
2. **Output/search/provider-style asset contributions**
3. **Trusted/signed visual effect contributions**
4. **Transition contributions**
5. **Clip-type contribution subset**
6. **Keyframe and animation contribution support**
7. **Agent tool contributions**
8. **Live data/data source contributions**
9. **Render material and render capability contributions**
10. **Trusted local process/sidecar contributions**
11. **Shader/WebGL bridge contributions**
12. **SDK packaging, examples, compatibility matrix, and release gates**

The first implementation pass may keep some families `trusted-only`, but the platform must make that posture explicit and enforce it through schema, loader, manager warnings, and render/export blockers.

## How Each Family Plugs Into The Foundation

### 1. Asset Parser And Enrichment Contributions

What to build:

- `AssetParserContribution` manifest collection and public SDK type.
- MIME/container declarations and permission requirements.
- Parser invocation during asset ingestion/materialization.
- Namespaced extension metadata on asset registry entries.
- Query/filter APIs for extension-enriched metadata.
- Consent/provenance vocabulary for metadata that may be sensitive.
- Failure diagnostics and retry/degraded states.

Foundation hooks:

- Manifest/schema/export drift gate validates contribution shape.
- Provider persistence stores parser-derived metadata and migration versions.
- Diagnostics reporter surfaces parser failures by extension/contribution ID.
- Manager shows parser contribution state and trust warning.
- Lifecycle cleanup disables parser execution and prevents stale enrichments from being treated as fresh.
- Render planner consumes metadata only where the parser declares export-relevant material.

Done:

- An example parser enriches assets, survives reload, exposes queryable metadata, and fails closed when disabled or invalid.

### 2. Output/Search/Asset Provider Contributions

What to build:

- `OutputFormatContribution` for compile/export targets where retained.
- `SearchProviderContribution` for extension-owned asset search/facets.
- Provider capability declarations for asset search/output behavior.
- Degraded/unsupported provider diagnostics.

Foundation hooks:

- Provider repository factories and capability flags determine support.
- SchemaForm configures provider/search settings.
- Manager shows unsupported-provider status.
- Render planner blocks unsupported output formats with actionable `RenderBlocker`s.

Done:

- Extension-provided search/output capabilities are discoverable, configurable, provider-aware, and render/export safe.

### 3. Trusted/Signed Effect Contributions

What to build:

- `EffectContribution` manifest collection.
- Public SDK type with ID, label, category, params schema, provenance, render capability, and trusted component reference.
- Provider-scoped effect registry.
- Picker/inspector integration.
- SchemaForm-backed parameter editor.
- Preview/render exception isolation.
- Provenance/renderability badges.
- Export blockers for preview-only or missing effect implementations.

Foundation hooks:

- Trust posture decides whether effects are trusted-only, signed, or sandboxed.
- SchemaForm edits effect params.
- Diagnostics reporter reports invalid params/render crashes.
- Lifecycle cleanup unregisters disabled effects and clears stale UI.
- Render planner consumes effect capabilities and emits blockers/material requirements.
- Manager shows effect contributions and trust warnings.

Done:

- A trusted extension effect can be picked, configured, serialized, reloaded, previewed, planned for export, disabled, and diagnosed.

### 4. Transition Contributions

What to build:

- `TransitionContribution` manifest collection.
- Dynamic/provider-scoped transition registry.
- Param schemas and transition picker/editor integration.
- Repair behavior for missing/disabled transition IDs.
- Preview and export planning.

Foundation hooks:

- SchemaForm edits transition params.
- Lifecycle cleanup unregisters transitions.
- Diagnostics reporter explains missing/invalid transitions.
- Render planner blocks unsupported transitions rather than silently falling back.

Done:

- A contributed transition can be selected, configured, persisted, rendered, disabled, repaired, and export-checked.

### 5. Clip-Type Contribution Subset

What to build:

- `ClipTypeContribution` manifest collection for a limited declarative/sequence-backed subset first.
- Insert command and inspector support.
- Serialization/reload support.
- Renderer dispatch.
- Capability metadata and fallback behavior.
- Missing/disabled clip repair placeholders.

Foundation hooks:

- Proposal envelope controls insert/edit mutations.
- SchemaForm edits clip params.
- Provider persistence stores contributed clip instances.
- Diagnostics reporter reports missing renderers/invalid params.
- Render planner decides export readiness.
- Manager disable path unregisters clip type and shows existing timeline impact.

Done:

- A contributed clip type can be inserted, inspected, serialized, reloaded, previewed, disabled with clear placeholders, and planned for export.

### 6. Keyframes And Animation

What to build:

- Minimal keyframe data model: ID, target path, time, value, easing.
- Supported property set first: opacity, position, scale, maybe effect/clip params.
- Add/edit/delete commands with proposal support.
- Inspector/timeline authoring UI.
- Serialization migration.
- Interpolation runtime for preview/export.

Foundation hooks:

- Proposal spine handles destructive edits.
- SchemaForm and field metadata identify animatable params.
- Provider persistence stores keyframes.
- Diagnostics reporter explains invalid keyframe paths.
- Render planner ensures interpolated values are deterministic.

Done:

- Keyframes can be authored, proposed, accepted, serialized, reloaded, interpolated, rendered, and migrated.

### 7. Agent Tool Contributions

What to build:

- `AgentToolContribution` manifest collection.
- Tool ID, label, description, input schema, output schema, permissions, lifecycle, and destructive/proposal policy.
- Backend dispatch registry instead of hardcoded tool-only behavior.
- Discovery UI for available extension tools.
- Progress/cancel/error surface.
- Proposal-first destructive result handling.

Foundation hooks:

- Proposal spine is mandatory for destructive tools.
- Provider persistence stores proposals/results/session references.
- SchemaForm validates tool input where user-visible.
- Diagnostics reporter captures permission denied/tool failed/degraded states.
- Manager enables/disables tools and shows trust warnings.
- Trust posture decides whether tools run frontend-only, backend-registered, or trusted-local.

Done:

- An extension tool can be discovered by the agent, invoked with schema validation, return a persisted proposal, and fail with scoped diagnostics.

### 8. Live Data/Data Source Contributions

What to build:

- `DataSourceContribution`/`LiveChannel` contract.
- Activate/deactivate/dispose lifecycle.
- Status/reconnect/error model.
- Permission declarations.
- Ring buffer for ephemeral samples.
- Bake action to deterministic asset/clip/material.
- Export blockers for unbaked live content.

Foundation hooks:

- Lifecycle cleanup disposes sources.
- Manager shows source status and trust warning.
- Provider persistence stores source config, not uncontrolled live samples.
- Diagnostics reporter surfaces disconnect/degraded status.
- Render planner blocks unbaked nondeterministic content.
- SchemaForm configures source params.

Done:

- A canary live source previews data, bakes to deterministic timeline content, reloads, and blocks export while unbaked.

### 9. Render Material And Capability Contributions

What to build:

- `RenderMaterialContribution` and capability declaration types.
- Extension material references in artifact manifests.
- Provider/render route capability mapping.
- Actionable blockers/remedies for unsupported content.
- Export/readiness UI integration.

Foundation hooks:

- Phase 4 readiness render planner contract becomes the central API.
- Every creative family must declare render/export posture.
- Manager/diagnostics expose blockers by extension/contribution.

Done:

- `planRender()` understands extension-declared materials/capabilities and never silently exports unsupported extension content.

### 10. Trusted Local Process/Sidecar Contributions

What to build:

- `ProcessContribution` manifest collection for trusted local packages only.
- Command/args/env schema/cwd policy.
- JSON-RPC stdio protocol.
- Health checks, logs, progress, cancellation, shutdown/restart.
- Manager process status and trust warnings.

Foundation hooks:

- Trust posture is mandatory; no untrusted sidecars.
- SchemaForm configures env/options.
- Diagnostics reporter captures startup/runtime failures.
- Lifecycle cleanup stops processes.
- Render planner records process-required materials or export blockers.

Done:

- A mock sidecar proves start/health/roundtrip/progress/cancel/shutdown and fails closed with diagnostics.

### 11. Shader/WebGL Bridge

What to build:

- `ShaderContribution` contract for vertex/fragment source, uniform schema, texture refs, pass type, fallback, and renderability.
- GLSL compile diagnostics with source ranges.
- WebGL preview surface and context-loss fallback.
- Uniform editor through SchemaForm.
- Deterministic pixel tests.
- Export posture or blockers.

Foundation hooks:

- Trust/sandbox decision gates whether this is supported, trusted-only, or deferred.
- Diagnostics reporter maps compile/runtime errors.
- SchemaForm edits uniforms.
- Lifecycle cleanup releases WebGL resources.
- Render planner blocks unsupported export routes.

Done:

- A shader canary previews deterministically, reports compile errors, handles context loss, and blocks export unless a render route exists.

### 12. SDK Packaging, Examples, Docs, And Gates

What to build:

- Real `@reigh/editor-sdk` package boundary after contracts stabilize.
- Public export audit.
- Example packages for each supported family.
- Error-path examples, not only happy paths.
- Compatibility matrix that maps every family to supported/trusted-only/deferred.
- Release gates that verify schema/runtime/docs/examples/export consistency.
- Production-build browser smoke for each supported family class.
- Post-epic validation walkthrough.

Foundation hooks:

- The Phase 1 drift gate becomes broader.
- Manager docs explain trust, permissions, support levels, and provider limitations.

Done:

- External authors can build against public SDK imports only, and every supported family has docs, examples, positive/negative tests, and release coverage.

## Suggested Epic Breakdown

This is too large for one megaplan. Recommended chain after foundation:

1. **FX-M1: Phase 4 readiness and render planner kernel**
   - Finalize render planner extension API, trust/sandbox decision, and family promotion checklist.
2. **FX-M2: Asset parser/search/output contributions**
   - Lower trust surface; proves metadata, provider, diagnostics, manager, and docs plumbing.
3. **FX-M3: Effect and transition contributions**
   - First high-value creative families; trusted/signed package path.
4. **FX-M4: Clip-type subset and keyframes**
   - Timeline schema, proposal mutations, serialization, render interpolation.
5. **FX-M5: Agent tool contributions**
   - Backend registry, proposal-first destructive results, discovery UI.
6. **FX-M6: Live data and bake/export semantics**
   - Nondeterminism, ring buffer, bake, blockers.
7. **FX-M7: Render material contributions**
   - Artifact manifests, provider route participation, readiness UI.
8. **FX-M8: Sidecars and shaders, if retained**
   - Trusted local process runtime and WebGL/shader bridge. This may split into two epics.
9. **FX-M9: SDK packaging, examples, docs, release validation**
   - Public package, examples for every supported family, post-epic validation.

## Locked Decisions

- Build on the foundation epic; do not bypass its manager, diagnostics, persistence, proposal, SchemaForm, lifecycle, or render planner contracts.
- Promote families one at a time. Each family starts as `deferred` or `trusted-only` and moves to `supported` only when the checklist passes.
- Keep arbitrary code families trusted/signed until an explicit sandbox or permission broker exists.
- Every family must participate in render/export planning before it can claim production support.
- Destructive agent and timeline changes must default to proposal-first unless a trusted direct-apply mode is explicit.

## Open Questions

- Which families are truly required for “complete” versus acceptable as permanently trusted-only or deferred?
- Is a runtime permission broker required before effects/agent/live families are public, or is a trusted-extension model acceptable?
- What signing/integrity mechanism is required for trusted packages?
- Should sidecars and shaders remain in this epic or become separate product-driven epics?
- What is the minimum `@reigh/editor-sdk` package shape once foundation contracts settle?
- How much marketplace/install/update lifecycle belongs to full extensibility versus a separate distribution epic?

## Constraints

- Do not implement a family without schema validation, SDK types, loader validation, runtime registration, manager visibility, diagnostics, lifecycle cleanup, docs, examples, tests, and render/export posture.
- Do not silently export unsupported extension content.
- Do not allow extension-authored diagnostics to spoof host diagnostics.
- Do not store nondeterministic live samples as durable timeline history until baked.
- Do not expose untrusted arbitrary code execution as if it were sandboxed.
- Do not introduce new mutation paths outside the proposal spine.

## Done Criteria

Complete extensibility is done when:

- Every retained contribution family is either `supported`, `trusted-only`, or `deferred` consistently across schema, runtime matrix, docs, examples, and tests.
- Every `supported` family has public SDK exports, manifest schema, loader validation, runtime registration/unregistration, manager visibility, scoped diagnostics, lifecycle cleanup, provider persistence posture, docs, examples, and positive/negative tests.
- Every creative/rendering family participates in `planRender()` and produces actionable blockers for unsupported/preview-only content.
- Agent tools cannot bypass proposal policy for destructive operations.
- Live sources cannot silently export unbaked nondeterministic data.
- Manager can inspect, disable, configure, and diagnose every supported family.
- Public SDK/package examples compile without internal imports.
- Full post-epic validation passes in Docker-capable CI.

## Touchpoints

- Foundation artifacts under `.megaplan/briefs/reigh-extension-layer-foundation/`
- `docs/extensions/reigh-extension-layer-foundation-plan.md`
- `docs/extensions/reigh-extension-layer-roadmap-v2.md`
- `docs/extensions/reigh-extension-layer-tickets.md`
- `src/tools/video-editor/extension.ts`
- `src/tools/video-editor/runtime/contributionFamilies.ts`
- `src/tools/video-editor/runtime/extensionManifest.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/diagnostics.ts`
- `src/tools/video-editor/effects/*`
- `src/tools/video-editor/clip-types/*`
- `src/tools/video-editor/sequences/*`
- `src/tools/video-editor/commands/*`
- `src/tools/video-editor/hooks/useTimelineCommands.ts`
- `src/tools/video-editor/hooks/useAgentSession.ts`
- `src/tools/video-editor/data/*`
- `src/tools/video-editor/lib/renderRouter.ts`
- `supabase/functions/ai-timeline-agent/*`
- `supabase/migrations/*`
- `examples/*`
- `docs/extensions/*`
- `tests/e2e/video-editor-*.spec.ts`
- `config/contracts/*`
- `scripts/quality/*`

## Anti-Scope

- Do not start this before the foundation done state and Phase 4 readiness gate exist.
- Do not build marketplace/discovery unless explicitly split into a distribution epic.
- Do not combine sidecars and shaders with lower-risk families if the trust decision is unresolved.
- Do not broaden keyframes into a timeline rewrite; start with a minimal property set.
- Do not treat docs/examples as substitutes for executable acceptance tests.

## Megaplan Dial Recommendation

This should be an epic chain, not a single megaplan.

Use per-milestone dials:

- Render planner/trust/family promotion kernel: `partnered-5/thorough/high`
- Effects/transitions, clip types/keyframes, agent tools, live data: `partnered-5/thorough/high`
- Asset parsers/search/output, render materials, docs/examples: usually `partnered-4/full/medium`, escalating to `partnered-5` if migrations/security/export invariants dominate.
- Sidecars/shaders: likely separate `partnered-5/thorough/high` epics if retained.

Suggested prep direction for the first full-extensibility chain:

```text
Start from the completed foundation epic and Phase 4 readiness artifact. Do not relitigate foundation primitives. Focus on the render planner extension contract, trust/signed/sandbox posture, and the family promotion checklist before planning individual contribution families.
```
