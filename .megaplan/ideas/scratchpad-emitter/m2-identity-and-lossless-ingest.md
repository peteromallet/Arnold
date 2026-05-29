# M2 — Durable node identity + lossless ingest  [premium tier — the real foundation]

## Outcome
**Broadens the M1.5 walking skeleton** (which froze the `VibeNode.uid` field, the uid-resolver signature,
and the store/`uid=` schema and proved the loop end-to-end on one flat workflow) into a node identity that
**survives the full JSON -> Python -> JSON round-trip by construction** for the whole corpus, plus an
ingest path that **stops throwing away** the layout and editor furniture it currently captures-then-drops.
M2 does NOT introduce identity — it extends M1.5's frozen contracts to full furniture, duplicates, and the
legacy hash bridge. After M2 the data needed to round-trip positions exists and is durable; M3 emits it,
M4 lays out what's missing, M5 preserves it.

Grounding (verified 2026-05-28, see ROBUSTNESS-REVIEW-2026-05-28.md): today `ir_node_id` is a
write-only stamp (`porting/ui_emitter.py:631`) that ingest never reads back; ids reset to the
litegraph integer on re-ingest (`_next_node_id` = max+1, `workflow.py:637`). Ingest captures the raw
litegraph node into `VibeNode.metadata["_ui"]` (`ingest/normalize.py:95` -> `porting/convert.py:144`)
but `pos`/`size`/`groups`/`mode`/`color`/`definitions` then die: the Python emitter never serializes
them and `emit_ui_json` ignores them. So the round-trip cannot preserve anything yet.

## Locked decisions (do not relitigate)  [updated by clarity phase K1-K5, Phase-D way-through]
- **[Phase-D KEYSTONE] Identity SCOPE and conversion plug into the vendored ComfyUI, not a snapshot.**
  `vendor/ComfyUI` is a pinned submodule that pip-installs as `comfyui` (CPU-only, torch-free, offline).
  Add an optional `vibecomfy[comfy]` extra + a memoized `vibecomfy/comfy_backend.py` (`ensure_nodes()` via
  `import_all_nodes_in_workspace(disable_all_custom_nodes=True)`). M2 uses it for: (a) ComfyUI's own
  **subgraph exec-id locator** `"graphUuid:localId"` (`workflow_convert.py:74`) as the identity scope we
  ADOPT; (b) `_collect_subgraph_defs`/`_expand_subgraph` (`:572`/`:765`) instead of re-deriving expansion.
  Offline-without-the-extra still works via the existing pure-Python path; CI installs the extra.
- **[Phase-D] Identity is a SCOPED PATH, not a flat scalar.** `vibecomfy_uid := scope_path + ":" + local_uid`.
  `scope_path == ""` for top-level (degrades to M1.5's scalar exactly). For subgraph-inner nodes,
  `scope_path` is a chain of stable **subgraph-DEFINITION keys** `sg_key = f"{sg.name}:{blake2b(skeleton)}"`
  over inner class_types + topology + wiring, **excluding pos/properties/widget-values AND the volatile
  graphUuid** (so it's stable even if ComfyUI regenerates the UUID on save — K5's risk, neutralized).
  `local_uid` is minted **per-scope** off the monotonic counter, so cloned subgraphs ("Generate Video" ×4)
  get distinct inner identities despite colliding inner integer ids. The "never content-derive identity"
  rule still holds for NODES; it does not apply to the near-immutable subgraph-definition BOUNDARY. Verified:
  z_image flat `76` vs inner `67` collide under a flat scalar; LTX cloned "Prompt Enhancer" inner `2117`/`5058`
  collide — scoping fixes both.
- **Identity = an EXTRINSIC, ASSIGNED-ONCE uid carried IN the artifacts — NEVER derived from content.**
  Add `uid` as a **real `VibeNode` field** (K2: `VibeNode` is a plain `@dataclass(slots=True)`, `metadata`
  is unconstrained, `contracts/ir.py` imposes no shape limit — a field is clean and survives
  `finalize_metadata`/`compile`, which never renumber). Do NOT key identity on an int-id-in-metadata: K2
  confirmed `_next_node_id` now **gap-fills** (lowest-unused), so integer ids are **reused** on delete+add.
  - **Why NOT content-addressed (Phase-B correction to the U1 resolution).** Phase A proposed deriving the
    uid from a `blake2b` over the Weisfeiler-Lehman label in `testing/canonical.py`. Two independent
    red-team reviewers showed this is **self-defeating**: that WL label folds in **widget values AND
    neighbor labels over 4 hops** (`canonical.py` `_literal_kwargs` includes widgets; refinement
    propagates upstream+downstream). So editing a widget (change a prompt/seed/cfg) OR inserting a node
    changes the uid of that node AND every node within 4 edges — losing exactly the positions preserve
    exists to protect, on exactly the edits users make most. **You cannot derive a stable identity from
    the thing that changes.** Identity must be extrinsic and assigned once.
  - **Where the uid lives (the durable carriers — the emitted artifacts ARE self-describing):**
    1. emitted UI JSON: `properties["vibecomfy_uid"]` (K1: survives Open->drag->Save) + the node's `pos`
       in the same JSON. So a shared `.json` round-trips identity+position with NO sidecar.
    2. Python source: an explicit **`uid=` kwarg per node**, written by the emitter/convert — the SAME
       mechanism the `.py` already uses for `id="98"` (see `ready_templates/image/z_image.py`). This is
       the durable identity home for authored/Python code. (The Phase-A "do not write uids into `.py`"
       rule was the root error — without it, authored code has no edit-invariant identity.)
  - **Minting (only when a node has NO carried uid yet — first appearance):** assign once from a STABLE
    EXTRINSIC seed, then persist into the carriers above:
    - `raw_call` node with explicit `id=` -> `uid = f(workflow_id, "id:"+id)` (the id is already a stable
      extrinsic key in the `.py`);
    - typed-wrapper node -> seed from its **authored creation order** in `build()` (stable across re-runs
      of the same source; reordering source is a source edit, acceptable/rare degradation) — never the
      reused gap-filled `_next_node_id` integer;
    - first ingest of a pre-existing editor JSON with no uid -> seed from the litegraph integer id
      captured AT that ingest, assigned once, and persisted immediately (into `properties` on next emit
      and into the generated `.py` `uid=`).
    The seed makes minting **deterministic** (same source -> same uids: satisfies M4) AND **edit-invariant**
    (widget/wiring edits don't move the seed: satisfies preserve). Determinism of the *emit* never required
    content-addressing — it required a reproducible seed, which source order is.
  - **Structural/WL hashing is NOT used here.** It is demoted to the **M5 legacy bridge only** — matching
    nodes that carry no uid at all (neither property nor `uid=`), best-effort, and on a successful match it
    **mints + persists** a uid so the next round-trip is exact. Never the primary key.
  - The uid is immutable for the life of a node; never reuse one. `ir_node_id` / int id are
    secondary/display keys only.
- **Layout + furniture become first-class, persisted, keyed by uid — but OPTIONAL.** Preservation is
  best-effort *maximized*: present data is kept faithfully; absent (Python-authored code) degrades
  gracefully to M4's fresh layout. No required sidecar, no failure when furniture is missing.
- **Persistence: the emitted UI JSON is SELF-DESCRIBING; the sidecar is only the `.py` form's cache
  (Phase-B correction).** ComfyUI users share a single `.json` (or a PNG with embedded workflow, or paste
  into Load) — a sidecar does NOT travel with any of those. So the durable layout record must live INSIDE
  the emitted `.json`: per-node `pos`/`size`/`flags`/`color` on the node, `uid` in `properties`, and the
  graph-level `groups[]`/`extra.ds`/Note+Reroute furniture/subgraph `definitions`/`state.lastRerouteId`
  in their native top-level slots. A `.json` round-trips fully on its own — **no sidecar needed for
  JSON<->JSON**.
  - The **sidecar `<workflow>.layout.json` exists only because the Python `.py` form has nowhere to put
    `pos`** — it is the layout memory for the *Python* representation, keyed by uid, and must be
    **regenerable from any emitted `.json`** (it is a cache, not a source of truth). Losing it degrades a
    `.py`-only workflow to fresh layout; it never affects a shared `.json`.
  - Invariant to test explicitly: "user B receives only the `.json`" round-trips with full position
    fidelity (no sidecar present).
- **`mode` (bypass=4 / mute=2) is NOT layout — it is EXECUTION semantics (K3 correction).** Real
  ComfyUI drops muted nodes and rewires around bypassed ones; VibeComfy's offline normalizer ignores
  `mode`, so a bypassed node currently round-trips ACTIVE = silent semantic corruption. M2 must capture
  `mode` into the **execution IR** (e.g. `VibeNode.metadata["mode"]` on the node, not the layout store);
  M3 owns the bypass-emit policy. Do not file `mode` under furniture.
- **The editor owns layout; the latest editor layout wins.** Every ingest of an editor JSON refreshes
  the store from that JSON's `pos`/furniture. This answers "what do we do with the new positions."
- **`port convert` must stop being lossy.** The per-node data is already in `metadata["_ui"]` (K3);
  M2 routes it into the store. Subgraph `definitions` must be **deep-copied into `metadata["definitions"]`
  BEFORE `resolve_subgraph_helpers` runs (K5: the resolver deletes inner nodes in place at
  ~`convert.py:186`)**. `compile("api")` output stays byte-identical for pure layout (K3 proved
  inertness; `mode` is the deliberate exception and goes through the execution path, not the store).

## Scope
- `vibecomfy/workflow.py`: add the durable `uid` (mint in node creation / `_next_node_id` path);
  ensure `finalize_metadata` / id remaps never mutate it. Coordinate with the in-flight
  `contracts/ir.py` so uid is part of the stable IR contract.
- `vibecomfy/ingest/normalize.py` + `vibecomfy/porting/convert.py`: read `properties["vibecomfy_uid"]`
  (mint if absent); capture `pos`/`size`/`flags`/`color`/`bgcolor` + the **full verbatim `properties`
  blob** per node, top-level `groups[]`/`extra.ds`/`state.lastRerouteId`, **Note + Reroute + Get/SetNode
  virtual-wire furniture (with their routed endpoints, keyed by uid)**, and `definitions` (incl.
  inner-node ids/pos) into the uid-keyed store. Capture `mode` into the execution IR (node metadata).
  Capture the widget-vs-input "converted input" state so it can be restored. Do NOT change what reaches
  the execution API graph (virtual wires still resolve to direct links there).
- `vibecomfy/workflow.py`: minting uses a **monotonic never-reused per-workflow uid counter** at
  `add_node`/`raw_call` (decoupled from the gap-filling `_next_node_id` integer) so agent/structural
  edits are uid-safe. Coordinate values are **canonicalized to fixed precision** wherever the store holds
  or compares them.
- New `vibecomfy/porting/layout_store.py`: `load_store(path)`, `write_store(path, data)`, schema/version,
  default path resolution next to the `.py`/emitted JSON.
- **[Phase-D] `vibecomfy/comfy_backend.py` (new):** `ensure_nodes()` boots the vendored ComfyUI registry
  (memoized) so M2's identity scope can adopt ComfyUI's exec-id locator and reuse `_collect_subgraph_defs`/
  `_expand_subgraph` rather than re-deriving. Behind the optional `vibecomfy[comfy]` extra; pure-Python
  fallback when absent.
- **[Phase-D] PNG/WebP ingest branch** in `load_port_source` (`vibecomfy/porting/workbench.py:711`):
  `PIL.Image.open(p).text["workflow"]` (fallback `"prompt"`) -> existing normalize/convert pipeline. ~35 LOC.
- **[Phase-D] Store lifecycle in `layout_store.py`:** envelope `{store_version, vibecomfy_version,
  schema_hash, entries}`; `migrate_store` version ladder on load; `gc(store, live_uids)` (default-on for the
  `.py` sidecar). CLI surface (`port store rebuild`/`migrate`) is wired in M6.
- **[Phase-D] Identity scope helper:** `scope_path` derivation (`sg_key = name+blake2b(skeleton)`) keyed off
  the deep-copied `metadata["definitions"]`; minting is per-scope.
- Subgraph inner-id recovery (M1 open question, resolved = "not recoverable today"): carry `definitions`
  verbatim so inner nodes keep stable ids/uids and M4 group boxes can anchor to them. Run helper
  resolution only on a compile-time copy.
- Migration: for legacy nodes with no uid and no stored layout, M5's hash fallback mints + persists a
  uid on first round-trip; M2 only needs to make minting + read-back exist.

## Open questions (resolve during planning)
- RESOLVED (Phase-D): coordinate canonicalization = **integer-snap (round-half-even to whole pixels)** —
  the only choice idempotent under repeated round-trip AND bit-stable through `json.dumps/loads` (2-decimal
  drifts); litegraph renders integer-grid anyway. Snap at the ingest boundary; the store is the authority.
- How `port convert`-generated Python references the store (path breadcrumb in the template header).
- Get/Set routing capture shape in the store (endpoint-by-uid vs endpoint-by-slot) under rewires.
- RESOLVED (Phase-B/C): `VibeNode.uid` is a real field; uid IS mirrored into emitted `properties`; the
  emitted `.json` is self-describing and the sidecar is the `.py` form's regenerable cache.

## Constraints
- Offline / deterministic. `compile("api")` and the forward parity gate stay green — furniture is
  additive and must never alter wiring or widget values.
- Coordinate with `contracts/ir.py`; do not fight the in-flight IR-purity work.

## Done criteria
- A node ingested from editor JSON, converted to Python, and re-ingested keeps the SAME uid (read-back
  proven, not just stamped). A round-trip through the real ComfyUI editor (Open->drag->Save) preserves
  the uid (K1 contract).
- `pos`/`size`/`groups`/`color`/`flags`/Note/Reroute/`definitions`/`extra.ds`/`lastRerouteId` from an
  editor JSON are captured into the store on `port convert` (corpus spot-check across editor-origin
  workflows); per-node vs graph-level sections populated correctly.
- `mode` is captured into the EXECUTION IR (node metadata) as DATA; M2 does not yet change compile
  semantics from it (the bypass drop/rewire policy is M3's). So `compile("api")` stays byte-identical in
  M2 (K3 inertness proof holds); the deliberate compile change for bypassed graphs lands in M3, where the
  parity gate is updated to EXPECT it (see m3 — "compile is byte-identical for non-bypassed graphs only").
- Subgraph `definitions` are deep-copied to metadata before helper resolution; inner `pos`/links survive.
- Graceful absence: Python-authored templates with no furniture convert/store with empty layout, no error.
- **[Phase-C] Virtual-wire capture:** a workflow with Get/SetNode/Reroute round-trips them as furniture
  (count of virtual nodes in == count restorable out, for a structurally-unchanged round-trip); proven on
  a corpus file that actually contains them (NOT just the flat M1.5 subject).
- **[Phase-C] Properties passthrough:** `cnr_id`/`ver` and other unknown per-node `properties` survive
  ingest->store and are present for re-emit (spot-check a corpus node carrying `cnr_id`).
- **[Phase-C] Agent-edit safety:** programmatically add a node, delete a different node, add another (so
  `_next_node_id` reuses an int id) -> no node's minted uid collides with a removed node's; the new node
  does NOT inherit a stale position. (The agent analogue of M5's edit-invariance.)
- **[Phase-C] Coordinate canonicalization:** the same IR converted on two machines yields
  canonicalized-identical stored coords (no float drift).

## Touchpoints
- `vibecomfy/workflow.py`, `vibecomfy/contracts/ir.py`, `vibecomfy/ingest/normalize.py`,
  `vibecomfy/porting/convert.py`, `vibecomfy/porting/layout_store.py` (new),
  `vibecomfy/porting/subgraph_resolve.py` (carry definitions), tests under `tests/`.

## Anti-scope
- No emitter changes (M3). No layout algorithm (M4). No preserve/merge logic (M5). No CLI/docs (M6).
- Do not put positions in the authoring `.py`. Do not make furniture required.
