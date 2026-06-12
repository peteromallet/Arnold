# M6 — Convention & API Enforcement (code only)

## Outcome
The Layer-2 boundary rules, CLI output contract, public-export surface, and node-package
structure are made consistent in code. Docs reconciliation is a separate, final milestone
(M7) — this one is the last *code* milestone, so M7 can describe a settled API.

## Problem (audit lenses 1, 3, 4, 8)
**Layer-2 boundary violations (lens 4):**
- `patches/gguf_unet.py` swaps node classes (`UNETLoader`→`UnetLoaderGGUF`) — that
  *changes handles*, which CLAUDE.md's rule ("changes-handles → block") says is block
  territory. `patches/controlnet.py` adds 3 net-new handle-producing nodes — same issue.
- `patches/ltx_lowvram.py:23-44` hardcodes node IDs from one specific LTX workflow;
  `applies_to` returns True for all LTX graphs but `apply` silently no-ops on any other.
- `patches/types.py:12-16` docstring explicitly licenses adding nodes — contradicting
  CLAUDE.md. `patches/resize_schema.py` is an orphan (not a `Patch`, not registered).

**CLI inconsistency (lens 1):** `commands/analyze.py` and `commands/test.py` define
their own `_emit()` instead of the shared `commands/_output.py:emit`; `nodes spec` and
`validate` ignore `--json`; `validate.py:67 --backend` is a dead, unread argument.

**API/naming (lens 3):** docs claim `load_workflow_json`, `workflow_from_template`, and
`load_template` are importable from `vibecomfy` — none are (verified). `load_workflow_json`
*exists* (`ingest/loader.py`) but is not top-level exported. `run_embedded`/
`run_embedded_sync` are exported via `__getattr__` but missing from `__all__`.
`export_to_json` duplicates `compile("api")`. `ready.py:185` references the ghost
`load_template` alias.

**Node split fiction (lens 8):** every `nodes/*.py` is a 4-line re-export from
`nodes/_generated/`; `.pyi` stubs are duplicated in both dirs.

## Scope
1. **Resolve the patch/block boundary.** EITHER move `gguf_unet`/`controlnet` to
   `vibecomfy/blocks/` (preferred per the rule), OR amend the rule + `patches/types.py`
   docstring to match reality — pick one and apply it consistently. Fix or generalize
   `ltx_lowvram` so it doesn't silently no-op (resolve IDs by class/role, or narrow
   `applies_to`). Register or relocate `resize_schema.py`.
2. **Unify CLI output.** Route `analyze.py`/`test.py` through `_output.py:emit`; make
   `--json` consistent (add where missing on `nodes spec`/`validate`, or document the
   omission); remove the dead `validate --backend` arg. Extract the `fetch.py`/`doctor.py`
   duplicated `_json_path_for_reference`/`_model_entries_for_workflow` helpers.
3. **Align exports with the (eventual) docs.** Export `load_workflow_json` from
   `vibecomfy` (it exists but isn't top-level); add the back-compat aliases
   `workflow_from_template`/`load_template` (docs promise them and `ready.py:185` already
   expects `load_template`) OR remove all references — pick one. Add `run_embedded`/
   `run_embedded_sync` to `__all__`. Decide `export_to_json` vs `compile` (keep one, alias
   the other with a note). Record the final import surface in
   `docs/api/m6-public-api.md` so M7's docs cite the real surface.
4. **Resolve the node split.** Either make `nodes/*.py` genuinely hand-authorable or
   collapse the indirection; remove the duplicate `.pyi` layer so stubs live in one place.

## Locked decisions
- May change public API surface, but only *additively* or to match documented intent.
  Any removal needs a deprecation note.
- **No doc edits here** (that is M7) beyond the `docs/api/m6-public-api.md` handoff.

## Done criteria
- A test asserts the intended top-level importable names actually import.
- One CLI output path; `--json` behavior consistent and tested; no dead args.
- Patch/block boundary is consistent with a single written rule; `ltx_lowvram` no longer
  silently no-ops.
- Node `.pyi` stubs live in one place; the indirection is resolved or justified.
- `docs/api/m6-public-api.md` records the final public import surface.
- M1 golden gate passes; full `pytest` green; CLI smoke green.

## Touchpoints
`vibecomfy/patches/{gguf_unet,controlnet,ltx_lowvram,types,resize_schema,__init__,builtins}.py`,
`vibecomfy/blocks/`, `vibecomfy/commands/{analyze,test,nodes,validate,fetch,doctor,_output}.py`,
`vibecomfy/__init__.py`, `vibecomfy/workflow.py`, `vibecomfy/porting/ready.py`,
`vibecomfy/nodes/` (+ `_generated/`).

## Anti-scope
Do not re-open M2–M5 structural work. **No documentation edits** — README/CLAUDE/AGENTS/
docs are M7. Keep API changes additive except where a documented contract demands a
deprecation.
