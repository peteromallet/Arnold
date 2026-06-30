# Widget Name Resolution Phase 1 Implementation

Date: 2026-06-29

## Files Changed

- `vibecomfy/porting/widgets/compact_resolver.py`: added the shared per-node compact `widgets_values` resolver, field lookup, and value lookup.
- `vibecomfy/porting/widgets/__init__.py`: exported the compact resolver API.
- `vibecomfy/porting/edit/projection.py`: routed agent projection field rows through the compact resolver.
- `vibecomfy/porting/edit/apply_slots.py`: made widget field lookup node-aware and compact-domain; kept explicit `widget_N` support.
- `vibecomfy/porting/edit/apply_resolve_base.py`: passed the node and schema provider into widget index resolution.
- `vibecomfy/porting/edit/_ir_utils.py`: routed widget value lookup through the compact resolver sentinel path.
- `vibecomfy/porting/edit/_describe.py`: stopped old/new summaries from reading widget values via raw input or schema input positions.
- `vibecomfy/porting/emit/emit_prepare.py`: rendered agent-edit widget kwargs through node-aware compact names.
- `vibecomfy/porting/emit/emit_constants.py`: used compact aliases for constant translation and extended `_ui_widget_aliases` to explicit `_ui.widgets` / `_ui.widget_names` evidence only.
- `vibecomfy/porting/emit/node_kwargs.py`: routed simple kwarg rendering through compact names.
- `vibecomfy/porting/emit/emit_kwargs.py`: routed ready-template kwarg rendering through compact names.
- `vibecomfy/porting/emit/ui.py`: added compact-vs-raw emission domain selection, preserved compact vectors for SVD-like nodes, and added `value_domain` evidence.
- `vibecomfy/porting/emit/emit_subgraph.py`: replaced raw object-info positional fallback with compact resolver names for subgraph widget value extraction.
- `vibecomfy/porting/emit/__init__.py`: restored the `emitter` package compatibility export needed by existing tests.
- `vibecomfy/porting/emitter.py`: restored compatibility facade exports for widget emitter tests after the emit package split.
- `tests/test_compact_widget_resolver.py`: added focused Phase 1 resolver/emission regression tests.

## Verification

- `py_compile`: passed for every touched Python file.
- Focused resolver tests: `tests/test_compact_widget_resolver.py -q` -> `4 passed`.
- Required gate command:
  - Command exited `0`.
  - Pytest summary reported `137 passed`, `1 skipped`, and `84 failed` quarantined baseline failures.
  - Quarantine plugin summary: `All 84 failure(s) are quarantined baseline failures. No regressions.`
- Focused former-new failures:
  - `test_apply_delta_reorders_unlinked_widget_values_only`
  - `test_schema_less_node_preserves_candidate_count_without_overflow_verdict`
  - `test_existing_static_overflow_recovers_by_preserving_observed_raw_widget_slot`
  - Result: `3 passed`.

## Evidence Reproduction

- SVD node `12` in `external_workflows/corpus/fc240f1c4331a5e5.json`:
  - `motion_bucket_id` resolves to compact index `3`.
  - Resolved value is `127`.
  - Emitted `widgets_values` stays `[1024, 576, 14, 127, 6, 0]` with length `6`.
  - `value_domain` is `compact`.
- ACN node `60` in `external_workflows/corpus/19d221f074b42462.json`:
  - Compact values stay `[0.6, 0, 0.75]`.
  - Resolved names are `widget_0`, `widget_1`, `widget_2`.
  - `strength` and `latent_kf_override` do not resolve to widget indices.
  - Emitted `widgets_values` stays length `3`.

## Gates Tightened

- Workflow-JSON stub object-info entries are not authoritative compact aliases. This prevents ACN-style socket-name fabrication from becoming writeable widget names.
- Duplicate widget names are surfaced as `widget_N` for the duplicate slots. Name-based writes fail closed; explicit bounded positional writes still work.
- Unknown compact slots render as `widget_N` instead of borrowing names from raw `_ui.inputs` socket rows.
- Emission defaults to compact-domain names unless raw-domain evidence is explicit: committed schema with `None` UI-only slots, or captured raw widget length equal to raw object-info order.

No Phase 2 ACN curated schema entry was added.
