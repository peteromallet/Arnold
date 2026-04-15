# State Management Refactor - Baseline Render Counts

Captured on 2026-04-15 via `useRenderBudget` telemetry on commit `1b8a5a6a192f929d96f95ec761f9f58ca8f96669`.

## Aggregation semantics (locked)

For all measurements in this document, telemetry is interpreted exactly as:

- Per component name, aggregate active mounted instances by taking the `max` per-mount render count seen within the active 1s interaction window.
- Budget status is `over` only when `maxCount > budget`.
- The 1s window resets after 1s idle (no renders), and a new interaction window starts on the next render.

This `max` aggregation contract is fixed for future milestone comparisons.

## Per-component baselines

`N/C` means not captured in the available runtime session.

| Component | Mount | Lightbox open | Clip select | Pane toggle |
|---|---|---|---|---|
| ImageLightbox | N/C | N/C | - | - |
| EditModePanel | N/C | N/C | - | - |
| LightboxShell | N/C | N/C | - | - |
| TimelineCanvas | N/C | - | N/C | - |
| SortableRow (TrackListRenderer row surface) | N/C | - | N/C | - |
| MediaGalleryItem | N/C | - | - | N/C |
| TasksPane | 3 (max active count observed) | - | - | 3 (max active count observed) |
| ShotsPanelContent | 0 (max active count observed) | - | - | 0 (max active count observed) |
| GenerationsPaneGallery | 0 (max active count observed) | - | - | 0 (max active count observed) |
| PreviewPanel | N/C | - | N/C | - |

## Interaction sequences

### Session bootstrap + pane visibility interactions (captured)
1. App/tool route bootstrap: `TasksPane` reached max active count `3`; `ShotsPanelContent` and `GenerationsPaneGallery` remained at `0` in the sampled window.
2. Pane visibility toggles in the same session: `TasksPane` remained bounded with observed max `3` (budget `5`).
3. Additional idle/resume window sampling: no over-budget transition observed for captured components.

### Opening image lightbox in video editor (blocked)
1. `ImageLightbox`, `EditModePanel`, and `LightboxShell` did not mount under available stub-backed runtime data.
2. No comparable counts were recorded.

### Selecting a timeline clip (blocked)
1. `TimelineCanvas`, `SortableRow`, and `PreviewPanel` did not mount under available stub-backed runtime data.
2. No comparable counts were recorded.

## Observations and constraints

- Budgets did not require upward calibration from the observed session data (`TasksPane` max `3` remained under budget `5`; no observed over-budget warnings).
- Coverage target of at least 5 components x 3 interactions each was not met in this run due to mount/access constraints in the available local stub-backed environment.
- `build:dev + preview` was not usable for telemetry capture because DEV-gated instrumentation is stripped when `import.meta.env.DEV` is false in previewed built artifacts.
- This document is therefore a partial baseline and should be rerun in an environment that can mount all required surfaces without HMR noise.
