# M14: Packaging, Runtime Loader, Extension Manager

## Outcome

Begin the move from local source imports to shareable packs: package metadata, runtime loader design/implementation for trusted packs, persisted enablement/settings, and a built-in extension manager surface.

## Execution Posture

Packaging preserves identity; it must not redefine the platform. Harden the source-pack contract, manager, loader, settings, migrations, and trust warnings while keeping installed trusted packs behaviorally continuous with local development.

## Scope

IN:
- Define package metadata format compatible with `ReighExtension`.
- Reuse and harden the M1 example metadata shape (`reigh-extension.json` or equivalent) rather than inventing package identity from scratch.
- Add local install/load path for trusted bundles or workspace packs.
- Add persisted extension enable/disable state.
- Add extension manager UI for installed/local packs.
- Persist extension settings beyond localStorage where the active provider supports it.
- Add migration hooks as reserved/validated contribution kind.
- Add extension-to-extension dependency declarations and settings-schema versioning/migration posture.
- Add integrity hash validation for installed packs.
- Add package API-version compatibility fields.
- Add typed settings schemas for manager-rendered settings.
- Add logging/telemetry namespace for extension lifecycle diagnostics.
- Define `ExtensionStateRepository`, `ExtensionLoader`, pack storage, package schemas, and disable/uninstall data policy.
- Document provider-backed extension state repository patterns for teams that need shared review/compliance data without host-owned CRDT sync.

OUT:
- Public marketplace.
- Remote untrusted code execution.
- Full sandbox/permission system.
- Cloud worker execution of extension code.

## Locked Decisions

- Same manifest/contribution model must serve local source and installed pack forms.
- M14 may revise the M1 metadata shape only through an explicit compatibility/migration note; earlier examples must remain loadable or produce clear migration diagnostics.
- Loader must feed provider-scoped registries; no global registration.
- Pack loading remains trusted until sandboxing is genuinely implemented.
- Integrity hashes prove package identity/tamper detection, not safety. The manager must label installed packs as trusted local code and avoid implying sandbox isolation.
- First package format supports both workspace source packages for local development and built ESM bundles for installed trusted packs.
- Persisted settings live through a provider-backed extension settings repository when available; local/Astrid mode falls back to localStorage until its provider explicitly supports extension settings.
- Permission metadata was reserved in M1 and is displayed here; it is still not enforced until sandboxing exists.
- Installed packs must declare ID, version, API compatibility range, author, description, homepage/icon metadata where available, and artifact integrity hash.
- Installed packs update project-level extension requirements/lock metadata when enabled in a project.
- Extension migrations are validated and listed, but migration execution only applies to extension-owned namespaced data.
- Extension `dependsOn` metadata is displayed and validated in the manager: extension ID, version range, optional contribution IDs, optional/degrade posture, and dependency-chain diagnostics. Missing required dependencies block activation; optional dependencies degrade with diagnostics.
- Settings schemas carry a schema version independent of extension version. On activation, the host compares persisted settings schema version and can call an optional settings migration hook. Failed or absent migrations reset to defaults with diagnostics rather than silently corrupting settings.
- Extension state persistence uses an explicit `ExtensionStateRepository` abstraction with installed packs, enabled extension IDs, and per-extension settings. Astrid/local mode stores this as project-local extension state; Supabase mode uses a provider-backed repository; browser-only fallback uses IndexedDB/localStorage according to payload size.
- `ExtensionStateRepository` is for enablement, settings, package/lock metadata, and provider-backed shared extension state. Patch-backed extension-owned project data from M3 remains part of project/timeline mutation history and is migrated through patch/data migration hooks, not through the settings repository.
- Provider-backed extension state can support team/shared extension data where the active provider supports it; conflict resolution and realtime collaboration remain extension/provider-specific unless a future host sync contract exists.
- Workspace source packs are directories with `reigh-extension.json` plus an entry module. Installed bundle packs are archives containing `manifest.json`, `bundle.mjs`, optional assets, API compatibility, and integrity hashes.
- Extension manager UI is a host-owned editor surface opened from the header/tools/settings area, not a contributed extension surface.
- Source-vs-installed conflicts render as manager rows with a dev-only per-extension "use local source" override and "revert to installed" action.
- Dependency chains render as expandable lists/trees with satisfied/missing/degraded badges. Circular dependency diagnostics name the cycle and block activation.
- Optional dependency degradation is contribution-scoped: the extension can be active degraded while dependent contributions are inactive with diagnostics and links to missing dependencies.
- Uninstall uses a reference report dialog for at least the current project: affected contribution IDs, counts by kind, expandable object refs, navigation where available, and uninstall/cancel actions. Provider-wide reference scans may be deferred explicitly.
- Settings migrations show compact manager status: pending migration notice, success/failure/reset result, old/new schema versions, timestamp, and diagnostics.
- Extension status drawer includes a compact lifecycle event log for recent install, load, migration, activation failure, disable, uninstall, and integrity events.
- Disable unregisters contributions and preserves settings/data. Existing timeline references become diagnostics and export blockers where appropriate. Uninstall unregisters, deletes settings, and requires a find-references warning before completion.
- Local source vs installed pack conflict policy: installed packs win by default; dev-only override can prefer local source with visible diagnostics.
- `ExtensionLoader` has `load`, `unload`, and `validate` methods. M5 ships the minimal trusted local-loader lifecycle; M14 hardens it for source packs and installed trusted bundles. Future sandboxed loaders implement the same interface.
- `services.logger` is an extension-scoped host logger that routes to console/diagnostics/telemetry where available; it is not a telemetry contribution kind.
- Local source extensions can be converted to installed trusted packs through a migration flow that preserves extension ID, settings, namespaced data, and timeline references.

## Constraints

- Existing local source-code extension path must keep working.
- Disable/uninstall must remove contributions and registry entries without refresh.
- Pack failures must be isolated and diagnosable.

## Done Criteria

- User/developer can see installed/local extensions, enable/disable them, and edit settings.
- Loader registers/unregisters contributions provider-safely.
- Tests cover persisted enablement, settings, failed load, and contribution cleanup.
- Integrity mismatch prevents installation/activation with clear diagnostics.
- Tests cover extension state persistence, workspace pack load, bundle pack validation, manager UI location, disable/uninstall reference behavior, migration failure blocking activation, and local-vs-installed conflict handling.
- Tests cover compatibility with M1 local-source metadata and clear migration diagnostics for older metadata shapes.
- Tests cover local-source-to-installed-pack migration, including settings/data preservation and reference continuity.
- Tests cover manager trust warnings and extension requirements/lock metadata updates for installed packs.
- Tests cover provider-backed extension state repository shape for a review/compliance-style extension without implementing CRDT collaboration.
- Tests cover extension dependency diagnostics, optional dependency degradation, settings schema migration success/failure, and default-reset diagnostics.
- Tests cover conflict override UI, dependency tree badges/cycle diagnostics, degraded contribution inventory, uninstall reference report, settings migration summary, and lifecycle event log.

## Touchpoints

- SDK manifest/package metadata
- Provider runtime
- Settings service
- Extension manager UI
- Persistence layer
