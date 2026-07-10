# Frontend Split-Brain Bug Inventory - 2026-07-08

This inventory came from two DeepSeek V4 Pro swarms:

- `/tmp/vibecomfy-overlay-swarm/results/` - first preview-overlay/root-cause
  pass, 10/10 agents succeeded.
- `/tmp/vibecomfy-bug-swarm2/results/` - broader "all instances of this bug
  class" pass, 12/12 agents succeeded.

Status note: this file has been updated after the 2026-07-09 cleanup. It records
what the swarms found and which items are now resolved.

## Resolved Direct Preview Bug Cluster

The direct root cause was a split between canvas-owned preview rendering and
DOM-owned preview text chips.

### 1. Duplicate Preview Renderers

Resolved. `panel_overlay.js` is the preview overlay implementation owner. The
production shell delegates to it rather than carrying local draw-model,
text-sanitizing, and ghost-rendering copies.

### 2. DOM Preview Text Chips

Resolved. The floating/clipped old preview text path was removed:

- `syncPreviewDomOverlay`
- `ensurePreviewDomOverlayRoot`
- `appendPreviewDomChip`
- `previewChipGeometry`

Only `clearPreviewDomOverlay` remains, so older browser sessions with a stale
DOM root can be cleaned without reintroducing DOM-owned preview rendering.

### 3. Preview Lifecycle Invalidation

Resolved for the transitions that leave preview mode:

- stop/abort
- apply success
- authoritative accept rejection
- rebaseline success

Those paths now clear candidate preview state through the lifecycle invalidation
primitive. Reject failure intentionally keeps the candidate visible because the
reject did not complete.

Demo preview stage navigation also fulfills reducer obligations from
`agent_lifecycle_commit.js`; it does not hand-clear preview diff state.

### 4. Coordinate Contract Drift

Resolved by removing the duplicate renderer and keeping one canvas preview
implementation in `panel_overlay.js`.

### 5. Served-Code / Cache Risk

Still operationally relevant. Source edits require relaunching ComfyUI, and the
browser may need a hard reload if it already imported old ESM modules.

Recommended verification after web changes:

```sh
python -c "import vibecomfy.comfy_nodes as m; print(m.WEB_DIRECTORY)"
curl -fsS http://127.0.0.1:8190/extensions/vibecomfy/panel_overlay.js | rg "syncPreviewDomOverlay|overlayDrawCacheKey|resolveSlotIndex"
curl -fsS http://127.0.0.1:8190/extensions/vibecomfy/vibecomfy_roundtrip.js | rg "function renderCandidate|appendCandidateDetailImpl|renderComposerActions,"
```

## Same-Smell Clusters Outside Preview

These are not the floating preview text bug, but they are the same architectural
failure mode: an orchestration shell or compatibility mirror can contradict the
intended owner.

### Thread Detail Rendering

Mostly resolved for the concrete duplicate surfaces found by the swarms. Dead
old shell renderers `renderCandidate`, `renderFailure`, and `renderQueue` were
removed. Thread detail rendering remains owned by `panel_thread.js` and guarded
by ownership tests.

### Composer / Developer Rendering

Partially resolved. Composer action and notice dispatch now go through wrapper
functions, and `renderDeveloper` no longer overwrites its own constructed DOM.

### Runtime Diagnostic Mirrors

Resolved for thread and notice diagnostics. The canonical fields are now
`_lastThreadRender` and `_lastNoticeRender`; duplicate `last*Render` mirrors were
removed.

### Scheduler / Status / Settings Boundaries

Still broader architecture debt. Existing ownership tests cover the most
important boundaries, but status/meta display, choose-engine overlay wiring,
research contribution workflow, and settings autosave still sit close to the
shell.

### State Compatibility Mirrors

Still broader architecture debt. Transcript, execution, candidate, scope, and
replay mirrors should continue moving toward selectors or centralized mutation
helpers. The preview candidate state transitions touched by the bug are now
covered by lifecycle tests.

Transient preview diff clearing is reducer-owned. Shell/demo modules may fulfill
cleanup obligations and repaint the canvas, but do not delete `_previewDiff*`
fields directly.

## Guardrails Added

- Preview overlay ownership static tests forbid reintroducing DOM-chip preview
  rendering.
- Roundtrip ownership tests forbid dead shell renderers.
- Frontend ownership regression tests guard composer wrapper dispatch,
  diagnostic mirror canonicalization, and developer DOM preservation.
- Lifecycle tests assert preview state is cleared on preview-exit transitions.
