# M3: Export Readiness Convergence

## Outcome

Make export readiness planner-owned. Guard scans, generated-module artifact checks, provider availability, compile-handler availability, contribution conflicts, shader/material blockers, live-binding blockers, and output-format availability should feed one readiness plan and one user-facing blocker vocabulary.

## Execution Posture

Do not delete useful scans just because they are legacy-shaped. Demote them into inputs. The user-facing decision must come from planner blockers.

## Scope

IN:
- Add a `buildExportReadinessPlan()` or equivalent planner-owned readiness API.
- Adapt existing export guard scans into planner input data rather than separate blocking authority.
- Move generated-module missing artifact failures into planner requirements/blockers.
- Represent provider availability and route/provider mismatch as planner readiness facts.
- Route user-facing export/render blocked messages through selected-route planner blockers.
- Keep lower-level route decision reasons available for debug/analytics only.
- Update stale export diagnostics docs and test fixtures.

OUT:
- Full removal of export guard scanner code unless it becomes provably dead after adaptation.
- Full worker/process/sidecar runtime redesign.
- New output-format product capabilities beyond readiness convergence.

## Constraints

- Do not introduce a second readiness API that disagrees with `planRender()`.
- Do not leave UI disabled states or blocking messages sourced from provider route strings when planner blockers exist.
- Do not hide post-execution failures as preflight readiness unless the code explicitly classifies them that way.
- Preserve current successful browser/worker export behavior.

## Done Criteria

- Every user-facing blocked render/export state can point to a `RenderBlocker` or planner-owned blocker object.
- `runExportGuard()` is either renamed/demoted to a scanner/adapter or its output is consumed only through the planner readiness layer.
- Generated-module missing artifact, worker unavailable, contributed clip conflict, unknown contribution IDs, shader/material blockers, live-binding blockers, disabled output format, missing output format, and missing compile handler have planner-owned tests.
- `renderRouter` route decisions carry planner blocker context for preview-only or blocked outcomes.
- Docs reflect the canonical blocker codes and remove stale parallel code lists.

## Touchpoints

- `src/tools/video-editor/rendering/renderPlanner.ts`
- `src/tools/video-editor/rendering/renderability.ts`
- `src/tools/video-editor/rendering/exportGuard.ts`
- `src/tools/video-editor/hooks/useRenderState.ts`
- `src/tools/video-editor/lib/renderRouter.ts`
- `src/tools/video-editor/**/__tests__/**`
- `docs/extensions/**`

