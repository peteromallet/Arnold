# Phase 4 Extension Readiness Gate

Date: 2026-06-23
Scope: readiness review before public contribution-family promotion.

This artifact is the Phase 4 gate requested by the extension manager milestone.
It reconciles current runtime behavior, render/export planning, trust posture,
and the roadmap/ticket backlog without editing the roadmap or ticket source
documents.

## Current Code Anchors

- The roadmap and ticket backlog still name
  `src/tools/video-editor/runtime/contributionFamilies.ts` as the contribution
  family matrix. That file is not present in this checkout. The current
  source-of-truth files are:
  - `src/sdk/video/families/contributionKinds.ts` — canonical source for the
    `VideoContributionKind` union and `VIDEO_CONTRIBUTION_KINDS` array
    (re-exported publicly as `ContributionKind` and `KNOWN_CONTRIBUTION_KINDS`
    via `src/sdk/index.ts`)
  - `src/sdk/video/families/familyDefinitions.ts` — canonical family registry
    with maturity posture, conformance reports, and milestone maps (provides
    `CONTRIBUTION_KIND_MILESTONE` and `contributionKindNotYetBridged()` via
    `src/sdk/familyBridge.ts`)
  - `config/extensions/family-maturity.json` — machine-readable family maturity
    snapshot for release gates
  - `src/tools/video-editor/runtime/extensionSurface.ts` — normalizes active
    or reserved contributions into provider/runtime descriptors
- `src/tools/video-editor/runtime/extensionSurface.ts` currently bridges or
  surfaces reserved descriptors for output formats, processes, shaders, and
  agent tools. Output formats are turned into planner metadata with route
  requirements, process requirements, blockers, next actions, sidecars, and
  capability metadata. Process descriptors are surfaced as planner-visible
  declarations without starting a runtime process.
- `src/tools/video-editor/lib/renderRouter.ts` remains the route decision
  adapter for user render clicks. It converts native, themed, generated
  Remotion module, and contributed clip content into `CapabilityRequirement`
  entries, calls `planRender()`, and returns a planner-backed route decision.
- `src/tools/video-editor/runtime/renderPlanner.ts` is the canonical render
  readiness reducer. It consumes timeline snapshot requirements, explicit
  requirements, output format descriptors, process descriptors, shader
  descriptors, material refs/statuses, render groups, request constraints, and
  diagnostics, then returns route plans, blockers, diagnostics, next actions,
  and `canBrowserExport`/`canWorkerExport`.

## Render Planner Participation Contract

Any Phase 4 family that can affect preview, export, generated artifacts, or
determinism must participate in planning through stable capability metadata
before it can be promoted to public support.

Required contract:

1. Each promoted family must expose provider-free planner inspection data. The
   planner must not import live registries, component implementations, provider
   stores, or extension package handles.
2. Each render-relevant contribution must declare one or more route-level
   `CapabilityRequirement` records or a descriptor that `planRender()` can
   convert into equivalent requirements.
3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
   process-dependent, missing-contribution, and route-unsupported states must
   produce actionable `RenderBlocker` records rather than silent fallback.
4. Route decisions must remain planner-backed. For clip routing,
   `renderRouter.ts` already indexes contributed clip records by `clipTypeId`,
   allows browser export only when the contribution explicitly declares a
   supported browser-export capability, and blocks worker conflicts for
   contributed code.
5. Output-format and process families must keep using planner descriptors
   rather than invoking providers directly from the planner. Current
   `extensionSurface.ts` output-format descriptors are the model: route
   requirements, process requirements, blockers, next actions, sidecars, and
   capability metadata are data, not execution.
6. Shader and render-material families must distinguish preview from export.
   Current `renderPlanner.ts` shader materializer handling discovers
   materializer routes, emits process-dependent blockers/next actions, and
   keeps unresolved material refs from silently exporting.
7. Diagnostics published from planner findings must remain source-scoped so
   Extension Manager and diagnostics surfaces can show package/family blockers
   without confusing them with extension-authored runtime diagnostics.

Promotion is blocked for any family whose content can render, mutate timeline
state, invoke processes, consume live data, or produce export artifacts without
planner-visible requirements and failure states.

## Trust And Sandbox Posture

Phase 4 must continue the current explicit trust posture:

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime
  enforcement, sandbox isolation, code signing, or a permission broker.
- The Extension Manager warning introduced in Phase 3 is therefore a product
  requirement, not just documentation. It must stay visible during loading,
  empty, populated, selected-package, and error states.
- Public promotion of arbitrary code families such as effects, transitions,
  clip types, agent tools, local processes, shaders, and sidecars is blocked
  until the accepted posture is either "trusted/signed local packages only" or
  a real sandbox/permission broker exists.
- If Phase 4 proceeds under trusted-local assumptions, every affected doc,
  manager surface, example, and compatibility table must avoid implying iframe
  isolation, runtime permission enforcement, marketplace review, or safe
  third-party execution.

## Per-Family Promotion Checklist

Apply this checklist to each family before changing compatibility status to
supported.

| Gate | Requirement |
| --- | --- |
| Manifest/schema | `config/contracts/reigh-extension.schema.json` accepts exactly the supported shape and rejects unknown or deferred fields. |
| Public SDK | `src/sdk/index.ts` exports stable types and public helpers only; examples do not import internals. |
| Runtime normalization | `extensionSurface.ts` or the owning runtime module converts manifest declarations into immutable provider-scoped descriptors with extension ID, contribution ID, order, disabled state, and diagnostics. |
| Lifecycle cleanup | Disable/unload unregisters renderers, commands, keybindings, diagnostics, settings-derived UI state, live channels, process handles, or shader resources owned by the extension. |
| Persistence posture | Any persisted state has provider-backed semantics or an explicit unsupported diagnostic. Settings/proposals must survive reload only where providers claim conformance. |
| Settings/parameters | Parameter schemas render through SchemaForm or an equivalent host-owned primitive, with unsupported shapes diagnosed and non-corrupting. |
| Diagnostics | Loader, runtime, planner, and extension-authored diagnostics are scoped by extension ID and contribution ID where applicable, bounded, and cleaned up. |
| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
| UI integration | Picker, inspector, manager, diagnostics, empty/loading/error/disabled states, and provenance labels are present where the family is visible. |
| Tests | Unit, provider/lifecycle, render planner, negative schema/runtime, and browser acceptance coverage prove supported and failure paths. |
| Docs/examples | Authoring, loading, compatibility, examples, and release gates agree on support status and trust posture. |

Family-specific readiness:

| Family | Minimum readiness before support |
| --- | --- |
| Asset parser | Permission/declaration checks, parser failure diagnostics, safe asset metadata enrichment, query/filter API boundaries, and export/bake posture. |
| Effect | Trusted/signed package decision, parameter SchemaForm, picker/inspector provenance, preview errors, serialization/reload, and planner blockers for preview-only or unsupported export. |
| Transition | Provider-scoped registry, selector/inspector parameters, missing/disabled repair behavior, serialization/reload, render coverage, and export blockers. |
| Clip type | Sequence-backed subset first, insertion/inspection/rendering, serialization/reload, duplicate/missing/blocked capability failures, and planner participation through `renderRouter.ts`/`planRender()`. |
| Keyframes | Minimal model, commands/proposals, migration, interpolation tests, and deterministic preview/export delivery. |
| Agent tool | Proposal-first destructive behavior, backend dispatch registry, permission declarations, result-family validation, persisted proposals, and disabled/failure diagnostics. |
| Live data | Source lifecycle, permission state, bounded ring buffer, bake-to-deterministic asset/material workflow, steering lineage, and unbaked export blockers. |
| Render material | Public material/capability declarations, artifact manifest integration, material status tracking, and planner blockers/next actions. |
| Process/sidecar | Trusted local process model, command/env/cwd policy, JSON-RPC protocol, health/log/cancel/shutdown behavior, manager health UI, and explicit trust warnings. |
| Shader/WebGL | Source/uniform/texture schema, compile diagnostics, deterministic preview canaries, context-loss fallback, materializer/export route posture, and honest export blockers. |

## Roadmap And Ticket Reconciliation

This table records what must be reconciled after review. It intentionally does
not edit `docs/extensions/reigh-extension-layer-roadmap-v2.md` or
`docs/extensions/reigh-extension-layer-tickets.md`.

| Source item | Current status | Reconciliation needed before Phase 4 |
| --- | --- | --- |
| Roadmap Phase 1 acceptance cites `runtime/contributionFamilies.ts` | Stale path in this checkout; canonical sources: `src/sdk/video/families/contributionKinds.ts` (kind union), `src/sdk/video/families/familyDefinitions.ts` (family registry), `config/extensions/family-maturity.json` (maturity snapshot). Runtime descriptor normalization lives in `extensionSurface.ts`. | Update roadmap/ticket references after review, or restore a generated/owned contribution-family matrix file if that remains the intended gate. |
| Roadmap Phase 4 "Contribution Families And Render Hardening" | Correctly identifies asset parsers, effects, transitions, clip types, keyframes, agent tools, live data, render materials, sidecars/processes, and shaders as the next higher-power families. | Keep this sequencing, but require the checklist above and planner participation before any family moves to supported. |
| EXT-030 AssetParserContribution | Planned. | Add explicit render/export/bake posture and diagnostics requirements to the ticket if asset parser output can affect timeline materialization. |
| EXT-031 EffectContribution | Planned as trusted/signed packages. | Preserve trusted/signed wording, add manager trust warning coverage, and require planner blockers for preview-only effects. |
| EXT-032 TransitionContribution | Planned. | Add route capability metadata and fallback/repair behavior to prevent silent export differences. |
| EXT-033 ClipTypeContribution | Planned as a sequence-backed subset. | Keep subset scope; require `renderRouter.ts` contributed clip records and `planRender()` blockers before support. |
| EXT-034 Keyframes | Planned. | Treat as timeline data/model work first, not an extension family shortcut; require proposal/migration/render interpolation gates. |
| EXT-035 Render planner integration | Planned. | Promote this from a later hardening ticket to a prerequisite for every render-relevant family. |
| EXT-036 AgentToolContribution | Planned. | Block until proposal persistence and backend dispatch registry are stable; no direct destructive mutation by default. |
| EXT-037 Live data | Planned. | Block until bake/export semantics are accepted; unbaked live bindings must block export. |
| EXT-038 RenderMaterialContribution | Planned. | Tie directly to planner material refs/statuses, artifact manifests, and next actions. |
| EXT-039 Process/sidecar runtime | Planned as trusted local runtime. | Require separate trust approval, process policy, health UI, cancellation, and shutdown tests before public exposure. |
| EXT-040 Shader/WebGL bridge | Planned. | Keep behind render materialization posture and deterministic preview/export blocker tests. |
| EXT-041 Final docs/examples/validation | Planned. | Must include this readiness checklist as a closure matrix input, plus compatibility drift checks across schema, SDK, runtime, docs, examples, and tests. |

## Phase 4 Entry Decision

Phase 4 should not start as broad parallel family implementation. The next
accepted action should be either:

1. Fix the stale `contributionFamilies.ts` reference by updating to current
   canonical sources (`src/sdk/video/families/contributionKinds.ts`,
   `src/sdk/video/families/familyDefinitions.ts`, and
   `config/extensions/family-maturity.json`), then update roadmap/ticket docs
   after review; or
2. Begin EXT-035-style render planner integration as a prerequisite slice for
   the first selected family, with this document as the acceptance checklist.

Until one of those paths is accepted, the readiness decision is: Phase 4 is
prepared but not cleared for public family promotion.

---

## M5: Lifecycle, Diagnostics, Inventory, and Readiness — Gate Rows

The rows below represent the completed M5 work. Every cleared row has a
verifiable code anchor (source file and symbol), a test anchor (test file and
describe/it block), and an objective pass condition. The column definitions
are:

| Column | Meaning |
| --- | --- |
| **ID** | Unique row identifier within M5. |
| **Category** | Feature area (Diagnostics, Recovery, Containment, Inventory, Manager, Docs). |
| **Owner** | Primary source module. |
| **Status** | `cleared` (anchors verified), `pending` (code exists but test missing or blocked). |
| **Test Anchor** | `file:describe block → it name` that proves the behaviour. |
| **Code Anchor** | `file:exported symbol` that implements the contract. |
| **Objective Pass Condition** | Machine-verifiable assertion about the anchor pair. |
| **Notes** | Rationale, edge cases, or scope boundary. |

### M5 Readiness Rows

| ID | Category | Owner | Status | Test Anchor | Code Anchor | Objective Pass Condition | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-001 | Diagnostics | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:createExtensionDiagnosticsService → overwrites spoofed extensionId with the service-owned extensionId | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionDiagnosticsService | createExtensionDiagnosticsService.report() overwrites both extensionId and source with host-owned values for every diagnostic. | Provenance pinning prevents extension-authored spoofing of identity or source. |
| M5-002 | Diagnostics | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:createExtensionDiagnosticsService → pins source to DIAGNOSTIC_SOURCE_EXTENSION on every reported diagnostic | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionDiagnosticsService | Diagnostic source field is always DIAGNOSTIC_SOURCE_EXTENSION regardless of caller input. | Source pinning prevents confusion between extension-authored and provider-authored diagnostics. |
| M5-003 | Diagnostics | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:createExtensionDiagnosticsService → lifecycle disposal removes extension diagnostics without affecting host/provider diagnostics | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | Lifecycle disposal calls removeExtensionDiagnosticsFromCollection which scopes removal to extension-authored diagnostics only. | Provider/host diagnostics preserved through disposal because they lack an extensionId. |
| M5-004 | Recovery | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:ExtensionLifecycleHost — recovery-key registry (T2) → recovery key is set to "1" on first activation via synchronize | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | getRecoveryKey() returns "1" after first synchronize() for a new extension. | Recovery keys are lifecycle-host-owned monotonic integers encoded as strings. |
| M5-005 | Recovery | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:ExtensionLifecycleHost — recovery-key registry (T2) → recovery key stays stable across unchanged synchronize calls | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | getRecoveryKey() returns the same value across repeated synchronize() calls with identical manifests. | Stable keys prevent unnecessary contribution remounts. |
| M5-006 | Recovery | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:ExtensionLifecycleHost — recovery-key registry (T2) → recovery key increments on manifest replacement | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | getRecoveryKey() increases when synchronize() receives a changed manifest for an existing extension. | Manifest changes trigger fresh boundary renders. |
| M5-007 | Recovery | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:ExtensionLifecycleHost — recovery-key registry (T2) → incrementRecoveryKey bumps the key for a managed extension | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | incrementRecoveryKey() returns a strictly larger string key and getRecoveryKey() reflects the bump. | Explicit retry from error boundaries. |
| M5-008 | Recovery | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:ExtensionLifecycleHost — recovery-key registry (T2) → recovery keys are independent across extensions | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | Changing one extension's recovery key does not affect any other extension's key. | Isolation prevents cascading remounts. |
| M5-009 | Recovery | extensionLifecycle.ts | cleared | src/tools/video-editor/runtime/extensionLifecycle.test.ts:ExtensionLifecycleHost — recovery-key registry (T2) → recovery keys are monotonic and never decrement | src/tools/video-editor/runtime/extensionLifecycle.ts:createExtensionLifecycleHost | No operation on the lifecycle host can decrease a recovery key. | Monotonicity guarantees boundary reset propagation. |
| M5-010 | Containment | ContributionErrorBoundary.tsx | cleared | src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx:HostContributionErrorBoundary → with real DataProviderWrapper context | src/tools/video-editor/runtime/ContributionErrorBoundary.tsx:HostContributionErrorBoundary | HostContributionErrorBoundary reads recovery keys from VideoEditorRuntimeContextValue, passes them to ContributionErrorBoundary, and exposes a visible user-initiated bounded retry action. | Wrapper preserves legacy fallback UI; retry button is shown only when owning extension is known and is debounced/bounded to prevent infinite loops. |
| M5-011 | Containment | TimelineEditorShellCore.tsx | cleared | src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:TimelineEditorShellCore — HostContributionErrorBoundary recovery keys → resolves extensionId for slot boundaries from extensionRuntime contributions | src/tools/video-editor/components/TimelineEditorShellCore.tsx:TimelineEditorShellCore | All 14 slot boundaries use HostContributionErrorBoundary with extensionId resolved from slotOwnerMap. | Slots with no owning extension fall back to legacy children-change reset. |
| M5-012 | Containment | PropertiesPanel.tsx | cleared | src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:HostContributionErrorBoundary — inspector sections → renders inspector sections through HostContributionErrorBoundary | src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:PropertiesPanel | Inspector sections and asset panels use HostContributionErrorBoundary with extensionId from contributionOwnerMap. | Owner metadata threaded through inspector and panel descriptors. |
| M5-013 | Containment | ClipPanel.tsx | cleared | src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx:HostContributionErrorBoundary → with real DataProviderWrapper context | src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:ClipPanel | ClipPanel uses HostContributionErrorBoundary with extensionId from clipTypeRegistryRecord.ownerExtensionId. | Clip panel had reliable owner metadata before M5. |
| M5-014 | Inventory | extensionSurface.ts | cleared | src/tools/video-editor/runtime/extensionSurface.test.ts:computePackageContributionSummary → computes declared count and kinds from manifest contributions | src/tools/video-editor/runtime/extensionSurface.ts:computePackageContributionSummary | computePackageContributionSummary() returns frozen PackageContributionSummary with declaredCount, activeCount, inactiveCount, kinds, and contributionIds. | Survives without active runtime descriptors; pure function of manifest data. |
| M5-015 | Inventory | extensionSurface.ts | cleared | src/tools/video-editor/runtime/extensionSurface.test.ts:normalizeExtensionRuntime — package contribution summaries → can produce declared counts, kind labels, and contribution IDs for manifest-only entries without active runtime descriptors | src/tools/video-editor/runtime/extensionSurface.ts:normalizeExtensionRuntime | normalizeExtensionRuntime() precomputes contributionSummary for both active and non-active packages from manifest data. | Disabled/error entries remain inspectable. |
| M5-016 | Inventory | useExtensionLoaderWiring.ts | cleared | src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:VideoEditorProvider → synthesizes loaded packageStateEntries for direct host-supplied extensions | src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:useExtensionLoaderWiring | No-repository fast path synthesizes PackageStateInventoryEntry[] with packageState=loaded, stateReason=Direct host-supplied extension, manifestContributions, and contributionSummary. | Direct extensions visible in manager inventory without a repository. |
| M5-017 | Inventory | useExtensionLoaderWiring.ts | cleared | src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:VideoEditorProvider → synthesizes entries for multiple direct extensions in input order | src/tools/video-editor/runtime/useExtensionLoaderWiring.ts:useExtensionLoaderWiring | Repository-backed path merges direct entries alongside managed entries, preserving managed loader state and enablement semantics. | Duplicate handling: direct entries distinguished from managed via stateReason. |
| M5-018 | Manager | ExtensionManager.tsx | cleared | src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:ExtensionManager — direct entry read-only (T11) → does NOT show enable/disable toggle for direct host-supplied loaded entries | src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:ExtensionManager | Direct entries have no toggle; managed entries retain toggle. Direct badge (Zap icon, blue) rendered on direct entries. | Read-only direct entries prevent invalid enable/disable operations. |
| M5-019 | Manager | ExtensionManager.tsx | cleared | src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:ExtensionManager — contribution summary from inventory (T11) → contribution summary display | src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:ExtensionManager | ExtensionManager uses entry.contributionSummary from inventory as card source of truth; falls back to manifest-derived summary for non-active packages. | Contribution summaries visible for loaded, disabled, and error states. |
| M5-020 | Manager | ExtensionManager.tsx | cleared | src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:ExtensionManager — empty, error, and mixed states (T11) → renders empty state with Zap icon when no packages in inventory | src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:ExtensionManager | Empty state renders trust warning and empty-state UI. Mixed direct+managed entries show correct badge/toggle isolation. | All 7 package states have correct badges and reasons in manager cards. |
| M5-021 | Docs | trust-and-security.md | cleared | src/tools/video-editor/runtime/phase4ReadinessDocs.test.ts:M5-021: trust-and-security.md → exists and is readable | docs/extensions/trust-and-security.md | Document exists and states trusted/unsandboxed posture without implying sandbox, permission broker, marketplace, install, or update enforcement. | 198 lines; covers execution model, permission posture, error containment, diagnostic provenance, recovery keys, boundary audit, inventory truthfulness. |
| M5-022 | Docs | foundation-contracts.md | cleared | src/tools/video-editor/runtime/phase4ReadinessDocs.test.ts:M5-022: foundation-contracts.md → exists and is readable | docs/extensions/foundation-contracts.md | Document exists and covers canonical foundation contract paths: extension definition, lifecycle state machine, contribution surfaces, runtime normalization, diagnostic contract, error boundary contract, recovery key system, package inventory, settings contract, export guard, provider compatibility. | 423 lines; includes code path index (section 13, 24 files). |
| M5-023 | Browser Acceptance | extension-harness.spec.ts | cleared | tests/e2e/extension-harness.spec.ts:Extension Harness — Populated → renders the Extension Manager with package cards | tests/e2e/extension-harness.spec.ts | Playwright acceptance specs cover populated, empty, package-error, and repaired-settings states across desktop (Desktop Chrome 1280x720), condensed (iPad Mini 768x1024), and mobile (iPhone 13 390x844) viewports. | (slow gate) Playwright acceptance is not part of the fast release command. Run manually before public family promotion. 57 unique tests run across 3 viewport projects (171 total). Asserts trust warning, inventory cards, summaries, error/repaired states, and no incoherent overlap between key UI elements. Command: npx playwright test --config playwright.config.ts tests/e2e/extension-harness.spec.ts |

### M5 Readiness Decision

All M5 rows (M5-001 through M5-023) are **cleared**. Every cleared row has
verifiable code and test anchors created during the M5 implementation batch.
The lifecycle diagnostics, recovery keys, host contribution boundaries, package
inventory, Extension Manager, and trust/docs work are in place and passing
their respective test suites.

The `npm run test:readiness` command validates that every cleared row's anchors
resolve to existing files and symbols. A missing or renamed anchor causes the
command to fail.

## SDK Boundary and Family Maturity Model

M4 closed the pristine SDK boundary:

- `@reigh/editor-sdk` (`src/sdk/index.ts`) is the author-facing extension SDK. It exports portable contracts, types, and pure helpers only.
- Host-wired factories (`createExtensionContext`, `setEditorShellRoot`, `getEditorShellRoot`) were moved to `src/tools/video-editor/runtime/extensionContextFactory.ts`. Extension authors receive a ready-made `ExtensionContext` from the host; they never construct one themselves.
- `createProposalRuntime()` remains host-owned in `src/tools/video-editor/lib/proposal-runtime.ts`. Portable proposal contracts (`ProposalRuntime`, `TimelineProposal`, `ProposalEnvelope`, etc.) remain in the SDK.
- Every contribution family now has a declared maturity (`declarationMaturity`) and an execution posture (`executionMaturity`) recorded in `config/extensions/family-maturity.json`. Bridged families have a real host adapter under `src/tools/video-editor/runtime/families/*`. Delegated families use placeholder adapters and are not yet runtime-supported.
- The generated table below is maintained by `scripts/quality/check-docs-maturity-sync.mjs` and enforced in release mode.

## Family Maturity Snapshot

<!-- family-maturity-table-start -->
| Family | Declaration | Execution | Trusted | Bridged | Host Adapter | Notes |
|---|---|---|---|---|---|---|
| Agent | typed | delegated | Yes | No | — | Agent contributions are proposal-backed; the host mediates tool dispatch and generation sessions. No standalone host adapter exists yet — execution is delegated through the agent-tool registration service. |
| Agent Tool | schema-backed | delegated | Yes | Yes | `agentToolAdapter.ts` | Agent tool contributions are host-mediated: the host owns invocation, progress, cancellation, proposal creation, and UI. Extensions register tool handlers imperatively via ctx.agentTools. Execution posture is delegated to a placeholder adapter while descriptor projection remains stable. Evidence: AgentToolContribution interface, AgentToolRegistrationService, and manifest schema oneOf coverage. |
| Asset Detail Section | schema-backed | delegated | No | Yes | `assetDetailSectionAdapter.ts` | Asset detail section contributions add custom sections to the asset detail panel with title and placement validation. Descriptor projection is delegated to a distinct placeholder adapter separate from metadataFacet. Evidence: manifest validation enforces non-empty title and valid placement (before-default, after-default). |
| Automation | schema-backed | runtime-bridged | No | Yes | `automationAdapter.ts` | Automation clips are host-owned timeline clips (built-in clip type) with baked keyframe curves that override target extension parameter values during preview and export. Bridged at M9 alongside clipType. Evidence: BUILTIN_CLIP_TYPES includes automation; AutomationClipTarget and AutomationClipParams types exist; contributionKindNotYetBridged returns null for automation at M9. |
| Clip Type | schema-backed | runtime-bridged | No | Yes | `clipTypeAdapter.ts` | Clip-type contributions are dispatched through the timeline composition registry. The host adapter normalizes clip-type descriptors and owns lifecycle. Keyframe interpolation is host-owned. |
| Command | documented | host-integrated | No | Yes | `commandAdapter.ts` | Commands are fully bridged with palette, context-menu dispatch, keybinding wiring, and export-scoped guard participation. |
| Context Menu Item | documented | host-integrated | No | Yes | `contextMenuItemAdapter.ts` | Context menu item contributions add items to clip, track, and timeline-area context menus. Fully bridged at M4 through the command dispatch system. Evidence: command-extension.ts example includes a clip-target context menu item. |
| Dialog | documented | host-integrated | No | Yes | `dialogAdapter.ts` | Dialog contributions render into named dialog layers (modal, overlay). Bridged at M1 through the slot extension surface. Schema: DialogContribution with layer enum validation. |
| Effect | schema-backed | delegated | No | Yes | `effectAdapter.ts` | Effect contributions are trusted local browser-preview components. Extensions register effect components imperatively via ctx.effects. Descriptor projection is delegated to a placeholder adapter while runtime registration remains host-mediated. Evidence: EffectContribution interface, EffectRegistrationService, manifest schema oneOf coverage, and kind enum inclusion. |
| Inspector Section | documented | host-integrated | No | Yes | `inspectorSectionAdapter.ts` | Inspector section contributions add custom sections to the inspector panel. Placement can be before-default or after-default. Evidence: dedicated inspector-example.ts with both placement values. |
| Keybinding | documented | host-integrated | No | Yes | `keybindingAdapter.ts` | Keybinding contributions bind keyboard shortcuts to commands with platform-aware key notation. Bridged at M4 through the command dispatch system. Evidence: command-extension.ts example includes a CtrlOrCmd+Alt+R keybinding. |
| Metadata Facet | schema-backed | runtime-bridged | No | Yes | `metadataFacetAdapter.ts` | Metadata facet contributions tell the host how to surface a metadata field as a searchable/filterable facet in the asset panel. Bridged at M6. Evidence: MetadataFacetContribution interface, kind enum inclusion, and M6-active bridging status in contributionKindNotYetBridged. |
| Output Format | typed | delegated | No | Yes | `outputFormatAdapter.ts` | Output format types are declared but runtime execution is reserved. Descriptor projection is delegated to a placeholder adapter that surfaces compile-only and render-dependent planner stubs. |
| Panel | documented | host-integrated | No | Yes | `panelAdapter.ts` | Panel contributions render into the asset panel region. Placement is limited to asset-panel. Bridged at M1 through the slot extension surface. Evidence: panel placement validation in SDK tests. |
| Parser | schema-backed | delegated | No | Yes | `parserAdapter.ts` | Parser contributions are bridged through the asset ingestion pipeline. Descriptor projection is delegated to a placeholder adapter; real ingestion lifecycle remains host-owned. |
| Process | typed | delegated | Yes | Yes | `processAdapter.ts` | Process contributions declare trusted local process descriptors with installation posture, lifecycle, and capability requirements. Execution is reserved for M12 — processes are declarable in manifests but not yet bridged for runtime. Evidence: ProcessContribution interface, ProcessSpec, ProcessLifecycleState types; contributionKindNotYetBridged returns M12. |
| Search Provider | typed | delegated | No | Yes | `searchProviderAdapter.ts` | Search provider contributions supply asset/material search results to the host search surface. The provider owns indexing, model choice, and refresh; the host owns query dispatch, result merge, and source labeling. Typed but execution is reserved (declarable, not yet bridged for runtime). Evidence: SearchProviderContribution interface; contributionKindNotYetBridged returns M6. |
| Shader | schema-backed | delegated | No | Yes | `shaderAdapter.ts` | Shader contributions declare WebGL materializer descriptors. Descriptor projection is delegated to a placeholder adapter while materializer requirements remain validated at export time. |
| Slot | documented | public-supported | No | Yes | `slotAdapter.ts` | Slot contributions are the original extension surface. Fully bridged with lifecycle, diagnostics, UI, persistence, examples, and tests. |
| Timeline Overlay | documented | host-integrated | No | Yes | `timelineOverlayAdapter.ts` | Timeline overlay contributions render over the timeline surface with order control and when-clause filtering. Bridged at M2. Evidence: dedicated overlay-example.ts. |
| Transition | schema-backed | delegated | No | Yes | `transitionAdapter.ts` | Transition contributions are trusted local browser-preview renderers for cross-clip transitions. Extensions register transition renderers imperatively via ctx.transitions. Descriptor projection is delegated to a placeholder adapter while runtime registration remains host-mediated. Evidence: TransitionContribution interface, TransitionRegistrationService, manifest schema oneOf coverage, and kind enum inclusion. |
<!-- family-maturity-table-end -->
