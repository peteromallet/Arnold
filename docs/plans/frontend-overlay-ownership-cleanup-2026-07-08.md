# Frontend Overlay Ownership Cleanup Record

Date: 2026-07-08

Status updated: 2026-07-09

## Goal

Eliminate the preview-overlay split brain and the broader frontend ownership
drift that let it ship. Preserve the newest working behavior, but make one owner
module responsible for each behavior so future fixes land in the active code
path and tests exercise that same path.

## Original Root Cause

The preview overlay path was mixed:

- `vibecomfy_roundtrip.js` still carried preview drawing/model logic.
- `panel_overlay.js` also carried preview drawing/model logic.
- A DOM-chip path created fixed-position preview text over the canvas, separate
  from the canvas renderer.

That split let stale preview text survive independently of the actual preview
state, especially after lifecycle transitions that left preview mode without a
clean repaint.

## Resolved Cleanup

### Preview Overlay Single Owner

Resolved. `panel_overlay.js` owns the preview overlay implementation, including
canvas preview text, ghost dimensions, draw-model cache keys, and port/node
fallback logic.

Removed from the runtime path:

- roundtrip-local preview renderer/model copies
- DOM preview chip creation
- vestigial install-time preview draw snapshots

Kept from recent useful work:

- layout and wire preview behavior
- full-row value overlays and bounded long-text handling
- stronger slot/port resolution
- candidate-preferred endpoint lookup for added wires

### Lifecycle Cleanup

Resolved for the preview-exit transitions that caused stale artifacts:

- stop/abort
- apply success
- authoritative accept rejection
- rebaseline success

Those transitions now clear candidate preview state through the lifecycle
invalidation primitive. Reject failure intentionally preserves preview state
because the candidate remains reviewable.

Demo preview picker stage navigation now uses the same lifecycle obligation
contract as production: commit helpers mutate reducer state, and the picker asks
the shell-provided fulfiller to perform cleanup side effects.

### Static Ownership Enforcement

Resolved for the direct bug surfaces. Ownership/static tests now prevent
reintroducing:

- DOM preview chip helpers
- dead shell thread renderers
- duplicate thread/notice diagnostic mirrors
- composer notice/action inline dispatch bypasses
- developer DOM text overwrites

### Broader Owner Drift

Partially resolved. The concrete thread detail renderers found by the swarm
(`renderCandidate`, `renderFailure`, `renderQueue`) were removed. Some larger
shell-adjacent responsibilities remain as future cleanup:

- status/meta display
- choose-engine overlay wiring
- research contribution workflow
- settings autosave coordination
- compatibility state mirrors outside the preview lifecycle

## Verification

Focused checks run after cleanup:

```sh
node --test tests/browser/preview_overlay_ownership_static.test.mjs tests/browser/ownership_contract.test.mjs tests/browser/frontend_ownership_regression.test.mjs tests/browser/agent_edit_lifecycle.test.mjs tests/browser/panel_thread_rating.test.mjs tests/browser/roundtrip_smoke.test.mjs
```

The suite passed with 446 tests.

## Done Criteria Status

- Runtime path and tested path use the same `panel_overlay.js` canvas renderer:
  done.
- No live DOM preview chips are created for widget value previews: done.
- `vibecomfy_roundtrip.js` no longer contains a local preview renderer or
  overlay draw-model builder: done.
- Useful recent behavior is preserved in `panel_overlay.js`: done.
- Lifecycle transitions clear preview state deterministically: done for the
  transitions that leave preview mode. `_previewDiff*` clearing is reducer-only.
- Static ownership tests fail if the direct owner implementations return to the
  shell: done.
- Relevant browser/static tests pass: done.
- Comfy relaunches locally and `/vibecomfy/agent/status` is ready: done on
  `http://127.0.0.1:8190` with `web_dist/1d34a44570f6`.
