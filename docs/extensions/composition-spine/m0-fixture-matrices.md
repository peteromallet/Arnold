# M0 Fixture Matrices - Composition Spine Literal Coverage

Date: 2026-07-02
Status: frozen (planning-only; no runtime implementation)
Milestone: M0 - Decisions, Fixtures, and Protocol V0

## Posture

This document enumerates the literal fixture rows that later milestones cite
when they need stable, source-backed examples for composition-spine planning.
Each row below exists to prove literal coverage only. It does not introduce
runtime behavior, SDK exports, or test fixtures.

The ground truth comes from the current SDK unions/const arrays and the current
host runtime literal unions already shipped in this repository. Where the host
runtime consumes those literals, the row notes the cross-check so later docs can
point to the same authority chain instead of inventing new states.

## Source Authorities

| Domain | Authority | Why it is authoritative |
|---|---|---|
| Contribution kinds | `src/sdk/video/families/contributionKinds.ts:17-75` | Defines `VideoContributionKind` and `VIDEO_CONTRIBUTION_KINDS`. |
| Maturity axes | `src/sdk/core/families/maturity.ts:23-64` | Defines `DECLARATION_MATURITY_LEVELS` and `EXECUTION_MATURITY_LEVELS`. |
| Family cross-check | `config/extensions/family-maturity.json:1-826` | Confirms every contribution kind is represented in the maturity snapshot without extras. |
| Package state inventory | `src/tools/video-editor/runtime/extensionLoader.ts:582-652` | Defines host runtime `PackageState` literals and package-state inventory semantics. |
| Package state consumers | `src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:112-124`, `src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:315-321`, `src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:504-514` | Confirms the seven package states are rendered and severity-grouped without hidden extras. |
| Render routes, determinism, blocker reasons | `src/sdk/video/rendering/renderability.ts:1-63` | Defines `RENDER_ROUTES`, `DETERMINISM_STATUSES`, and `RENDER_BLOCKER_REASONS`. |
| Process lifecycle | `src/sdk/video/families/processes.ts:55-129` | Defines `ProcessSpec`, `ProcessLifecycleState`, and process operation literals. |
| Artifact/material/output literals | `src/sdk/video/rendering/artifacts.ts:8-155` | Defines `RenderMaterialMediaKind`, `RenderArtifactSidecarKind`, `RenderLocatorKind`, and `ArtifactBoundary`. |
| Planner/runtime cross-check | `src/tools/video-editor/runtime/renderPlanner.ts:33-1010`, `src/tools/video-editor/runtime/renderability.ts:121-349` | Confirms planner route coverage, determinism ordering, material-state mapping, blocker alignment, and one concrete `ArtifactBoundary` instance. |

## Version And Reference Dimensions

### Video Contribution Kind Fixture Rows

| Row | Literal | Fixture intent | Authority |
|---|---|---|---|
| `VK-01` | `slot` | Baseline fully supported host surface contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:711` |
| `VK-02` | `dialog` | Host-integrated dialog layer contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:278` |
| `VK-03` | `panel` | Host-integrated panel placement contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:514` |
| `VK-04` | `inspectorSection` | Host-integrated inspector section contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:356` |
| `VK-05` | `timelineOverlay` | Host-integrated overlay contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:750` |
| `VK-06` | `command` | Host-integrated command contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:200` |
| `VK-07` | `keybinding` | Host-integrated keybinding contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:395` |
| `VK-08` | `contextMenuItem` | Host-integrated context-menu contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:239` |
| `VK-09` | `parser` | Delegated parser contribution with schema-backed declaration. | `contributionKinds.ts:53-75`; `family-maturity.json:553` |
| `VK-10` | `outputFormat` | Delegated output-format contribution reserved for route planning. | `contributionKinds.ts:53-75`; `family-maturity.json:474` |
| `VK-11` | `searchProvider` | Delegated search-provider contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:632` |
| `VK-12` | `metadataFacet` | Runtime-bridged metadata-facet contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:434` |
| `VK-13` | `assetDetailSection` | Delegated asset-detail-section contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:81` |
| `VK-14` | `process` | Trusted process contribution with declaration-only runtime posture. | `contributionKinds.ts:53-75`; `family-maturity.json:593` |
| `VK-15` | `effect` | Delegated effect contribution that starts preview-first. | `contributionKinds.ts:53-75`; `family-maturity.json:317` |
| `VK-16` | `transition` | Delegated transition contribution that starts preview-first. | `contributionKinds.ts:53-75`; `family-maturity.json:789` |
| `VK-17` | `clipType` | Runtime-bridged clip-type contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:160` |
| `VK-18` | `shader` | Delegated shader/materializer contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:671` |
| `VK-19` | `automation` | Runtime-bridged automation contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:120` |
| `VK-20` | `agentTool` | Delegated host-mediated agent-tool contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:42` |
| `VK-21` | `agent` | Reserved delegated agent contribution. | `contributionKinds.ts:53-75`; `family-maturity.json:3` |

Cross-check: `family-maturity.json` contains exactly the same 21 `kind` values
as `VIDEO_CONTRIBUTION_KINDS`; this document adds no extra kind literals.

### Declaration Maturity Fixture Rows

| Row | Literal | Fixture intent | Authority |
|---|---|---|---|
| `DM-01` | `typed` | Type contract exists, but schema/docs may still be incomplete. | `maturity.ts:23-30` |
| `DM-02` | `schema-backed` | Manifest schema and normalized descriptor shape are stable. | `maturity.ts:23-30` |
| `DM-03` | `documented` | Author-facing docs/examples exist. | `maturity.ts:23-30` |

Cross-check: all `declarationMaturity` values in `family-maturity.json`
resolve to one of these three literals only (`family-maturity.json:6-7`,
`45-46`, `714-715` show representative entries).

### Execution Maturity Fixture Rows

| Row | Literal | Fixture intent | Authority |
|---|---|---|---|
| `EM-01` | `absent` | No real host runtime behavior exists. | `maturity.ts:50-64` |
| `EM-02` | `delegated` | Runtime posture exists through a delegated or placeholder adapter. | `maturity.ts:50-64` |
| `EM-03` | `runtime-bridged` | Independent host adapter owns normalization/lifecycle. | `maturity.ts:50-64` |
| `EM-04` | `host-integrated` | Host planner/render/UI participation is real. | `maturity.ts:50-64` |
| `EM-05` | `public-supported` | Lifecycle, diagnostics, examples, and tests are complete. | `maturity.ts:50-64` |

Cross-check: all `executionMaturity` values in `family-maturity.json` come from
this five-value set; no sixth execution state is present.

### Package State Fixture Rows

These are host-runtime package inventory states, not SDK maturity-axis values.
They therefore cite the extension loader as authority instead of
`family-maturity.json`.

| Row | Literal | Fixture intent | Authority | Consumer cross-check |
|---|---|---|---|---|
| `PS-01` | `loaded` | Package activated and available to the runtime. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:507`; `ExtensionManager.tsx:112-124` |
| `PS-02` | `disabled-by-user` | Package present but intentionally disabled. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:508`; `ExtensionStatusDrawer.tsx:319-321` |
| `PS-03` | `invalid` | Package rejected because manifest or validation failed. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:509`; `ExtensionStatusDrawer.tsx:316-318` |
| `PS-04` | `incompatible` | Package rejected because compatibility checks failed. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:510`; `ExtensionStatusDrawer.tsx:316-318` |
| `PS-05` | `duplicate` | Package lost precedence to another install/source. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:511`; `ExtensionStatusDrawer.tsx:319-321` |
| `PS-06` | `settings-error` | Package metadata loaded, but settings snapshot/schema failed. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:512`; `ExtensionStatusDrawer.tsx:319-321` |
| `PS-07` | `runtime-error` | Package failed during runtime load or integrity checks. | `extensionLoader.ts:589-596` | `ExtensionManager.test.tsx:513`; `ExtensionStatusDrawer.tsx:316-318` |

Cross-check: the manager test enumerates all seven package states in one place,
which is a useful audit guard against accidental additions.

## Target, Material, Process, And Output Dimensions

### Render Route Fixture Rows

| Row | Literal | Fixture intent | Authority | Planner cross-check |
|---|---|---|---|---|
| `RR-01` | `preview` | Interactive preview route. | `renderability.ts:1-11` | `renderPlanner.ts:989-1009` |
| `RR-02` | `browser-export` | Browser-owned export route. | `renderability.ts:1-11` | `renderPlanner.ts:989-1009` |
| `RR-03` | `worker-export` | Worker-owned export route. | `renderability.ts:1-11` | `renderPlanner.ts:989-1009` |
| `RR-04` | `sidecar-export` | Process/sidecar export route. | `renderability.ts:1-11` | `renderPlanner.ts:640-685`, `989-1009` |

### Determinism Status Fixture Rows

| Row | Literal | Fixture intent | Authority | Planner cross-check |
|---|---|---|---|---|
| `DS-01` | `deterministic` | Same inputs should produce equivalent outputs. | `renderability.ts:13-37` | `renderPlanner.ts:116-122`, `845-848` |
| `DS-02` | `preview-only` | Preview is allowed, authoritative export is not. | `renderability.ts:13-37` | `renderPlanner.ts:227-236` |
| `DS-03` | `live-unbaked` | Route depends on live state until materialized/baked. | `renderability.ts:13-37` | `renderPlanner.ts:227-236`, `761-773` |
| `DS-04` | `process-dependent` | Route depends on an external process or sidecar. | `renderability.ts:13-37` | `renderPlanner.ts:227-236`, `535-680` |
| `DS-05` | `unknown` | Metadata is insufficient; planner stays conservative. | `renderability.ts:13-37` | `renderPlanner.ts:116-122`, `227-236` |

### Render Blocker Reason Fixture Authority

The blocker reason vocabulary is intentionally not duplicated in this matrix.
The canonical source is `RenderBlockerReason` plus `RENDER_BLOCKER_REASONS` in
`src/sdk/video/rendering/renderability.ts`, and planner-produced readiness
records are owned by `src/tools/video-editor/runtime/renderPlanner.ts`. Fixture
prose and release examples should cite those sources or specific planner
mapping code when they need an individual blocker code.

### Process Lifecycle Fixture Rows

| Row | Literal | Fixture intent | Authority | Planner/runtime cross-check |
|---|---|---|---|---|
| `PL-01` | `not-installed` | Process is declared but not installed. | `processes.ts:67-129` | `renderPlanner.ts:593-607` blocks route work when not ready. |
| `PL-02` | `stopped` | Process is installed but not running. | `processes.ts:67-129` | `renderPlanner.ts:593-607` blocks route work when not ready. |
| `PL-03` | `starting` | Process boot is in progress. | `processes.ts:67-129` | `renderPlanner.ts:593-607` blocks route work when not ready. |
| `PL-04` | `ready` | Process can serve operations for the route. | `processes.ts:67-129` | `renderPlanner.ts:604-607` treats `ready` as non-blocking. |
| `PL-05` | `busy` | Process is executing an operation. | `processes.ts:67-129` | `renderPlanner.ts:358-360`, `593-607` keeps blocker active unless/until ready. |
| `PL-06` | `degraded` | Process is usable but in a warning state. | `processes.ts:67-129` | `renderPlanner.ts:604-610`, `613-633` downgrades route status to warning. |
| `PL-07` | `failed` | Process crashed or is otherwise unavailable. | `processes.ts:67-129` | `renderPlanner.ts:593-607` blocks route work when not ready. |
| `PL-08` | `stopping` | Process shutdown is in progress. | `processes.ts:67-129` | `renderPlanner.ts:593-607` blocks route work when not ready. |

### Render Material Media Kind Fixture Rows

| Row | Literal | Fixture intent | Authority | Runtime/planner cross-check |
|---|---|---|---|---|
| `MM-01` | `image` | Image material or artifact payload. | `artifacts.ts:8-16` | `runtime/renderability.ts:355-362` |
| `MM-02` | `video` | Video material or artifact payload. | `artifacts.ts:8-16` | `runtime/renderability.ts:355-362` |
| `MM-03` | `audio` | Audio material or artifact payload. | `artifacts.ts:8-16` | `runtime/renderability.ts:355-362` |
| `MM-04` | `text` | Text payload emitted as a material/artifact. | `artifacts.ts:8-16` | `runtime/renderability.ts:359-360` |
| `MM-05` | `json` | JSON payload emitted as a material/artifact. | `artifacts.ts:8-16` | `runtime/renderability.ts:359` |
| `MM-06` | `binary` | Opaque binary payload. | `artifacts.ts:8-16` | `runtime/renderability.ts:361` |
| `MM-07` | `sidecar` | Material used only as a sidecar-like payload. | `artifacts.ts:8-16` | Reserved in SDK type; planner records `mediaKind` opaquely in `renderPlanner.ts:795-801`. |
| `MM-08` | `unknown` | Fallback when MIME or producer metadata is insufficient. | `artifacts.ts:8-16` | `runtime/renderability.ts:289-299`, `355-362` |

### Render Artifact Sidecar Kind Fixture Rows

| Row | Literal | Fixture intent | Authority |
|---|---|---|---|
| `SK-01` | `metadata` | Structured metadata sidecar. | `artifacts.ts:70-97` |
| `SK-02` | `thumbnail` | Thumbnail/preview-image sidecar. | `artifacts.ts:70-97` |
| `SK-03` | `scene-report` | Scene-analysis or scene-structure report. | `artifacts.ts:70-97` |
| `SK-04` | `log` | Process/render log sidecar. | `artifacts.ts:70-97` |
| `SK-05` | `provenance` | Provenance/evidence sidecar. | `artifacts.ts:70-97` |
| `SK-06` | `rendered-pass` | Individual rendered-pass payload. | `artifacts.ts:70-97` |
| `SK-07` | `cue` | Cue/timing sidecar. | `artifacts.ts:70-97` |
| `SK-08` | `label` | Label or tokenized annotation sidecar. | `artifacts.ts:70-97` |
| `SK-09` | `caption` | Caption/transcript sidecar. | `artifacts.ts:70-97` |
| `SK-10` | `diagnostics` | Diagnostics bundle sidecar. | `artifacts.ts:70-97` |
| `SK-11` | `manifest` | Render manifest sidecar. | `artifacts.ts:70-97`; `runtime/renderability.ts:188-205` |
| `SK-12` | `other` | Explicit catch-all sidecar kind when no specialized kind applies. | `artifacts.ts:70-97` |

### Render Locator Kind Fixture Rows

| Row | Literal | Fixture intent | Authority | Runtime/planner cross-check |
|---|---|---|---|---|
| `LK-01` | `asset-registry` | Material/artifact resolves through the asset registry. | `artifacts.ts:18-33` | `runtime/renderability.ts:290-299` |
| `LK-02` | `artifact-store` | Material/artifact resolves through the artifact store. | `artifacts.ts:18-33` | Reserved in SDK locator union. |
| `LK-03` | `url` | Material/artifact resolves from a URL. | `artifacts.ts:18-33` | Reserved in SDK locator union. |
| `LK-04` | `local-file` | Material/artifact resolves from a local file path. | `artifacts.ts:18-33` | Reserved in SDK locator union. |
| `LK-05` | `inline` | Material/artifact data is embedded directly. | `artifacts.ts:18-33` | `runtime/renderability.ts:302-306` |
| `LK-06` | `provider` | Material/artifact is provided by a host/provider bridge. | `artifacts.ts:18-33` | Reserved in SDK locator union. |

### Artifact Boundary Source Fixture Rows

| Row | Literal | Fixture intent | Authority | Runtime/planner cross-check |
|---|---|---|---|---|
| `ABS-01` | `provider` | Provider-originating material/artifact boundary. | `artifacts.ts:62-68` | Planner consumes boundary-bearing artifacts; no extra source literals are introduced. |
| `ABS-02` | `browser` | Browser-originating artifact boundary. | `artifacts.ts:62-68` | `runtime/renderability.ts:308-313` |
| `ABS-03` | `worker` | Worker-originating artifact boundary. | `artifacts.ts:62-68` | Planner reserves worker-export route in `renderPlanner.ts:989-1009`. |
| `ABS-04` | `sidecar-process` | Sidecar/process-originating artifact boundary. | `artifacts.ts:62-68` | Process-dependent route logic in `renderPlanner.ts:535-680`. |
| `ABS-05` | `artifact-store` | Artifact-store-originating artifact boundary. | `artifacts.ts:62-68` | Reserved in SDK boundary union. |

### Artifact Boundary Target Fixture Rows

| Row | Literal | Fixture intent | Authority | Runtime/planner cross-check |
|---|---|---|---|---|
| `ABT-01` | `provider` | Provider-target boundary. | `artifacts.ts:62-68` | Reserved in SDK boundary union. |
| `ABT-02` | `browser` | Browser-target boundary. | `artifacts.ts:62-68` | Reserved in SDK boundary union. |
| `ABT-03` | `worker` | Worker-target boundary. | `artifacts.ts:62-68` | Reserved in SDK boundary union. |
| `ABT-04` | `sidecar-process` | Sidecar-target boundary. | `artifacts.ts:62-68` | Reserved in SDK boundary union. |
| `ABT-05` | `artifact-store` | Artifact-store target boundary. | `artifacts.ts:62-68` | Reserved in SDK boundary union. |
| `ABT-06` | `export-output` | Final user-visible export/output boundary. | `artifacts.ts:62-68` | `runtime/renderability.ts:308-313` |

### Artifact Boundary Failure Behavior Fixture Rows

| Row | Literal | Fixture intent | Authority | Runtime/planner cross-check |
|---|---|---|---|---|
| `ABF-01` | `block-export` | Boundary failure hard-blocks export. | `artifacts.ts:62-68` | Aligns with planner blocker semantics in `renderPlanner.ts:502-532`, `704-723`. |
| `ABF-02` | `fallback-to-preview` | Boundary failure permits preview fallback instead of export success. | `artifacts.ts:62-68` | Aligns with route-level preview/export separation in `renderPlanner.ts:227-236`. |
| `ABF-03` | `emit-diagnostic` | Boundary failure records diagnostics without claiming export success. | `artifacts.ts:62-68` | `runtime/renderability.ts:308-313` |

## Render Planner Cross-Checks

The fixture rows above are not free-floating. The planner/runtime already
codifies several invariants that the matrices must respect.

| Invariant | Source | Planning implication |
|---|---|---|
| Route plans are built by iterating `RENDER_ROUTES` directly. | `renderPlanner.ts:989-1009` | Every route matrix must stay limited to `preview`, `browser-export`, `worker-export`, `sidecar-export`. |
| Determinism ordering is fixed as `deterministic < preview-only < live-unbaked < process-dependent < unknown`. | `renderPlanner.ts:116-122`, `845-848` | Route examples and release gates should treat `unknown` as the most conservative status. |
| Determinism-to-blocker mapping reuses the corresponding canonical `RenderBlockerReason` for all non-deterministic states. | `renderPlanner.ts:227-236` | No extra blocker reason should be invented outside `RENDER_BLOCKER_REASONS`. |
| Material planner state is exactly `missing`, `stale`, `resolved`, `unbaked`. | `renderPlanner.ts:33-40` | Future fixture prose can mention these planner states, but must not add a fifth planner-only literal. |
| Material blocker mapping is exact: `missing -> missing-material`, `stale -> materialization-failed`, `unbaked -> determinism-derived reason`, `resolved -> no blocker`. | `renderPlanner.ts:761-807`, `809-840` | Release examples should cite the canonical blocker code source instead of ad hoc material failure labels. |
| Process route handling is exact: `ready` clears blockers, `degraded` downgrades to warning, all other lifecycle states block. | `renderPlanner.ts:593-633`, `658-680` | Process examples in later milestones should not invent separate route states beyond the eight lifecycle literals. |
| Compile-only artifact creation instantiates one concrete boundary: `browser -> export-output` with `emit-diagnostic`. | `runtime/renderability.ts:308-349` | The boundary tables stay literal-complete while still citing one existing runtime example. |

## Coverage Notes

1. Package-state literals are intentionally kept separate from the declaration
   and execution maturity axes. They are loader/runtime inventory states, not
   family maturity values.
2. `sidecar`, several locator kinds, and most artifact-boundary combinations are
   currently vocabulary-level contracts rather than actively exercised runtime
   branches. They still need M0 rows so later milestones can cite stable names
   without inventing literals.
3. No literals outside the cited source unions/const arrays are introduced by
   this matrix. Any future row addition requires a source-authority change
   first, then an M0-doc update.
