# M4 — Fresh layout engine (required) + constrained new-node placement  [partnered tier]

## Outcome
A deterministic layout engine that assigns `pos`/`size`/`groups[]` so a workflow with **no positioning
metadata** opens looking sensible and hand-placed — and a **constrained-placement primitive** that drops
a few new nodes into otherwise-pinned graphs without overlap. This is NOT optional: ~50 Python-authored
ready templates have no positions, so fresh layout is the PRIMARY path for them, and M5's preserve uses
this milestone's placement primitive to put new nodes in sensible spots near their wired neighbors.

Robustness mandate (from the review): build the SIMPLE robust version, not the over-engineered one. The
original spine-first design fails ~60% of the corpus (12 zero-sampler edit/t2i graphs, 17 multi-sampler,
serial sampler chains) and underestimates node width (real widths reach ~1775px vs a 320px assumption)
-> guaranteed overlap. Favor a layering that is provably total and never overlaps over a clever spine.

## Locked decisions (do not relitigate)
- **Layout is a pure, deterministic function of (graph structure + roles).** Same IR -> byte-identical
  coords. Every ordering step has an explicit tie-break: sort every neighbor/lane set by
  `(layer, class_type, zero-padded uid)` — reuse the emitter's existing zfill edge-sort discipline.
  **[Phase-C] All emitted coordinates are canonicalized to the fixed precision M2 defines** (96% of corpus
  pos are 13-digit floats); layout math operates on canonicalized values so no float drift leaks into the
  "byte-identical" guarantee. Tie-break sorts on the canonicalized uid, never the gap-filling integer id.
- **Layering, not spine-detection, is the backbone.** Assign each node a layer by longest-path depth
  from sources over the full DAG **after SCC collapse** (provably total — every node gets a layer;
  orphans/unreferenced nodes included). Use samplers only to *label/straighten* columns, never as the
  required backbone. This replaces the fanin-difference stage partition (non-total under parallel samplers).
- **Fixed generous column pitch (~520px), height estimated from widget count.** Do NOT try to predict
  exact per-node width (driven by labels/multiline widgets the schema can't give). Overestimate; accept
  whitespace; never overlap. Tall-widget bonuses (IMAGE/VIDEO/AUDIO/MASK previews) read from schema.
- **One lane per weakly-connected component**; parallel branches get sub-lanes. Canvas extent derives
  from summed band widths — NO fixed 2000px cap (real layouts span 8-11k px).
- **Constrained placement (the part M5 reuses):** the API takes a pinned set `{uid -> pos/size}` + a
  per-new-node anchor hint (the matched wired neighbor's uid). New nodes start at the anchor's right
  edge + gap and do a bounded spiral-ray search outward until the bbox clears all pinned bboxes; the
  cap derives from canvas extent, and the documented degradation is "dump at `(max_x + gap, anchor.y)`
  + warn." In fresh mode the pinned set is empty; the code path and tests must exist regardless.
- **Subgraphs render as visible titled group boxes** (from M2's carried `definitions`), not collapsed
  UUID nodes; title from the subgraph function name.

## Scope
- New `vibecomfy/porting/layout/` package: `layering.py` (longest-path + SCC collapse via Tarjan with a
  deterministic neighbor order), `sizing.py` (height-from-widgets + tall-widget bonuses), `lanes.py`
  (WCC lanes + sub-lanes + fixed pitch), `placement.py` (constrained spiral-ray + anchor), `groups.py`
  (engine-generated group boxes + subgraph boxes), `engine.py` (compose; the `layout=` entry point).
- Wire into `emit_ui_json` (`porting/ui_emitter.py`): replace `_stub_layout` with the engine; pass the
  pinned set/anchors through the existing (currently `del`-eted) `layout` parameter.
- A left reserved column for leaf controls (Primitive*/LoadImage), ordered to match public inputs.

## Open questions (resolve during planning)
- Crossing-reduction: include a cheap barycenter sweep or defer to polish? (Default: one deterministic
  sweep, off the critical path.)
- Group-box coloring palette (basic, consistent across all emitted workflows).

## Constraints
- Offline/deterministic. Geometry is additive: M3's wiring + object_info gates stay green after layout.
- No positions read from Python; fresh layout never depends on a prior emission.

## Done criteria
- flux (single sampler), an LTX multi-sampler, a zero-sampler edit graph, and the music-video monster
  (~90 nodes, 10 subgraphs) all open without errors. **[auto-merge] The GATE is the no-overlap invariant +
  the automated editor-open smoke (vendored ComfyUI), not a human "looks sensible"** — the chain auto-merges
  unattended. "Looks hand-placed" is an optional post-hoc confidence check; the machine gate is no-overlap +
  determinism + opens-clean.
- **No-overlap invariant** passes corpus-wide, including tall-widget custom nodes.
- **Determinism:** emit twice -> identical geometry (byte-identical), golden test.
- **Constrained test:** synthetic pinned subset + anchors -> pinned nodes unchanged, new nodes placed
  without overlap, spiral fallback exercised on a dense case.
- Subgraphs render as titled boxes anchored to recovered inner ids.

## Touchpoints
- `vibecomfy/porting/layout/*` (new), `vibecomfy/porting/ui_emitter.py` (wire engine, drop stub),
  `tests/test_ui_layout.py` (new). Read-only: schema provider, public inputs, M2's carried definitions.

## Anti-scope
- No preserve/merge/identity matching (M5). No ingest changes (M2). No CLI/docs (M6).
- No spine-first backbone, no fanin-stage partition, no fixed canvas cap, no per-node width prediction.
