## LENS 3 — Public API Surface & Naming Audit

### HIGH

1. **Documented back-compat aliases `workflow_from_template` and `load_template` do not exist anywhere in the source.**
   `AGENTS.md:61` states both are "kept as back-compat aliases." Zero definitions, zero imports anywhere in the package. `ready.py:185` still checks AST for `"load_template"` — dead code predicated on a ghost alias. This directly contradicts a stated project convention and would cause a user following the docs to hit `AttributeError`.

2. **`run_embedded` and `run_embedded_sync` are runtime-exported via `__getattr__` but omitted from `__all__`.**
   `__init__.py:26` puts them in `_RUNTIME_EXPORTS`; `__init__.py:73-75` lists only `"run"` and `"run_sync"`. `from vibecomfy import *` silently misses half the runtime surface. `run_embedded_sync` is the primary Artifact runner (`artifacts.py:39`) yet invisible to star-import.

3. **`load_workflow_json` is documented as a first-class loader but not exported from the top-level package.**
   `AGENTS.md:59` table-lists it alongside `workflow_from_file` etc. It's defined at `ingest/loader.py:8` but never appears in `vibecomfy/__init__.py`'s imports or `__all__`. `cli_loader.py:6` imports it internally, so the chain works, but a user hitting `vibecomfy.load_workflow_json` gets `AttributeError`.

### MEDIUM

4. **`VibeInput` has dual names for the same field: `media_semantics` (dataclass field) and `media` (property alias).**
   `workflow.py:61` defines `media_semantics: str | None`, `workflow.py:70-76` exposes `media` as a getter/setter wrapping it. `register_input` (`workflow.py:199-200`) accepts *both* `media_semantics` and `media` parameters with collision detection. This leaks an internal rename into the public API and forces callers to guess which is canonical.

5. **`VibeWorkflow.export_to_json` is just `compile("api")` under a different name.**
   `workflow.py:483-486` — literally `return self.compile("api")`. Two public methods that do the exact same thing. The redundancy forces users to wonder which is preferred; AGENTS.md only documents `compile`.

6. **`blocks/__init__.py` re-exports `Handle` in its `__all__`, but `Handle` is defined in `vibecomfy/handles.py`.**
   `blocks/__init__.py:114` lists `"Handle"` in `__all__` even though the import chain is `from vibecomfy.handles import Handle` at `blocks/__init__.py:9`. `vibecomfy/__init__.py:1` also imports `Handle` directly from `.handles`. Two subpackage `__all__` lists claim ownership of the same symbol.

### LOW

7. **`Handles` (container class) and `Handle` (single handle) differ by one character and sit side-by-side in `blocks.__all__`.**
   `blocks/__init__.py:114` — `"Handle"` and `"Handles"` exported together. Easy to misread/mistype, especially for newcomers. No disambiguation in docstrings.

8. **`set_input` silently writes to `node.widgets` when the field isn't in `node.inputs`.**
   `workflow.py:229-232` — the method name says "set input" but mutates widgets as a fallback. This conflates two distinct ComfyUI concepts under a single verb, which is a semantic leak in the public method name.

9. **`router` module imported at `__init__.py:13` with `__all__` inclusion but exposes only `RouterResult` and `pick` — no `router`-prefixed naming convention.**
   `router.py:51` — `__all__ = ["RouterResult", "pick"]`. The function `pick` is a terse, non-descriptive verb floating at package level. No `router_pick` or `route` wrapper; inconsistent with the noun-like naming of sibling exports (`load_workflow_any`, `workflow_from_file`).

---

**Worst thing in this lens:** The AGENTS.md-documented back-compat aliases `workflow_from_template` and `load_template` **do not exist** anywhere in the code. This isn't a style nit — it's a documentation falsehood that would break any user or tool relying on the stated contract. The AST classifier in `ready.py:185` still references `load_template`, proving the alias was planned/expected but never wired.