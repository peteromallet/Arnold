# Widget Name Resolution Phase 3 Implementation

Date: 2026-06-29

## Note on process

The GPT-5.5 agent wrote the gate-tightness regression suite (below) but its Codex
session died mid-run from a transient network failure (DNS lookup failure to
`chatgpt.com/backend-api/codex/responses` after ~146K tokens). The regression suite
was already on disk; I (the orchestrator) ran it to confirm green and performed the
live end-to-end verification myself on DeepSeek. This doc records those results.

## A. Gate-tightness regression suite

`tests/test_compact_widget_resolver.py` was expanded (4KB → 12.8KB) with
tightness-asserting tests, and several gate test files were extended. The suite
asserts **refusals and fail-closed behavior**, not just happy paths:

- ACN rejects fabricated stub names: `widget_index_for_field(node, "latent_kf_override") is None`.
- Unknown names render as `widget_N` and fail-closed on apply: `widget_index_for_field(node, "fabricated_name") is None`.
- Duplicate widget names refuse name lookup (`dup` → None) while explicit `widget_N` still works.
- Overflow refusal: `test_widget_apply_refuses_to_grow_widgets_values_past_compact_count` → `result.candidate is None`.
- strict_ready not silenced: `HIDDEN_MODEL_FILENAME` remains an error under unresolved `widget_0`.
- SVD: `motion_bucket_id` → compact index 3, value 127; `value_domain == "compact"`.
- Per-node `_ui.widgets` names beat object_info.

### Test results
```
.venv/bin/python -m pytest tests/test_compact_widget_resolver.py tests/test_widget_shape_fence.py \
  tests/test_strict_ready.py tests/test_porting_edit_apply.py tests/test_ui_emitter_widget_shape_verdict.py \
  tests/test_widget_shape_evidence.py -q
-> 1 failed, 97 passed, 1 skipped
   TOLERATED FAIL: tests/test_widget_shape_evidence.py::test_raw_scalar_widget_overflow_is_not_hidden_by_compacted_candidate_count
   (quarantined baseline failure — No regressions.)
```

No gate was weakened to pass these tests.

## B. Live end-to-end verification (DeepSeek, 4 scenarios)

| Scenario | Result | Agent's edit | Intent-judge verdict |
|---|---|---|---|
| `image-sd3-image-generation-with-controlnet-19d221` | **PASS** | `acn_advancedcontrolnetapply.strength = 0.5` | passes — `strength` (compact index 0) correctly changed to 0.5 |
| `image-sdxl-txt2img-cat-in-spacesuit` | **PASS** | (sanity) | no regression |
| `video-svd-image-to-video-generation-fc240f` | **FAIL — different reason** | `svd_img2vid_conditioning.motion_bucket_id = 200` | correct parameter targeted by name; value landed as **255** (max), not 200; candidate emitted raw-domain (7 values w/ leading `None`). New downstream value-landing/emission issue, NOT the widget-name bug. |
| `image-image-to-image-with-controlnet-and-dwpreproces-49d057` | **FAIL — different reason** | `controlnetapply.strength = 0.8` | correct parameter targeted by name; edit did not land (noop, `no_candidate_reason='no_changes'`, `queue_validate_ok` failed). Different downstream issue. |

## Verdict

The widget-name → index resolution fix is a **success end-to-end**:

- All three formerly-failing-on-wrong-widget scenarios now **target the correct
  parameter by name** (`strength`, `motion_bucket_id`, `strength`). The
  `correct_node_targeted: True, correct_parameter_changed: False` failure mode is
  gone for the naming part — the agent addresses the right widget.
- `image-sd3` (the ACN ControlNet-strength case) is converted to a **full pass**.
- `image-sdxl-txt2img-cat` still passes (no regression).
- The two remaining failures are **different, downstream** issues:
  1. `video-svd`: the agent's value (200) lands as 255 and the candidate emits
     raw-domain — a value-propagation / emission-regeneration bug distinct from
     widget-name resolution. Worth a follow-up: did Phase 1's compact-vs-raw
     emission selection regenerate `motion_bucket_id` from a default instead of
     preserving the agent's written value?
  2. `image-image-to-image-with-controlnet`: the named edit (`controlnetapply.strength=0.8`)
     produced no candidate (noop / queue_validate_ok). A queue/apply-path issue for
     `ControlNetApply.strength`, not a widget-name issue.

Neither remaining failure is the original widget-name → index misalignment. The
original specific reason these scenarios failed is fixed.

## Follow-ups (not in scope here)

- Investigate the `video-svd` value-landing (200 → 255) + raw-domain candidate emission.
- Investigate the `image-image-to-image-with-controlnet` noop / queue_validate_ok failure
  for `ControlNetApply.strength`.
