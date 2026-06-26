# Foundation Closure Assessment

**Epic:** `reigh-foundation-closure` — M4 Release Readiness Gate  
**Date:** 2026-06-24  
**Status:** M4 complete; broad Phase 4 family implementation remains blocked.

## Objective

Close the Reigh extension foundation gaps identified in `NORTHSTAR.md` and the `foundation-contract-ledger.md` blocking rows. The M4 gate makes readiness a release-quality gate: every blocking foundation contract has runnable evidence, `quality:check` includes readiness, proposal reload semantics are explicit and tested, the contract ledger is closed, and the trust posture is documented without overclaim.

## Contracts Satisfied

| Contract | Evidence command | Status |
|---|---|---|
| Public proposal import (M1) | `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/lib/proposal-runtime.test.ts` | Satisfied |
| Agent proposal vertical (M2) | `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/hooks/useAgentSession.proposal-vertical.test.tsx` | Satisfied |
| Settings runtime write-through (M3) | `npx vitest run --config config/testing/vitest.config.ts src/sdk/extensionSettingsService.test.ts` <br> `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx` <br> `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx` <br> `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/runtime/extensionSettingsNotification.test.ts` | Satisfied |
| M5 lifecycle, diagnostics, inventory, and readiness rows | `npm run test:readiness` | Satisfied |
| Proposal reload semantics (M4) | `npx vitest run --config config/testing/vitest.config.ts src/tools/video-editor/lib/proposal-runtime.test.ts` | Satisfied |

## Evidence

- `npm run test:readiness` passes in strict mode. It validates that every cleared M5 readiness row in `docs/extensions/phase4-readiness.md` has resolvable code and test anchors, and that cleared non-e2e rows are wired into the fast release test command.
- `npm run quality:check` now includes `npm run test:readiness` as its final step, so the readiness gate is enforced by the release-quality command.
- `docs/extensions/foundation-contract-ledger.md` has no blocking rows; every foundation contract is either satisfied or explicitly waived.
- Proposal reload semantics are documented and tested: the runtime hydrates only `pending` proposals from the persistence provider; terminal history (accepted, rejected, stale, expired) is intentionally not reloaded.

## Phase 4 Family Work

Broad Phase 4 family implementation is **not cleared**. Each contribution family (asset parser, effect, transition, clip type, keyframes, agent tool, live data, render material, process/sidecar, shader/WebGL) remains blocked until it passes the checklist in `docs/extensions/phase4-readiness.md` and participates in render planning through `planRender()` with visible requirements and failure states.

## Trust Posture

The current posture remains **trusted/unsandboxed local packages only**:

- Extension code runs as trusted, unsandboxed code in the host environment.
- Manifest permissions are declarative metadata only; they are not runtime enforcement, sandbox isolation, code signing, a permission broker, marketplace review, or safe third-party execution.
- No sandbox, permission broker, marketplace, remote install, or signing claims are made in the docs, examples, or manager surfaces.

M4 closes the foundation gate; it does not authorize public promotion of arbitrary Phase 4 families.

## SDK Boundary and Host Adapter Architecture

M4 finalized the split between the portable extension SDK and the host runtime:

- `@reigh/editor-sdk` (`src/sdk/index.ts`) is the extension author surface: contracts, types, manifest helpers, and pure utilities. It must not import from `src/tools/video-editor/**`.
- Host-owned wiring lives under `src/tools/video-editor/**`. The `ExtensionContext` factory, proposal runtime, and family host adapters are all host modules.
- Contribution families declare `declarationMaturity` and `executionMaturity` in `config/extensions/family-maturity.json`. A family is only `public-supported` or `runtime-bridged` when it has a real host adapter. Families marked `delegated` are declarable in manifests but their runtime execution is not yet supported.
- The allowlist at `config/governance/video-editor-sdk-import-allowlist.json` records every non-public deep import into video-editor internals, with owner, rationale, removal condition, and expiration.

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
