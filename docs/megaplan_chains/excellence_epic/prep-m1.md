# Prep M1 — Sprint 1 safety net + correctness evidence

**Generated:** 2026-05-28T00:43Z  
**Source:** Approved sprint brief in `m1-net-and-correctness.md`, plan `sprint-1-safety-net-20260527-2343/plan_v1.meta.json`  
**Evidence artifact:** `evidence/pre_fix_inventory_20260528.json`

---

## 1. Emitter Desync Mechanism

### Root cause: positional desync between `input_items` and `widgets_values`

The emitter in `vibecomfy/porting/emitter.py` builds widget-value dictionaries from the UI node's `widgets_values` positional array. The core of the problem is in `_subgraph_instance_widget_values()` (line 2894) and its downstream `_ui_widget_values_by_name()` (line 2943).

**The desync path (call chain):**

1. `_emit_subgraph_call_statement()` (line 2729) calls `_subgraph_call_kwargs()` (line 2751/2777).
2. `_subgraph_call_kwargs()` calls `_subgraph_instance_widget_values(node)` at line 2795 to get the widget-value dict.
3. `_subgraph_instance_widget_values()` (line 2894) builds values from multiple sources:
   - First from node `.inputs`/`.widgets` attrs (line 2897).
   - Then calls `_ui_widget_values_by_name(ui)` at line 2906, which updates values from the UI node's `widgets_values` positional array.
4. `_ui_widget_values_by_name()` (line 2943) uses **three fallback strategies** to map positional indices to named keys:
   - **proxyWidgets** (line 2953): Maps `properties.proxyWidgets[index]` → name. Only works for widgets with proxy entries.
   - **WIDGET_SCHEMA** (line 2962): Static schema lookup by `class_type`. This is a hand-maintained dict that can be incomplete/stale.
   - **input_items ordering** (line 2971): Iterates `ui.inputs` sequentially, assigning `raw_values[widget_index]` to `input_name`. This assumes positional alignment between the `input_items` array and `widgets_values` array.

**Where alignment breaks:**

The `widgets_values` array from ComfyUI ONLY contains values for widget-type inputs (those with `"widget": {...}` in their input item). Non-widget inputs (links, image uploads, etc.) do NOT contribute entries to `widgets_values`. But `_ui_widget_values_by_name()` iterates ALL `input_items` (line 2971), incrementing `widget_index` for every item regardless, potentially skipping widget positions when non-widget inputs appear in the middle of the list.

5. Back in `_subgraph_call_kwargs()` (line 2798), the function iterates `subgraph.inputs` in port order and looks up values by candidate names (via `_subgraph_instance_port_candidate_names()` at line 2866). When `_ui_widget_values_by_name()` has assigned values to the wrong names (or the WIDGET_SCHEMA fallback mapped them incorrectly), the lookup pairs wrong-typed values with parameter names.

**Example symptom — `video/ltx2_3_runexx_talking_avatar_qwen_tts.py:244-246`:**
```python
voice=986337553816914,        # seed-magnitude int where a path/string belongs
unload_models=116899311982882, # seed-magnitude int where a bool belongs
seed='randomize',             # control_after_generate string where an int belongs
```

### Duplicate widget-value paths in the codebase

The `_ui_widget_values_by_name()` helper is called from two places:
- `_subgraph_instance_widget_values()` (line 2906) — the main widget-value resolution path
- `_widget_default_for_target()` (line 2034) — only uses `.get(widget_name)` for a single widget lookup

The `_subgraph_instance_widget_values()` function also builds values independently from node `.inputs`/`.widgets` attrs (line 2897) AND then overlays `_ui_widget_values_by_name()` results on top (line 2906). This merge can mask the positional desync for fields where the node attr happens to carry the correct value but still produces wrong values when the UI dict is the authoritative source.

---

## 2. `_ui_widget_values_by_name()` Caller Caveat

| Call site | Line | Context | Risk |
|-----------|------|---------|------|
| `_subgraph_instance_widget_values()` | 2906 | Builds full widget-value dict for subgraph kwargs | **High** — feeds the positional-desync values directly into emitted template source code |
| `_widget_default_for_target()` | 2034 | Looks up a single widget default by target slot | **Low** — only reads one widget value, but still uses the same potentially-misaligned dict |

**Key caveat for the fix:** If the SD1 resolution (one authoritative positional widget-value path owned by `_ui_widget_values_by_name()`) is adopted, BOTH callers must route through the same corrected path. The fix must ensure `_subgraph_instance_widget_values()` does NOT independently reconstruct values from node attrs and then overlay the UI dict — instead it should use the UI dict as the sole positional-to-named translation source.

---

## 3. Audited Seed Source Mappings with File-Existence Checks

### Confirmed value-corruption templates (audit j2 finding)

| Template ID | Fields | Status | Source JSON exists? |
|-------------|--------|--------|---------------------|
| `image/z_image` | `steps`, `cfg` | **Already fixed** in working tree | ✅ `ready_templates/sources/official/image/z_image.json` |
| `video/ltx2_3_runexx_talking_avatar_qwen_tts` | `voice`, `unload_models`, `seed` | **Still corrupted** (lines 244-246) | ✅ `ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json` |

### All templates with `widget_n_fields > 0` (potential leak carriers)

From the pre-fix inventory at `evidence/pre_fix_inventory_20260528.json` (captured 2026-05-28T00:43Z):

| Template ID | widget_n_fields | Source JSON | Source exists? |
|-------------|-----------------|-------------|----------------|
| `audio/ace_step_1_5_t2a_song` | 1 | `ready_templates/sources/official/audio/ace_step_1_5_t2a_song.json` | ✅ |
| `audio/qwen3_tts_voice_clone` | 1 | `ready_templates/sources/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json` | ✅ |
| `edit/qwen_image_edit` | 1 | `ready_templates/sources/official/edit/qwen_image_edit.json` | ✅ |
| `video/ltx2_3_i2v` | 8 | `ready_templates/sources/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json` | ✅ |
| `video/ltx2_3_iamccs_audio_extend_low_ram` | 181 | `ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json` | ✅ |
| `video/ltx2_3_iamccs_audio_image_to_video` | 194 | `ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json` | ✅ |
| `video/ltx2_3_iamccs_long_i2v` | 119 | `ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json` | ✅ |
| `video/ltx2_3_lightricks_iclora_hdr` | 2 | `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json` | ✅ |
| `video/ltx2_3_lightricks_iclora_motion_track` | 9 | `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json` | ✅ |
| `video/ltx2_3_lightricks_iclora_union_control` | 7 | `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json` | ✅ |
| `video/ltx2_3_lightricks_two_stage` | 2 | `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json` | ✅ |
| `video/ltx2_3_runexx_first_last_frame` | 2 | `ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json` | ✅ |
| `video/ltx2_3_runexx_first_last_raw_video_guide` | 2 | `null` | ❌ No source |
| `video/ltx2_3_runexx_first_middle_last_frame` | 12 | `ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json` | ✅ |
| `video/ltx2_3_runexx_talking_avatar_qwen_tts` | 6 | `ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json` | ✅ |
| `video/ltx2_3_runexx_video_to_video_extend` | 1 | `ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json` | ✅ |
| `video/ltx2_3_t2v` | 8 | `ready_templates/sources/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json` | ✅ |
| `video/wan_i2v` | 4 | `ready_templates/sources/official/video/wan_i2v.json` | ✅ |
| `video/wanvideo_wrapper_13b_control_lora` | 2 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json` | ✅ |
| `video/wanvideo_wrapper_13b_recammaster` | 15 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json` | ✅ |
| `video/wanvideo_wrapper_21_14b_fun_control` | 1 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json` | ✅ |
| `video/wanvideo_wrapper_21_14b_fun_control_camera` | 6 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json` | ✅ |
| `video/wanvideo_wrapper_21_14b_t2v` | 1 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json` | ✅ |
| `video/wanvideo_wrapper_21_14b_v2v_infinitetalk` | 10 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json` | ✅ |
| `video/wanvideo_wrapper_21_14b_wanmove_i2v` | 8 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_wanmove_i2v.json` | ✅ |
| `video/wanvideo_wrapper_22_14b_t2i` | 5 | `ready_templates/video/wanvideo_wrapper_22_14b_t2i.py` (self-referential) | ✅ |
| `video/wanvideo_wrapper_22_5b_ovi_audio_i2v` | 1 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json` | ✅ |
| `video/wanvideo_wrapper_22_s2v_context_window` | 11 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json` | ✅ |
| `video/wanvideo_wrapper_22_s2v_framepack_pose` | 4 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json` | ✅ |
| `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai` | 9 | `null` | ❌ No source |
| `video/wanvideo_wrapper_wan_animate` | 9 | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json` | ✅ |

**Inventory summary:** 64 templates, 37 with issues (widget_n_fields > 0), 636 total widget_n_fields, 6 with missing source provenance. All source JSON files that exist in the inventory are verified present on disk at the time of this prep.

---

## 4. Starting-State Caveats

### `z_image.py` appears already corrected
The `ready_templates/image/z_image.py` file in the current working tree does NOT show the corruption documented in the structural audit (May 2026). The `steps` and `cfg` parameters are correctly mapped:
```python
ksampler = KSampler(
    _id='9b9009e4:69',
    seed=770044821593082,
    sampler_name='res_multistep',
    steps=steps,          # Correct: takes the function parameter
    cfg=cfg,              # Correct: takes the function parameter
    ...
)
```
The seed value `770044821593082` is properly in the `seed` field, not leaked into `steps`. This means either:
- The fix was applied before this sprint began, OR
- The corruption was in a different version/branch and the audit captured a prior state.

**Per SD2 (failing-first as evidence attempt, not manufactured):** The harness must still include `z_image` in its comparison to prove it remains right-typed, but we do not manufacture a false failure for a template that is already corrected. The `ltx2_3_runexx_talking_avatar_qwen_tts` template provides the red-state evidence.

### `ltx2_3_runexx_talking_avatar_qwen_tts` is still corrupted
Verified lines 244-246:
```python
voice=986337553816914,          # int where path/string expected
unload_models=116899311982882,  # int where bool expected  
seed='randomize',               # string where int expected
```

### `widget_N` leaks are widespread
37 templates carry `widget_N` unresolved-alias leaks. Many are `widget_N=''` (empty string default) from custom-node widgets with no discoverable schema. Per the sprint brief, only alias-resolvable leaks (those where the ComfyUI/WIDGET_SCHEMA can map `widget_N` to a documented field) are fixed in this sprint. Schema-addition-needed leaks are deferred and documented in `handoff-m1.md`.

---

## 5. Snapshot Script and CI Comment Facts

### Missing scripts
| Referenced path | Status | Citation |
|-----------------|--------|----------|
| `scripts/materialize_ready_templates.py` | ❌ Does not exist | Cited in `CLAUDE.md` line 340, `docs/authoring.md` line 171 |
| `scripts/regenerate_snapshots.py` | ❌ Did not exist at this prep checkpoint | Referenced in sprint brief done criterion 7 |
| `tools/check_canonical_parity.py` | ❌ Does not exist on this branch | Referenced in `docs/templates/decorator_template_emitter_completion.md` line 266 (noted as feature-branch-only) |

### Convert parity gate status
The ~55-line compile/build/compare parity validation block at `vibecomfy/porting/convert.py:318-374` is wrapped in:
```python
except Exception:
    # Parity failure is non-fatal for the result; diffs are reported.
    pass
```
This silently swallows ALL parity failures. The gate exists but is disarmed. This is the `except: pass` at line 372 that the sprint must replace with a loud failure surface.

### CI workflow facts
- Current CI at `.github/workflows/ci.yml` uses `uv sync --extra dev` which only includes `pytest` + `pytest-asyncio`.
- Three test modules fail at collection due to missing transitive dependencies (`comfy.cli_args`, `python-dotenv` for `runpod_lifecycle`).
- The `conftest.py` `pytest_collection_modifyitems` at lines 21-37 uses `and` logic for `--runpod`/`--runpod-full` which silently deselects regular runpod tests when `--runpod-full` is used.

---

## 6. Red/Green Evidence Commands

### Pre-fix (red state) evidence
```bash
# Capture pre-fix inventory (ALREADY CAPTURED — see evidence/)
python -m vibecomfy.cli port inventory --ready --json > docs/megaplan_chains/excellence_epic/evidence/pre_fix_inventory_20260528.json

# Verify known corruption in the talking_avatar template
grep -n 'voice=\|unload_models=\|seed=' ready_templates/video/ltx2_3_runexx_talking_avatar_qwen_tts.py | head -15

# Verify z_image is clean (prove it's already fixed)
grep -n 'steps=\|cfg=' ready_templates/image/z_image.py

# Generate failing-first corruption fixture (harness must produce this)
# python -m pytest tests/test_template_roundtrip.py::test_generate_corruption_fixture -v
```

### Post-fix (green state) evidence
```bash
# Differential round-trip harness — must pass for ALL comparable ready templates
python -m pytest tests/test_template_roundtrip.py -v

# Armed convert parity — must fail loudly on mismatch
python -m vibecomfy.cli port convert video/ltx2_3_runexx_talking_avatar_qwen_tts --out /tmp/test_parity.py

# Fast suite must be green
python -m pytest -q --tb=short --ignore=tests/test_models_registry.py --ignore=tests/test_runpod_runner.py --cov=vibecomfy --cov-report=term-missing --cov-report=xml

# Marker selection test
python -m pytest tests/test_conftest_markers.py -v

# Post-fix inventory (verification only, not classification)
python -m vibecomfy.cli port inventory --ready --json > docs/megaplan_chains/excellence_epic/evidence/post_fix_inventory.json
```

---

## 7. Evidence Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Pre-fix inventory | `evidence/pre_fix_inventory_20260528.json` | Full `port inventory --ready --json` output before any emitter fix. 64 templates, 37 with issues, 636 widget_n_fields, 6 missing provenance. |
| Structural audit | `docs/structural_audit_2026-05.md` | Two-part audit identifying the desync bug family and ~8 corrupted templates. |
| Sprint brief | `m1-net-and-correctness.md` | Approved sprint scope with locked decisions. |
| Plan metadata | `.megaplan/plans/sprint-1-safety-net-20260527-2343/plan_v1.meta.json` | Plan version with success criteria and assumptions. |

---

## 8. Debt Watch Items Relevant to This Sprint

The following debt items from the plan's watch list are directly relevant to T1 evidence collection:

- **[DEBT] validation-ordering:** The harness may start green if audited corruptions have already been fixed in the working tree — confirmed for `z_image.py`.
- **[DEBT] widget-leak-classification:** Post-fix inventory can undercount leaks that existed before remediation — per SD3, the pre-fix inventory (captured above) is the classification source.
- **[DEBT] find-the-callers:** `set_prompt` callers for edit templates — T1 scope, documented as known debt.
- **[DEBT] handle-equality-hash-semantics:** Hash/eq compromise for bare-ID bridge — known, not addressed this sprint.
