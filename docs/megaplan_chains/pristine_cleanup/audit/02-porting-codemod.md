Here is the ranked audit for **LENS 2 — Porting / codemod subsystem**:

---

### HIGH

1. **emitter.py is a 3304-line god-module with no decomposition** — `emitter.py:1-3304`. It contains over 50 functions covering code generation, widget alias resolution, constant hoisting, subgraph handling, type hinting, section grouping, AST formatting, and a 37-line inline `_NODE_HELPER_SOURCE` string literal (`emitter.py:3251-3287`). `_emit_build_function` alone spans 300+ lines (`emitter.py:1687-1987`), and `_node_kwargs` spans ~270 lines (`emitter.py:2727-2990+`). Everything is smashed into one file.

2. **`_sort_key` identically copy-pasted across two modules** — `widget_aliases.py:473-477` and `workbench.py:920-924`. Same 4-line function with zero divergence. No shared utility module. This is the clearest "someone forgot it already existed" smell.

3. **`OPAQUE_COMPONENT_CLASS_RE` duplicated with inconsistent implementation** — `workbench.py:41` uses `_OPAQUE_COMPONENT_CLASS_RE` with `[0-9a-fA-F]` mixed-case character class; `strict_ready.py:27` uses `OPAQUE_COMPONENT_CLASS_RE` with `[0-9a-f]` + `re.IGNORECASE`. Same regex, different approach, different visibility prefix (`_` vs public). Two files reinventing the same wheel differently.

4. **`UI_ONLY_CLASS_TYPES` defined twice** — `emitter.py:122` and `helpers.py:7` both define `frozenset({"Note", "MarkdownNote"})`. `helpers.py` exports it; `emitter.py` ignores `helpers.py` entirely and defines its own. `emitter.py:1125` then uses its local copy instead of importing from `helpers`.

### MEDIUM

5. **Widget-key translation implemented in three separate places** — `_translate_widget_for_key` at `emitter.py:541-557` parses `widget_N` and delegates to `widget_aliases.resolve_widget_key_with_provenance`, but an inner closure `_translate_widget` at `emitter.py:2768-2771` does the identical parse-then-delegate inside `_node_kwargs`. `widget_aliases.py` also has both `resolve_widget_key` and `resolve_widget_key_with_provenance` with overlapping dispatch.

6. **`_readability_diagnostics` (workbench.py:937-1079) reimplements widget-alias analysis already in `widget_aliases.py`** — It manually iterates `widget_N` keys, checks alias range boundaries, detects unresolved widgets. `widget_alias_analysis` (`widget_aliases.py:337`) and `unresolved_widget_aliases` (`widget_aliases.py:301`) already do the same work. Two divergent code paths for the same analysis.

7. **`_looks_like_model_value` is private in `convert.py:732` but cross-imported by `workbench.py:1087`** — A private `_`-prefixed function in one module is imported and used by another. Either it belongs in a shared location, or it should be public in `convert.py`.

8. **Three parallel diagnostic dataclasses with no shared base** — `EmissionDiagnostic` (`emitter.py:52`), `PortIssue` (`report.py:19`), and `LintDiagnostic` (`lint.py:17`) all carry `code`, `message`, `severity`, `node_id`, `class_type`, `detail`. No shared protocol or base. `convert.py` manually maps `EmissionDiagnostic` → `PortIssue` during validation (`convert.py:241`).

9. **`_strict_template_style_diagnostics` (workbench.py:1152-1198) checks only 1 thing vs `lint_ready_template` (lint.py:44-76) checking 8** — Two modules both claim to lint/check ready-template source. `lint.py` has a full 8-rule AST scanner (integer suffixes, UUID names, set_id_map, duplicate PUBLIC_INPUTS, finalize kwargs, raw_call, outputs, custom_node_packs). `workbench.py:1152` only checks for `def _node` in source text. Unclear why these aren't one linter.

### LOW

10. **`WIDGET_SCHEMA` and `WIDGET_SEMANTIC_NAMES` are separate dicts in the same file (`widget_schema.py:11,19`) but resolved at different precedence tiers in `widget_aliases.py:155,160`** — The schema dict is tier-2 and semantic-names is tier-3, yet they serve the same purpose (mapping class → positional widget names). Unclear why they aren't a single merged source.

11. **`_subgraph_topological_order` (`emitter.py:2053-2081`) implements a local recursive DFS cycle-detector** — The closure `visit()` mutates outer-scope lists (`ordered`, `temporary`, `permanent`) and raises `RuntimeError` on cycles. No sharing with any other topological sort in the codebase.

---

### Worst thing in this lens

**`emitter.py` as a 3304-line god-module** (`emitter.py:1-3304`). It is the root cause of most other findings: diagnostics types are siloed there instead of shared, widget translation is re-implemented inside it, inline strings bloat the module, and responsibilities from codegen to formatting to import management to constant-hoisting are all commingled. The file has no internal partitioning — every function after line ~1500 is a private helper that callers elsewhere in the porting subsystem cannot reach without importing the whole emitter surface.