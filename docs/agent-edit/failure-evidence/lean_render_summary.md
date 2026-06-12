# Lean Render: BEFORE → AFTER comparison

Target: `video/ltx2_3_runexx_first_last_frame` (RuneXX)

## Character counts

| Metric | BEFORE | AFTER | Delta |
|---|---|---|---|
| system_chars | 4,418 | 1,482 | −2,936 |
| user_chars | 45,096 | 43,445 | −1,651 |
| **total_chars** | **49,514** | **44,927** | **−4,587** |
| python_chars | 11,038 | 9,387 | −1,651 |
| catalog_chars | 4,737 | 4,737 | 0 |
| names_chars | 29,068 | 29,068 | 0 |

*Source: `lean_render_before/video_ltx2_3_runexx_first_last_frame.metrics.json` and `lean_render_after/video_ltx2_3_runexx_first_last_frame.metrics.json`.*

## Framing-line excerpts

**BEFORE** (line 2 of system prompt):

> You edit a VibeComfy ComfyUI canvas as a Python-native dataflow program.

**AFTER** (line 2 of system prompt):

> You edit a ComfyUI canvas as live Python objects.

## `.OUTPUT` examples

**BEFORE** — system prompt uses `.OUTPUT_SLOT` convention:

> `new_var = ClassType(field=value, input_kwarg=other_var.OUTPUT_SLOT, near=anchor_var)`, for example `upscaled = ImageScaleBy(image=vaedecodetiled.IMAGE, …)`

**AFTER** — system prompt uses `.OUTPUT` convention:

> Add: `x = NodeType(field=val, input=other.OUTPUT)`
>
> Always name the output slot: write `up.IMAGE`, never bare `up`.

## `placed (` evidence

`placed (` occurs **60 times** in the BEFORE prompt and **0 times** in the AFTER prompt.

```sh
$ grep -c 'placed (' docs/agent-edit/failure-evidence/lean_render_before/video_ltx2_3_runexx_first_last_frame.prompt.txt
60

$ grep -c 'placed (' docs/agent-edit/failure-evidence/lean_render_after/video_ltx2_3_runexx_first_last_frame.prompt.txt
0
```

The BEFORE Python source section includes `placed (x, y)` annotations on every node assignment line (e.g. `# uid:n1 placed (0.0, 632.0)`). The AFTER Python source section omits all coordinate annotations — only `# uid:n1` style comments remain.

## Deferred: REPL feedback-trace measurement

The task description references REPL feedback-trace measurement as a follow-on step. This has not yet been executed; no feedback-trace dumps are present in `docs/agent-edit/failure-evidence/`. Deferred to a future batch.

## Faithfulness structural check (T10)

### Protected-test sweep

```
tests/test_porting_edit_session.py
tests/test_porting_emitter.py
tests/test_comfy_nodes_agent_backend_spine.py
tests/test_comfy_nodes_agent_edit.py
tests/test_comfy_nodes_agent_contracts.py
tests/test_agent_edit_safety.py
```

Result: **473 passed, 9 failed** (7 pre-existing in `known_failures.txt`, 2 new).

| Failure | Status | Cause |
|---|---|---|
| `test_handle_agent_edit_batch_repl_turn0_catalog_is_scoped_and_search_first` | NEW | T5 prompt rewrite removed "below" from search-first phrasing; test assertion expects old wording |
| `test_failure_kind_enum_matches_closed_contract_exactly` | NEW | Pre-existing enum drift (unrelated to T3/T5); `FailureKind` has 5 more members than the closed-contract list |
| 7 `test_porting_emitter.py` ready-template tests | pre-existing | All in `known_failures.txt`; no net-new from this sprint |

The 1 sprint-attributable new failure is localized to `test_comfy_nodes_agent_edit.py` line 1107: the test asserts `"Only signatures … shown below"` but the T5 prompt says `"Only signatures … shown."` (no "below"). The corresponding backend-spine test (`test_comfy_nodes_agent_backend_spine.py`) was updated in T6; this file was not in scope.

### Structural-faithfulness coverage (SC10)

The in-process faithfulness coverage lives in `tests/test_porting_edit_session.py` across three test classes:

| Requirement | Covered? | Where |
|---|---|---|
| ≥3 graphs (real fixture + two synthetic) | ✅ | `_load_flat_fixture_wf()` (flat.json) + 5 synthetic VibeWorkflows in `TestAgentEditLeanRender` + synthetic graphs in `TestRenderEditRerenderIdentity` |
| `placed (` not in rendered | ✅ | `test_emitter_accepts_vibeworkflow` (line 194), `test_agent_edit_python_is_parseable_assignment_view_with_identity_comments` (line 552) |
| `[elided ` for long-string widget | ✅ | `test_long_string_elision_threshold_respected` (line 640) |
| Normalized text equality of two successive renders | ✅ | `test_render_then_rerender_preserves_variable_names` (line 223: `rendered1 == rendered2`), `test_session_rerender_keeps_locked_names_after_topology_change` (line 271: `rendered2 == rendered3`), `test_agent_edit_python_preserves_locked_names_without_changing_scratchpad` (line 575: `baseline_scratchpad == after_scratchpad`) |
| No gate-helper imports chased (`ui_fidelity_ok`, `state_match_ok`) | ✅ | All equality assertions use raw text comparison of `emit_agent_edit_python`/`emit_scratchpad_python` outputs; no import from `vibecomfy/comfy_nodes/agent_gates.py` |

**Verdict:** The faithfulness test file meets SC10 requirements. The fallback strategy (text equality) is the locked path per watch-item guidance.

## Full-suite parity-baseline delta (T11)

### Protected files tested

```
tests/test_porting_emitter.py
tests/test_porting_emitter_widgets.py
tests/test_porting_edit_session.py
tests/test_porting_edit_session_harness.py
tests/test_comfy_nodes_agent_backend_spine.py
tests/test_comfy_nodes_agent_edit.py
tests/test_comfy_nodes_agent_contracts.py
tests/test_agent_edit_safety.py
```

Result: **493 passed, 9 failed** (502 collected). 7 pre-existing in `known_failures.txt`, 2 not in baseline.

| Failure | Status | Δ from T10 | Cause |
|---|---|---|---|
| `test_handle_agent_edit_batch_repl_turn0_catalog_is_scoped_and_search_first` | NEW | same as T10 | T5 prompt rewrite removed "below" from search-first phrasing; `test_comfy_nodes_agent_edit.py:1107` asserts old wording |
| `test_failure_kind_enum_matches_closed_contract_exactly` | pre-existing/undocumented | same as T10 | `FailureKind` enum has 5 more members than the closed-contract list; `test_comfy_nodes_agent_contracts.py` not in changed-file set |
| 7 `test_porting_emitter.py` ready-template tests | pre-existing | same as T10 | All in `known_failures.txt` |

### Delta vs T10 sweep (T11 adds 2 files)

T10 swept 6 files (482 tests, 473+9). T11 adds `test_porting_emitter_widgets.py` (4 tests) and `test_porting_edit_session_harness.py` (16 tests). All 20 incremental tests passed — no regressions from the wider protection boundary.

### Verdict

The 1 sprint-attributable failure (`test_handle_agent_edit_batch_repl_turn0_catalog_is_scoped_and_search_first`) persists from T5's prompt change. The assertion at `test_comfy_nodes_agent_edit.py:1107` expects `"Only signatures … shown below"` but the rewritten prompt says `"Only signatures … shown."` (no final "below"). This was documented in T10 and remains the only sprint-attributable new failure. The corresponding backend-spine test (`test_comfy_nodes_agent_backend_spine.py`) was updated in T6 to match the new phrasing; `test_comfy_nodes_agent_edit.py` was not in scope for T6.

## Deferred: Live-traffic measurement

The task description references live-traffic measurement against real agent-edit sessions. This has not yet been executed — no live-traffic capture infrastructure exists in the current artifact set. Deferred to a future batch.
