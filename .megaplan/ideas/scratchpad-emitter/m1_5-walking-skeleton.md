# M1.5 — Walking skeleton: prove the whole round-trip loop end-to-end, early  [partnered tier]

## Outcome
ONE concrete, eyeball-able demonstration that a node position survives a full
`editor JSON -> VibeComfy Python -> editor JSON` round-trip, cutting the thinnest possible path through
identity + capture + emit + restore. Everything not essential to proving the loop is hardcoded or
stubbed. This inverts the epic's risk: instead of proving the round-trip works only at M5 (after four
milestones of infrastructure), we prove the riskiest integration — *does a hand-placed position actually
survive against the REAL ComfyUI editor?* — in milestone one, then thicken each dimension with confidence.
The original (merged) M1 already shipped identity that was never read back; this slice exists so that
class of "built on sand" failure is caught immediately.

## Why before M2 — and how it avoids double-building identity (Phase-B correction)
"Make it work" means the loop runs end-to-end on something real, early, then gets better. The slice's
seams ARE the later milestone boundaries, so M2-M6 become "broaden one stubbed dimension" rather than
"build a new layer." To make that real (and not a merge-collision generator), **M1.5 OWNS and FREEZES the
interface contracts the later milestones fill in** — the `VibeNode.uid` field, the uid-resolver signature,
and the layout-store/`.py` `uid=` schema. M2 is then reframed as "**broaden** M1.5's identity+capture to
full furniture + the legacy hash bridge + duplicates," NOT "introduce identity." They share one owner and
one interface; M2 never redefines what M1.5 froze.

It does NOT change the M0 gate (still: commit m3-seams-ir work, retarget PR #26 to main, green suite).
**Subject: a minimal FLAT editor JSON** (loader -> sampler -> save, ~3-5 nodes) with real `pos` values and
**verified to have NO `definitions.subgraphs`** (grep the file first). Do **NOT** use `z_image` — it ships
subgraphs, which the slice deliberately stubs, so it would hit a stubbed dimension on step one. If no
clean flat corpus file exists, hand-make a tiny editor JSON for the slice.

## Scope IN (the minimum from each layer)
- **From M2 (identity + capture) — and FREEZE these interfaces here:** add the `uid` field to `VibeNode`;
  on ingest read `properties["vibecomfy_uid"]` if present, else mint once from the **dumbest stable
  extrinsic seed** — the explicit `raw_call id=` / the litegraph integer id captured at this ingest (NOT a
  content/WL hash, NOT `uuid4`); persist it into `properties` on emit and as a `uid=` kwarg in the
  generated `.py`. Capture `pos`/`size` so the emitted `.json` is self-describing (uid in properties + pos
  on the node); also write the regenerable sidecar `<file>.layout.json` for the `.py` form (K3: positions
  already reach `metadata["_ui"]`). **Stub:** capture only `pos`/`size` (ignore groups, mode, color,
  definitions, notes); minting is the dumb extrinsic seed only — the full multi-tier mint + legacy bridge
  is M2/M5. The `VibeNode.uid` field, the resolver signature, and the store/`uid=` schema defined here are
  **frozen contracts** M2 extends, not replaces.
  - **[Phase-D] Freeze `uid` as the DEGRADE CASE of a scoped path**, not a bare scalar: shape it as
    `scope_path + ":" + local_uid` where `scope_path == ""` for top-level (collapses to today's scalar).
    M2 then *extends* the path for subgraph-inner nodes rather than *replacing* the scalar. One-line shape
    change now, zero added skeleton scope — but it prevents a foundation rewrite when subgraph identity lands.
- **From M3 (emit + wire CLI):** wire `port export --to ui` -> `emit_ui_json` -> disk (the import exists
  at `commands/port.py:39`; the handler rejects non-json today). Emit `properties["vibecomfy_uid"]` on
  every node. **Stub:** keep the existing stub-grid layout for any node WITHOUT a stored position; no
  object_info oracle, no provider swap, no recovery report.
- **[Phase-C] MUST also carry the widget-count crash fix.** The skeleton's subject includes a KSampler
  (seed + control_after_generate trailing slot), so `emit_ui_json` hits the
  `assert len(widget_values) <= expected_widget_count` crash (`ui_emitter.py:657`) the instant it runs.
  So the skeleton lands the minimal version of M3's first task: derive the expected count from
  `object_info_widget_order` (already encodes the trailing `None` extras) and downgrade the bare `assert`
  to a non-fatal report. Without this the skeleton cannot emit anything real. (M3 generalizes/hardens it.)
- **From M5 (restore):** in `emit_ui_json`, before falling back to `_stub_layout`, look up each node's
  uid in the sidecar and use the stored `pos`/`size` if found. **Stub:** uid exact-match only — no
  structural-hash fallback, no duplicate disambiguation, no constrained placement for new nodes.
- **[Phase-D] Make the phantom in-editor foothold REAL (tracer for M7).** `pyproject.toml:43` declares a
  `comfyui.custom_nodes` entry point `vibecomfy = "vibecomfy.comfy_nodes"` but the module does not exist on
  disk. Create `vibecomfy/comfy_nodes/__init__.py` (export `WEB_DIRECTORY`, empty `NODE_CLASS_MAPPINGS`) +
  a trivial `@PromptServer.instance.routes.get("/vibecomfy/ping")`, and confirm via
  `entry_points().select(group="comfyui.custom_nodes")` that the vendored server loads it. Turns the
  phantom into a live, tested loader path so M7 builds on something real — and gives the "primary user
  never touches Python" risk an owned home from day one. (No round-trip logic here; just the loader.)

## Scope OUT (explicitly deferred — NOT thrown away; each is a milestone that thickens a stub)
Layout intelligence (M4), the independent object_info oracle (M3), structural-hash fallback + duplicate
safety (M5), groups/notes/reroutes/mode/color/subgraph furniture (M2/M3), schema-provider determinism
swap (M3), `--fresh`/`--from` flags + recovery report (M6).

## Acceptance demonstration (genuine, human-runnable — NOT a tautological test)
Per the maintainer's standing instruction, the acceptance is the actual product loop run by hand with the
**real ComfyUI editor as the oracle**, not a unit test asserting an internal value:
```
# SUBJECT = a flat (no-subgraph) editor JSON with real positions; call it flat.json.
# 1. Convert it -> writes a uid= kwarg per node in flat.py + a regenerable flat.layout.json
python -m vibecomfy.cli port convert flat.json --out out/scratchpads/flat.py
# 2. Emit a UI view from the Python
python -m vibecomfy.cli port export out/scratchpads/flat.py --to ui --out out/flat_emit.json
# 3. Proof A (offline): a node's pos in flat_emit.json == its pos in the original flat.json (not a grid cell)
# 4. Proof B (real oracle): open out/flat_emit.json in the ComfyUI editor -> the node sits where it sat
# 5. Proof C (the keystone, end-to-end): drag it in the editor, save, re-run convert+export ->
#    the new position survives. Confirms K1's uid-in-properties claim against the RUNNING editor.
# 6. Proof D (edit-invariance): change a widget value in flat.py, re-export -> the node KEEPS its position
#    (proves identity is extrinsic, not content-derived — the Phase-B fatal-flaw guard).
```

## Done criteria
- The demo above runs end to end on the flat subject; Proof A passes offline.
- **[auto-merge] The gate is MACHINE-checkable** (the chain auto-merges unattended — no human-in-the-loop
  gate). Proof B/C become an **automated editor-open smoke**: boot the vendored ComfyUI via
  `comfy_backend.ensure_nodes()`, run its `convert_ui_to_api` on `flat_emit.json` (and/or load it through
  the server load path), assert zero "node type not registered" / dangling-link errors and that the
  uid-matched node's `pos` equals the source. A human opening it in the real editor is an OPTIONAL post-hoc
  confidence step, NOT the gate.
- **Proof D (edit-invariance):** changing a widget value does NOT move a node's preserved position —
  the guard against the Phase-B content-addressing flaw (automated).
- uid minting is deterministic (same source -> same uids -> same emitted positions) AND edit-invariant.
- `compile("api")` for the subject is unchanged by the slice (furniture inert; K3).

## Risks retired early (the whole point)
1. The keystone end-to-end: does `properties["vibecomfy_uid"]` survive a REAL ComfyUI save (not just
   litegraph source, which K1 read)? Highest-leverage unknown — retired in milestone one.
2. Furniture inertness in practice: emitting pos + uid doesn't break load/compile for a real workflow.
3. The CLI seam: `convert` (writes layout) <-> `export --to ui` (reads layout) plumbing works.
4. The sidecar/uid data-model shape is workable before M2 hardens it.

## Risks NOT retired (honestly)
Duplicate-node identity, layout quality, schema-less correctness, subgraph round-trip, multi-cycle
position drift, the full determinism guarantee under structural edits — genuinely M2-M5 concerns.

## Touchpoints
- `vibecomfy/workflow.py` (uid field), `vibecomfy/ingest/normalize.py` + `vibecomfy/porting/convert.py`
  (read-back/derive uid, capture pos -> sidecar), `vibecomfy/porting/layout_store.py` (new, minimal),
  `vibecomfy/porting/ui_emitter.py` (restore-by-uid before stub), `vibecomfy/commands/port.py` (wire
  `--to ui`), `vibecomfy/testing/canonical.py` (reuse `canonical_form` for the derivation).

## Anti-scope
- No layout engine, no oracle, no furniture beyond pos/size, no hash fallback, no flags/docs. Resist
  thickening any stub here — that is what M2-M6 are for. Do not write throwaway tests; the acceptance is
  the real loop against the real editor.
