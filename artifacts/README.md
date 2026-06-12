# Artifacts

This directory contains historical generated baseline and review evidence from
the pristine-cleanup and megaplan milestone passes. These files are tracked for
auditability and reference, not runtime output.

## Contents

| File / Directory | Content |
|---|---|
| `m1-safety-gate.md` | M1 milestone gate evidence — confirms the pre-cleanup safety baseline before structural changes. |
| `m2-symbol-map.md` | M2 helper symbol map — records duplicated helpers that were consolidated. |
| `m4/` | M4 baseline golden evidence and pre/post apply snapshots. |
| `m5_baseline_red.txt` | M5 red/green baseline evidence. |
| `m5_agent_edit_imports.txt` | M5 agent-edit import analysis. |
| `m5a-emitter-baseline/` | M5a emitter baseline evidence (pytest logs, generated templates, manifest). |
| `m5a-emitter-after/` | M5a emitter after-evidence (generated templates, manifest). |

## What was moved

- `m6-public-api.md` → `docs/api/m6-public-api.md` — active public API surface documentation.
- `m1-step1-audit.md` → `docs/audits/m1-step1-audit.md` — M1 audit baseline evidence.
- `m2-diff-hygiene.md` → `docs/audits/m2-diff-hygiene.md` — M2 dirty-worktree classification.

These moved documents are now in their functional doc locations; this directory
retains only the generated baseline and review evidence that is not actively
consumed as user-facing documentation.

## Note

This is **not** runtime output. Runtime output goes under `out/`. Do not place
new generated evidence here — use `out/agentic/reports/<tag>/` or the appropriate
`docs/` subdirectory instead.
