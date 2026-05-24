Here's my ranked findings for LENS 10 — Repo hygiene, dead code & duplication:

---

## HIGH

1. **`source_map.py` is completely dead code** — `vibecomfy/source_map.py`. Zero imports anywhere in the entire repo (confirmed via content search for `import.*source_map|from.*source_map` and grep across all `__init__.py` files). The entire 149-line module (182 lines of AST-walking logic including `NodeSourceEntry`, `build_source_map`, `source_map_from_tree`) is unreachable. It also sits at the top of the `vibecomfy/` package rather than in a subpackage like `analysis/` or `registry/`, where similar AST utilities live.

2. **`_literal_value` duplicated 4 times with divergent behavior** — `source_map.py:135`, `readability_inventory.py:190`, `static_contract.py:631`, `analysis/fields.py:204`. Each is a near-identical AST literal evaluator but with different sentinel values (`_UNSUPPORTED` vs `None`), different container-type support (some handle `ast.Subscript`/`ast.Call`, others don't), and different parameter signatures. Fixing a bug means finding all 4 copies.

3. **`_call_name` duplicated 3 times** — `source_map.py:144` and `static_contract.py:898` are *character-for-character identical* (5 lines each: check `ast.Name`→`.id`, `ast.Attribute`→`.attr`, else `""`). `ready.py:241`'s `_ast_call_name` is a third variant adding prefix-dotted resolution. Three modules each rolled their own "get the name of an AST call node."

## MED

4. **`_regen_templates.py` is abandoned one-shot migration debris** — `_regen_templates.py:6–7`. Hardcodes an absolute path to the author's machine (`/Users/peteromalley/Documents/.megaplan-worktrees/vibecomfy-v232`), references v2.3.1→v2.3.2 migration, and is never imported or called by anything. Should have been deleted after the migration.

5. **Generated index files committed despite `.gitignore`** — `node_index.json` and `template_index.json` both exist on disk but are listed in `.gitignore:9–11` as generated artifacts. This is the classic "committed before gitignore was added" problem — `node_index.json` is an empty `[]` (0 bytes of real content) while `template_index.json` is 342KB. Both are tracked repo clutter.

6. **`this.env` contains plaintext API credentials** — `this.env:4–7`. Even though `.gitignore:32` lists it, the file exists on disk with what appear to be actual FAL_API_KEY values in plaintext. A single `git add -f` or pre-gitignore commit would leak these.

## LOW

7. **`__pycache__/` directories tracked across three locations** — `scripts/__pycache__/`, `vibecomfy/porting/object_info/__pycache__/`, and `vendor/ComfyUI/comfy_compatibility/__pycache__/` all contain `.pyc` files for multiple Python versions (3.11, 3.12, 3.14) despite `.gitignore:2` listing `__pycache__/`. Same root cause as #5.

8. **`vendor/.DS_Store` committed** — `vendor/.DS_Store`. macOS artifact in the tracked tree. `.gitignore:4` lists `.DS_Store` but only at root level, not recursively.

9. **`CUSTOM_NODES_AUDIT.md` and `custom_nodes.lock` clutter repo root** — Both sit at `/` alongside `_regen_templates.py`, `asset_manifest.json`, and two generated index files. The root has 7+ "leaf" files that aren't source, config, or standard project files — no clear organizational scheme.

---

**Worst thing in this lens:** The `source_map.py` dead-code module. It's a fully realized, 149-line, import-free module with a dataclass, public API, and 8 private helpers — all untethered from the rest of the codebase. Combined with the 4-way `_literal_value` / 3-way `_call_name` duplication, it suggests copy-paste-driven development without a shared AST utility layer. Deleting it would surface whether the duplicates should be consolidated into one canonical location (likely `registry/` where the richer `static_contract.py` variant lives).