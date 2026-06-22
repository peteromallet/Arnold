# Post-Epic Validation Walkthrough: Reigh Extension Layer

Date: 2026-06-21
Epic: `reigh-extension-layer-epic`
Workspace: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

## Purpose

This is the final validation plan for an agent to run after the extension-layer implementation epic completes. It is intentionally stricter than a normal review checklist. The agent should prove that extensibility works end to end through public surfaces, that negative cases fail safely, and that docs/examples match executable behavior.

The output should be a validation report with pass/fail status, evidence links, command output summaries, screenshots where relevant, and a short list of blocking issues.

## Validation Rules

- Use only public extension APIs unless the step explicitly says to inspect internals.
- Prefer executable evidence over narrative claims.
- Every pass must cite a test, screenshot, command output, or source reference.
- A feature with only unit coverage but no public-provider/browser coverage is not end-to-end validated.
- A positive path without a negative path is incomplete.
- If a claimed contribution family is not supported, the agent must verify it is explicitly documented as out of scope or trusted-only.

## Required Evidence Pack

Create a validation folder, for example:

`/tmp/reigh-extension-layer-validation-YYYYMMDD-HHMM/`

Capture:

- `git-status.txt`
- `git-rev-parse.txt`
- `npm-test-extension.log`
- `npm-build.log`
- `contract-checks.log`
- `import-boundary-checks.log`
- browser screenshots for visible extension UI, diagnostics, proposal review, and render blocker UI
- a final `validation-report.md`

## Step 1: Baseline And Scope Check

Commands:

```bash
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
find .megaplan/briefs/reigh-extension-layer-epic -maxdepth 2 -type f | sort
```

Pass criteria:

- Branch and commit are recorded.
- Uncommitted changes are identified and classified as expected or unexpected.
- Final implementation docs and test fixtures are present.

Fail if:

- Validation is running against the wrong branch.
- There are unexplained edits in extension-layer files.

## Step 2: Public API Contract Validation

Inspect:

- `config/contracts/registry.json`
- `config/contracts/import-allowlist.json`
- public entrypoints such as `index.ts`, `browser.ts`, `browser-provider.ts`, and extension-specific entrypoint(s)

Run the relevant contract/import checks, for example:

```bash
npm run check:video-editor-sdk-contracts
npm run check:video-editor-sdk-imports
```

Pass criteria:

- Extension public exports are frozen in the contract registry.
- Extension authors can import the required types/helpers from a public entrypoint.
- Deep imports into `src/tools/video-editor/runtime/*` are rejected or absent from fixtures.
- Existing video editor SDK exports remain compatible.

Fail if:

- Test extensions import internal runtime files.
- The contract registry omits extension APIs.
- Import-boundary checks were disabled or loosened broadly.

## Step 3: Canonical Extension Fixture Audit

Inspect canonical fixtures, expected under a path like:

- `src/tools/video-editor/testing/extensions/basic-extension/`
- `src/tools/video-editor/testing/extensions/conflicting-extension/`
- `src/tools/video-editor/testing/extensions/incompatible-extension/`
- `src/tools/video-editor/testing/extensions/render-blocked-extension/`

Pass criteria:

- `basic-extension` has a valid manifest/package.
- It contributes at least one visible UI surface, command, diagnostic, setting, and proposal-producing action.
- Negative fixtures intentionally exercise duplicate IDs, incompatible API versions, disabled state, and render blockers.
- Fixtures import only public APIs.

Fail if:

- Fixtures are just mocks that bypass loader/provider code.
- Negative fixtures do not exist.
- Fixtures are colocated in a way that allows privileged internal imports.

## Step 4: Package Manifest And Loader

Run:

```bash
npm run test -- src/tools/video-editor/extension
npm run test -- src/tools/video-editor/testing/extensions
```

Pass criteria:

- Valid manifest loads.
- Missing required fields fail validation.
- Unsupported `apiVersion` fails closed with diagnostics.
- Duplicate contribution IDs fail or are deterministically disabled with diagnostics.
- Loader output is the same shape used by the public provider runtime.

Fail if:

- Manifest validation is only snapshot-tested.
- Loader accepts malformed packages silently.
- Loader tests do not touch the runtime config consumed by the editor.

## Step 5: Runtime Injection Through Public Provider

Run the browser/provider acceptance test, for example:

```bash
npm run test -- src/tools/video-editor/__tests__/public-extension.acceptance.test.tsx
```

The test should mount the public browser/provider API with `basic-extension`.

Pass criteria:

- Extension toolbar/status/slot UI renders.
- Extension dialog opens.
- Extension inspector section appears for the intended selection.
- Extension state can disable/re-enable the contribution.
- No internal provider-only test doubles are required for the public path.

Fail if:

- The test mounts `VideoEditorRuntimeContext` directly.
- The extension appears only in unit tests, not browser/provider tests.
- Disabled extension UI remains visible.

## Step 6: Diagnostics And Failure Isolation

Exercise:

- invalid manifest
- incompatible API version
- duplicate command/keybinding
- extension render exception
- failed asset/materialization diagnostic if applicable

Pass criteria:

- Diagnostics appear in a user-visible diagnostics/status panel.
- Diagnostics include `extensionId`, stable code, severity, and source.
- A throwing extension does not blank the editor.
- The agent can capture a screenshot of diagnostics UI.

Fail if:

- Failures are visible only in console logs.
- Extension runtime exceptions crash or blank the editor.
- Diagnostics have no stable codes and cannot be asserted in tests.

## Step 7: Commands, Menus, Palette, And Keybindings

Run command contribution tests and browser acceptance.

Pass criteria:

- Extension command appears in command palette.
- Context-menu command appears only in matching context.
- Keybinding triggers the command or opens proposal review.
- Duplicate command IDs and duplicate keybindings report diagnostics.
- Reserved internal command IDs cannot be overridden by an extension.

Fail if:

- Commands are registered only by editing core command files.
- Command palette is not connected to extension command registry.
- Conflicts silently pick one command.

## Step 8: Timeline Proposal Safety

Exercise extension and agent mutations.

Pass criteria:

- Extension command can return a `TimelineProposal`.
- Preview does not mutate timeline.
- Apply mutates only with matching `baseVersion`/`expectedVersion`.
- Stale proposal rejects before mutation.
- User can reject a proposal and timeline remains unchanged.
- AI agent destructive tool path uses the same proposal/review mechanism or is explicitly documented as out of scope.

Fail if:

- Extension commands directly mutate timeline without review/version semantics.
- Proposal tests do not verify stale rejection.
- Agent path remains direct-apply while claiming proposal support.

## Step 9: Contribution Family Matrix

For each claimed family, verify public registration, runtime behavior, positive test, and negative test.

Families to check:

- surfaces
- commands
- diagnostics
- settings
- effects
- transitions
- clip types
- agent tools
- data sources/live channels
- render materials/capabilities

Pass criteria:

- Supported families have public types, loader validation, runtime registration, dispose/unregister behavior, and E2E tests.
- Unsupported families are explicitly documented as out of scope or trusted-only.

Fail if:

- A family appears in docs or manifests but has no browser/provider test.
- A family is partially hardcoded in core and marketed as third-party extensible.

## Step 10: Render Capability And Export Readiness

Run render planner tests and browser export-readiness checks.

Pass criteria:

- Planner accepts built-in content.
- Planner accepts extension content with declared export capability.
- Planner blocks preview-only extension content with actionable `RenderBlocker`.
- Export/readiness UI shows blocker details.
- Any render artifacts/materials required by extension content are represented in a manifest or explicit plan output.

Fail if:

- `renderRouter.ts` still silently guesses support without explainable findings.
- Unsupported extension content reaches export without a blocker.
- Render capability metadata exists but is unused by UI/export.

## Step 11: Provider Parity

Run provider conformance tests.

```bash
npm run test -- src/tools/video-editor/__tests__/extension-provider-parity.test.ts
```

Pass criteria:

- Supabase, Astrid bridge, browser/local, and in-memory/test providers either support extension state/settings/proposals or report unsupported capabilities explicitly.
- Version conflict behavior is consistent for proposals.
- Missing `timeline_events` is diagnosed as degraded sync, not treated identically to an empty event log.
- Asset materialization failures surface through diagnostics.

Fail if:

- Optional provider methods are guessed without capability reporting.
- Providers silently drop extension metadata.
- Supabase fallback masks sync protocol drift without a diagnostic.

## Step 12: Docs And Examples

Inspect:

- `docs/extensions/authoring.md`
- `docs/extensions/loading.md`
- `docs/extensions/compatibility.md`
- example extension directory under `examples/`

Pass criteria:

- Docs show public imports only.
- Example extension can be built/tested.
- Docs explain supported versus unsupported contribution families.
- Docs explain diagnostics and proposal safety.
- Example aligns with canonical test fixture behavior.

Fail if:

- Docs reference APIs not exported publicly.
- Example requires internal source edits.
- Docs claim shader/WebGL, sidecars, clip types, transitions, or agent tools without tests.

## Step 13: Full Gate

Run the final suite:

```bash
npm run typecheck
npm run test -- src/tools/video-editor
npm run check:video-editor-sdk-contracts
npm run check:video-editor-sdk-imports
npm run build
```

If exact script names differ, discover the project equivalents and record them in the validation report.

Pass criteria:

- Typecheck passes.
- Extension unit/integration/browser tests pass.
- Provider parity tests pass.
- Contract/import checks pass.
- Build passes.

Fail if:

- Any required extension acceptance test is skipped.
- Contract/import checks are absent and no replacement exists.
- Build passes only with extension tests disabled.

## Final Validation Report Template

Write:

`/tmp/reigh-extension-layer-validation-YYYYMMDD-HHMM/validation-report.md`

Template:

```markdown
# Reigh Extension Layer Post-Epic Validation Report

Date:
Branch:
Commit:
Validator:

## Verdict

Pass / Fail / Conditional Pass

## Commands Run

- `<command>`: pass/fail, log path

## Public API Evidence

- Contract exports:
- Import-boundary result:
- Public provider extension mount:

## E2E Evidence

- Extension UI screenshot:
- Diagnostics screenshot:
- Proposal review screenshot:
- Render blocker screenshot:

## Contribution Family Matrix

| Family | Supported? | Public API? | E2E test? | Negative test? | Verdict |
| --- | --- | --- | --- | --- | --- |

## Provider Parity

| Provider | State/settings | Proposals | Diagnostics | Verdict |
| --- | --- | --- | --- | --- |

## Blocking Issues

1.

## Non-Blocking Followups

1.

## Final Decision

The epic is / is not ready to call complete because:
```

## Absolute Completion Bar

The epic passes validation only if a fresh agent can:

1. Read docs.
2. Find public extension APIs.
3. Inspect a real extension package.
4. Run tests proving it loads through public provider/browser APIs.
5. See extension UI in a browser test.
6. Trigger an extension command.
7. Review and apply or reject a timeline proposal.
8. See extension diagnostics for a bad fixture.
9. Confirm disabled/incompatible/conflicting extensions fail safely.
10. Confirm provider parity behavior.
11. Confirm render/export readiness for extension content.
12. Confirm contract/import/build gates pass.

Anything less is partial implementation, not complete extensibility.
