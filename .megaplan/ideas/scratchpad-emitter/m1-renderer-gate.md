# M1 — Foundation: renderer + durable identity + sound parity + deterministic schema

> **STATUS: MERGED (PR #18) — but superseded as "the foundation."** The 2026-05-28 robustness review
> (see `ROBUSTNESS-REVIEW-2026-05-28.md`) found M1 shipped the renderer but NOT a working position
> round-trip: `ir_node_id` is write-only, ingest discards positions/furniture, emit re-grids via a stub,
> and `port export --to ui` is unwired. The real foundation now lives in
> `m2-identity-and-lossless-ingest.md`. This file is kept as the historical record of what M1 built.
> The revised, authoritative milestone set is m2..m6 + the chain `scratchpad-emitter.yaml`.

## Outcome
The foundation milestone. A renderer that turns a `VibeWorkflow` IR into ComfyUI
**UI/litegraph editor JSON**, built on four things layout (M2) and preserve (M3) must be
able to trust: (1) **durable per-node identity** stamped in the emitted JSON, (2) a
**sound parity oracle** that actually reflects what ComfyUI does, (3) a **deterministic,
pinned schema source**, and (4) **locked output-path + prior-discovery semantics**. Layout
quality is NOT in scope — a dumb stub layout is fine. Two independent frontier reviews
concluded the renderer is the *easy* part; these four foundations are the real work and
must land before anything builds on them.

## Why this is the foundation
The missing direction is Python → UI editor JSON (`port convert` does JSON → Python;
`compile("api")` does Python → API JSON). Preserve-mode's entire value rests on stable
identity; the layout's correctness rests on a parity oracle that means what it claims; and
reproducibility rests on a schema source that doesn't vary by machine. Get these wrong and
M2/M3 are built on sand.

## Locked decisions (do not relitigate)
- **Target is UI/litegraph editor JSON, not API JSON.** CLI surface is
  `port export --to ui` (the existing subcommand uses `--to`, default `json`,
  `port.py:1257` — NOT `--format`); extend `--to` and `export_to_json(format=...)`.
- **Python stays pure** of layout/position metadata. The renderer reads the in-memory IR.
- **Durable identity, stamped from day one, framed honestly as best-effort.** Every
  emitted node carries BOTH:
  - `properties["ir_node_id"]` = the IR node id (`VibeNode.id`) — the **primary** key
    preserve-mode matches on. Stable for source-derived / `raw_call` nodes (explicit ids
    like `'98'`); **NOT** fully stable for typed-wrapper nodes, whose ids come from
    `_next_node_id()` (`workflow.py:290`) and renumber when a wrapper is inserted earlier.
  - `properties["vibecomfy_id"]` = the forward emitter's variable/role label — **display
    only**, never the match key (it renumbers on edits per `_compute_variable_names`,
    `emitter.py:2645`).
  This is best-effort by construction: heavy Python restructuring can lose some preserved
  positions. The docs and reports MUST say so plainly; do not promise lossless
  preservation.
- **Parity gate = canonical graph ISOMORPHISM, not dict equality.** `compile()` preserves
  string node ids (`workflow.py:471`, e.g. `"238:218"`) and the emitter remaps to
  litegraph integers, so `normalize_to_api(emitted)` and `normalize_to_api(source)` will
  NOT compare equal by key. Compare the two API graphs up to node-id remapping
  (structural/topological match on class_type + resolved edges + widget values).
- **The offline gate is a WIRING check with a known blind spot; the release gate uses
  ComfyUI.** `normalize_to_api` (`normalize.py:38`) uses ComfyUI's real
  `convert_ui_to_api` only when `comfy` imports, else VibeComfy's own `_normalize_ui_to_api`
  fallback (`:56`). Offline CI runs the fallback — proving emitter and normalizer share
  assumptions, NOT that the editor opens the file. Therefore: offline unit parity
  (isomorphism, fast) + a **comfy-required load/convert smoke gate** that is release-gating
  and marked appropriately (`runpod`/comfy env). Do not conflate them.
- **Schema source is the PINNED `ConversionSchemaProvider`, not `AuthoringSchemaProvider`.**
  `port export` currently builds the authoring provider whose precedence puts mutable
  `out/cache` object-info ahead of the pinned index (`provider.py:340`) — widget order and
  socket types could differ between machines. Use the deterministic conversion provider,
  record per-node schema provenance, and **loudly warn/fail on low-confidence (schema-less)
  nodes**, since their widget order is otherwise a guess the wiring gate can't catch.
- **Renderer and layout are separate modules.** Geometry is stubbed here.

## Scope
- New module `vibecomfy/porting/ui_emitter.py`:
  `emit_ui_json(wf, *, schema_provider, layout=None) -> dict`, stamping both identity keys.
- **Slot/type resolution:** `VibeEdge.from_output` (`workflow.py:50`) may be a NAME
  (`"MODEL"`) not an index, and edges carry NO socket type — resolve names→slot indices and
  socket types via the pinned provider's `OutputSpec` list.
- **`widgets_values`:** emit all schema widgets in schema order incl. linked ones; the
  link/widget split only decides which input slots get a `"widget": {"name": ...}` object.
- **`control_after_generate` retention (amends the read-only-IR rule):** the value
  (`fixed`/`randomize`) is dropped at ingest by `_is_ui_only_prompt_input`
  (`workflow.py:767`), so the emitter cannot reconstruct it. M1 MAY touch ingest to retain
  it in `VibeNode.metadata`; if retention is rejected, commit to a single named default
  (`fixed`) and document the determinism consequence. Guessing silently is not allowed.
- **Litegraph structural fields** the wiring gate ignores but the editor needs:
  `properties["Node name for S&R"]` = node type; input-slot `widget` objects; output
  `slot_index`; `links: null` for unwired outputs; OBJECT-style links inside
  `definitions.subgraphs[].links[]`; `state.lastRerouteId` if `definitions` is emitted.
- Node-id remap (string→int, `last_node_id`); `links[]` table (`last_link_id`); broadcast
  edges; `raw_call`/primitive feeders; multi-output nodes; envelope (`version: 0.4`).
- **Structural-validation pass** (slot counts vs schema, link endpoints exist,
  widgets_values length matches widget count) — green-on-corpus is a done criterion.
- **Output-path + prior-discovery semantics (locked here, pulled out of M4 — M3 depends on
  it):** deterministic default output path under `out/`, and a breadcrumb
  `extra.vibecomfy = {layout_version, source_template, prior_path}` so preserve-mode can
  always find the prior file. `--out` overrides.
- **`port export --to ui`** wiring (text + `--json`) with **loud default-text** reporting
  of unrecoverable content (stripped `Note`/`Reroute`/etc., low-confidence schema nodes).
- **Compatibility audit** of `ready_templates/**/*.py`: which round-trip cleanly vs which
  hit schema-less / subgraph-id issues. Record results.
- Tests: `tests/test_ui_emitter_parity.py` (isomorphism gate + structural validation +
  identity-stamp checks).

## Open questions (resolve during planning)
- Exact isomorphism canonicalization (topological signature) and its complexity bound on
  the largest corpus graphs.
- Schema-less community node policy: warn-and-emit-best-effort vs hard-fail under a strict
  flag.

## Constraints
- Offline / deterministic for the unit parity + structural suite; the ComfyUI smoke gate
  is separate and env-gated.
- Same-IR → byte-identical JSON (stub layout).
- Read-only on `compile("api")` and forward `port convert`. The single sanctioned ingest
  change is `control_after_generate` retention (above), if chosen.

## Done criteria
- `emit_ui_json` output opens in the ComfyUI editor without errors (flux + LTX two-stage),
  even if crude.
- **Isomorphism wiring gate** green on a starter set (≥5 spanning image/video/edit) and
  across full `workflow_corpus/**` + `ready_templates/**` minus a documented allowlist.
- **Structural-validation** green corpus-wide; **ComfyUI load/convert smoke gate** green on
  the starter set in a comfy env.
- Both identity keys present on every node; `ir_node_id` provably stable for source-derived
  nodes; the wrapper-node instability is documented, not hidden.
- Schema provenance recorded; low-confidence nodes reported loudly.
- **Subgraph inner-id recoverability VERIFIED** (was an open question) — inner `raw_call`
  nodes expose real ids M2's group boxes can anchor to.
- `port export --to ui` emits file + recovery report; output-path + breadcrumb implemented.

## Touchpoints
- `vibecomfy/porting/ui_emitter.py` (new); `vibecomfy/commands/port.py` (extend `--to`,
  use pinned `ConversionSchemaProvider`); `vibecomfy/workflow.py` (`export_to_json` accept
  `ui`); `vibecomfy/ingest/normalize.py` + ingest (read-only except `control_after_generate`
  retention); `vibecomfy/schema/provider.py`, `vibecomfy/porting/widget_aliases.py`
  (read-only reuse); `tests/test_ui_emitter_parity.py` (new).

## Anti-scope
- No layout quality (M2). No preserve reconciliation (M3) — but DO stamp both identity keys
  and lock output-path/discovery. No forward-conversion / API-export changes.
