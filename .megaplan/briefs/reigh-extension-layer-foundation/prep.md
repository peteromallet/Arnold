# Megaplan Prep: Reigh Extension Layer Foundation

Date: 2026-06-22
Workspace: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`
Source plan: `docs/extensions/reigh-extension-layer-foundation-plan.md`

## Outcome

Turn the current narrow extension-author preview into a durable foundation for deeper contribution families. A developer should be able to load an extension package, see and manage it, persist enablement/settings/proposals through supported providers, execute proposal-backed commands safely, inspect scoped diagnostics, edit settings through a host-owned form, reload without losing state, and see honest trust/permission warnings.

This epic intentionally stops before public effects, transitions, clip types, keyframes, asset parsers, agent tools, live data, render materials, sidecars, and shaders. It ends with a Phase 4 readiness gate that defines what must be true before those deeper families start.

## Scope Sizing

This does not fit in one sprint-sized megaplan. Phase 1 is small, but Phase 2 includes provider persistence, Supabase/RLS, browser-local storage, proposal envelopes, and agent policy wiring. Phase 3 includes manager UI, diagnostics reporter, SchemaForm, lifecycle cleanup, and trust warnings. Treat it as an epic chain of sprint-sized megaplans.

Recommended chain:

1. **M1: Preview truth and contract freeze**
   - Regenerate/record validation.
   - Freeze current public exports.
   - Fix the known `panels.placement` docs/schema contradiction.
   - Add compatibility drift checks and production-build extension smoke.
   - Normalize docs and trust language.
2. **M2: Provider persistence spine**
   - Decide and implement provider-owned repository factories.
   - Add sync cache over async stores.
   - Add Supabase schema/RLS design and migrations.
   - Add browser-local persistence and provider conformance tests.
3. **M3: Proposal spine and agent policy**
   - Add public `TimelinePatch`/proposal envelope types over existing command execution.
   - Persist proposals with TTL/expiry.
   - Wire frontend `proposal_policy` through edge function to backend mutation mode.
   - Prove agent proposal response, no immediate mutation, accept/reject flow.
4. **M4: Diagnostics reporter, SchemaForm, and lifecycle cleanup**
   - Add scoped extension diagnostic reporter with spoofing prevention and capacity bounds.
   - Add host-owned SchemaForm primitive.
   - Define cleanup contract and tests for disable/unload/re-enable.
5. **M5: Extension manager and Phase 4 readiness gate**
   - Build manager UI for already-loaded packages only.
   - Add settings editor, per-package diagnostics, trust warnings, empty/loading/error states.
   - Add optional timeline overlay only if still justified.
   - Produce Phase 4 readiness artifact: render planner extension contract, trust/sandbox decision, family promotion checklist, roadmap/ticket reconciliation.

Each milestone should produce a durable handoff artifact: validation report, persistence contract, proposal contract, diagnostics/Form/lifecycle contract, manager/readiness report.

## Locked Decisions

- Keep the existing preview scope honest: supported now means surfaces, commands, settings, loader/runtime diagnostics visibility, and command-backed proposals.
- Do not promote effects, transitions, clip types, keyframes, agent tools, live data, render materials, sidecars, or shaders during this epic.
- Fix docs/schema/runtime drift before adding new families.
- Keep `ExtensionStateRepository` synchronous for now; bridge async Supabase/IndexedDB stores through an explicit cache/store adapter.
- Use provider-owned repository factories rather than bolting many extension persistence methods directly onto `DataProvider`.
- Current schema is single-user. Extension state/settings/proposals are user-scoped by timeline ownership until project RBAC exists.
- `TimelinePatch` is an envelope over the current command/proposal engine, not a second mutation executor.
- Extensions are trusted, unsandboxed code in the preview. Manifest permissions are declarative until runtime enforcement exists.
- The manager is local installed-package management only. No marketplace, catalog, install-from-URL, dependency graph, updates, or discovery UI.
- Actual `@reigh/editor-sdk` packaging is deferred until after Phase 2 contracts settle. Phase 1 should only prove public-entrypoint extractability.

## Open Questions For The Planner

- Should browser-local enabled/settings state remain localStorage-compatible while proposal payloads move to IndexedDB, or should all browser-local extension persistence move to IndexedDB?
- Should Astrid bridge support extension persistence/proposals in this epic, or remain explicitly unsupported with diagnostics?
- Should proposals live in a command/proposal-specific repository or a generic provider repository family?
- Is timeline overlay still useful in Phase 3, or should it move after manager/settings/diagnostics hardening?
- Should trust/security docs be a standalone `docs/extensions/trust-and-security.md` or folded into authoring/compatibility docs?
- What is the minimal production-build extension smoke that avoids depending only on dev harness routes?

## Constraints

- Preserve current editor behavior when no extension packages are supplied.
- Do not loosen import-boundary checks to make examples pass.
- Do not convert the loader to promise-based unless the sync-cache-over-async-store bridge fails.
- Do not claim production readiness without provider-backed persistence and Docker-capable release validation.
- Do not claim sandboxing, iframe isolation, permission enforcement, code signing, or marketplace trust.
- Do not let provider capability flags claim support without repository factories and conformance tests.
- Do not let agent shortcuts bypass proposal policy.
- Do not let extension-authored diagnostics spoof host sources.
- Do not add inert public surfaces unless they answer a product workflow.

## Touchpoints

- `docs/extensions/reigh-extension-layer-foundation-plan.md`
- `docs/extensions/reigh-extension-layer-roadmap-v2.md`
- `docs/extensions/reigh-extension-layer-tickets.md`
- `docs/extensions/authoring.md`
- `docs/extensions/loading.md`
- `docs/extensions/compatibility.md`
- `docs/extensions/validation/*`
- `src/tools/video-editor/extension.ts`
- `src/tools/video-editor/runtime/contributionFamilies.ts`
- `src/tools/video-editor/runtime/extensionManifest.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/runtime/extensionStateRepository.ts`
- `src/tools/video-editor/runtime/diagnostics.ts`
- `src/tools/video-editor/runtime/ExtensionRenderBoundary.tsx`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/data/DataProvider.ts`
- `src/tools/video-editor/data/SupabaseDataProvider.ts`
- `src/tools/video-editor/data/AstridBridgeDataProvider.ts`
- `src/tools/video-editor/commands/*`
- `src/tools/video-editor/hooks/useTimelineCommands.ts`
- `src/tools/video-editor/hooks/useAgentSession.ts`
- `src/tools/video-editor/components/DiagnosticsPanel.tsx`
- `src/tools/video-editor/lib/renderRouter.ts`
- `supabase/migrations/*`
- `supabase/functions/ai-timeline-agent/*`
- `config/contracts/registry.json`
- `config/contracts/reigh-extension.schema.json`
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- `package.json`
- `Makefile`
- `playwright.config.ts`
- `examples/video-editor-extension/*`
- `tests/e2e/video-editor-*.spec.ts`

## Anti-Scope

- No public creative contribution families in this epic.
- No marketplace/discovery/install/update/dependency manager UI.
- No SDK package publishing until Phase 2 contracts settle.
- No broad refactor of video editor state management.
- No automatic offline conflict merge unless a contained, tested policy emerges; fail closed with diagnostics is acceptable for the first production version.
- No permission broker unless explicitly chosen as a separate follow-on; do not pretend permissions are enforced.

## Done Criteria

- Phase 1 contract truth passes: docs/schema/runtime/examples/public exports agree, manifest examples validate, unsupported collections fail closed, and production-build extension smoke passes.
- Supabase and browser-local providers only report extension persistence/proposal capabilities after conformance tests pass.
- Extension enablement, settings overrides, and pending proposals survive reload in supported providers.
- Agent `proposal_policy: 'always'` returns a persisted proposal, does not mutate immediately, and can later be accepted through the same proposal apply path.
- Extension-authored diagnostics are scoped, bounded, cleaned up on unload, and cannot spoof host-owned sources.
- SchemaForm supports the agreed primitive subset with per-field validation and accessibility requirements.
- Manager lists installed/loaded/disabled/invalid/incompatible packages, supports enable/disable/settings, shows per-package diagnostics and trust warnings, and has empty/loading/error/no-settings states.
- Phase 4 readiness artifact exists before any deeper contribution family starts.

## Megaplan Dial Recommendation

This should run as an epic chain, not a single plan.

Overall plan difficulty:

- **M1:** 4/5, `partnered-4`; public contract and release gates can create false confidence if planned badly.
- **M2:** 5/5, `partnered-5`; persistence/RLS/provider capability mistakes can pass local tests while leaking or corrupting state.
- **M3:** 5/5, `partnered-5`; proposal/agent policy touches mutation safety and could silently direct-apply.
- **M4:** 4/5, `partnered-4`; diagnostics/form/lifecycle are cross-cutting host primitives.
- **M5:** 4/5, `partnered-4`; manager UX plus Phase 4 readiness decides whether future families start safely.

Planning complexity:

- Use `thorough` for M2 and M3.
- Use `full` for M1, M4, and M5 unless critique reveals hidden architecture risk.

Depth:

- Use `high` for M2 and M3.
- Use `medium` for M1/M4/M5 unless the planner struggles; M5 may use `high` if the Phase 4 readiness gate becomes architecture-heavy.

Recommended chain invocation:

```bash
python -m arnold.pipelines.megaplan chain start \
  --project-dir /Users/peteromalley/Documents/reigh-workspace/reigh-app \
  --spec .megaplan/briefs/reigh-extension-layer-foundation/chain.yaml
```

Suggested single-step mode while this remains high-trust planning:

```bash
python -m arnold.pipelines.megaplan chain start \
  --project-dir /Users/peteromalley/Documents/reigh-workspace/reigh-app \
  --spec .megaplan/briefs/reigh-extension-layer-foundation/chain.yaml \
  --one
```

## Required Briefs

- `.megaplan/briefs/reigh-extension-layer-foundation/chain.yaml`
- `.megaplan/briefs/reigh-extension-layer-foundation/m1-preview-truth-contract-freeze.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/m2-provider-persistence-spine.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/m3-proposal-agent-policy-spine.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/m4-diagnostics-schemaform-lifecycle.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/m5-manager-phase4-readiness.md`
