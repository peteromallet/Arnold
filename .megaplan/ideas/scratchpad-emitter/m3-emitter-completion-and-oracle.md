# M3 — Emitter completion + independent verification oracle  [partnered tier]

## Outcome
Turn the merged-but-unwired emitter into a real, user-reachable, trustworthy command, and replace the
self-referential parity gate with an oracle that is independent of the emitter's own assumptions. After
M3 a user can actually run `port export --to ui`, get back a file that opens in ComfyUI with its
furniture intact (when present), and CI proves the emitted graph matches what ComfyUI itself expects.

Grounding: `port export --to ui` is dead — `_cmd_port_export` rejects any `--to` but `json`
(`commands/port.py:430`) and `emit_ui_json` is imported but never called (`port.py:39`). Export builds
the MUTABLE `AuthoringSchemaProvider` (`port.py:433`) -> non-deterministic widget order across machines.
`emit_ui_json` hardcodes `groups: []` and `mode:0`/`flags:{}` and ignores `metadata["_ui"]`. The offline
parity gate compares `_normalize_ui_to_api(emit_ui_json(wf))` to `compile("api")` — both VibeComfy code,
with a test (`test_parity_gate_never_imports_comfy`) that *enforces* ComfyUI is never imported; the only
real-ComfyUI gate runs on ONE workflow and only asserts "didn't crash."

## [Phase-D] The oracle is the vendored ComfyUI, not a snapshot (see WAY-THROUGH-2026-05-29.md #8)
The independent gate becomes REAL by plugging into `vendor/ComfyUI` in-process (the `vibecomfy[comfy]`
extra + `comfy_backend.ensure_nodes()`): emit -> ComfyUI's own `convert_ui_to_api`
(`workflow_convert.py:1122`) -> compare to `compile("api")` via the existing `compile_equivalent`/
`canonical_equal` (`parity.py:200`). We ALREADY call `convert_ui_to_api` at `normalize.py:41-46` but
SWALLOW errors into our self-referential fallback — **make it the primary path and let it raise.** Live
`object_info` from the booted registry gives real provenance for the 838 null-provenance core classes;
the pinned snapshot demotes to a cache for un-importable custom packs. `schema_freshness.yml` (today diffs
the cache against itself) is rewritten to FAIL on a per-pack hash diff vs the booted registry. Add a zod
CONFORMANCE gate (Node + the `comfyui-frontend-package` wheel) and emit schema **version 1.0, not 0.4**.
Schema collection must NEVER auto-install untrusted packs (static-AST only). RunPod demotes to pack-schema
confirmation with a named owner.

## Locked decisions (do not relitigate)
- **[Phase-C] FIRST TASK — fix the widget-count crash (it takes down ~30% of the corpus today).**
  `ui_emitter.py:657` does `assert len(widget_values) <= expected_widget_count`, where
  `_full_widget_name_count` counts the curated *schema-input* table. But ComfyUI's real frontend appends
  trailing widget slots — `vendor/.../workflow_convert.py:130 _extra_widgets_after`: a
  `control_after_generate` slot for INT fields named `seed`/`noise_seed`, and an upload slot for
  `image/video/audio_upload`. So real saved nodes legitimately have MORE widgets than the curated count.
  **Verified: 17/48 corpus files (all wan*/ltx2_3*/qwen*) hard-crash `emit_ui_json`.** Proper fix, in
  order: (1) count widgets the way ComfyUI does — derive the expected slot model from
  `object_info_widget_order` (the pinned snapshot already encodes the extras as trailing `None`s, e.g.
  KSampler `[None,'seed',...,None,None,None,'denoise']`), falling back to the curated table + an explicit
  application of the `_extra_widgets_after` rule; ONE authoritative widget-slot model matching ComfyUI.
  (2) Downgrade the bare `assert` to a **recovery-report warning** — a genuine mismatch means a
  schema-less/version-drifted node, which is emit-best-effort-and-report, never a crash (and `assert`
  vanishes under `python -O` anyway). (3) Real correctness is enforced by the independent object_info
  gate below, not the in-line guard. This also unifies widget counting + ordering on the same pinned
  snapshot, killing a cross-machine determinism leak. Nothing downstream is validatable until this lands.
- **Wire `port export --to ui`** through `emit_ui_json` -> `default_output_path` -> disk (all three exist
  in isolation; connect them at `commands/port.py:428`). Mirror the `port convert` mental model.
- **Export uses the pinned `ConversionSchemaProvider`**, never `AuthoringSchemaProvider` (one-line swap +
  schema-less handling). Cross-machine byte-identical widget order is a done criterion.
- **Emit the captured furniture verbatim** from M2's store: real `groups[]`, `flags.collapsed`,
  `color`/`bgcolor`, Note/Reroute nodes, subgraph `definitions` (populate `metadata["definitions"]` so
  the existing `_emit_definitions` path, `ui_emitter.py:311-339`, fires — K5 confirmed it emits a
  near-valid block from verbatim corpus definitions). Mirror the uid into emitted
  `properties["vibecomfy_uid"]` (K1: survives editor saves) and into inner subgraph nodes. **[Phase-C]
  Re-stamp the full verbatim `properties` blob from M2 (cnr_id/ver/mask-data/etc.), not a fresh dict.**
- **[Phase-C] Re-emit Get/SetNode/Reroute virtual wires as real editor nodes** from M2's furniture
  capture (default ON — the editor-first user lives by them; 723 in the corpus). The execution graph
  still resolves them to direct links; the EDITOR graph shows them where the user placed them. When a
  structural rewire has orphaned a captured route, degrade that wire to a direct connection and name it
  in the recovery report (never silently). This is what makes "round-trip works" true for real graphs,
  not just the flat M1.5 subject.
- **[Phase-C] Canonicalize all emitted coordinates** to the fixed precision M2 defined, so two machines
  emit byte-identical (== canonicalized-identical) output.
- **Bypass policy (K3 — the dangerous one). `mode` is execution-relevant, not furniture. DECISION
  (Phase-B): compile changes by design for bypassed/muted nodes.** Real ComfyUI drops muted (mode 2)
  nodes and rewires around bypassed (mode 4) ones; the offline normalizer ignores `mode`, so today a
  bypassed node round-trips ACTIVE = silent semantic corruption. M3: (a) emit the node's `mode` back into
  the UI JSON so the editor shows the user's bypass/mute state; (b) `compile("api")` **drops/rewires
  bypassed+muted nodes to match ComfyUI** — this is a deliberate semantic change, so the parity gate is
  updated to **expect** it. State the invariant precisely: *compile is byte-identical for graphs with no
  bypassed/muted nodes; for graphs that have them, compile matches ComfyUI's drop/rewire output* (NOT
  "unchanged"). This only surfaces against the object_info / real-comfy gates, so it MUST be covered there.
- **The offline self-consistency check stays but is RENAMED honestly** — it proves "emitter <-> normalizer
  agree," not "correct." It must never again be cited as the correctness gate.
- **Schema-less nodes:** keep warn-and-emit by default with a loud report; add a `--strict` hard-fail.
  Their widget order is a guess the offline gate cannot catch — the object_info oracle below is how we do.

## Scope — the layered independent oracle (ship Layer 2 first; it needs no GPU)
- **Layer 1 (offline, no shared normalizer):** differential vs `compile("api")` using an independent
  read-back derived from the emitted `links[]` table + `object_info` widget order (from the real snapshot
  at `porting/cache/object_info/` — K4; NOT the `porting/object_info/` decoy), NOT `_normalize_ui_to_api`.
  Disagreement with Layer 0 localizes a shared-table bug.
- **Layer 2 (offline, BLOCKING CI gate):** validate every emitted node against the committed
  `object_info` snapshot. K4 confirmed the real snapshot is at **`vibecomfy/porting/cache/object_info/`**
  (`index.json` = 1401 classes, pinned via `provenance.json`) — NOT `porting/object_info/` (a decoy).
  Read via `ObjectInfoIndexSchemaProvider(root)` **directly**, bypassing the gitignored `node_index.json`
  so a stale local copy can't shadow the pinned snapshot. Check widget count+order
  (`object_info_widget_order`), output socket count/types, required inputs. Executable-node coverage is
  ~95%+; classify UUID/subgraph instances, `SetNode`/`GetNode`/rgthree, `@stub.json` entries, and unknown
  classes as **schema-less -> loud warn+skip with a max-skip budget** (so coverage can't silently rot).
  No GPU needed — land it early. **Honest framing (Phase-B correction):** Layer 2 is a fast *pre-filter*,
  NOT a full independence guarantee — the emitter ALSO derives widget order from the same object_info via
  the schema-provider chain, so a wrong object_info entry could pass both (provenance-shared, even though
  the code path differs from `_normalize_ui_to_api`). And it can only warn-skip schema-less community nodes
  — exactly the nodes most likely to have wrong widget order. So Layer 2 must NOT be cited as proving those
  nodes correct.
- **Layer 3 is the GATE OF RECORD for any workflow containing schema-less nodes (Phase-B correction).**
  Real ComfyUI `convert_ui_to_api` + live `object_info` (RunPod) is the only provenance-independent oracle.
  Any round-trip whose nodes Layer 2 had to skip is marked **"layout-verified, widgets-UNVERIFIED"** in the
  recovery report until it passes Layer 3 — never reported as fully verified on a green Layer 2.
- **Layer 3 (release gate, comfy/RunPod):** deepen the existing `convert_ui_to_api` smoke
  (`tests/test_porting_ui_emitter.py:672`) to corpus-wide + `canonical_equal` vs `compile("api")` +
  object_info input-name check.
- **Layer 4 (smoke):** headless litegraph "does it open" check (no unregistered-node / dangling-link errors).
- **Property/fuzz:** random valid IR -> emit -> Layer-1 read-back == `compile("api")` up to isomorphism;
  widget-count and slot-range invariants. Catches the duplicate/collision cases the fixed corpus misses.

## CLI / report
- `port export --to ui [--out PATH] [--strict] [--main-positions]` with stable text + `--json`, and a
  **loud recovery report**: stripped/low-confidence nodes, schema-less widget-order guesses, any furniture
  that couldn't be emitted. (`--fresh`/`--from`/preserve flags are M5/M6.)
- **`--main-positions` (richer editor metadata, opt-in).** By default the emitter writes the lean editor
  fields needed to open cleanly (`pos`/`size`/`flags`/`color` + uid). `--main-positions` additionally
  emits the **fuller litegraph metadata that makes the file feel native and self-contained**: top-level
  `extra.ds` (canvas pan/zoom so the user opens centered where they left off), `state` counters
  (`lastNodeId`/`lastLinkId`/`lastRerouteId`), node `order`/`title`, and the complete `groups[]` geometry —
  anything captured in M2's store that a minimal open doesn't strictly require. Rationale: the editor-first
  user values a `.json` that reopens exactly as they left it (viewport included), but a lean default keeps
  emitted files diff-small and avoids leaking machine-specific canvas state into shared templates. The flag
  is the explicit "give me everything" switch; pairs naturally with preserve mode (M5) where the prior
  canvas/viewport is known. Determinism: under `--main-positions`, any captured-but-absent field falls back
  to a fixed default (never a machine-dependent guess), so two machines still emit byte-identical output.

## Open questions (resolve during planning)
- Where object_info snapshots come from for offline Layer 2 vs live RunPod Layer 3; refresh cadence.
- Exact independent read-back canonicalization for Layer 1 (reuse `testing/canonical.py` WL form).

## Constraints
- Offline/deterministic for Layers 1-2 + the suite; Layers 3-4 are env-gated (comfy/RunPod), never in
  the offline default run. `compile("api")` untouched.

## Done criteria
- **[Phase-C] `emit_ui_json` no longer crashes on ANY corpus file** — the 17 previously-crashing
  wan*/ltx2_3*/qwen* files emit; widget counting matches `object_info_widget_order`; the in-line check is
  a report warning, not an assert.
- `port export --to ui` writes an editor-openable file end-to-end via the CLI; furniture from M2 present.
- **[Phase-C] Get/SetNode/Reroute round-trip** — a corpus file containing virtual wires re-emits them as
  visible editor nodes in their captured positions; the execution graph is unchanged.
- Two machines emit byte-identical UI JSON for the same IR (provider swap + schema-less determinism +
  coordinate canonicalization).
- Layer 2 object_info gate is green corpus-wide and BLOCKING in offline CI; a deliberately swapped
  widget order FAILS it (proof the self-reference is broken).
- Layer 3 green on the starter set under a comfy env; `convert_ui_to_api` output == `compile("api")`.
- bypass/mute (`mode`), groups, notes, colors survive emit when present in the store.

## Touchpoints
- `vibecomfy/commands/port.py` (wire `--to ui`, provider swap, report), `vibecomfy/porting/ui_emitter.py`
  (emit furniture, uid in properties), `vibecomfy/porting/object_info/`, `vibecomfy/porting/parity.py`,
  new `tests/test_emitter_object_info_validation.py`, `tests/parity/test_independent_readback.py`,
  `tests/property/test_emitter_fuzz.py`, deepen `tests/test_porting_ui_emitter.py`.

## Anti-scope
- No layout algorithm (M4). No preserve/merge (M5). No docs (M6). Do not change ingest (M2).
