# Workflow Golden Normalization

M1 workflow-manifest-runtime fixtures are normalized contract fixtures, not
behavioral rewrites of existing Megaplan goldens.

Locked volatile fields:

- `run_id`
- `event_id`
- `timestamp`
- `duration_ms`
- `absolute_path`
- `model_latency`
- `token_count`

Canonical transforms:

- Replace volatile scalar values with `"<normalized>"`.
- Sort object keys and route lists lexicographically by stable ID.
- Preserve versioned artifact names as `vN.<ext>` paths.
- Preserve seeds when present; otherwise omit seed fields.
- Do not rewrite `tests/fixtures/golden/pipeline_*.json` for import/package-only
  moves. If behavior legitimately changes, add a sibling
  `.explanation.md` artifact that names the behavioral reason.

New volatile fields require the amendment protocol in
`docs/arnold/workflow-manifest-amendments.md`.
