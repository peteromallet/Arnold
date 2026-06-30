# Widget Name Resolution Follow-ups Implementation

Date: 2026-06-29

## Bug 1: SVD `motion_bucket_id` rejected as non-widget

### Fix

- `vibecomfy/porting/widgets/compact_resolver.py`
  - Replaced provider alias filtering that only skipped `LINK_ONLY_TYPES` with a widget-value predicate matching `object_info_widget_value_order` semantics: scalar literal types and enum choices are widget values; socket-like uppercase types such as `IMAGE`, `VAE`, `CLIP`, `CONDITIONING`, etc. are not.
  - Tightened `_ui.inputs[].widget` alias evidence so it only wins when it covers the compact widget vector exactly. This prevents a single linked-socket alias such as SVD `clip_vision` from shadowing compact provider/object_info names.

This keeps the gate strict: link-only inputs still do not become editable. It only makes the alias domain accurate.

### Reproduction

Before the fix, the authoring provider path for `SVD_img2vid_Conditioning` returned non-compact aliases:

```text
names with provider: clip_vision, width, height, video_frames, motion_bucket_id, fps
motion_bucket_id index: 4
clip_vision index: 0
```

The live apply path also hit `non_widget_field_not_editable` for `motion_bucket_id` because per-node input-stub aliases hid the compact names.

After the fix:

```text
names with provider: width, height, video_frames, motion_bucket_id, fps, augmentation_level
motion_bucket_id index: 3
clip_vision index: None
```

### Tests

- `tests/test_compact_widget_resolver.py::test_svd_schema_provider_aliases_are_compact_widget_value_order`
- `tests/test_compact_widget_resolver.py::test_set_node_field_rejects_svd_link_only_input_with_schema_provider`
- `tests/test_compact_widget_resolver.py::test_set_node_field_applies_svd_motion_bucket_with_schema_provider`

## Bug 2: Pure ControlNet parameter edit discarded as topology blockers

### Fix

- `vibecomfy/executor/revision_evidence.py`
  - Added stable topology-blocker identity comparison.
  - `candidate_topology_blockers` now means blockers newly introduced by the candidate, not blockers merely present in the candidate graph because they already existed in the original.
  - Pre-existing original topology blockers no longer make `compute_scoped_diff` ineligible by themselves; newly introduced dangling links, absent endpoints, socket mismatches, unknown classes, missing required inputs, or missing graph still block.

This does not skip topology validation. It changes attribution: old blockers are tolerated for unrelated parameter edits; new topology damage is still refused.

### Tests

- `tests/test_revision_evidence.py::test_scoped_diff_tolerates_preexisting_topology_blockers_for_parameter_edit`
- `tests/test_revision_evidence.py::test_scoped_diff_blocks_new_topology_damage_from_removed_load_bearing_node`

## Verification

### Compile

```text
.venv/bin/python -m py_compile vibecomfy/porting/widgets/compact_resolver.py vibecomfy/executor/revision_evidence.py tests/test_compact_widget_resolver.py tests/test_revision_evidence.py
PASS
```

### Focused and gate suites

```text
.venv/bin/python -m pytest tests/test_compact_widget_resolver.py tests/test_revision_evidence.py -q
67 passed
```

```text
.venv/bin/python -m pytest tests/test_compact_widget_resolver.py tests/test_widget_shape_fence.py tests/test_strict_ready.py tests/test_porting_edit_apply.py tests/test_ui_emitter_widget_shape_verdict.py tests/test_widget_shape_evidence.py -q
exit 0; 100 passed, 1 skipped, 1 quarantined baseline failure
```

The tolerated baseline was:

```text
tests/test_widget_shape_evidence.py::test_raw_scalar_widget_overflow_is_not_hidden_by_compacted_candidate_count
```

### Live DeepSeek verification

Command run with `VIBECOMFY_FORCE_MODEL` and `VIBECOMFY_HERMES_API_KEY` unset:

```text
for sid in video-svd-image-to-video-generation-fc240f image-image-to-image-with-controlnet-and-dwpreproces-49d057; do
  .venv/bin/python -m tests.live_agentic_harness.runner --single tests/live_agentic_harness/scenarios/$sid.json --tag verify-followups --single-out /tmp/verify-followups/$sid.json --output-base out/agentic
done
```

#### `video-svd-image-to-video-generation-fc240f`

Result: PASS.

- Guard: `success=true`, `status=success`, no error issues.
- Outcome: `candidate`; `apply_allowed=true`; `canvas_apply_allowed=true`.
- Agent edit: `svd_img2vid_conditioning.motion_bucket_id = 250`.
- Landed change:

```json
{"field_path":"motion_bucket_id","new":250,"old":14,"uid":"12"}
```

- Diagnostics: none; no `non_widget_field_not_editable`.
- Intent judge: passed, with `correct_node_targeted=True`, `correct_parameter_changed=True`, `value_semantically_matches_intent=True`, `no_orphaned_wiring=True`.

Note: the live headless graph presented the current SVD value as `14` even though the source corpus raw widget vector has `motion_bucket_id=127`. The follow-up bug fixed here is the apply rejection; the live candidate now lands a direct `motion_bucket_id` field change and passes intent.

#### `image-image-to-image-with-controlnet-and-dwpreproces-49d057`

Result: PASS.

- Guard: `success=true`, `status=success`, no error issues.
- Outcome: `candidate`; `apply_allowed=true`; `canvas_apply_allowed=true`.
- Agent edit: `controlnetapply.strength = 0.8`.
- Landed change:

```json
{"field_path":"strength","new":0.8,"old":1,"uid":"20"}
```

- Diagnostics: none; no topology eligibility blockers.
- Intent judge: passed, with `correct_node_targeted=True`, `correct_parameter_changed=True`, `value_semantically_matches_intent=True`, `no_orphaned_wiring=True`.

## Verdict

Both follow-up scenarios convert to passes:

- SVD no longer rejects the named `motion_bucket_id` edit as non-widget; it lands and applies as a candidate.
- ControlNet no longer discards the pure `strength=0.8` parameter edit as candidate topology damage; it lands and applies as a candidate.
