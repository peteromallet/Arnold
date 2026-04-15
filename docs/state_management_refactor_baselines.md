# State Management Refactor - Baseline Render Counts

Captured on 2026-04-15 via `useRenderBudget` telemetry on commit `1b8a5a6a192f929d96f95ec761f9f58ca8f96669`. Cold-load + interaction numbers added 2026-04-15 from a real local dev session (Vite at `localhost:2222`, branch `megaplan/m0-render-telemetry`).

## Aggregation semantics (locked)

For all measurements in this document, telemetry is interpreted exactly as:

- Per component name, aggregate active mounted instances by taking the `max` per-mount render count seen within the active 1s interaction window.
- Budget status is `over` only when `maxCount > budget`.
- The 1s window resets after 1s idle (no renders), and a new interaction window starts on the next render.

This `max` aggregation contract is fixed for future milestone comparisons.

## Per-component baselines

`N/C` means not yet captured. `-` means not applicable to that interaction.

| Component | Mount | Lightbox open (image) | Final-video open (video-travel) | Clip select | Pane toggle |
|---|---|---|---|---|---|
| ImageLightbox | - | 1 | - | - | - |
| EditModePanel | - | 1 | - | - | - |
| LightboxShell | - | 1 | **31 (OVER, budget 5)** | - | - |
| TimelineCanvas | - | - | - | N/C | - |
| SortableRow (TrackListRenderer) | - | - | - | N/C | - |
| PreviewPanel | - | - | - | N/C | - |
| MediaGalleryItem (per item, 48 mounts) | 1 | 1 | - | - | N/C |
| TasksPane | 0 | 0 | 0 | - | 0* |
| ShotsPanelContent | 0 | 0 | 0 | - | 0 |
| GenerationsPaneGallery | 1 | 1 | 1 | - | 1 |

\* TasksPane pane-toggle showed 0 because the 1s idle window had reset by the time the overlay was read; the underlying mount count is captured during cold load.

## Interaction sequences

### Cold load — image generation page
- `MediaGalleryItem`: 1 render across 48 mounts (the gallery enumerated 48 items; each mount rendered once).
- `GenerationsPaneGallery`, `TasksPane`, `ShotsPanelContent`: bootstrap renders within budget.

### Open image lightbox (image generation page)
- `ImageLightbox`, `EditModePanel`, `LightboxShell`: each rendered exactly 1× on open. Comfortably under budget.
- Sibling components (`MediaGalleryItem`, `GenerationsPaneGallery`, `TasksPane`, `ShotsPanelContent`) unchanged.

### Open final video (video-travel tool page) — **OVER-BUDGET FINDING**
- `LightboxShell` rendered **31×** (budget 5) → status `OVER`, ~6× the configured budget.
- Same component renders cleanly (1×) when opening the image lightbox on the image-generation page.
- Indicates the render storm is specific to the video-travel tool's lightbox flow, not the lightbox shell itself.
- This is exactly the kind of asymmetry M0 was designed to surface, and gives M1a + M2 a concrete, falsifiable target: **`LightboxShell` on video-travel final-video open must drop from 31 → ≤ 5 (≥ 84% reduction)**.

### Open Tasks pane
- `TasksPane` overlay reading captured 0 renders due to the 1s idle reset; underlying mount count captured on cold load (1 mount, 0 active renders in the post-mount window).
- Other panes (`ShotsPanelContent`, `GenerationsPaneGallery`) unchanged at 0 / 1 respectively.

### Selecting a timeline clip — NOT YET CAPTURED
- `TimelineCanvas`, `SortableRow`, `PreviewPanel`: pending a real-session capture from the video editor. Required before M1c gates can be meaningfully evaluated.

## Observations and constraints

- The cold-load + lightbox + pane numbers came from a real local dev session, not stub data.
- The 31-render `LightboxShell` storm on video-travel is the headline finding.
- The instrumented budgets (`useRenderBudget` defaults from M0 spec) all hold for the captured components except `LightboxShell` in the video-travel flow.
- TasksPane's 0 reading is a measurement-timing artifact, not a hook bug — re-capture by reading the overlay within 1s of pane toggle.
- Timeline clip-select baselines remain to be captured; without them, M1c's "≤ 2 renders per scroll" and "0 renders for non-dragged rows" gates have no comparison point.
