# Frontend Split-Brain Swarm Findings - 2026-07-09

DeepSeek fan-out:

- Runner: `~/.claude/skills/subagent-launcher/fan.py`
- Model: `deepseek:deepseek-v4-pro`
- Tasks: 10
- Results: `/tmp/vibecomfy-bug-swarm-results/`

Follow-up review:

- Runner: `~/.claude/skills/subagent-launcher/fan.py`
- Model: `zhipu:glm-5.2`
- Results: `/tmp/vibecomfy-glm-cleanup-results/cleanup-review.txt`

## Root Smell

The repeated preview bug was a frontend ownership split. Canonical owner modules
had newer behavior, but `vibecomfy_roundtrip.js` and compatibility mirrors still
held older render/state paths. That allowed stale preview text, stale candidate
state, or duplicate diagnostic mirrors to survive after the intended owner
changed.

## Fixed in This Cleanup

### Preview Overlay

- `panel_overlay.js` is the only preview renderer implementation owner.
- The DOM-chip preview renderer was removed:
  - `syncPreviewDomOverlay`
  - `ensurePreviewDomOverlayRoot`
  - `appendPreviewDomChip`
  - `previewChipGeometry`
- `clearPreviewDomOverlay` remains only as cleanup for stale DOM roots that may
  exist in older browser sessions.
- `overlayDrawCacheKey` now prefers live panel candidate graph hash over a stale
  diff hash.
- The vestigial `app.__vibecomfyAgentPreviewOverlayDraw` install-time snapshot
  was removed.
- Useful recent/stashed overlay fixes were preserved:
  - stronger port resolution for named ports, slot indexes, `input_N` /
    `output_N`, unique type matches, and single-port fallbacks
  - `nodeOverlayKey` fallback to `node.id`
  - candidate-preferred endpoint lookup for added wires

### Preview State Lifecycle

- Stop/abort, apply success, authoritative accept rejection, and rebaseline
  success now clear candidate preview state through the lifecycle invalidation
  primitive.
- Rebaseline success now clears candidate state immediately, not just by
  emitting an obligation for a later caller.
- Apply success returns both `invalidateCandidate` and `clearCandidatePreview`.
- Reject failure intentionally preserves candidate preview state because a failed
  reject should leave the candidate reviewable.
- Demo preview picker stage navigation now fulfills lifecycle obligations from
  commit helpers instead of hand-clearing preview diff state.
- Shell preview cleanup now owns only side effects such as overlay cache
  invalidation, stale DOM-root cleanup, and repaint; `_previewDiff*` state
  clearing lives in the lifecycle reducer.

### Thread / Composer / Diagnostics

- Dead old shell renderers were removed from `vibecomfy_roundtrip.js`:
  - `renderCandidate`
  - `renderFailure`
  - `renderQueue`
- Composer action and notice rendering now dispatch through wrapper functions
  instead of duplicating owner-module dependency assembly inline.
- `renderDeveloper` no longer destroys the rich DOM it just built by overwriting
  `textContent`.
- Diagnostic render mirrors were canonicalized to `_lastThreadRender` and
  `_lastNoticeRender`; duplicate `last*Render` fields were removed.

## Regression Coverage Added

- Static ownership tests forbid reintroducing DOM preview chips and dead shell
  renderers.
- Lifecycle tests assert preview/candidate state is cleared on the transitions
  that leave preview mode.
- Composer/thread/runtime tests assert diagnostic mirrors stay canonical and the
  developer DOM is preserved.
- Roundtrip smoke tests cover stale DOM-root cleanup and the canvas repaint
  contract after apply.
- Preview picker tests assert demo stage transitions fulfill lifecycle
  obligations, and lifecycle ownership tests forbid `_previewDiff*` deletes
  outside the reducer.

## Remaining Broader Architecture Debt

These are the same smell class, but they are not the active floating/clipped
preview bug:

- `vibecomfy_roundtrip.js` still owns some orchestration-adjacent UI behavior
  such as meta/status display, choose-engine overlay wiring, research
  contribution workflow, and settings autosave coordination.
- Lifecycle obligations still mix two concepts: direct reducer state mutation
  and commands that shell callers fulfill. The preview bug is fixed by clearing
  state in the reducer path, but a future cleanup should make obligation
  semantics more explicit.
- Some compatibility state mirrors still exist elsewhere, including transcript,
  execution, scope, and replay snapshots. They should continue moving toward
  selector-based reads or centralized mutation helpers.

## Verification

Focused checks run after cleanup:

```sh
node --check vibecomfy/comfy_nodes/web/panel_overlay.js
node --check vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js
node --check vibecomfy/comfy_nodes/web/panel_composer.js
node --check vibecomfy/comfy_nodes/web/panel_thread.js
node --check vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js
node --test tests/browser/preview_overlay_ownership_static.test.mjs tests/browser/ownership_contract.test.mjs tests/browser/frontend_ownership_regression.test.mjs tests/browser/agent_edit_lifecycle.test.mjs
node --test tests/browser/panel_thread_rating.test.mjs
node --test tests/browser/roundtrip_smoke.test.mjs
```
