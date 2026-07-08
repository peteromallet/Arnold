# Frontend Overlay Ownership Cleanup Plan

Date: 2026-07-08

## Goal

Eliminate the preview-overlay split brain and the broader frontend ownership drift that let it ship. Preserve the newest working behavior, but make one owner module responsible for each behavior so future fixes land in the active code path and tests exercise that same path.

## Current Active Code

The live Comfy launch serves `vibecomfy/comfy_nodes/web_dist/1eb705784ca0`, built from `vibecomfy/comfy_nodes/web`.

The currently active preview overlay path is mixed:

- `vibecomfy_roundtrip.js` imports `installAgentPreviewOverlay` from `panel_overlay.js`.
- `vibecomfy_roundtrip.js:installAgentPreviewOverlay()` passes the roundtrip-local `drawPreviewOverlay` into that owner module as a dependency.
- `panel_overlay.js:installAgentPreviewOverlay()` calls the injected `drawPreviewOverlay(ctx, diff)` and then calls `syncPreviewDomOverlay(...)`.

That means:

- Canvas drawing is currently the old `vibecomfy_roundtrip.js` implementation.
- DOM preview text chips are currently the `panel_overlay.js` implementation.
- The exported `panel_overlay.js:drawPreviewOverlay(ctx, diff, deps)` is mostly tested but not the live canvas renderer.

This explains why fixes to one file can appear not to work locally.

## Swarm Findings

Ten DeepSeek subagents audited the codebase. Reports live under `/tmp/vibecomfy-overlay-swarm/results/`.

Top findings:

1. `drawPreviewOverlay` exists in both `panel_overlay.js` and `vibecomfy_roundtrip.js`. The roundtrip copy is active; the owner-module copy is test-active but runtime-inactive.
2. Overlay draw model construction exists in both files with different cache behavior.
3. Widget preview text is drawn twice: canvas overlay plus `position: fixed` DOM chips in `#vibecomfy-preview-dom-overlay`.
4. The DOM overlay converts graph coordinates to viewport pixels, which is fragile under pan, zoom, device-pixel ratio, scroll containers, and stale canvas rects.
5. Tests validate chip existence and non-empty coordinates, but not actual landing on the widget under pan/zoom or that the runtime path equals the tested owner-module path.
6. `vibecomfy_roundtrip.js` still contains several owner-module implementations: overlay rendering, panel thread detail builders, composer/status wrappers, scheduler/status-poller helper copies, scope-resolver helper copies.
7. Static ownership tests cover some owner boundaries but miss enough symbols that split-brain implementations can survive.
8. Lifecycle cleanup is incomplete for the DOM overlay: rebaseline/reject/failure/scope-switch can leave chips until the next canvas repaint.
9. The active roundtrip overlay has useful newer behavior missing from `panel_overlay.js`, especially layout-move rendering.
10. Ghost-node geometry has drifted between implementations: one copy positions added ghosts too low, the other can double-count title height.

## Cleanup Strategy

### Phase 1: Preview Overlay Single Owner

Make `panel_overlay.js` the only preview overlay owner.

Preserve from the active roundtrip implementation:

- `layout_moved` ghost rendering.
- removed/added wire drawing behavior.
- badge and marker behavior.
- useful value-label rendering and long-text clipping.

Fix while moving:

- Remove `syncPreviewDomOverlay` from the live path. Preview value text should be rendered only on the LiteGraph foreground canvas.
- Standardize ghost geometry: node body position is `pos.y`; full visual bounds are `{ y: pos.y - TITLE_H, h: bodyHeight + TITLE_H }`. `computeGhostDimensions` must have one documented contract: either body height or full height, not both.
- Use the owner-module draw model cache consistently.

Required tests:

- Runtime import/wiring test proves roundtrip passes `panel_overlay.drawPreviewOverlay`, not a local implementation.
- Browser smoke proves no `#vibecomfy-preview-dom-overlay` chips are created during preview.
- Layout-moved preview still draws.
- Added ghost bounds include the title bar exactly once.
- Widget value overlay is drawn on canvas row bounds.

### Phase 2: Lifecycle Cleanup

Even after removing live DOM chips, keep cleanup robust:

- Candidate invalidation must clear preview diff/cache and repaint.
- Apply/reject/rebaseline/failure/scope-switch should all route through one preview-clear obligation.
- Remove dead DOM overlay cleanup if DOM overlay is deleted; otherwise make it synchronous in the lifecycle layer.

Required tests:

- Reject success clears preview immediately without graph mutation.
- Rebaseline success clears stale `_previewDiff`.
- Canvas apply failure clears candidate preview state.
- Scope switch does not leave old preview artifacts.

### Phase 3: Static Ownership Enforcement

Expand ownership tests so `vibecomfy_roundtrip.js` cannot re-own extracted code.

Required checks:

- `vibecomfy_roundtrip.js` must not export or define `drawPreviewOverlay`, `_buildOverlayDrawModel`, `safePreviewOverlayText`, or preview DOM overlay helpers.
- Every owner symbol imported as `*Impl` must have a wrapper that calls the imported implementation and does not contain owner logic.
- Add missing composer symbols: `submitReadinessState`, `syncComposerButtons`, `renderComposerNotice`, `renderComposerActions`, `renderComposerNoticeSection`, `composerApplyDisplayState`.
- Add scheduler symbols imported from `panel_scheduler.js`.
- Add status-poller projection helpers imported from `agent_status_poller.js`.
- Actually call the currently dead `assertDelegatingWrapper()` helper.

### Phase 4: Broader Owner Drift Cleanup

After overlay is clean, reduce remaining roundtrip ownership drift in priority order:

1. Panel thread detail builders (`appendCandidateDetail`, `appendFailureDetail`, `appendQueueDetail`, `createBubbleDetailSection`, `createDetails`) move into `panel_thread.js` or a small `panel_thread_details.js`.
2. Scope projection helpers in `scope_resolver.js` become the sole source; roundtrip imports them.
3. Lifecycle predicate mirrors in `agent_lifecycle_commit.js` / roundtrip get centralized.
4. Composer/status wrappers become thin, verified delegates or move fully into owner modules.

## Work Slices For Subagents

Use separate worktrees to avoid write conflicts:

1. `overlay-owner`: edit `panel_overlay.js`, `vibecomfy_roundtrip.js`, and overlay browser tests.
2. `lifecycle-clear`: edit `agent_edit_lifecycle.js`, roundtrip obligation fulfillment, and lifecycle tests.
3. `ownership-tests`: edit ownership/static tests and `frontend_ownership_map.md`.
4. `thread-owner-audit`: read-only or patch-plan for panel-thread/detail extraction after overlay is stable.

## Done Criteria

This is clean only when all are true:

- Runtime path and tested path use the same `panel_overlay.js` canvas renderer.
- No live DOM preview chips are created for widget value previews.
- `vibecomfy_roundtrip.js` no longer contains a local preview renderer or overlay draw-model builder.
- Useful active behavior from roundtrip is preserved in `panel_overlay.js` tests.
- Lifecycle transitions clear preview state deterministically.
- Static ownership tests would fail if roundtrip reintroduced owner implementations.
- Relevant browser/static tests pass.
- Comfy relaunches locally and `/vibecomfy/agent/status` is ready.
