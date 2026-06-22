# Megaplan Prep: Reigh Extension Layer Completion

Date: 2026-06-21
Workspace: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`
Epic: `reigh-extension-layer-epic`

## Outcome

Implement the video editor extension layer as a real public platform and prove it end to end. A developer should be able to author an extension package outside the video editor core, load it through public browser/provider APIs, contribute UI/commands/proposals/diagnostics/settings/render metadata, and have automated tests prove those contributions work without deep imports or source-tree edits.

## Scope Sizing

This is larger than one sprint-sized megaplan. It should run as an epic chain of multiple sprint-sized plans, not as one giant plan.

Recommended chain:

1. **Runtime spine and public contracts**
   - Public extension entrypoint.
   - Provider/browser injection.
   - Contract registry/import-boundary updates.
   - Minimal extension fixture rendering through public API.
2. **Manifest, loader, state, settings**
   - `reigh-extension.json` schema.
   - `ExtensionLoader`.
   - `ExtensionStateRepository`.
   - Enable/disable/settings persistence.
3. **Diagnostics and failure isolation**
   - Public diagnostic contract.
   - Unified diagnostic stream.
   - Diagnostics/status drawer.
   - Bad extension fallback behavior.
4. **Timeline proposals and extension commands**
   - `TimelinePatch`/`TimelineProposal`.
   - Proposal review/apply UX.
   - Extension command/keybinding/menu contribution surface.
5. **Contribution families**
   - Normalize explicit support for surfaces, commands, diagnostics, effects, transitions, clip types, agent tools, data sources.
   - For unsupported families, remove epic claims or document trusted-only scope.
6. **Render planner and provider parity**
   - `RenderCapability`, findings, blockers, artifacts.
   - Provider capability detection and conformance tests.
   - Supabase/Astrid/browser/test provider parity.
7. **Docs, examples, release gates, and post-epic validation**
   - Public authoring/loading/compatibility docs.
   - Basic extension example.
   - Full acceptance gate.
   - Run the post-epic validation walkthrough.

Each sprint should produce a durable handoff artifact that the next sprint can cite: public API surface, schema, fixture package, diagnostics contract, proposal contract, contribution family matrix, render planner contract, or final validation report.

## Locked Decisions

- Public extensibility must be exercised through public SDK entrypoints, not `runtime/*` deep imports.
- Existing `extensionSurface.ts` slot/dialog/panel work should be treated as a starting point, not discarded.
- Extension support must be provider-scoped and deterministic.
- Invalid extension state must produce diagnostics and fail closed.
- Agent/editor mutations from extensions should go through proposal/review semantics where they can affect timeline state.
- Tests must include both positive and negative extensibility cases.
- Any contribution family that cannot be implemented and tested should be explicitly declared out of scope instead of implied.

## Open Questions For The Planner

- Are shader/WebGL and local sidecar/process support truly required for this epic, or should they be removed from acceptance criteria?
- Should third-party clip types be public now, or should clip types remain trusted-only while other families become public?
- Which provider should own extension package/settings persistence first: Supabase, browser/local, or a small provider-agnostic state repository with adapters?
- How much package manager UI is required now versus contract/loader/state only?
- Should AI agent tools be extension-contributed in this epic, or deferred until proposal review is fully stable?

## Constraints

- Do not break existing video editor public SDK contracts.
- Do not require extension authors to import internal `src/tools/video-editor/runtime/*` paths.
- Do not make package loading execute arbitrary untrusted code without an explicit trust boundary.
- Keep disabled/incompatible extensions inert.
- Keep existing editor behavior unchanged when no extensions are provided.
- Preserve existing tests for Supabase/Astrid/browser providers.
- Use existing design patterns where possible: contract registry, import-boundary checks, provider tests, browser acceptance tests, and existing command/mutation infrastructure.

## Touchpoints

- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/useVideoEditorRenderContext.ts`
- `src/tools/video-editor/contexts/VideoEditorProvider.tsx`
- `src/tools/video-editor/contexts/EditorRuntimeProvider.tsx`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/browser.ts`
- `src/tools/video-editor/browser-provider.ts`
- `src/tools/video-editor/index.ts`
- `config/contracts/registry.json`
- `config/contracts/import-allowlist.json`
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- `src/tools/video-editor/commands/*`
- `src/tools/video-editor/lib/timeline-mutation-engine.ts`
- `src/tools/video-editor/hooks/useTimelineCommands.ts`
- `src/tools/video-editor/data/*`
- `src/tools/video-editor/lib/renderRouter.ts`
- `src/tools/video-editor/effects/*`
- `src/tools/video-editor/clip-types/*`
- `src/tools/video-editor/components/*`
- `supabase/functions/ai-timeline-agent/*`
- `docs/`
- `examples/`
- extension test fixtures under `src/tools/video-editor/testing/extensions/`

## Anti-Scope

- Do not build marketplace/discovery UI before package schema, loader, state, and tests are stable.
- Do not implement shader/WebGL or process sidecars unless the planner explicitly keeps them in scope with tests.
- Do not refactor unrelated video editor state management while adding extension contracts.
- Do not loosen import-boundary checks to make tests pass.
- Do not let tests mount internal providers if the feature is meant for embedders.
- Do not treat docs/examples as substitutes for executable acceptance tests.

## Done Criteria

- Public provider/browser API accepts extension packages or extension configs.
- A canonical test extension loads without internal imports.
- The test extension contributes visible UI, a command, a timeline proposal, a diagnostic, settings, and render metadata where in scope.
- Invalid, disabled, conflicting, and incompatible extensions produce expected negative outcomes.
- Public contracts and import boundaries are updated.
- Provider parity tests cover extension state and proposal behavior.
- Browser acceptance tests prove the full path.
- Post-epic validation walkthrough passes and produces a validation report.

## Megaplan Dial Recommendation

Overall plan difficulty: **5/5; selected profile: `partnered-5`; because this work changes public contracts, provider initialization, package/loading topology, mutation safety, and release gates in ways that could pass local tests while damaging downstream extensibility.**

Planning complexity: **`thorough` for the first two sprints**, then reassess.

- Runtime/public contract and manifest/loader/state are architectural foundation sprints; a bad plan here contaminates all later work.
- Later contribution-family and docs/test-gate sprints may drop to `full` if the contracts are stable and the work becomes mostly mechanical.

Depth: **`high` for the first sprint planner**, then reassess.

- The first sprint needs structural reasoning across public exports, providers, runtime context, import governance, and tests.
- Critique/review can stay default/adaptive unless the plan struggles.

Recommended shorthand:

`partnered-5/thorough/high +prep`

Recommended prep direction:

```text
Focus on the public extension runtime spine first: provider/browser injection, public exports, contract registry/import allowlist, and a minimal fixture extension acceptance test. Treat package manager UI, shader/WebGL, and sidecars as explicit scope decisions, not assumed work.
```

Suggested chain invocation shape:

```bash
python -m arnold.pipelines.megaplan chain start \
  --project-dir /Users/peteromalley/Documents/reigh-workspace/reigh-app \
  .megaplan/briefs/reigh-extension-layer-completion/chain.yaml
```

If running a single first sprint before creating the full chain:

```bash
python -m arnold.pipelines.megaplan init \
  --project-dir /Users/peteromalley/Documents/reigh-workspace/reigh-app \
  --profile partnered-5 \
  --robustness thorough \
  --depth high \
  --with-prep \
  --prep-direction "Focus on the public extension runtime spine first: provider/browser injection, public exports, contract registry/import allowlist, and a minimal fixture extension acceptance test. Treat package manager UI, shader/WebGL, and sidecars as explicit scope decisions, not assumed work." \
  .megaplan/briefs/reigh-extension-layer-completion/runtime-spine.md
```

## Required Briefs To Create Before Init

- `.megaplan/briefs/reigh-extension-layer-completion/chain.yaml`
- `.megaplan/briefs/reigh-extension-layer-completion/m1-runtime-spine.md`
- `.megaplan/briefs/reigh-extension-layer-completion/m2-manifest-loader-state.md`
- `.megaplan/briefs/reigh-extension-layer-completion/m3-diagnostics.md`
- `.megaplan/briefs/reigh-extension-layer-completion/m4-proposals-commands.md`
- `.megaplan/briefs/reigh-extension-layer-completion/m5-contribution-families.md`
- `.megaplan/briefs/reigh-extension-layer-completion/m6-render-provider-parity.md`
- `.megaplan/briefs/reigh-extension-layer-completion/m7-docs-release-validation.md`

Use `implementation-and-e2e-test-plan.md` and `post-epic-validation-walkthrough.md` as source material for the milestone done criteria.
