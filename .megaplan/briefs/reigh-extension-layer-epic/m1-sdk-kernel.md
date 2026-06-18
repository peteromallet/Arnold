# M1: SDK Kernel And Trusted Local Extension Runtime

## Outcome

Deliver the trusted local source-code extension kernel: provider injection, public SDK entrypoint, frozen contribution normalization, runtime containment, settings/i18n/chrome scaffolding, and a first local example extension.

## Execution Posture

Build the host-owned spine without pretending to know every future organ. Be strict about lifecycle, identity, diagnostics, trust honesty, and no raw editor internals; be humble about reserved contribution shapes and require later API-fit reviews before they become real contracts.

## Scope

IN:
- Add `extensions?: ReighExtension[]` to internal and public video editor providers.
- Normalize contributions into a provider-scoped frozen runtime.
- Define the host-owned `ExtensionRuntime`/`ExtensionHost` lifecycle state machine that owns normalization, enablement, disposal, diagnostics cleanup, and registry projection.
- Fix `VideoEditorRuntimeContextValue` drift so `extensions` is consistently present.
- Create `@reigh/editor-sdk` or an equivalent stable workspace entrypoint.
- Add `defineExtension()`, core types, ID rules, and contribution ID validation.
- Add reserved-but-validated manifest fields for future `permissions`, `migrations`, `comments`, `processes`, renderability descriptors, effects, transitions, clip types, parsers, agent tools, and agents.
- Add `ExtensionContext` shell with conservative stable members.
- Reserve the `CreativeContext` service shape so timeline is one scoped context member beside assets, materials, sessions, export, stage/canvas, and writing/script. M1 should expose only inert typed stubs for inactive primitives, but the public mental model must not make `TimelineSnapshot` the root of all future reads.
- Export `DisposeHandle` from `@reigh/editor-sdk`.
- Add localStorage-backed extension settings defaults.
- Add `chrome.toast`, `chrome.progress`, and `chrome.subscribe` scaffolding.
- Add contribution-level error boundaries, diagnostics, and dev logging.
- Add export guard baseline for extension-only render features.
- Add project-level extension requirements metadata shape: required extension IDs, API/version ranges, referenced contribution IDs, installed integrity where known, and missing-extension diagnostics.
- Add V1 trust-envelope documentation/table for local source extensions, parser code, package loading, edge-tool declarations, browser permission helpers, local processes, filesystem/env/network posture, logs, and shutdown visibility.
- Add early package identity metadata for examples: `reigh-extension.json` or equivalent ID/version/API compatibility/settings schema/dependency metadata, even though real installable archives wait for M14.
- Start the flagship extension pack as the living cross-milestone example. In M1 it proves metadata, runtime activation, toolbar/status UI, diagnostics, and trusted-local warnings; later milestones extend the same pack rather than creating unrelated examples only.
- Define the source-pack/package contract freeze for V1: manifest schema, source-pack layout, package ID/version rules, API compatibility range semantics, settings schema location, and local-source-to-installed-pack invariants. M14 implements archives/manager persistence rather than inventing these semantics.
- Add SDK boundary tests and shared fake-extension/diagnostic fixtures used by later milestones.
- Add one example local extension and integration tests for provider injection, toolbar render, HMR-safe re-registration, and failure containment.

OUT:
- Dynamic remote loading.
- Marketplace/package install.
- Sandbox/permissions.
- Deep timeline patch API.
- Effects, transitions, clip-type dispatch, render providers.

## Locked Decisions

- V0 is trusted local source-code extensions.
- V0 extensions are powerful trusted developer code. Permission metadata is descriptive until sandboxing; user-facing warnings must not imply isolation that does not exist.
- Extension authors import from `@reigh/editor-sdk`, not editor internals.
- Duplicate extension IDs and contribution IDs fail registration.
- Deterministic ordering: built-ins first, then `order`, then extension/contribution ID.
- Host owns containment; extension render failures must not blank the editor.
- The first SDK exports both types and helper constructors such as `defineExtension()`.
- Dev diagnostics go to both structured console groups and a host-visible diagnostics/status surface.
- Permissions metadata is validated but not enforced until sandboxing exists.
- Remote extension loading and untrusted marketplace execution are not supported by any M1 path.
- Future contribution fields that are reserved but not implemented fail with clear diagnostics if used.
- Reserved-but-unbridged contribution namespaces are explicitly `experimental/reserved`; each milestone that activates one must run an API-fit review against the M1 shape before treating it as stable.
- M1 `ExtensionContext` exposes only working members: `chrome`, `services.settings`, `services.i18n`, `services.diagnostics`, readonly extension metadata, and reserved stubs for future members that throw typed "not implemented until Mx" errors. `ctx.creative` reserves scoped `project`, `timeline`, `assets`, `materials`, `sessions`, `export`, `stage`, and `writing` members; each becomes live only in the milestone that owns its contract.
- `ExtensionContext` exposes `apiVersion: number`, starting at `1`. The version increments when a new contribution kind is actually bridged into the runtime, not merely when its manifest field exists.
- Contribution kinds declared in a manifest but not yet bridged by the active runtime are parsed for basic shape/ID uniqueness, held inactive, and diagnosed with `contribution_kind_not_yet_bridged` naming the earliest milestone that activates the kind. They do not crash or silently disappear.
- All contribution lifecycle methods that require cleanup return a `DisposeHandle`: `{ dispose(): void; [Symbol.dispose]?: () => void }`. Dispose is idempotent, must not throw, and is callable synchronously. Async teardown work reports progress through diagnostics/status rather than blocking editor disable forever.
- The reserved `processes` manifest field is validated against a concrete inactive shape: `{ id, label, spawn: { command, args?, env?, cwd? }, protocol: 'stdio-jsonrpc', healthCheck?, shutdown?, restartPolicy? }`. M1 validates required fields and duplicate IDs; M12 implements local trusted stdio execution. Websocket/http process protocols remain deferred until a later trust model explicitly supports them.
- `chrome.subscribe` event schema is limited to toast/progress/save/render status events available in the host today; additional events require explicit SDK additions.
- `@reigh/editor-sdk` starts as a TypeScript/Vite path alias to `src/sdk/index.ts`; later packaging can move it to a workspace package without changing import paths.
- Re-rendering providers with an extension removed must unregister that extension's contributions and settings defaults. A separate UI manager is deferred, but lifecycle removal is not.
- Project/timeline data may record extension requirements, but M1 does not auto-install or fetch anything. Missing requirements produce diagnostics and placeholders only.
- Extension manifests may reserve `dependsOn` entries with extension ID, version range, optional contribution IDs, and optional/degrade posture. M1 validates shape only; M14 surfaces dependency chains in the manager.
- The V1 trust envelope is honest, not protective: trusted extensions can run local code according to the host path that loaded them; sandboxing, remote code trust, and marketplace isolation are separate future work.
- Trusted-local safety baseline: show explicit activation warnings for code/process execution, redact secrets from logs by default, bound parser/process work with timeout/cancel where applicable, avoid passing broad env/cwd by default, and surface declared network/filesystem/process posture. These are blast-radius controls, not sandboxing.
- The M1 export diagnostic baseline is a real testable scan: resolved clips are checked for unknown effect/transition/clip-type IDs and receive structured diagnostics with severity, clip reference, contribution kind, and reason. M1 only blocks what it can prove from known IDs; later milestones add feature-specific blockers, and M12 unifies routing through the capability planner.
- Host-visible diagnostics in M1 are a minimal diagnostics service plus compact status/fallback rendering; the full diagnostic panel arrives in M2.

## Constraints

- Preserve all existing editor behavior when `extensions` is empty.
- Do not expose raw `DataProvider`, raw `applyEdit`, or internal ops as public SDK.
- Keep the implementation provider-scoped and HMR-safe.

## Done Criteria

- A local extension can be imported, passed into the editor, rendered in toolbar, updated under Fast Refresh, and removed without leaking contributions.
- Extension failure is visible and contained.
- Pure-native export routing remains unchanged.
- Tests cover empty runtime compatibility, duplicate IDs, contribution ordering, provider injection, and error boundary behavior.
- Tests cover the `ExtensionRuntime` lifecycle state machine, including activate, deactivate, dispose, failed activation, provider teardown, and diagnostics cleanup.
- Type tests or example compilation prove `@reigh/editor-sdk` is the only import path needed for the example.
- Example metadata proves ID/version/API compatibility/settings schema are available before M14 package installation exists.
- Flagship extension pack compiles and runs as the living example seed.
- Tests prove reserved future fields fail with clear diagnostics, not silent ignore.
- Tests prove removing an extension from provider props unregisters its contributions.
- Tests prove synthetic unknown render IDs trigger structured export diagnostics and only alter routing when the milestone owns a proven blocker.
- Tests prove an extension using a not-yet-bridged contribution kind receives `contribution_kind_not_yet_bridged` diagnostics.
- Tests prove invalid `processes` entries produce diagnostics while valid inactive process entries are accepted.
- Tests prove `ExtensionContext` exposes no raw `DataProvider`, raw `applyEdit`, or internal mutation escape hatch.
- Tests prove project-level extension requirement metadata produces diagnostics for missing/unsupported extensions without network fetch or install behavior.
- Tests prove no public primitive added in M1 is SDK-only: the example extension renders through the host runtime and visible UI path.

## Touchpoints

- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/contexts/VideoEditorProvider.tsx`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- SDK/package export config.
