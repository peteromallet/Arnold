## Schema & Node Specs Audit — Ranked Findings

### HIGH

1. **Three overlapping validation schemas with incompatible return models.** `schema/validate.py:17-210` uses `ValidationIssue`, `schema/call_validation.py:41-130` uses `NodeCallValidationIssue`/`NodeCallValidationReport`, and `porting/validate_call.py:46-92` uses `CallValidationError`/`CallValidationResult`. All three check required/unknown inputs and enum/range values against a `SchemaProvider`, but they diverge: `call_validation.py` adds primitive-type checking (line 114–129) that the other two lack; `porting/validate_call.py` skips enum, range, and type validation entirely; `validate.py` has class-specific dynamic-input handling (LTX/SimpleCalculator, lines 294–374) absent in the others. A fix to validation logic must be replicated across three files — they are already out of sync.

2. **provider.py is a 984-line god module with a misleading comment bug.** `schema/provider.py` bundles 9 `SchemaProvider` implementations, the `SchemaProvider` Protocol, a factory function, and 20+ helpers into a single file. `ConversionSchemaProvider.get_schema()` (lines 402–517) documents a 5-step precedence order (lines 355–367: local → object_info_cache → source_parser → widget → runtime) but the code injects an unlisted `ObjectInfoIndexSchemaProvider` between steps 2 and 3, then labels the actual source-parser step with a duplicate `# 3. Source parser` comment at line 463 — making the real step count 6 while the docstring says 5. This mislabels the actual precedence.

3. **"Handwritten" nodes are empty shells — the split is fictional.** Every file in `nodes/` (e.g., `nodes/core.py:1-4`, `nodes/kjnodes.py:1-4`, `nodes/wanvideowrapper.py:1-4`) is exactly 4 lines re-exporting from `nodes/_generated/`. There is zero hand-authored node logic in the `nodes/` directory; all 14 modules are identical boilerplate. The directory structure implies a hand-authored vs. generated split that does not exist — it's pure indirection.

### MEDIUM

4. **Duplicate .pyi stubs in both `nodes/` and `nodes/_generated/`.** All 14 node families have .pyi files in *both* locations. The `nodes/XXX.pyi` stubs (e.g., `nodes/core.pyi:1-3`, `nodes/kjnodes.pyi:1-3`) are trivial 3-line re-exports adding zero type information. This doubles the .pyi maintenance surface; the `nodes/` stubs can drift from `_generated/` stubs with no warning.

5. **Inconsistent schema attribute access across validation layers.** `porting/validate_call.py:66` accesses `schema.inputs` as a bare attribute, while `schema/validate.py:70` and `schema/call_validation.py:57` use defensive `getattr(schema, "inputs", {})`. If `NodeSchema` ever adds a property or changes its internal shape, the porting path breaks silently while the schema path degrades gracefully.

### LOW

6. **Dead `_generated/__init__.py` with empty `__all__`.** `nodes/_generated/__init__.py:1` declares `__all__: list[str] = []` and `_generated/__init__.pyi:1` mirrors it. These exist but serve no purpose — users import submodules directly, and the top-level generated package has no meaningful exports. Dead weight that misleads about the package's public API.

---

**Worst thing:** The triple overlapping validation (`schema/validate.py` vs `schema/call_validation.py` vs `porting/validate_call.py`) — three incompatible "sources of truth" for the same correctness check, already diverged in capabilities, guaranteed to drift further.