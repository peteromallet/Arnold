# Reigh Extension Layer Epic Anchor Audit Synthesis

Date: 2026-06-21
Branch/epic: `reigh-extension-layer-epic`
Workspace: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

## Inputs

- 3 Codex anchor reviews:
  - `codex/contracts.log`
  - `codex/ux-runtime.log`
  - `codex/backend-devex.log`
- 30 DeepSeek granular reports:
  - `deepseek/*.txt`
  - Fan report: `deepseek/_report.json` (`30/30 ok`, `0 failed`, 4244.399 summed agent seconds)
- DeepSeek brief index:
  - `briefs/deepseek-brief-index.md`

## Executive Verdict

The epic does not currently look fulfilled as an end-to-end extension layer. The branch contains valuable foundations: a governed public video-editor SDK, a typed internal slot/dialog/panel surface, a capable sequence/clip-type path for trusted clips, dynamic effect infrastructure, render routing, and provider/persistence work. But the core extension-platform contract described by the milestone chain is mostly absent or unreachable.

The consistent finding across Codex and DeepSeek is that the work landed as a set of internal editor capabilities, not as a packageable, provider-scoped, public extension platform. The most important missing anchors are: public extension exports, runtime injection, manifest/package loader, extension manager/state/settings, diagnostics, proposal/versioned timeline patches, extension-safe commands, render capability/blocker vocabulary, third-party contribution APIs, and docs/release gates.

## Alignment Against Epic Goals

- M0/M15 SDK governance: partial. `config/contracts/registry.json` freezes existing video-editor SDK entrypoints, but not extension-layer APIs.
- M1 kernel/runtime: mostly absent. `extensionSurface.ts` exists, but no `defineExtension`, manifest, lifecycle, provider-scoped injected runtime, permissions, migrations, or package identity.
- M2 UX surfaces: partial. Slot/dialog/panel types exist, but several declared slots are not rendered and expected diagnostics/code/writing/stage surfaces are missing.
- M3/M10 patch/proposal/agent flow: mostly absent. Internal mutation and save versioning exist, but no public `TimelinePatch`/`TimelineProposal` or reviewable proposal lifecycle.
- M4 extension commands: absent. Commands are internal and typed, but not extension-contributed, namespaced, menu-discovered, or conflict-managed.
- M5/M7/M8/M9 contributions: partial and fragmented. Clip/effect/transition/keyframe surfaces are trusted/internal or static, not coherent third-party extension contracts.
- M11 live data bridge: partial. Supabase realtime/agent sessions exist but are hardwired, not `DataSourceContribution`/`LiveChannel` style extension data sources.
- M12 render/process/sidecars: mostly absent. Render router exists, but no canonical planner/blocker/artifact/process sidecar model.
- M13 shaders/WebGL: absent.
- M14 packaging/loader/manager: absent.

## Highest-Leverage Polish Plan

### 1. Make the Existing Extension Surface Reachable

Goal: turn the typed slot/dialog/panel surface from internal scaffolding into an injectable runtime.

- Add `extensions?: VideoEditorExtensionConfig` to `VideoEditorProvider`, `EditorRuntimeProvider`, and `BrowserVideoEditorProvider` props.
- Pass that config through `resolveVideoEditorExtensionRuntime()` instead of hardcoding `DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME`.
- Export the extension types from an intentional public entrypoint, not only `runtime/extensionSurface.ts`.
- Add public browser/provider tests that mount a minimal extension and assert a slot, dialog, panel, and inspector section actually render.
- Update contract governance so these exports are frozen and deep imports are blocked.

This is the first gate. Without it, every other extension feature remains unreachable.

### 2. Define the Extension Package Contract

Goal: establish the missing M1/M14 anchor: package identity, compatibility, lifecycle, and installability.

- Add a `reigh-extension.json` schema under `config/contracts/`.
- Define public types: `ReighExtension`, `ExtensionManifest`, `ExtensionPackage`, `ExtensionContribution`, `ExtensionPermission`, `ExtensionCompatibility`, `ExtensionMigration`.
- Implement a small `ExtensionLoader` that loads bundled JSON/test fixtures into `VideoEditorExtensionConfig`.
- Implement `ExtensionStateRepository` for enabled/disabled state and per-extension settings, backed first by in-memory/local storage, then provider settings.
- Add `ExtensionManager` UI only after the loader/state contracts are testable.

### 3. Unify Diagnostics

Goal: make extension failures inspectable instead of console-only/test-only.

- Define `Diagnostic`, `DiagnosticSource`, `DiagnosticSeverity`, `DiagnosticCollection`, and `DiagnosticReporter` in the public extension SDK.
- Route perf diagnostics, asset materialization diagnostics, generation asset diagnostics, render blockers, and extension loader failures into this channel.
- Add a status drawer or diagnostics panel surface and a slot/registry contract for extension-specific diagnostics.
- Tests should assert failed extension registration and failed asset materialization appear in the same diagnostics stream.

### 4. Add Versioned Timeline Proposals

Goal: give agents and extensions a safe mutation primitive.

- Define `TimelinePatch` and `TimelineProposal` around semantic operations, base `configVersion`, preview/dry-run result, and stale rejection.
- Wrap the existing command pipeline and `saveTimeline(expectedVersion)` in this proposal contract.
- Make the AI timeline agent default to proposal/dry-run/review for destructive changes, with explicit apply.
- Add conflict tests: proposal based on stale version must reject before applying.

### 5. Make Commands Extension-Safe

Goal: promote internal command infrastructure into an extension contribution surface.

- Add `CommandContribution` with namespaced IDs, labels, contexts, keybindings, menu placements, and diagnostics on conflicts.
- Wire contributions into command palette and context menus.
- Use existing `commands/types.ts` and `commands/runner.ts` as the execution core, but enforce namespace/reserved-command rules at registration.
- Add tests for duplicate command IDs, keybinding conflicts, and contributed context-menu actions.

### 6. Normalize Contribution Families

Goal: stop clip/effect/transition/agent contributions from evolving as unrelated bespoke mechanisms.

- Clip types: make `defineClipType` explicitly public or explicitly trusted-only. If public, add registration and wire `Inspector` adapters into `ClipPanel`.
- Effects: add `EffectContribution` to extension config, with trusted component registration, parameter schema, provenance, and renderability metadata.
- Transitions: replace static `transitions` map with `TransitionContribution`/registry, add UI selector, and preserve existing four transitions as built-ins.
- Keyframes: decide whether keyframes are part of this epic. If yes, add authoring, inspection, commands, serialization, and render-time interpolation. If no, remove the claim from acceptance criteria.
- Agent tools: add `AgentToolContribution` only after proposals exist, so tools can return proposals rather than direct mutation text.

### 7. Build a Render Capability Planner

Goal: replace scattered route decisions with one export/readiness truth.

- Define `RenderCapability`, `CapabilityFinding`, `RenderBlocker`, `RenderMaterial`, and `RenderArtifactManifest`.
- Convert `renderRouter.ts` from a classifier into an input to a planner that can explain blockers and required sidecars/processes.
- Integrate effect/clip/transition contribution metadata into the planner.
- Add pre-export readiness UI and tests for unsupported extension content.

### 8. Provider and Local Runtime Parity

Goal: make providers safe for extension-era behavior.

- Extend `DataProvider` with explicit capability detection, not optional-method guessing.
- Create a provider parity test suite for Supabase, Astrid bridge, browser, and in-memory providers.
- Separate "missing event log table" from "empty event log" in Supabase sync diagnostics; current fallback fixes app loading but masks protocol drift.
- Define local process/sidecar runtime only if render planner needs it. Otherwise remove process/sidecar claims from the epic scope.

### 9. Docs, Examples, and Release Gates

Goal: prevent another false-complete epic state.

- Add `docs/extensions/authoring.md`, `docs/extensions/loading.md`, and `docs/extensions/compatibility.md`.
- Add `examples/video-editor-extension-basic` with a real extension manifest, slot, inspector section, command, and diagnostic.
- Add contract checks for extension exports and manifest schema.
- Add acceptance tests that mount the public browser provider with an extension package and verify: injection, rendering, diagnostics, proposal mutation, and unload/disable behavior.

## Suggested Execution Order

1. Runtime injection + public exports + contract freeze.
2. Manifest/schema + loader + state repository.
3. Diagnostics stream + status drawer.
4. Timeline proposal contract + agent review flow.
5. Commands + menus/palette contributions.
6. Clip/effect/transition contribution normalization.
7. Render planner + blockers/artifacts.
8. Provider parity + local process decision.
9. Docs/examples/release gates.

## Decision Points

- Is this epic meant to ship a full third-party extension platform now, or only internal extension-ready seams? If the latter, rename the epic deliverables and make the internal scope explicit.
- Are shader/WebGL and local process sidecars required? The codebase currently has no real anchor for either. Keeping them in scope means new architecture work, not polish.
- Should clip types be public third-party APIs? Today they are strong internally but not externally registerable.
- Should agent tools ever direct-apply? If the epic goal is safe extensibility, proposal-first should be the default.

## Residual Caveats

- One DeepSeek report claimed imports referenced `nSurface.ts`; direct verification showed imports correctly reference `extensionSurface.ts`, so that claim was excluded.
- This synthesis did not change product code. It only created audit artifacts.
- There are unrelated/uncommitted code changes in the working tree from the video editor app-mode loading fix; they are outside this audit plan.
