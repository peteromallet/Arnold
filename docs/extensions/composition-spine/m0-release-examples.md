# M0 Release Examples - Composition Spine Future Deliverables

Date: 2026-07-02
Status: frozen target inventory (planning-only; no runtime implementation)
Milestone: M0 - Decisions, Fixtures, and Protocol V0

## Posture

This document inventories the four release examples as **future graph-backed
target deliverables**. None of the four exists today as a single composed,
graph-authoritative runtime example. Existing canaries and examples are cited
only as source material for later milestones to reuse or replace.

The graph vocabulary for every example is limited to the public edge names
frozen in `m0-decisions.md`: `consumes`, `animates`, `binds-live`, and
`requires`. Deferred names stay out of release assertions.

Legacy planner data (descriptor-level fields that predate the composition
graph) is **compatibility-only** in V1. EX-01, EX-02, and EX-03 assert their
release readiness through graph-backed edges projected from the composition
graph rather than through legacy planner lookups. Any planner field that
duplicates graph-observable facts (e.g. shader assignment, effect selection,
transition identity) is treated as a compat shim and must not be the sole
source of truth for export blocking, diagnostics, or release gating.

## Ownership Snapshot

| Example | Future deliverable | Owning milestone | Current status | Source material only |
|---|---|---|---|---|
| `EX-01` | Clip + shader + shader-uniform keyframes | M4 | Graph-backed V1 example | `clip-local-shader-canary` |
| `EX-02` | Effect + live data + bake | M5 | Graph-backed V1 example | `flagship-local`, `live-webcam-canary`, `live-generated-frame-canary`, `live-data-bridge` |
| `EX-03` | Transition + agent-produced mask material | M5 | Graph-backed V1 example | `flagship-local`, `agent-tools-canary`, `live-generated-frame-canary` |
| `EX-04` | Output format + sidecar/process dependency with non-video artifact output | M7b | Not yet composed as a graph-backed example | `metadata-json-output-example`, `process-example`, planner/runtime descriptor tests |

## EX-01 - Clip + Shader + Shader-Uniform Keyframes

**Owning milestone:** M4 (`m4-clip-shader-keyframes.md`)

### Graph-path assertions

- A clip-scoped shader assignment resolves through graph-owned `shader.assign`
  and remains identifiable by `(extensionId, kind, contributionId)` instead of
  a legacy-only planner field.
- The shader contribution projects a `consumes` path for its clip-frame input
  and for any export-path material requirement used to clear browser or worker
  export blockers.
- Keyframes targeting `shader-uniform` paths project `animates` paths for the
  exact uniform names being edited; round-trip serialization must preserve the
  same target-path identity.
- Any export dependency needed to materialize the shader output projects a
  route-scoped `requires` path and must not silently downgrade to preview-only
  success.

### Fixture row references

- Contribution and route vocabulary: `VK-18`, `RR-01`, `RR-02`, `RR-03`
- Determinism and blockers: `DS-02`, `BR-06`, `BR-02`
- Material and locator evidence: `MM-01`, `LK-01`

### UI surface markers

- `Inspector/shader-uniform-form`: reuse the existing `ShaderInspector` editing
  surface that currently drives `schema-form-widget-intensity`.
- `Preview/clip-shader-canvas`: reuse the clip preview surface now exercised by
  `testId="canary-clip-shader-preview"`.
- `Export/browser-route-blocker`: browser-export must show the exact shader
  blocker instead of treating preview support as export readiness.

### Blocker scenarios

- Missing materializer output for browser export: `BR-06 missing-material`
- Worker or browser route unavailable for the assigned shader: `BR-02 route-unsupported`
- Preview-only shader posture leaking into export claims: `DS-02 preview-only`

### Artifact/completion evidence

- A graph snapshot or equivalent readiness artifact shows the clip-scoped
  shader assignment, the `animates` target-path assertions, and any
  `requires` dependency facts needed for export.
- Planner evidence proves preview may pass while browser/worker export remains
  blocked until the required material exists.
- UI evidence shows the assigned shader on the preview surface and the edited
  uniform values surviving a round trip.

### Release gates

- M4 acceptance must prove graph-owned `shader.assign`/`shader.remove`, not a
  legacy-only write path.
- The example must emit non-empty `consumes`, `animates`, and `requires`
  assertions where applicable, with exact target-path identities for shader
  uniforms.
- Export blockers must stay route-scoped and use the exact blocker vocabulary
  already frozen in `m0-fixture-matrices.md`.
- The example is not releasable until the graph-backed canary supersedes the
  current shader-only source material.

### Source material only

- `src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:22-27`
  defines the current clip shader identifiers and contribution shell.
- `src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:161-178`
  defines the preview-only clip shader contribution and uniform schema.
- `src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:276-367`
  proves current inspector edits, preview rendering, and missing-material
  export blockers.
- Current gap: no existing file composes clip assignment, graph-owned shader
  keyframes, and route-scoped `requires` assertions as one release example.

## EX-02 - Effect + Live Data + Bake

**Owning milestone:** M5 (`m5-effects-transitions-mask.md`)

### Graph-path assertions

- An effect contribution resolves as a graph-backed contribution ref rather
  than a legacy-only effect registry selection.
- The live source projects a `binds-live` path into an `effect-param`
  target-path owned by the effect contribution.
- Export remains blocked until bake replaces the live binding with durable
  evidence; after bake, the same parameter path may be satisfied by durable
  capture data or another graph-owned animation source.
- Any dependency between the effect example and the live-source provider stays
  visible as `requires` or resolver-state evidence instead of collapsing into a
  generic export error.

### Fixture row references

- Contribution and route vocabulary: `VK-15`, `VK-17`, `RR-01`, `RR-02`
- Determinism and blockers: `DS-03`, `BR-04`
- Material/artifact evidence: `MM-01`, `LK-01`

### UI surface markers

- `Inspector/effect-param-form`: the future effect parameter surface reuses the
  Flagship Glow schema as its source material.
- `Timeline/live-preview`: reuse the current `data-testid="live-frame-preview"`
  live preview marker for preview-state evidence.
- `Export/live-bake-guard`: browser-export must show a distinct
  `export/live-binding-unresolved` style blocker with a bake repair action.
- `Status/live-source-lineage`: existing status or diagnostics surfaces must
  show whether the live binding is active, orphaned, partially baked, or fully
  cleared for export.

### Blocker scenarios

- Active live binding blocks export until baked: `DS-03 live-unbaked`,
  `BR-04 live-unbaked`
- Provider disposal or orphaned live source leaves preview possible but export
  blocked until the binding is removed or replaced
- Partial bake clears only the baked ranges and must not claim full export
  readiness

### Artifact/completion evidence

- Preview evidence shows live samples reaching the timeline surface.
- Bake evidence shows deterministic refs or durable material replacements
  attached to the same example rather than a detached canary-only output.
- Export evidence shows blocker clearance only after a complete bake, not after
  preview success or partial progress.
- Lineage evidence preserves steering/provenance for whichever live source is
  chosen as the canonical release example input.

### Release gates

- M5 acceptance must prove a non-empty `binds-live` assertion on an
  `effect-param` target path.
- Export must stay blocked until durable bake evidence exists; preview success
  alone is insufficient.
- The example must document one happy path and one blocker/repair path across
  existing inspector, export, or status surfaces.
- The graph-backed composed example must replace the current split source
  material before it can count toward release readiness.

### M5 implementation evidence (V1 graph-backed)

- `src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-effect-live-canary.integration.test.tsx`
  composes Flagship Glow with an `effect-param` live binding on `intensity` and
  proves the full M5 EX-02 lifecycle:
  - **Effect `consumes` edge:** `clip:…` → `contribution:effect:…` with
    `consumedKind: 'effect'`, `refKey`, and `effectType` detail.
  - **`binds-live` edge:** `clip:…` → `contribution:effect:…` with
    `targetKind: 'effect-param'`, `targetPath: 'intensity'`, and source
    provenance (`bindingId`, `sourceId`).
  - **Export block before bake:** `scanExportConfig` surfaces
    `export/live-binding-unresolved`; `planRender` rejects `browser-export`
    with `live-unbaked`.
  - **Bake and clearance:** after baking a `deterministic-capture` ref
    (`contentHash`, `provenanceHash`, `routeConstraints: ['preview', 'browser-export']`),
    both export and planner clear — `hasBlockingErrors: false`,
    `canBrowserExport: true`.
- `src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx`
  provides Testing Library browser acceptance:
  - **Happy path:** baked config renders `consumes: true`, `binds-live: true`,
    export unblocked, no blocker card.
  - **Blocker/repair path:** unbaked config renders
    `export/live-binding-unresolved` inside a `BlockerActionCard`; clicking
    "Bake live binding" triggers bake, clears the blocker, and surfaces
    graph-backed readiness.

### Source material only

- `src/tools/video-editor/examples/extensions/flagship-local/index.ts:292-301`
  defines the current Flagship Glow effect contribution.
- `src/tools/video-editor/examples/extensions/flagship-local/index.ts:436-449`
  registers the current preview-only effect component and parameter schema.
- `src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:97-140`
  defines the live webcam preview clip and binding metadata.
- `src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:173-217`
  defines the generated-frame preview clip and binding metadata.
- `src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:383-596`
  proves current preview delivery, orphaned export blockers, partial bake, full
  bake, and export-guard clearance.
- Current gap: the EX-02 graph-backed canary above supersedes the split source
  material; the source files remain as reference only.

## EX-03 - Transition + Agent-Produced Mask Material

**Owning milestone:** M5 (`m5-effects-transitions-mask.md`)

### Graph-path assertions

- A transition contribution resolves as a graph-backed contribution ref, not
  just a registry entry.
- The transition mask slot projects a `consumes` path with typed detail
  equivalent to `mask-material` on `transition-mask`.
- The promoted mask material stays a resolved `RenderMaterialRef`; the
  transition example may carry a `requires` path to the agent-side or process
  prerequisite that produced the mask, but the release assertion ends at the
  resolved material ref.
- If transition parameter automation is included, it uses `transition-param`
  target paths only; no extra target kinds are introduced.

### Fixture row references

- Contribution vocabulary: `VK-16`, `VK-20`
- Routes, determinism, and blockers: `RR-01`, `RR-02`, `DS-01`, `DS-03`, `BR-06`, `BR-07`
- Material and locator evidence: `MM-01`, `LK-01`

### UI surface markers

- `Inspector/transition-param-form`: reuse the existing Flagship Wipe schema as
  the parameter-editing source material.
- `Status/transition-mask-material`: the existing status or diagnostics surface
  must show whether the transition mask is resolved, stale, or missing.
- `Export/transition-mask-blocker`: browser-export must surface
  `missing-material` versus `materialization-failed` distinctly for the mask
  slot.

### Blocker scenarios

- No resolved mask material attached to the required slot: `BR-06 missing-material`
- Mask material exists but is stale or failed and must be re-promoted:
  `BR-07 materialization-failed`
- Live or generated intermediate data remains unbaked when export is requested:
  `DS-03 live-unbaked`

### Artifact/completion evidence

- A resolved `RenderMaterialRef` is attached to the transition mask slot with
  durable provenance, not a raw agent-session handle.
- Planner evidence distinguishes resolved, stale, and missing mask material
  states without collapsing them into generic package or route errors.
- UI evidence shows the transition contribution, its parameter schema, and the
  mask-material repair path in one composed example.

### Release gates

- M5 acceptance must prove the typed `consumes` assertion for the
  `transition-mask` slot.
- The example must show that agent-produced material is promoted before the
  transition claims export readiness.
- Missing and stale mask states must emit different blocker evidence and repair
  actions.
- The example is not release-ready until the graph-backed transition+mask path
  supersedes the current split canary sources.

### M5 implementation evidence (V1 graph-backed)

- `src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-transition-mask-canary.integration.test.tsx`
  composes Flagship Wipe and proves the full M5 EX-03 lifecycle:
  - **Transition `consumes` edge:** `clip:…` → `contribution:transition:…` with
    `consumedKind: 'transition'`, `refKey`, `transitionType`, and owner
    provenance (`ownerKind: 'transition'`, `ownerId`).
  - **Mask-material `consumes` edge:** `clip:…` → `contribution:transition:…` with
    `consumedKind: 'mask-material'`, `targetSlot: 'transition-mask'`,
    `materialRefId` matching the promoted durable ref, and owner provenance.
  - **Agent-promoted material:** invokes the agent-tool durable-promotion path
    through `createAgentToolInvocationService` → `invokeTool`, producing a
    `RenderMaterialRef` with `determinism: 'deterministic'`, durable
    provenance (`capture: 'agent-mask'`, `model: 'deterministic-masker'`),
    and `routeConstraints: ['preview', 'browser-export']`.
  - **Material slot declaration:** Flagship Wipe descriptor declares a
    `transition-mask` material slot (`name: 'transition-mask'`,
    `label: 'Transition Mask'`).
  - **Attach + preview clearance:** `applyGraphPreviewOperations` with
    `material.attach` targeting the `transition-mask` slot produces zero
    diagnostics and both `consumes` edges.
- `src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx`
  provides Testing Library browser acceptance:
  - **Happy path:** resolved material state renders `transition-consumes: true`,
    `mask-consumes: true`, no `composition/material-not-resolved` blocker.
  - **Blocker/repair path:** missing material state renders
    `composition/material-not-resolved` inside a `MaterialBrowser` card;
    clicking "Materialize transition mask" attaches the material and surfaces
    the mask-material `consumes` edge.

### Source material only

- `src/tools/video-editor/examples/extensions/flagship-local/index.ts:305-312`
  defines the current Flagship Wipe transition contribution.
- `src/tools/video-editor/examples/extensions/flagship-local/index.ts:452-459`
  registers the current preview-only transition renderer and schema.
- `src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts:94-436`
  proves current transition declaration, renderer behavior, and schema shape.
- `src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:196-260`
  provides current fake baked asset/material outputs that later milestones can
  replace with real promotion flows.
- `src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:264-319`
  provides steering-lineage and generated-session source material for future
  agent-produced mask provenance.
- Current gap: the EX-03 graph-backed canary above supersedes the split source
  material; the source files remain as reference only.

## EX-04 - Output Format + Sidecar/Process Dependency With Non-Video Artifact Output

**Owning milestone:** M7b (`m7b-output-format-sidecars.md`, after M7a route planning and M6 process runtime)

### Graph-path assertions

- An output-format contribution resolves as a graph-backed contribution ref
  keyed by `OutputFormatRef`, not as a descriptor that bypasses graph facts.
- The output format projects a route-scoped `requires` path for the trusted
  process and operation needed to run the `sidecar-export` route.
- The output format records `consumes` evidence for the material and artifact
  inputs listed in the final `RenderArtifactManifest`; completion is proven by
  artifact records, not by a bare success bit.
- Multi-artifact completion remains conjunctive: every required final artifact
  and required sidecar must resolve before the example clears its release gate.

### Fixture row references

- Contribution and route vocabulary: `VK-10`, `VK-14`, `RR-04`
- Determinism and blockers: `DS-04`, `BR-05`, `BR-01`
- Process lifecycle: `PL-01`, `PL-06`, `PL-07`
- Artifact and boundary evidence: `SK-05`, `SK-10`, `SK-11`, `ABS-04`, `ABT-06`, `ABF-01`

### UI surface markers

- `Export/sidecar-route-plan`: sidecar-export route row shows the output format,
  process requirement, and `start-process` repair action.
- `Process/dashboard-state`: existing process status surfaces must show stopped,
  degraded, failed, and ready states without leaking them into unrelated routes.
- `Completion/artifact-panel`: route completion surface lists the final output,
  manifest, provenance, and diagnostics sidecars required for release evidence.

### Blocker scenarios

- Required sidecar process not installed, stopped, or failed: `BR-05 process-dependent`
- Requested output format missing from the runtime inventory: `BR-01 missing-contribution`
- Route completion missing one or more required artifacts or sidecars: hard
  release failure under `ABF-01 block-export`

### Artifact/completion evidence

- Planner evidence shows the output format only on `sidecar-export` and emits
  route-scoped process blockers plus `start-process` next actions.
- Final artifact evidence includes `RenderArtifact` plus manifest fields for
  `outputFormatId`, `processId`, `operationId`, determinism, provenance, and
  consumed material refs.
- Release evidence includes at least one non-video final artifact plus manifest
  and provenance/diagnostics sidecars; partial output is inspectable but does
  not clear the route.
- EX-04 claims only graph facts, route blockers, repair actions, and artifact
  evidence. It does not claim sandboxing, marketplace, headless rendering,
  process execution support, preview support, or runtime certification for
  `machine-path` / `executable-package` profiles.

### Release gates

- M7b acceptance must prove the fourth composed example with route-scoped
  `requires` facts and multi-artifact completion evidence.
- The example must fail closed on stopped, degraded, failed, or missing process
  states until the process-runtime and repair UI milestones land.
- Sidecar/process evidence must stay outside the V1 composition SDK surface and
  rely on host/runtime contracts only.
- Example readiness and graph-path marker checks in M7b must explicitly include
  this example alongside the first three examples.

### M7b implementation evidence (V1 graph-backed)

- `src/examples/output-format-sidecar-composed-example.ts`
  composes the trusted-process and metadata JSON output examples into
  `EX-04/output-format-sidecar-composed`, keeping the graph vocabulary to
  `requires` and `consumes` while exporting route-scoped ready and
  stopped-process scenarios.
- Graph-path markers now prove the exact sidecar route chain:
  - **Route `requires` marker:** `contribution:outputFormat:…` →
    `contribution:process:…` with `requirementKind: 'process'`,
    `processId`, `operationId`, and `routeScope: ['sidecar-export']`.
  - **Artifact-input `consumes` marker:** `contribution:outputFormat:…` →
    `clip:…` with `consumedKind: 'material'` and the durable
    `materialRefId` required by the metadata export.
- Artifact evidence is now concrete and conjunctive:
  - **Final artifact:** `artifact.ex04.metadata-json` on `sidecar-export`
    with a typed `sidecar` manifest, `outputFormatId`, `processId`,
    `operationId`, determinism, `inputHashes`, and `graphPathMarker`.
  - **Required sidecars:** manifest and provenance sidecars with SHA-256 hashes
    and `routeConstraints: ['sidecar-export']`; missing any required artifact or
    sidecar leaves the route incomplete or blocked.
- Route blockers and repair actions are now explicit and route-scoped:
  - **Stopped process blocker:** `process-dependent` on `sidecar-export`
    when the Example Analyzer process is stopped.
  - **Repair action:** `start-process` scoped to `sidecar-export`; it is not
    allowed to block browser or worker routes.
- `src/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx`
  renders the selected route status, artifact completion by profile, final
  artifacts, sidecars, process lifecycle badges, and route-scoped repair cards
  without surfacing unrelated-route blockers or actions.
- `src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx`
  provides Testing Library browser acceptance:
  - **Happy path:** the dashboard shows the graph-backed `requires` and
    `consumes` markers, `complete` sidecar profile completion, the attached
    metadata artifact, sidecars, and a `ready` process badge.
  - **Stopped/repair path:** the dashboard shows the
    `process-dependent` blocker, a `start-process` repair action, a `stopped`
    lifecycle badge, and route completion recovery after the repair action.

### Source material only

- `src/examples/metadata-json-output-example.ts:80-92`
  defines the current compile-only output format contribution shell.
- `src/examples/process-example.ts:94-152`
  defines the current trusted local process declaration shell.
- `src/tools/video-editor/runtime/extensionSurface.test.ts:968-1035`
  proves current render-dependent output descriptors, route requirements,
  process requirements, and `start-process` next actions.
- `src/tools/video-editor/runtime/renderPlanner.test.ts:670-709`
  proves current route-scoped sidecar-export blockers for a render-dependent
  output format and process pair.
- `src/tools/video-editor/runtime/outputFormatRegistry.test.ts:171-200`
  and `:1394-1472` prove current artifact manifest and boundary evidence for
  compile-only output formats.
- Remaining posture: the earlier descriptor-level files remain source material
  for EX-04 history, but release evidence now comes from the composed fixture
  and its route-completion browser acceptance rather than from the isolated
  shells alone.

## Cross-Example Release Gate Summary

1. Every example must become graph-backed before it can count as release
   evidence; reusing legacy-only planner facts is a release blocker.
2. Every example must cite fixture rows from `m0-fixture-matrices.md` instead of
   inventing new route, blocker, determinism, lifecycle, or artifact names.
3. Preview success never clears export readiness on its own.
4. Existing canaries and examples remain source material only until the owning
   milestone ships the composed graph-backed deliverable.
