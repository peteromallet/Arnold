# Stash Recovery Plan - 2026-07-08

Source stash: `stash@{0}: On main: codex-preserve-before-agent-edit-canonical-deltas-merge`

Current base: `main` at `57377059 Restore preview overlay value labels`

Swarm artifacts: `/tmp/vibecomfy-stash-swarm/results`

## Executive Judgment

Do not apply this stash wholesale. It is a pre-canonical-delta snapshot mixed with useful follow-on work. Whole-stash application would conflict with current `main`, roll back parts of the canonical-delta merge, and reintroduce stale root/build state when compared against `HEAD`.

The right move is selective recovery. Keep current `delta_ops_envelope` / canonical-v2 contract as the source of truth. Extract small additive improvements where they fit that contract. Treat broad stash rewrites as design notes, not patches.

## Highest-Value Recovery Items

### 1. Preview Repaint And Demo Field-Change Plumbing

Recover from:

- `vibecomfy/comfy_nodes/web/preview_picker.js`
- `tests/browser/preview_picker.test.mjs`

Useful ideas:

- Add `requestPreviewOverlayRepaint()` after demo stage transitions.
- Include `change_details` in the demo terminal result.
- Populate `lastSubmitFieldChanges` from `normalizeCommitFieldChangesFromSubmit(...)`.
- Add a browser test proving the review stage triggers a canvas repaint and demo field changes feed the preview overlay.

Why this matters:

This is the most plausible missing piece behind "old preview text/style still appears after a value changes." The server is already serving the new cache-busted bundle, so stale display is more likely an overlay repaint/cache-state problem than an old backend.

Risk:

Low. This is additive and fits current lifecycle code.

Validation:

```bash
node --test tests/browser/preview_picker.test.mjs tests/browser/roundtrip_smoke.test.mjs
```

### 2. Candidate Baseline Persistence In Replay

Recover from:

- `vibecomfy/comfy_nodes/web/agentic_replay.js`

Useful idea:

- Persist and restore `candidateBaselineGraph`.

Why this matters:

Preview diffs should compare candidate against the submit-time baseline, not whatever the live canvas has mutated into later.

Risk:

Low. Current `main` already has `candidateBaselineGraph` in lifecycle state; replay persistence is the missing complement.

Validation:

```bash
node --test tests/browser/agent_edit_lifecycle.test.mjs tests/browser/lifecycle_ownership_static.test.mjs
```

### 3. LiteGraph Indexed Geometry

Recover from:

- `vibecomfy/porting/canonical_coords.py`
- `tests/test_canonical_coords.py`
- `tests/test_reorganise_skill.py`

Useful idea:

- Accept geometry objects like `{ "0": 315, "1": 122.5 }` in `snap_pos` and `snap_size`.

Why this matters:

Some LiteGraph/ComfyUI payloads serialize coordinates as indexed objects instead of arrays. Reorganise and canonical coordinate paths should tolerate both.

Risk:

Low. It broadens accepted input and keeps existing list behavior.

Validation:

```bash
.venv/bin/python -m pytest tests/test_canonical_coords.py tests/test_reorganise_skill.py
```

### 4. Reorganise Before/After Assessment

Recover from:

- `vibecomfy/comfy_nodes/agent/reorganise.py`
- `tests/test_reorganise_skill.py`

Useful ideas:

- Assess the candidate graph after applying the layout patch.
- Store `before_assessment`, `after_assessment`, and make `assessment` equal the after-assessment when available.
- Report whether the assessed graph is `source` or `candidate`.

Why this matters:

Reorganise is supposed to be layout-only. The audit trail should prove that the candidate graph, not just the source graph, still passes structural checks.

Risk:

Low to medium. The implementation touches agent response artifacts, but the concept is sound.

Validation:

```bash
.venv/bin/python -m pytest tests/test_reorganise_skill.py
```

### 5. Executor Freshness Fields

Recover from:

- `vibecomfy/executor/contracts.py`
- `vibecomfy/executor/core.py`
- `tests/test_executor_contracts.py`
- `tests/test_executor_flows.py`

Useful ideas:

- Add optional request fields:
  - `client_graph_hash`
  - `client_structural_graph_hash`
  - `client_live_canvas_token`
- Forward them into `handle_agent_edit(...)`.

Why this matters:

This gives durable apply/CAS code the browser's submit-time freshness evidence. It is separate from response-side submitted hashes and should be additive.

Risk:

Low, if implemented as optional fields with type validation.

Validation:

```bash
.venv/bin/python -m pytest tests/test_executor_contracts.py tests/test_executor_flows.py
```

### 6. Authoring Constructor Aliases

Recover from:

- `vibecomfy/porting/authoring_names.py` from `stash@{0}^3`
- `vibecomfy/porting/edit/_describe.py`
- `vibecomfy/porting/edit/_resolve.py`
- `vibecomfy/porting/emit/signatures.py`
- `tests/test_porting_edit_session.py`

Useful ideas:

- Preserve class-style constructor names in model-facing signatures.
- Convert non-Python identifiers predictably, for example `MiDaS-DepthMapPreprocessor` -> `MiDaS_DepthMapPreprocessor`.
- Disambiguate alias collisions, for example `A-B` and `A_B`.
- Resolve constructor aliases back to raw Comfy `class_type`.

Why this matters:

The current lowercase signature style is mechanically valid but model-hostile. Better constructor names should improve graph edit quality.

Risk:

Medium. This crosses model-facing prompting, code emission, and resolver behavior. Recover as a dedicated patch with focused tests.

Validation:

```bash
.venv/bin/python -m pytest tests/test_porting_edit_session.py tests/test_porting_emit_signatures.py
```

### 7. Legacy Field-Change Recovery

Recover conceptually from:

- `vibecomfy/comfy_nodes/agent/session.py`

Useful ideas:

- If a persisted old response has no canonical `delta_ops_envelope`, infer safe `upsert_link` ops from legacy `field_changes`.
- Search all likely field-change locations: top-level `field_changes`, `outcome.changes`, `batch_turns[].field_changes`, `change_details.batch_turns[].field_changes`.

Why this matters:

Old artifacts can become accept/apply-compatible without falling back to whole-graph reloads.

Risk:

Medium. Do not take the stash's `_load_turn_delta_ops` rewrite. Current `main` already validates canonical envelopes. Add inference only as a final fallback after canonical envelope and flat-list handling fail or are absent.

Validation:

Add a focused test such as:

```bash
.venv/bin/python -m pytest tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py
```

## Useful But Design-Heavy

### Preview Overlay Visual Rewrite

Stash has good ideas in `panel_overlay.js` and `vibecomfy_roundtrip.js`:

- Zoom-aware chip sizing.
- Long text wrapping.
- Full widget-row value chips.
- Offscreen chip clipping.
- More stable port/slot matching for link diffs.
- Preview diff clamping from field changes.

My judgment: do not merge this as a blob. The current pushed fix restored labels without redesigning the overlay. The stash changes are partly UX direction, partly rendering correctness. Extract low-risk helpers first:

- `resolveSlotIndex(...)`
- offscreen chip clipping
- text wrapping helper
- tests for named-port wire changes and long widget values

Then decide separately whether full-row chips are the desired style.

## Do Not Recover Directly

### Canonical Delta Rollback

Do not apply stash deletions of:

- `vibecomfy/comfy_nodes/web/canonical_delta.js`
- `vibecomfy/porting/edit/schemas/v2/*`
- `tests/browser/canonical_delta.test.mjs`
- `tests/test_porting_edit_delta_contract.py`

The agents disagreed here, but the repo state decides it: current `main` has already merged the canonical-v2 contract. Removing it from a stash would be a rollback, not recovery.

Possible future refactor:

If canonical delta feels overbuilt, simplify it deliberately in a separate design patch while keeping compatibility tests green. Do not smuggle that into stash recovery.

### Flat `delta_ops` Response Rewrite

Do not directly recover `_attach_delta_ops_if_present(...)` as the primary response path. Current `main` emits canonical `delta_ops_envelope`. If flat `delta_ops` remains useful for frontend convenience, derive it alongside the envelope, not instead of the envelope.

### Whole `session.py` Diff

Do not apply the stash version of `session.py`. It removes current diagnostic and canonical validation behavior. Extract only:

- legacy field-change inference as fallback
- `original.ui.json` / `candidate.ui.json` loading fallback if still absent
- `widget_N` alias support if still absent
- root-scope add-node handling only if it preserves current uid/node-id priority

### Build/Root State

Do not reintroduce `test_tmp.txt` or remove current root allowlist fixes. The working tree must stay clean under:

```bash
make root-clean
```

## Recommended Implementation Order

1. Preview repaint/data plumbing.
2. Replay `candidateBaselineGraph` persistence.
3. LiteGraph indexed geometry.
4. Reorganise after-assessment metrics.
5. Executor freshness request fields.
6. Authoring constructor aliases.
7. Legacy field-change to canonical-delta fallback.
8. Overlay visual helper extraction.

This order front-loads the likely user-visible preview bug and low-risk backend hardening, while keeping the larger refactors isolated.

## Final Gate

After all selected recovery patches:

```bash
make
node --test tests/browser/agent_edit_lifecycle.test.mjs tests/browser/lifecycle_ownership_static.test.mjs tests/browser/preview_picker.test.mjs tests/browser/roundtrip_smoke.test.mjs
VIBECOMFY_COMFY_SMOKE=1 VIBECOMFY_COMFYUI_URL=http://127.0.0.1:8190/ .venv/bin/python -m pytest -q --tb=short tests/test_comfy_nodes_live_smoke.py
```

The live smoke may still fail on the known disabled submit button issue; track that separately from stash recovery.
