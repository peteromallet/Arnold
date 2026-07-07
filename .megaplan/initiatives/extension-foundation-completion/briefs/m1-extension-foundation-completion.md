# Extension Foundation Completion

## Prep Sizing

Overall plan difficulty: **5/5**; selected profile: **partnered-5**; because a bad plan could make public SDK/release gates pass while still lying about extension safety, proposal mutation behavior, or supported/deferred platform contracts.

Planning complexity: **thorough**; because the work crosses public SDK governance, release scripts, frontend proposal flow, browser/runtime behavior, and docs source-of-truth claims.

Depth: **high**; because the planner must reason across the previous M1-M5 foundation artifacts, current dirty branch state, quality scripts, and runtime/editor surfaces.

Recommended run: `partnered-5/thorough/high @codex`.

## Outcome

Finish the last extension-foundation completion work identified by the independent validation pass on 2026-07-07. The final result should make the foundation epic claim true from a clean checkout: contract/release gates pass, production smoke is real, proposal-mode agent results are user-reviewable, manager enable/disable and settings behavior are validated, and docs distinguish completed foundation work from staged composition-spine work.

## Starting Evidence

Read these before planning:

- `.agent-work/epic-validation-20260707/holistic-validation-report.md`
- `.agent-work/epic-validation-20260707/deepseek-results/m1-preview-truth-contract-freeze.txt`
- `.agent-work/epic-validation-20260707/deepseek-results/m3-proposal-agent-policy-spine.txt`
- `.agent-work/epic-validation-20260707/deepseek-results/m5-manager-phase4-readiness.txt`
- `.agent-work/epic-validation-20260707/codex-end-state.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/chain.yaml`
- `.megaplan/briefs/reigh-extension-layer-foundation/m1-preview-truth-contract-freeze.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/m3-proposal-agent-policy-spine.md`
- `.megaplan/briefs/reigh-extension-layer-foundation/m5-manager-phase4-readiness.md`

Validation summary to treat as input, not gospel:

- M1 is **FAIL**: `npm run test:extensions` fails, release drift fails, production smoke is dead code, SDK packagability smoke fails, and contract governance has unregistered exports.
- M3 is **PASS WITH CAVEATS**: proposal infrastructure exists, but edge-returned proposals may not be imported into `ProposalRuntime`, so agent proposals may be invisible.
- M5 is **PASS WITH CAVEATS**: manager exists and is well tested, but settings uses inline key-value controls instead of M4 `SchemaForm`, changed-file evidence is incomplete, and no browser/integrated smoke proves contribution disappearance/reappearance after disable.

## Scope

In:

- Make M1 release readiness truthful and green:
  - `npm run test:extensions` passes from a clean checkout.
  - `scripts/quality/check-extension-drift.mjs --release` no longer fails on an unresolved advisory unless that advisory is explicitly reclassified in source-controlled policy.
  - `config/contracts/registry.json` matches intentional public exports from `src/sdk/index.ts`.
  - `src/sdk/smoke/extensionSmoke.ts` is wired into production app/runtime behavior so `?extensionSmoke=1` actually registers and renders a stable extension contribution.
  - SDK packagability smoke is fixed if feasible; if not feasible within this sprint, turn it into an explicit documented deferred gate that does not let the foundation claim overstate publishability.
- Complete the M3 proposal last mile:
  - Import edge-returned proposal envelopes into frontend proposal runtime using the existing `importProposal` / `importEdgeProposals` path or a narrowly equivalent integration.
  - Prove `proposal_policy: 'always'` does not mutate immediately, returns/imports a proposal, makes it visible to the user-facing proposal UI/runtime, and applies/rejects through the existing proposal apply semantics.
- Complete the M5 manager caveats:
  - Replace manager settings editing with the M4 `SchemaForm` path where appropriate, or explicitly document/test why the manager intentionally uses a narrower key-value/raw-JSON editor.
  - Add at least one browser-level or equivalent integrated smoke test proving enable/disable -> persistence write -> runtime re-resolution -> contribution disappearance/reappearance without page refresh.
- Reconcile docs/source-of-truth claims:
  - Update stale supported/deferred docs that contradict foundation M5.
  - Resolve or replace references to missing/stale `contributionFamilies.ts`.
  - Clearly label composition-spine capabilities as planned/staged, not completed.
- Keep changes scoped to the extension foundation completion work and the minimum supporting tests/docs.

Out:

- Do not implement composition-spine graph authority, target paths, material statuses, deterministic capture, process runtime, or output-format sidecars.
- Do not add marketplace/discovery/install/update/delete flows.
- Do not add sandboxing, runtime permission enforcement, code signing, or remote/untrusted process execution.
- Do not refactor the broader video editor architecture unless directly necessary to close a listed gate.
- Do not weaken tests or release gates just to make them pass.

## Locked Decisions

- The foundation epic is not complete until M1 release gates pass.
- Extension code remains trusted and unsandboxed; manifest permissions are declarative only.
- `@reigh/editor-sdk` publishability may be deferred only if docs and gates make that explicit. The preview can be extractable without being fully publishable, but the repo must not claim more than it proves.
- Proposal mode must be user-reviewable. Returning a proposal from the edge is insufficient if it never enters frontend proposal runtime.
- The Extension Manager is local loaded-package/package-state management only.
- Composition-spine work remains future planning material in this sprint.

## Open Questions For The Planner

- Is SDK packagability intended to be a required foundation gate now, or should this sprint explicitly reclassify it as post-foundation package-publishing work while keeping import-boundary tests strong?
- Where is the least invasive production hook for `?extensionSmoke=1` so it exercises real runtime loading without becoming a dev-only harness?
- What is the smallest reliable test for edge proposal import into frontend runtime: unit around `useAgentSession`, integration around `ProposalRuntime`, or component flow with a fake agent response?
- Should manager settings reuse the full `SchemaForm` component directly, or should the manager expose a read/edit wrapper around the same schema adapter/validation primitives while preserving simpler UI?
- Which docs are the release source of truth: `docs/video-editor/extension-platform-supported-deferred.md`, `docs/extensions/compatibility.md`, `docs/extensions/phase4-readiness.md`, or a new reconciliation file?

## Constraints

- Preserve existing editor behavior when no extension packages are supplied.
- Do not undo unrelated dirty local changes; work with the branch state supplied to the cloud checkout.
- Keep public SDK export changes intentional and contract-registered.
- Do not allow proposal-mode responses to imply mutation when none occurred.
- Do not persist malformed or schema-invalid settings snapshots.
- Avoid broad styling/layout redesigns; this is foundation completion, not a UI redesign sprint.
- Any docs claim must be backed by code/tests in the same checkout.

## Done Criteria

- `npm run test:extensions` passes.
- Contract governance/public export checks pass.
- Extension drift release mode passes or has an explicit, source-controlled, reviewed deferral that does not block `test:extensions`.
- Production smoke for `?extensionSmoke=1` is wired into app/runtime and tested.
- SDK packagability smoke either passes or is honestly moved out of foundation completion with docs/gate semantics updated.
- Proposal-mode agent response path imports returned proposals into frontend proposal runtime and has tests for visible pending proposal plus accept/reject behavior.
- Timeline config does not mutate immediately in proposal mode.
- Manager enable/disable has integrated/browser-level proof of re-resolution and contribution disappearance/reappearance without page refresh.
- Manager settings behavior is aligned with M4 SchemaForm primitives or explicitly documented/test-covered as narrower.
- Stale supported/deferred docs are reconciled with current foundation state.
- Composition-spine work is documented as staged/planned rather than completed.
- `npm run build` passes.
- Any remaining failures are documented as unrelated pre-existing baseline failures with evidence.

## Touchpoints

- `package.json`
- `Makefile`
- `config/contracts/registry.json`
- `config/contracts/reigh-extension.schema.json`
- `scripts/quality/check-extension-drift.mjs`
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- `scripts/quality/check-sdk-public-exports.mjs`
- `src/sdk/index.ts`
- `src/sdk/smoke/extensionSmoke.ts`
- SDK boundary/governance/example tests under `src/sdk/**`
- `src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx`
- `src/tools/video-editor/runtime/useExtensionLoaderWiring.ts`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/lib/proposal-runtime.ts`
- `src/tools/video-editor/hooks/useAgentSession.ts`
- proposal UI/runtime tests under `src/tools/video-editor/**`
- `src/tools/video-editor/components/ExtensionManager/**`
- `src/tools/video-editor/components/SchemaForm/**`
- `src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx`
- `playwright.config.ts`
- `tests/e2e/**`
- `docs/video-editor/extension-platform-supported-deferred.md`
- `docs/extensions/compatibility.md`
- `docs/extensions/phase4-readiness.md`
- `docs/extensions/authoring.md`
- `docs/extensions/loading.md`

## Anti-Scope

- No composition-spine implementation.
- No sidecar/process execution expansion.
- No marketplace or extension discovery UI.
- No sandbox/security enforcement implementation.
- No sweeping refactor of timeline state management.
- No claim of full SDK package publishing unless packagability and docs prove it.

