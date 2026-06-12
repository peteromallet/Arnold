# Agent-Edit Fixture Coverage

## Purpose
This document tracks available faithful browser UI JSON fixtures for the
agent-edit v2 editing corpus (C6). Only browser UI JSON fixtures — those
containing LiteGraph substrate shape (`pos`, `size`, `widgets_values`,
`inputs`/`outputs` with `link`/`links`, root `links` as arrays) — are valid
for byte-preservation assertions.

API-only template JSON (e.g., `class_type`-style with `["node_id", slot]`
link references, as found in `canonical_parity_baseline.json`) is explicitly
**not** a valid substitute for browser UI JSON fixtures.

## Available Fixtures

| Fixture | File | Graph Type | Nodes | Subgraphs | Notes |
|---------|------|-----------|-------|-----------|-------|
| flat | `flat.json` | Standard flat text-to-image | 7 | No | Simple prompt-edit target; copied from `tests/fixtures/walking_skeleton/flat.json` |
| subgraphed_wan_i2v | `subgraphed_wan_i2v.json` | Wan 2.2 I2V workflow | ~40 root + subgraph | Yes (`definitions.subgraphs`) | Covers scope-addressing and subgraph link formats. |

## Coverage Gaps (block default-on cut-over only)

### LTX-specific workflows
No faithful browser UI JSON fixture available for LTX (Lightricks) workflows.
The vendor directory contains API-format LTX templates but not browser UI JSON
exports with full LiteGraph substrate shape.
- **Impact**: LTX-specific byte-preservation cannot be asserted.
- **Mitigation**: Standard flat and subgraphed fixtures provide adequate
  coverage for the core edit primitives (set_node_field, add_node, remove_node,
  upsert_link, set_mode). The LTX gap affects only LTX-specific node types.
- **Resolution**: Obtain a sanitized LTX browser UI JSON export from a running
  ComfyUI instance with the LTX nodes installed.

### Gemini workflows
No faithful browser UI JSON fixture available for Gemini/Google workflows.
- **Impact**: Gemini-specific node types are not covered.
- **Mitigation**: Same as LTX — standard fixtures cover core primitives.
- **Resolution**: Obtain a sanitized Gemini workflow export.

### ByteDance workflows
No faithful browser UI JSON fixture available for ByteDance (Seedance, etc.)
workflows. The vendor directory contains browser-UI-shaped exports for some
ByteDance templates (e.g., `api_bytedace_seedance1_5_image_to_video.json`)
but these are labeled as API-prefixed direct templates and may not represent
faithful user-facing browser exports.
- **Impact**: ByteDance-specific node types are not covered.
- **Mitigation**: Same as above.
- **Resolution**: Obtain a sanitized ByteDance workflow export from a running
  ComfyUI instance.

## Runtime Coverage Gaps (T17 — LiteGraph / web apply path)

### Python-side LiteGraph
`comfy.litegraph` is **not importable** in the dev/test environment (expected:
it is vendored inside the ComfyUI server process). The `normalize_ui_json`
preferred path (``serialize → configure → serialize``) falls back to raw-dict
normalization when LiteGraph is unavailable. This is mechanically verified by
``_t17_check_litegraph.py`` and is safe: the raw-dict fallback is deterministic
and produces stable output for byte-comparison.

### Browser-side LiteGraph (web edit apply path)
`window.LiteGraph` is referenced in ``vibecomfy_roundtrip.js`` (line 2778)
and is available in any ComfyUI browser runtime. ``LGraph.configure``,
``LGraph.serialize``, and ``LGraph.clear`` are **standard LiteGraph.js API
methods** (confirmed via upstream ``litegraph.d.ts`` type definitions and
ComfyUI frontend source).

**Automated coverage:** ``tests/browser/roundtrip_smoke.test.mjs`` now exercises
the deterministic browser harness path for:
1. v2 same-canvas success: accept returns first, then ``graph.clear()`` and
   ``graph.configure(candidate)`` run in order, with no ``app.loadGraphData()``
   fallback.
2. stale live-canvas refusal: the client blocks local apply when the
   submit-time live token no longer matches immediately before configure.

**Info gate only:** a true live-browser/ComfyUI smoke still depends on local
Playwright browsers and a running Comfy frontend. When that environment is
unavailable, keep automated CI on the deterministic harness and treat the live
smoke as informational/manual coverage rather than a blocking gate. A human
operator should still verify in a live ComfyUI browser that:
1. Accept applies the candidate in-place without forking a new tab.
2. The undo stack correctly restores the pre-apply canvas.
3. The stale-state guard fires correctly (canvas changed during apply window).
4. The candidate graph is visually correct (nodes positioned, links intact,
   annotations preserved).

This live-smoke gap **does not block** landing the opt-in v2 implementation.
It remains an info gate before the `VIBECOMFY_AGENT_EDIT_V2` default-on
cut-over.

## Policy
- Missing fixture coverage **blocks** the `VIBECOMFY_AGENT_EDIT_V2` default-on
  cut-over but does **not** block landing the opt-in v2 implementation.
- Missing live-browser confirmation blocks default-on but does not block opt-in
  v2 landing when the deterministic JS/browser harness is green.
- All fixtures are sanitized (no user PII, no API keys, no copyrighted prompts).
- Fixtures are read-only during test execution; tests deep-copy before mutation.
