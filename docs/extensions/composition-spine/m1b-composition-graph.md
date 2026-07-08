# M1b Composition Graph — Shader/Ref Fact Authority

Date: 2026-07-03
Status: implemented

## Purpose

M1b makes `CompositionGraph` projection the **authoritative** source for shader/ref
facts and contribution-index lookups in the Reigh extension composition spine. When
a `CompositionGraph` is present on `ExtensionRuntime`, it replaces — not supplements
— legacy shader summaries and direct contribution-index access for all M1b-owned
fact families.

This document describes M1b scope, contracts, authority boundaries, and what is
explicitly out of scope.

## M1b Scope

### What M1b Owns

M1b owns **only** `consumes` edges and shader/ref authority:

| Surface | Description |
|---------|-------------|
| `consumes` edges | The only public graph edge kind in M1b. A clip or timeline-postprocess node consumes a shader contribution from a target contribution node. |
| Shader reference resolution | All 10 resolver states with locked precedence (see below). |
| Composition diagnostics | Canonical `composition/` diagnostic codes with structured detail fields. |
| Graph preview | Internal `shader.assign` and `shader.remove` preview operations. |
| Graph-first planner authority | `planRender` derives shader facts from graph nodes/edges/reference states. |
| Graph-first export scan input | `scanExportConfig` derives guard scanner findings from graph-resolved facts and feeds them to planner readiness; `planRender` remains the final export-readiness reducer. |
| Graph-first shader validation | `validateShaderComposition` derives projected shaders from graph edges. |

### Legacy Inputs Are Compatibility Sources

Legacy `TimelineShaderSummary[]`, `ContributionIndex`, and descriptor arrays remain
in the runtime surface for **graph-absent compatibility callers**, but they are
**not alternate authority** for M1b-owned facts:

- Graph-present **planner** calls ignore legacy snapshot shader refs and derive all
  shader/ref facts from the graph.
- Graph-present **export guard** calls do not read legacy timeline shader metadata.
- Graph-present **shader validation** does not consult legacy shader summaries or
  direct contribution-index candidates.
- Graph-absent callers continue to work through legacy paths but emit a
  **compatibility warning** diagnostic.

Legacy descriptor arrays (e.g. `VideoEditorShaderDescriptor[]`) remain populated
for existing consumers but are derived from the graph when one is present, ensuring
they cannot become a second authority pathway.

### Out of Scope for M1b

The following surfaces are **explicitly out of scope** for M1b. They belong to
later milestones or are excluded from the entire epic:

| Surface | Owner / Status |
|---------|---------------|
| **Target paths** (`clip-param`, `effect-param`, `transition-param`, `shader-uniform`) | M2 |
| **`animates` edges** (keyframe-driven parameter animation) | M2 |
| **`binds-live` edges** (live data binding) | M2 |
| **`requires` edges** (graph-projected requirements) | M4 |
| **Material statuses** (`missing`, `pending`, `resolved`, `stale`, `failed`) | M3a |
| **Live material promotion** (bake live inputs to durable artifacts/captures) | M3b |
| **Agent material promotion** (promote masks/materials to durable `RenderMaterial`/`RenderArtifact`) | M3c |
| **Process vocabularies** (lifecycle, JSON-RPC protocol, runtime overlays) | M6a/M6b |
| **Output-format vocabularies** (route artifacts, manifest profiles, sidecars) | M7a/M7b |
| **`materializes`, `produces`, `fallbacks` edge kinds** | Excluded from entire epic |
| **Node kinds beyond `clip`, `timeline-postprocess`, `contribution`** (e.g. track, output, process nodes) | Later milestones |
| **Public `shader.assign` / `shader.remove` SDK patch families** | Excluded from entire epic |
| **Shader stacks, FBO chains, arbitrary material graphs** | Excluded from entire epic |
| **Visual graph editor, headless renderer, WebGPU** | Excluded from entire epic |

## CompositionGraph Contracts

### Node Kinds

M1b supports exactly three node kinds, available as the `COMPOSITION_NODE_KINDS`
constant from `@reigh/editor-sdk`:

| Kind | Description |
|------|-------------|
| `clip` | A timeline clip node (shader-assignable scope). |
| `timeline-postprocess` | The timeline-wide postprocess scope node. |
| `contribution` | A contribution declared by an extension (shader, effect, parser, etc.). |

Every node carries a unique graph-level `id`, a `kind`, and an optional `ref` that
links it to a `ContributionRef` when applicable. Kind-specific metadata is carried
in `detail`.

Future milestones may add nodes for tracks, outputs, processes, and other surfaces.
These are **not** M1b scope.

### Edge Kinds

M1b supports exactly one public edge kind, available as the `COMPOSITION_EDGE_KINDS`
constant:

| Kind | Description |
|------|-------------|
| `consumes` | A source node (clip or timeline-postprocess) consumes a shader contribution from a target contribution node. |

Each edge carries a unique `id`, the `kind`, `sourceNodeId`, `targetNodeId`, and
optional `detail` (e.g. `shaderId`).

Future milestones will add `animates` (M2), `binds-live` (M2), and `requires` (M4).
No other edge kinds are public in M1b.

### Resolver States

The M1b resolver produces exactly 10 reference states, available as the
`REFERENCE_STATES` constant. Precedence is **locked**:

| Precedence | State | Meaning |
|-----------|-------|---------|
| 1 (highest) | `invalid-package` | Package marked invalid by the loader. |
| 2 | `settings-error` | Package loaded but settings migration failed. |
| 3 | `runtime-error` | Package loaded but runtime activation error. |
| 4 | `version-incompatible` | Package is incompatible with the current host version. |
| 5 | `disabled` | User-disabled package. |
| 6 | `duplicate` | Exact scoped-key duplicate (first-wins loser). |
| 7 | `inactive-reserved` | Kind not yet bridged in this runtime. |
| 8 | `missing` | No scoped candidate exists in the index. |
| 9 | `unknown` | Fallback for unrecognised states. |
| 10 (lowest) | `resolved` | Valid, active, package-healthy contribution ref. |

**Critical semantics**:

- `missing` is defined **only** as zero scoped candidates. It is never used when
  candidates exist but are in a non-resolved state.
- Package-failure states (`invalid-package`, `settings-error`, `runtime-error`,
  `version-incompatible`) classify **before** inactive/reserved states
  (`disabled`, `duplicate`, `inactive-reserved`).
- All non-resolved states classify **before** `resolved`.
- `version-incompatible` is driven by existing package-level incompatible state;
  no new manifest or contribution metadata fields are added for M1b.

### Graph Preview

M1b supports internal graph preview operations for shader assignment changes:

- **`shader.assign`** — add a `consumes` edge from a clip/postprocess node to a
  shader contribution node.
- **`shader.remove`** — remove a `consumes` edge for a given shader scope.

Preview operations are applied to a **cloned** graph. The preview result returns
updated `nodes`, `edges`, `referenceStates`, and `diagnostics` without mutating
the original `CompositionGraph`.

These are **internal** operations, not public SDK patch families. No new
`shader.assign` or `shader.remove` patch families are added to the public SDK.
They are derived from existing timeline patch payloads (`clip.update` with
`app.shader`, `app.update` with `shaderPostprocess`) and routed through
internal graph preview functions.

### Composition Diagnostics

M1b defines canonical `composition/` diagnostic codes:

| Code | Meaning |
|------|---------|
| `composition/missing-ref` | No scoped candidate exists for the contribution ref. |
| `composition/disabled-ref` | The contribution's package is user-disabled. |
| `composition/inactive-reserved-ref` | The contribution kind is not yet bridged in this runtime. |
| `composition/invalid-package-ref` | The contribution's package is marked invalid. |
| `composition/duplicate-ref` | Exact scoped-key duplicate (first-wins loser). |
| `composition/settings-error-ref` | Package loaded but settings migration failed. |
| `composition/runtime-error-ref` | Package loaded but runtime activation error. |
| `composition/version-incompatible-ref` | Package incompatible with current host version. |
| `composition/unknown-ref` | Unrecognised reference state. |
| `composition/scope-occupied` | A shader scope is already occupied (first-wins). |
| `composition/duplicate-scope` | Duplicate scope conflict. |

All diagnostics carry structured detail fields: `nodeId`, `refKey`, `refState`,
`scope`, `extensionId`, `contributionId`, `shaderId`.

## Graph Projection Pipeline

```
TimelineSnapshot ─────┐
ContributionIndex ─────┤
RuntimeOverlay? ───────┼──► projectCompositionGraph() ──► CompositionGraph
PatchOverlay? ─────────┘                                      │
                                                              ├── nodes (clip, timeline-postprocess, contribution)
                                                              ├── edges (consumes only)
                                                              ├── referenceStates (10-state resolver)
                                                              ├── diagnostics (composition/ codes)
                                                              └── preview (shader.assign / shader.remove)
```

The projector (`graphProjector.ts`):
1. Projects clip nodes from the timeline snapshot.
2. Projects a timeline-postprocess node.
3. Projects contribution nodes from the contribution index.
4. Builds `consumes` edges from enabled shader summaries using `ContributionRef`
   identity.
5. Synthesizes missing contribution nodes when refs are absent from the index.
6. Resolves reference states and diagnostics through the shared resolver.
7. Treats `undefined` runtime overlay and explicitly empty runtime overlay as
   equivalent no-ops.

## Authority Integration Points

### Planner (`renderPlanner.ts`)

When a `CompositionGraph` is present in `planRender` input:
- Shader materializer requirements are derived **only** from graph-resolved refs.
- Scope validation uses graph nodes/edges, not legacy shader summaries.
- Legacy snapshot shader refs are **ignored**.
- Graph-absent callers emit a compatibility warning.

### Export Guard Scanner (`exportGuard.ts`)

When a `CompositionGraph` is present:
- `scanExportConfig` derives guard-compatible scanner findings from
  `validateShaderComposition` with graph input.
- Legacy timeline shader metadata is **not** read.
- Graph-absent callers emit a compatibility warning.
- The scan payload is planner input. `buildExportReadinessPlan()` adapts it into
  `planRender()`, and planner `RenderBlocker` records are the canonical
  user-facing readiness vocabulary.
- Any `export/*` diagnostic code emitted by the scanner is retained as
  diagnostic metadata, not as independent readiness authority.

### Shader Validation (`shaderValidation.ts`)

When a `CompositionGraph` is present:
- `projectShaderRefs` derives projected shaders from graph nodes/edges.
- `validateShaderComposition` uses graph edges for first-wins occupancy.
- Legacy `TimelineShaderSummary[]` and direct `ContributionIndex` access are
  **not** consulted.

### Runtime Assembly (`FamilyRuntimeAssembly.ts`)

- `CompositionGraph` is constructed eagerly after contribution-index assembly.
- Attached to `ExtensionRuntime.compositionGraph`.
- Legacy `ContributionIndex` and descriptor arrays are preserved for compatibility.
- Shader descriptors are derived from the graph when present via
  `buildShaderDescriptorsFromGraph()`.

### Production Hook (`useRenderState.ts`)

- `extensionRuntime.compositionGraph` is passed to `planRender`, `scanExportConfig`,
  and `hasTimelineShaderMetadata` calls. Guard scans remain scanner inputs;
  blocked readiness text is sourced from planner blockers.
- Graph propagation is the only change; all other hook behavior is preserved.

## SDK Exports

M1b exports from `@reigh/editor-sdk` (`src/sdk/index.ts`):

| Export | Kind | Description |
|--------|------|-------------|
| `CompositionGraph` | Interface | Top-level graph contract with `nodes`, `edges`, `referenceStates`, `diagnostics`, `preview` |
| `CompositionGraphNode` | Interface | Graph node with `id`, `kind`, optional `ref`, `detail` |
| `CompositionGraphEdge` | Interface | Graph edge with `id`, `kind`, `sourceNodeId`, `targetNodeId`, optional `detail` |
| `CompositionReferenceStateEntry` | Interface | Reference state entry with `refKey`, `state`, `nodeIds` |
| `CompositionGraphPreviewResult` | Interface | Preview result with `nodes`, `edges`, `referenceStates`, `diagnostics` |
| `CompositionNodeKind` | Type | Union of `'clip' \| 'timeline-postprocess' \| 'contribution'` |
| `CompositionEdgeKind` | Type | `'consumes'` |
| `ReferenceState` | Type | Union of all 10 resolver states |
| `COMPOSITION_NODE_KINDS` | Const | `['clip', 'timeline-postprocess', 'contribution']` |
| `COMPOSITION_EDGE_KINDS` | Const | `['consumes']` |
| `REFERENCE_STATES` | Const | All 10 resolver states |

No host runtime modules, internal preview operations, projector logic, or
resolver logic is exposed through the SDK barrel.

## Guardrails

M1b enforces the following guardrails:

1. **No public edge kinds beyond `consumes`.** SDK tests assert that
   `COMPOSITION_EDGE_KINDS` contains only `'consumes'`.

2. **No node kinds beyond `clip`, `timeline-postprocess`, `contribution`.**
   SDK tests assert that `COMPOSITION_NODE_KINDS` contains only the three M1b kinds.

3. **No public `shader.assign` / `shader.remove` patch families.** These are
   internal graph preview operations, not SDK exports.

4. **No graph authority bypass.** When `compositionGraph` is present, planner,
   export guard scanning, and shader validation do not fall back to legacy fields
   for M1b-owned facts. Guard scanner output is then reduced through planner
   blockers before it becomes user-facing readiness.

5. **No legacy authority leak.** Legacy descriptor arrays are graph-derived
   when a graph is present; they are not a second authority pathway.

6. **No future surface leakage.** Tests assert no track/output/process nodes,
   no `animates`/`binds-live`/`materializes` edges in M1b exports.

## Related Documents

- [V8 Architecture Baseline](./v8-architecture-baseline.md) — Full epic architecture, constraints, and milestone chain.
- [M1b Brief](/.megaplan/initiatives/reigh-extension-composition-spine-epic/m1b-shader-graph-authority.md) — M1b outcome, scope, locked decisions, and done criteria.
- [CompositionGraph SDK Contracts](../../src/sdk/video/composition/graph.ts) — Public SDK type definitions.
- [Graph Projector](../../src/tools/video-editor/runtime/composition/graphProjector.ts) — Host projection logic.
- [Reference Resolver](../../src/tools/video-editor/runtime/composition/referenceResolver.ts) — Host resolver with locked precedence.
- [Patch Preview](../../src/tools/video-editor/runtime/composition/patchPreview.ts) — Internal graph preview operations.
- [Composition Diagnostics](../../src/tools/video-editor/runtime/composition/diagnostics.ts) — Canonical diagnostic codes.
