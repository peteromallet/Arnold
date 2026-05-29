# The way through — resolutions for the 11 unknown-unknowns (2026-05-29)

Nine "way-through" architect agents took the unknown-unknowns (UNKNOWN-UNKNOWNS-2026-05-29.md) and found
the concrete path through each, grounded in the real repo + the vendored ComfyUI. **One keystone discovery
collapses half of them.** This doc is the resolution layer; the milestone edits derived from it follow at
the bottom.

---

## THE KEYSTONE: the vendored ComfyUI is the universal backend (resolves #1 partial, #2, #3, #8)

`vendor/ComfyUI/` is a pinned git submodule (`peteromallet/ComfyUI`, `.gitmodules:1-5`) that pip-installs as
the distribution `comfyui` (0.18.2, `vendor/ComfyUI/pyproject.toml:2`). Everything the plan kept deferring
to RunPod or reverse-engineering from a snapshot is **already importable, CPU-only, torch-free, offline**:

- **`convert_ui_to_api(workflow, *, preserve_unknown_nodes=True)`** — `vendor/ComfyUI/comfy/component_model/workflow_convert.py:1122`.
  The real `graphToPrompt`/`ExecutableNodeDTO` port. Pure stdlib + a NamedTuple; needs only the node
  registry (`get_nodes`, raises if empty), no models/GPU. **We already call it** at
  `vibecomfy/ingest/normalize.py:41-46` — but defensively, swallowing errors and falling back to our own
  `_normalize_ui_to_api` (the self-referential trap). The fix: make it the PRIMARY path, let it raise.
- **Live `object_info`** — boot the registry once via `import_all_nodes_in_workspace(disable_all_custom_nodes=True)`
  (`comfy/nodes/package.py:163`), then build schema exactly as the server does (`_node_info`,
  `comfy/cmd/server.py:757`). Real provenance for all ~838 core classes (the 60%-null problem) for free.
  The pinned snapshot (`vibecomfy/porting/cache/object_info/`) demotes to a cache for *custom packs we can't
  import locally* (stub/runpod-snapshot entries).
- **Native subgraph expansion + identity** — `_expand_subgraph` (`workflow_convert.py:765`),
  `_collect_subgraph_defs` (:572). ComfyUI's own identity is the **colon-path exec id** `"54:12"`
  (`instance_path = exec_id.split(':')`, :74) — the locator the UU doc demanded. We ADOPT it, not invent.
- **PNG workflow chunk** — ComfyUI writes via `PngInfo.add_text("workflow"|"prompt", ...)`
  (`comfy/nodes/base_nodes.py:1797-1809`). Backend READ is frontend-JS-only, so our reader is
  `PIL.Image.open(p).text["workflow"]` keyed to the exact chunk names — ~15 lines, no new dep (PIL present).
- **zod schema** — the ONE thing NOT vendored; it lives in the `comfyui-frontend-package` wheel
  (`vendor/ComfyUI/pyproject.toml:22`), pip-installable but not on disk → the conformance gate needs that
  wheel (+ a tiny Node validate step), a separate optional dep.

**Architecture decision:** depend on the vendored/pip ComfyUI as an **optional extra `vibecomfy[comfy]`,
imported in-process** for conversion + schema (CPU, deterministic). Offline default still works via the
pure-Python fallback for installs without the extra; **CI installs the extra and runs the real gate as
blocking**. Add one boot module `vibecomfy/comfy_backend.py` (`ensure_nodes()`, memoized). Determinism
holds: conversion is a pure function of the dict + the frozen submodule SHA.

---

## #1 — Subgraph-scoped identity (foundation reshaper) → ADOPT ComfyUI's locator, key the SCOPE on content

Identity becomes a **path**: `vibecomfy_uid := scope_path + ":" + local_uid`. `scope_path` is "" for
top-level (degrades to exactly the flat M1.5 scalar), else a chain of **stable subgraph-DEFINITION keys**.
The key insight resolving the M2 "never content-derive identity" lock: that rule is about NODES (whose
content users edit constantly) — it does NOT apply to the subgraph-definition BOUNDARY, a near-immutable
library unit. So `sg_key = f"{sg.name}:{blake2b(structural_skeleton)}"` over inner class_types + topology +
wiring, **excluding pos/properties/widget-values AND excluding the volatile graphUuid**. This is stable
even if ComfyUI regenerates the subgraph UUID on save (K5's stated risk) — robust either way.
`local_uid` is minted **per-scope** off the monotonic counter, so clones of "Generate Video" get distinct
inner identities even though their inner integer ids collide. At emit we still write the real `graphUuid`
verbatim and can reconstruct ComfyUI's `"<graphUuid>:<inner_id>"` locator on demand (we hold both).
Verified on corpus: z_image flat node `76` vs inner CLIPTextEncode `67` collide under a flat scalar;
LTX music-video's cloned "Prompt Enhancer" inner ids `2117`/`5058` collide — path-scoping fixes both.
**Critical M2 prerequisite (also the K5 fix):** `copy.deepcopy` the raw `definitions` into
`metadata["definitions"]` BEFORE `resolve_subgraph_helpers` runs (it deletes inner nodes in place,
`convert.py:~186`) — currently MISSING.

## #2 — Frontend validates `properties` (zod) → NAMESPACE + version-match + conformance gate

litegraph round-trips property *values*, but the Vue frontend's zod REJECTS bad shapes on known keys
(`aux_id` format, `ver` semver — ComfyUI#13985, #7309), an un-dismissable editor-open wall. Corpus:
`ver`×1590, `cnr_id`×1526, `aux_id`×550. Resolutions: (a) **namespace ALL our keys under a single
`properties["vibecomfy"]` sub-object** — one key to defend against a future `.strict()` instead of N
top-level keys that get dropped (= identity death); (b) we emit `version: 0.4` (`ui_emitter.py:91`) but the
spec is **1.0** — emit the version matching the ingested source; (c) preserve `cnr_id`/`aux_id`/`ver`
verbatim-and-valid; (d) add a **zod conformance gate** (Node-in-CI against the frontend schema wheel).

## #3 — Wrong container (PNG) → plug into PIL text chunks, ingest belongs in M2

Workflows travel as PNGs (graph in uncompressed `tEXt` "workflow" chunk); share verb is drag-onto-canvas.
Our two emitters already produce both halves: `emit_ui_json()` == the "workflow" chunk, `compile("api")` ==
the "prompt" chunk. **Ingest:** add a `.png`/`.webp` branch in `load_port_source` (`workbench.py:711`) →
`PIL.Image.open(p).text["workflow"]` (fallback `"prompt"`) → existing `normalize_to_api`/`convert` pipeline;
~35 LOC, and all `port` subcommands accept PNGs immediately. **Emit:** `--to png` writer mirroring
`base_nodes.py:1799-1809`; also always emit an A1111-style `parameters` provenance string since
Civitai/OpenArt re-encode and strip the workflow chunk. **Placement: PNG INGEST is an M2 acceptance
criterion** (the primary user's inbound artifact IS a PNG; the "workflow" chunk is the litegraph envelope
M2's furniture capture must be exercised against); PNG emit can trail to M5/M6. Scope M2 to PNG+WebP; punt
JPEG (EXIF). ~100-120 LOC total.

## #4 — In-editor surface (biggest scope add) → real custom-node module + server route, new M7

The `comfyui.custom_nodes` entry point `vibecomfy = "vibecomfy.comfy_nodes"` (`pyproject.toml:43`) is a
**phantom — the module doesn't exist on disk.** First PR makes it real. Mechanism: a thin **frontend
extension (JS, `WEB_DIRECTORY` + `app.registerExtension`) + a server route**
(`@PromptServer.instance.routes.post("/vibecomfy/roundtrip")`) over the SAME Python engine — NOT a graph
node (can't see editor furniture), NOT pure-JS (forks the engine). v1: "Round-trip this graph" → the route
ingests `app.graph.serialize()`, runs `emit_ui_json(recovery_report=[])`, returns graph + report; the JS
renders a **preview/diff** (preserved=green, moved=red, new=flagged) — read-only, never writes, never
overwrites. That visual in-editor proof IS the brand-trust event adoption hinges on. **New milestone M7,
after M5** (nothing to show until positions survive), but **seed the real `comfy_nodes/__init__.py` + a
trivial `/vibecomfy/ping` route in M1.5** so the phantom becomes a live, tested loader path.

## #5 + #7 — Trust UX + observability → wire the report we already compute; preview/backup/never-overwrite

`recovery_report` is already populated per-node (`ui_emitter.py:705-723`) but **never wired to the CLI,
never persisted** (`_cmd_port_export` only does `--to json`, throws it away). The whole way through is
"wire up signals already on the floor." (a) Add a per-node `disposition` enum (preserved / auto_placed /
degraded / refused / dropped) at the existing loop (`ui_emitter.py:709`); promote `recovery_report` to a
typed `NodeDisposition` in `porting/report.py`. (b) Bake provenance into the artifact's `extra.vibecomfy`
(`ui_emitter.py:177`): `vibecomfy_version` (via importlib.metadata, not hardcoded), `object_info_schema_hash`,
`source_schema_version`, `emitted_at`, a `disposition_summary`, and a `report_ref` — the SUMMARY in the
artifact, the per-uid DETAIL in a persisted `out/roundtrips/<id>/report.json` (mirror `runtime/run.py:49-114`
+ `atomic_write_json`). (c) Trust UX in `_cmd_port_export`: **`--dry-run` is the DEFAULT** (follow `repair`'s
posture, `port.py:748`), printing the per-node delta via the inline `difflib` machinery; **auto-backup**
(`shutil.copy2` to `.bak-<ts>`) before any destructive write; **refuse `--out == input`**; refuse
un-round-trippable by default (`--force` to override). (d) First-run legibility: print the summary on every
emit ("no prior layout → fresh" vs "preserved N / new M / refused K"). (e) Opt-in `port share <id>` tars the
already-persisted report — local-first, no auto-send.

## #6 — Untrusted-input compiler → escape free-text (1 confirmed RCE), confine paths, sandbox exec

`repr()` actually holds for all *value* interpolation; the hole is **non-value text**. CONFIRMED RCE:
`emitter.py:2858` interpolates the attacker-controlled subgraph `raw_name` into a triple-quoted docstring
with no escaping — a crafted name closes the docstring and injects a statement that then runs at
`exec_module` (`convert.py:333/466/489`, `scratchpad_loader.py:24`). Ranked: **(1, FIRST FIX, ~15 LOC)**
escape all free-text interpolation (subgraph name/title/source/id at emitter.py:2858-2864, section comments)
+ a malicious-name fuzz regression. **(2, cheap)** one `confine(path, root)` helper at every write base
(`ui_emitter.py:201` `--out` is raw today though the *derived* path right below is already sanitized —
proving the team knows the pattern; also `port.py:163`, `copy_to_recipe.py:37`, `prior_path`). **(3, M6
milestone)** sandbox the validation `exec_module` in a resource-capped, network-denied, CWD-confined
subprocess (clean boundary — gates only consume JSON-serializable `compile("api")` + diagnostics).
**(4, M2/M3)** properties passthrough size/depth caps + key denylist. **(5, M3 policy)** schema collection
must NEVER auto-install untrusted packs (static-AST only; running `__init__` is the LLMVISION vector).
**(6, ongoing)** codegen fuzz oracle. Adopt the untrusted-input-compiler threat-model statement verbatim.

## #8 — Gate sustainability → real gate from the vendored ComfyUI (see keystone)

Layer 0: emit → vendor `convert_ui_to_api` → `compile_equivalent`/`canonical_equal` (`parity.py:200`) — same
canonical machinery, genuinely independent producer; runs offline in CI. Layer 1: rewrite
`schema_freshness.yml` (today diffs the cache against itself) to derive object_info from the booted registry
and FAIL on per-pack hash diff vs committed cache — "live" = the pinned submodule, deterministic. Layer 2:
zod conformance (Node, frontend wheel). Layer 3: RunPod demoted to pack-schema confirmation, with a named
owner + a real alert (today: "email-to-nobody"). Layer 4: coverage ratchet — fail when a corpus/template
uses a class the gate can't verify. Source of truth = pinned `vendor/ComfyUI` submodule + `custom_nodes.lock`;
refresh = a deliberate, reviewed PR. The snapshot can no longer rot silently.

## #9 — Longitudinal → integer-snap precision, store GC/version/migrate, dogfood corpus

Pin canonicalization to **integer-snap (round-half-even to whole pixels)** — the only choice idempotent
under repeated round-trip AND bit-stable through `json.dumps/loads` (2-decimal still drifts); snap at the
single ingest boundary so the store is the coordinate authority. Add the missing **emit→re-emit×N=50
property test** (hypothesis, already a dev dep) with a random structural edit each cycle, asserting
bit-identical pos on uid-matched nodes + the change-report names only edited nodes (cry-wolf guard). Give
the new `layout_store.py` an envelope `{store_version, vibecomfy_version, schema_hash, entries}`, a
`migrate_store` version ladder run on every load, and a `gc(store, live_uids)` (default-on for the `.py`
sidecar where orphans accumulate, opt-in for self-describing `.json`). New CLI: `port store rebuild`
(regenerate sidecar from `.json` — proves "sidecar is a cache") + `port store migrate`. Dogfood: do NOT put
positions in authored `.py`; commit `tests/fixtures/roundtrip_corpus/*.json` of real editor-arranged
workflows and run the convergence + regression suite over them.

## #10 — Bypass firewall + identity unification → one atomic PR + demote ir_node_id

Verified: compile/canonical are inert to furniture today (read only widgets+inputs / class_type+literals+
topology). Bypass is the one deliberate breach: teach compile to drop mode-2 and rewire-around mode-4, and
land it ATOMICALLY in one PR with (1) a `compile_invariance` contract test (byte-identical with/without
uid+furniture — locks the firewall for everything except mode), (2) a full `regenerate_snapshots.py --write`
re-baseline, (3) a real-ComfyUI bypass-equivalence test (the offline normalizer can't see mode). Invariant:
*compile is byte-identical for graphs with no bypassed/muted nodes; for graphs that have them, compile
matches ComfyUI's drop/rewire output.* Identity unification: **`vibecomfy_uid`** is THE durable identity
(sole match/store/`uid=` key); **`ir_node_id`** demoted to execution-internal — STOP writing it to
`properties` (`ui_emitter.py:631`), a stale re-ingested value is exactly how positions get stolen;
**`vibecomfy_id`** stays display-only, never matched. All under `properties["vibecomfy"]`.

## #11 — Success measurement → layout-diff oracle (the gate parity structurally can't express)

No JS/litegraph frontend is vendored (`vendor/ComfyUI` is server+nodes only; the one litegraph artifact is a
links-only NamedTuple, `litegraph_types.py:7`) — so headless PIXEL rendering means a browser in CI. Reject
it. The sacred axis ("positions look right") is fully captured by geometry, not rasterization.

**Tier 0 — layout-diff oracle (build FIRST, ~80 LOC, zero deps, offline).** Canonical layout vector per
workflow keyed by `vibecomfy_uid`: `L(wf) = {uid -> (pos.x, pos.y, size.w, size.h, group_id, mode, collapsed)}`.
Oracle = diff `L(ingest)` vs `L(re-emit)` over the uid intersection → a **drift distribution** (Δpos
histogram p50/p95/max, Δsize, group churn, mode flips, matched/auto-placed/refused/dropped counts).
**Acceptance contract = the falsifiable definition of "faithful":** for every uid-matched node,
`Δpos == 0 ∧ Δsize == 0`. The "8px on every node passes every gate" hoax FAILS this — and the
self-referential parity gate *structurally cannot* express it (parity hashes class_type+literals+topology,
geometry-blind by construction). This is the M5-preserve acceptance gate.

**Tier 1 — SVG snapshot (only if Tier 0 lands).** Draw node bboxes + group rects + link splines from the same
pos/size into a deterministic SVG; golden-image diff catches *relational* wrongness (two nodes both shifted
+200 — zero relative drift but the canvas "feels off", overlap, off-canvas). Regression visual, not gate of
record. Skip headless-litegraph entirely.

**Wild-corpus validation:** 200 real workflows, **PNG-first** (correct the corpus's video bias — target ≥60%
image/edit), scraped from Civitai/OpenArt/comfyworkflows/Banodoco via the PNG `text["workflow"]` chunk
(#3 mechanism). Run ingest→Python→re-emit, score with the layout-diff oracle, report **% survival by failure
class** (parses / opens / drift=0 / degraded / refused / crashed / schema-less / zod-reject) as one stacked
bar. Safety: workflow JSON is metadata (low copyright risk) but store only hashes + per-class outcomes, never
redistribute, and NEVER `exec()` ingested Python unsandboxed in CI (#6 path-traversal).

**Per-persona operational metrics (NOT "tests pass"):** editor-artist = `max Δpos over matched uids == 0`;
engineer = idempotence converges in 1 (emit→re-emit byte-identical, clean git diff); agent = zero
uid-collision under edit-fuzz; team = byte-identical cross-machine. **Leading indicators of "green tests,
wrong product"** (all read off the #5/#7 persisted report): coordinate-drift histogram trending off zero,
degradation-event rate by pack (rising = oracle staleness, #8), re-open-without-edit rate (opt-in telemetry —
a user re-exporting an unchanged file didn't trust the first output). First step: ship the Tier-0 pure
function + land it RED on a synthetic "+8px on one matched node" fixture to prove falsifiability, then make
`max Δpos == 0` the M5 gate.

---

## NET EFFECT ON THE MILESTONES (derived edits — to be applied to m1_5..m6 + a new M7)

- **NEW foundation dependency:** `vibecomfy[comfy]` optional extra + `vibecomfy/comfy_backend.py` (ensure_nodes,
  memoized). Touches M2/M3. The single highest-leverage change in the whole epic.
- **M1.5:** make `comfy_nodes/__init__.py` real (+ `/vibecomfy/ping`); freeze `uid` as the degrade-case of the
  scoped path (not a bare scalar); carry the widget-count crash fix (already noted).
- **M2:** identity = scoped path (`scope_path:local_uid`) adopting ComfyUI exec-id, per-scope minting;
  deepcopy `definitions` before resolver; PNG/WebP ingest as an acceptance criterion; namespace keys under
  `properties["vibecomfy"]`; integer-snap canonicalization at the ingest boundary; capture full verbatim
  `properties`; `mode` → execution IR; properties passthrough caps.
- **M3:** the REAL gate via vendored `convert_ui_to_api` (replace the self-referential oracle); make it the
  primary normalize path (stop swallowing); live object_info freshness; zod conformance + version 1.0; emit
  furniture incl. virtual wires; FIRST TASK widget-count fix via `object_info_widget_order`; schema-collection
  never auto-installs packs.
- **M4:** layout math on integer-snapped coords; tie-break on uid not int id.
- **M5:** scoped-path preserve matching (incl. inner subgraph nodes); the bypass-firewall PR shape;
  identity unification (demote `ir_node_id`); per-uid disposition; emit→re-emit×N convergence test;
  dogfood corpus; the visual/bbox-diff oracle as a done-criterion.
- **M6:** wire `recovery_report` to CLI + persist `out/roundtrips/<id>/report.json`; provenance in artifact;
  `--dry-run` default + auto-backup + never-overwrite + refuse-by-default; `port store rebuild`/`migrate`;
  free-text escaping + path confinement + sandboxed exec subprocess; wild-corpus validation; named gate owner.
- **NEW M7 — In-editor surface:** the custom-node + server-route + JS preview/diff; PNG drag-drop load path.
  The biggest scope add; delivers the feature to the user who never runs a CLI.

This is a scope EXPANSION (the maintainer's standing instruction), and crucially it makes the plan SMALLER
in risk: four reverse-engineered subsystems become thin adapters over ComfyUI's own code.
