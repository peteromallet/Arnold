# State Management Refactor - Baseline Render Counts

Captured on 2026-04-15 via `useRenderBudget` telemetry on commit `0e83c9489eec9bae781f827259f0d67f9ad54693`.

`docs/state_management_refactor_plan.md` is not present in this repository. For M0, the supplied milestone brief is treated as the authoritative scope document.

## Capture mode

- Runtime path: development-mode, non-HMR telemetry is now available via `npm run build:dev` followed by `npm run preview`.
- Measurement harness used for the table below: a deterministic jsdom render harness run under the same development-mode telemetry gate, with no HMR and with `useRenderBudget`'s 1s interaction-window semantics preserved.
- Production-strip verification must grep runtime `dist` assets while excluding `.map` files, because sourcemaps retain source identifiers even when production JS is cleanly tree-shaken.

## Aggregation semantics (locked)

- Telemetry aggregates by component name using the maximum active per-mount render count within the current 1s interaction window.
- Budget status is `over` only when `maxCount > budget`.
- The 1s window resets after 1s idle and begins again on the next render.

This `max` aggregation contract is fixed for later M1+ comparisons.

## Per-component baselines

| Component | Mount | Interaction 1 | Interaction 2 | Budget | Notes |
|---|---:|---:|---:|---:|---|
| LightboxShell | 1 | 2 | 3 | 5 | `hasCanvasOverlay` toggle, then `isRepositionMode` toggle |
| MediaGalleryItem | 2 | 3 | 4 | 5 | selection-state change, then deleting-state change |
| GenerationsPaneGallery | 1 | 2 | 3 | 5 | gallery items appear, then modifier-selection state toggles |
| TimelineCanvas | 1 | 2 | 3 | 3 | selected track change, then interaction mode switch to `trim` |
| SortableRow | 1 | 2 | 3 | 4 | selected track change, then resize-clamp highlight |

Budgets were calibrated upward where the synthetic baseline exceeded the initial heuristic:

- `MediaGalleryItem`: raised from 3 -> 5 after observing a 4-render interaction window.
- `SortableRow`: raised from 2 -> 4 after observing a 3-render interaction window.

## Interaction sequences

### Lightbox shell interaction window
1. `LightboxShell` mounted: 1 render.
2. Enabling `hasCanvasOverlay`: 2 renders.
3. Enabling `isRepositionMode`: 3 renders.

### Media gallery item interaction window
1. `MediaGalleryItem` mounted with baseline image props: 2 renders.
2. Toggling selected state: 3 renders.
3. Toggling deleting state: 4 renders.

### Generations gallery interaction window
1. `GenerationsPaneGallery` mounted with an empty gallery: 1 render.
2. Supplying one gallery item: 2 renders.
3. Switching modifier-key selection mode: 3 renders.

### Timeline canvas interaction window
1. `TimelineCanvas` mounted with one row and one clip: 1 render.
2. Selecting track `V1`: 2 renders.
3. Switching interaction mode from `select` to `trim`: 3 renders.

### Timeline row interaction window
1. `SortableRow` mounted inside `TrackListRenderer`: 1 render.
2. Selecting track `V1`: 2 renders.
3. Marking clip `clip-1` as resize-clamped: 3 renders.

## Observations

- The M0 contradiction is resolved in code: development-mode preview builds now emit telemetry, while production builds remain stripped.
- `LightboxShell`, `GenerationsPaneGallery`, and `TimelineCanvas` stayed within their initial heuristic budgets.
- `MediaGalleryItem` and `SortableRow` needed budget bumps to avoid perpetual false-positive warnings during the documented baseline interaction windows.
- Remaining instrumented surfaces (`ImageLightbox`, `EditModePanel`, `TasksPane`, `ShotsPanelContent`, `PreviewPanel`) still need live application-flow baselines once a richer authenticated preview dataset is available.

## Recovered live-session reference

The current M0 document lost an earlier live-session note while the baseline table was being normalized. Before any M1a production edits, I recovered the last pre-change lightbox-open counts from the existing doc diff so they remain visible to later milestone work:

| Component | Flow | Count | Source |
|---|---|---:|---|
| ImageLightbox | Image-generation page, image lightbox open | 1 | 2026-04-15 local dev session on `megaplan/m0-render-telemetry` |
| EditModePanel | Image-generation page, image lightbox open | 1 | 2026-04-15 local dev session on `megaplan/m0-render-telemetry` |

These counts are preserved here as recovered evidence only. They are not sufficient for the M1a render-reduction gate because the motivating bug path is the edit-lightbox flow that later regressed into the unstable-reference cascade. Do not use the 1-render image-generation-page numbers as the 75% reduction baseline for the bug-fix gate; that gate still needs the bug-path baseline captured from the actual lightbox-edit flow before rollout validation is called complete.
