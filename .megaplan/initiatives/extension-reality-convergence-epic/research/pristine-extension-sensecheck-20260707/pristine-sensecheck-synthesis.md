# Pristine Extension Sense-Check Synthesis

Date: 2026-07-07

This synthesis combines three read-only Codex subagent investigations against the current codebase:

- `01-permission-model-truth.md`
- `02-composition-spine-authority.md`
- `03-export-readiness-convergence.md`

## Executive Verdict

The criticism is valid. The repo is close enough that the right work is no longer "add more features"; it is convergence work:

1. Make the trust boundary honest and machine-checked.
2. Ratchet one fact family at a time onto the composition authority spine.
3. Make export readiness flow from the planner, not parallel compatibility gates.

The important correction is that "permission enforcement" should not be treated as a small extension of the current system. The near-term pristine version is an honest trusted-code model with visible access disclosures and tests preventing false safety claims. Real permission enforcement requires isolation plus a brokered host API and belongs in a later dedicated epic if third-party or marketplace extensions are intended.

## 1. Permission Model Truth

### Current Threat

Severity: medium now, high if third-party extension loading is promoted.

The current model is mostly honest in the manager UI and docs, but structurally risky because manifest permissions look like security declarations while nothing enforces them at runtime.

Key findings:

- `src/sdk/index.ts` defines extension permission declarations as descriptive until sandboxing exists.
- `ExtensionManifest.permissions` is frozen by `defineExtension`, but not enforced.
- `extensionLoader.ts` validates manifests, install state, enablement, and integrity, but does not gate runtime behavior by permissions.
- `ExtensionContext` is capability-shaped, but extension code still runs same-thread/same-origin and is not sandboxed.
- `config/contracts/reigh-extension.schema.json` drifts from the SDK shape. It accepts a different permission object than the SDK defines.
- The manager trust warning is directionally correct: extensions are trusted, unsandboxed code.

### What Pristine Means

Near-term pristine is not partial sandboxing. It is:

- A trusted-local extension model.
- Permission-like fields renamed or reframed as non-enforcing access disclosures.
- UI that shows those disclosures under the existing trust warning.
- Contract/schema tests proving SDK, JSON schema, docs, and manager copy agree.
- A quality gate preventing docs/UI from implying runtime enforcement or third-party safety.

Later pristine, if the product wants untrusted extensions, is:

- iframe, Worker, SES-like, or process isolation.
- Message-passed SDK access.
- Brokered host APIs.
- CSP/import restrictions.
- Revocation tests for network, storage, filesystem, process, env, DOM, and host services.

### Recommended Work

Do now:

1. Fix SDK/schema permission contract drift.
2. Rename or clearly deprecate `permissions` as non-enforcing access disclosures.
3. Surface access disclosures in `ExtensionManager` beside the trusted-code warning.
4. Add tests that fail if docs/UI imply sandboxing or permission enforcement.
5. Keep marketplace/third-party language explicitly deferred.

Avoid:

- Adding a few declarative permission names and calling that enforcement.
- Blocking one or two host APIs while leaving same-origin JavaScript unrestricted.

## 2. Composition Spine Authority

### Current Threat

Severity: high as architectural drift, but not a reason to delete legacy paths immediately.

The codebase has strong planner-compatible scaffolding, but not yet a true composition authority model. Today, legacy timeline fields remain authoritative for key fact families.

Key findings:

- `TimelineSnapshot` and `TimelineReader` give provider-free planner input.
- `planRender()` already reduces requirements, blockers, output formats, routes, render groups, material refs, diagnostics, and request constraints.
- Renderability/material/artifact vocabulary exists.
- `CompositionGraph` and graph-backed fact authority do not exist yet in the checked code.
- Shader assignment, live bindings, target paths, render route facts, preview material facts, and output-format contributions are still mostly read from legacy timeline/config surfaces.

Legacy-authoritative examples:

- Shader assignment: `clip.app.shader`, `config.app.shaderPostprocess`.
- Live bindings and target params: `clip.app.liveBindings`, `clip.params.liveBindings`, `targetParamName`.
- Preview/render route inference: raw `clipType`, theme/generated-module shapes, contributed clip records.
- Export guard scanning: raw `ResolvedTimelineConfig`, then wrapping results into planner diagnostics.

### What Pristine Means

Legacy timeline fields can remain for storage and backward compatibility, but planner/export/preview readiness should consume canonical graph facts.

The target shape is:

- One projector from legacy timeline/config into composition facts.
- One validator for those facts.
- One diagnostics vocabulary.
- One planner/export path.
- Tests proving planner/export cannot pass from legacy-only facts that were not projected into the graph.

### Recommended Work

Do next:

1. Land the first authority ratchet for shader/ref facts.
2. Add a `CompositionGraph` projection for shader assignment and material/reference facts.
3. Make shader/ref planner and export blockers consume graph facts instead of direct `clip.app.shader` or `shaderPostprocess`.
4. Keep legacy shader fields only as projector inputs.
5. Add a fixture where raw legacy shader fields exist but projection is disabled; planner/export must not treat them as authoritative.
6. Add a static or test gate forbidding new shader/ref planner/export code from reading raw legacy fields.

Then:

- Ratchet target paths.
- Ratchet material/live bindings.
- Ratchet output-format contribution facts.

Avoid:

- Wrapping old scanners in graph-shaped objects while leaving the legacy scanners authoritative.
- Deleting old fields before graph projection and compatibility tests exist.

## 3. Export Readiness Convergence

### Current Threat

Severity: medium-high.

Planner blockers are intended to be the canonical readiness vocabulary, but export readiness still flows through a compatibility guard and legacy route decisions. That leaves room for the UI to say something is supported in one layer while another layer blocks it with a different reason.

Key findings:

- `renderability.ts` has a strong shared vocabulary: routes, blocker reasons, warnings, renderability diagnostics.
- `planRender()` is a real reducer and computes `canBrowserExport` and `canWorkerExport` from route blockers.
- `useRenderState.ts` says planner blockers are canonical.
- `runExportGuard()` still scans registry/timeline config separately and returns blocking diagnostics.
- `getFastRenderRouteDecision()` can produce `preview-only` decisions before the planner owns the user-facing blocker.
- `renderRouter.ts` has a separate provider route taxonomy and reason strings.
- Compile-only export uses planner output format availability but can still fail via handler registry availability outside the planner vocabulary.

### What Pristine Means

There should be one export readiness API that answers:

- requested output,
- candidate routes,
- selected route,
- blockers,
- warnings,
- next actions.

Everything should feed `planRender()` or a planner-owned readiness wrapper as data:

- registry renderability,
- missing contribution IDs,
- live bindings,
- shader materialization,
- output formats,
- process health,
- provider availability,
- generated-module artifact state,
- compile handler availability.

`ExportDiagnostic` can remain as a presentation artifact, but it should be derived from planner findings rather than acting as a separate readiness authority.

### Recommended Work

Do next:

1. Add `buildExportReadinessPlan()` near the render planner or `useRenderState` boundary.
2. Let it perform today's guard scans, but return `RenderPlannerResult` plus derived diagnostics.
3. Replace boolean-style export blocking with "get readiness plan, block on selected route blockers."
4. Move generated-module artifact failures from `getFastRenderRouteDecision()` into planner requirements/blockers.
5. Change render blocking UI to display selected-route planner blocker messages.
6. Keep lower-level route decision reasons for analytics/debug only.
7. Update stale docs and diagnostic-code references.

Tests/gates:

- Fail if user-visible render/export blocked messages do not originate from `RenderBlocker`.
- Cover missing generated-module artifact, worker unavailable, contributed clip conflicts, unknown contribution IDs, shader materializer blockers, live binding blockers, disabled/missing output formats, and missing compile-only handlers.
- Ensure every `preview-only` decision carries stable planner blockers.

Avoid:

- Deleting `exportGuard` immediately. Its scans are useful; its authority should be demoted.
- Treating compile-only `hasBlockingErrors` as the canonical planner gate without deciding post-execution semantics.

## Recommended Sequence

1. Finish the current extension-foundation completion sprint on `main`:
   - SDK/schema/docs truth,
   - quality gate truth,
   - current failing extension tests,
   - manager trust/access disclosure clarity.

2. Run a dedicated composition authority sprint:
   - implement the shader/ref fact-family ratchet,
   - introduce the graph projection,
   - prove legacy-only shader/ref facts no longer count unless projected.

3. Run an export readiness convergence sprint:
   - introduce `buildExportReadinessPlan()`,
   - route all user-facing export blockers through planner blockers,
   - demote export guard to scanner/adapter input.

4. Defer true permission enforcement until the product needs untrusted extensions:
   - isolation,
   - brokered API,
   - revocation tests,
   - third-party marketplace threat model.

## The Deep Validation Questions

Permission model:

- Can an extension do anything materially sensitive that its manifest does not disclose?
- Does any user-facing text imply sandboxing, permission enforcement, or third-party safety that the runtime does not provide?
- Does the JSON schema accept exactly the same trust/access shape the SDK documents?
- If a malicious extension is installed locally today, what concrete boundaries stop it?

Composition spine:

- For each fact family, which module is the authority?
- Can planner/export/preview pass using only legacy timeline fields after graph projection is disabled?
- Are legacy fields storage inputs, or are they still behavioral inputs?
- Is every blocker attached to a canonical graph fact, or to an incidental legacy shape?

Export readiness:

- For every disabled export button or blocked render, can we point to one planner blocker as the cause?
- Can the UI and router disagree about whether browser export, worker export, or preview-only is supported?
- Are provider availability and generated-module artifact state planner inputs, or late route surprises?
- Are compile-only export errors preflight readiness failures, execution failures, or both?

## Raw Outputs

The full Codex subagent transcripts and final answers are in:

- `.agent-work/pristine-extension-sensecheck-20260707/results/01-permission-model-truth.md`
- `.agent-work/pristine-extension-sensecheck-20260707/results/02-composition-spine-authority.md`
- `.agent-work/pristine-extension-sensecheck-20260707/results/03-export-readiness-convergence.md`
