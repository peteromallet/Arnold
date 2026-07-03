# Reorganise a large messy LTX workflow

The user has a large LTX workflow loaded from
`tests/fixtures/editor_sessions/327b0e1235c353a9/request.json`. It has 119 nodes,
long helper chains, and overlapping groups.

Run the workflow reorganisation preview/apply path. Freeze:

- `layout_observation.json` with before/after metrics and structural hash evidence.
- `layout_before.png` and `layout_after.png`, abstract color-block renderings that
  a vision model can inspect.
- `actions.jsonl` proving the preview, layout-only apply, and observation steps ran.

The reorganisation is successful only if it preserves graph structure, removes
node/group overlaps, lowers spacing density, and creates coherent colored group
sections. Long helper/backward-edge warnings are acceptable only as visible
warnings; they must not mask overlap or structural-hash regressions.
