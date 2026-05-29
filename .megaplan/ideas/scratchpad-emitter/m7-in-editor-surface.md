# M7 — In-editor surface: the round-trip reaches its primary user  [partnered tier — Phase-D add]

## Outcome
The editor-first ComfyUI artist — the stated PRIMARY user — **never runs a CLI**. Today the entire round-trip
is `.py` files + `port` commands, so the feature is invisible to the person it's for; adoption can only flow
through engineers as intermediaries (Phase-D U-U #4). M7 delivers a **zero-Python in-editor touchpoint**: the
artist, inside ComfyUI, triggers "Round-trip (VibeComfy)" and gets a visual preview/diff proving their layout
survives — then applies it. This is the brand-trust event adoption hinges on, and it reuses the SAME engine
the CLI does (one engine, two surfaces).

## Grounding (Phase-D way-through D)
- `pyproject.toml:43` declares `[project.entry-points."comfyui.custom_nodes"] vibecomfy = "vibecomfy.comfy_nodes"`
  — but **`vibecomfy/comfy_nodes/` does not exist on disk**. The foothold is a phantom; M1.5 makes it real
  (a live, tested loader path) so this milestone builds on something that already loads.
- The vendored fork enumerates that group at `vendor/ComfyUI/comfy/nodes/package.py:205` and reads three
  attributes off the loaded module: `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`, `WEB_DIRECTORY`
  (`package.py:74-89`). That is the entire surface contract.

## Locked decisions (do not relitigate)
- **Mechanism = thin frontend extension (JS) + thin server route, over the existing Python engine.** NOT a
  graph node (executes only in a prompt run; can't see whole-editor furniture — positions/groups live in the
  frontend, not the API prompt) and NOT pure-JS (forks the engine, can't reach object_info/schema). This is
  how Manager / comfyui-deploy / pydn / rgthree operate.
  - Frontend: `WEB_DIRECTORY` → a `.js` that `app.registerExtension(...)` adds a "Round-trip (VibeComfy)"
    command (selection toolbox / top menu).
  - Server: `@PromptServer.instance.routes.post("/vibecomfy/roundtrip")` receives `app.graph.serialize()`,
    ingests it through the SAME path the CLI uses (`emit_ui_json`, `ui_emitter.py:457`), returns
    `{graph, report}`.
- **v1 is READ-ONLY: never writes a file, never touches the input.** It returns the round-tripped graph + the
  recovery report (the per-uid disposition from M6); the JS renders a **preview/diff** — preserved=green,
  moved=red, new=flagged, refused=named — and the artist clicks Apply (loads it into the editor) or Cancel.
  Read-only v1 also sidesteps the path-traversal write surface (M6/security) entirely.
- **One engine.** All correctness stays in `porting/` (CLI-tested via `test_ui_emitter_parity.py`); the route
  is ~30 lines of glue. A frontend break degrades to "button missing", never "wrong graph."
- **PNG drag-drop load path** belongs here too: the editor-first artist drops a PNG onto the canvas; verify
  our emitted PNG (M5/M6) opens via drag AND File>Open (different code paths the parity gate never tested).

## Scope
- `vibecomfy/comfy_nodes/` real module: `__init__.py` exporting `WEB_DIRECTORY="./web"` + empty
  `NODE_CLASS_MAPPINGS={}`, importing `routes.py` so the POST route registers on load; `web/*.js` extension.
- The `/vibecomfy/roundtrip` route (read-only) + the in-editor preview/diff UI rendering M6's disposition report.
- Drag-drop + File>Open verification of emitted artifacts (.json and .png).

## Open questions (resolve during planning)
- Exact frontend API surface to use (command vs sidebar vs modal) — pin a frontend version; keep to the most
  stable primitives (a command + a modal). The frontend is the fastest-moving part of ComfyUI.
- Whether "Apply" eventually also offers "save Python" (export to a `.py`), or stays layout-only in v1.

## Constraints
- Reuse the core engine; no logic forked into JS. Pin a ComfyUI frontend version; degrade gracefully.
- No new round-trip semantics — this is a surface over M2-M6. Read-only in v1 (no write/overwrite surface).

## Done criteria
- An artist, in a running ComfyUI (vendored), triggers "Round-trip (VibeComfy)" and sees a preview/diff of
  their current graph with per-node disposition; Apply loads it; positions of unchanged nodes are visually
  intact. No CLI, no `.py`, no `uv sync` touched by the artist.
- The route reuses `emit_ui_json` + the M6 report; zero round-trip logic lives in the JS.
- Emitted `.json` and `.png` both open via drag-drop AND File>Open without errors.

## Touchpoints
- `vibecomfy/comfy_nodes/{__init__.py,routes.py,web/*.js}` (new), reuse `vibecomfy/porting/ui_emitter.py` +
  the M6 report/provenance, `vendor/ComfyUI` custom-node + server-route loading.

## Anti-scope
- No new layout/preserve/identity logic (M2-M5). No write/overwrite from the editor in v1 (preview+apply only).
- No reimplementation of the engine in JS. JPEG/EXIF container support (PNG/WebP only, from M2/M5).
