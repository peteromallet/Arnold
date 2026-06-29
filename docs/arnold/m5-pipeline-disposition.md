<!-- M5 Phase 3 inventory: pipeline disposition. -->

# M5 Pipeline Disposition

> **M6 Phase A update:** All `delete` and `archive` rows have been executed on
> branch `workflow-manifest-runtime-m6-purge`. `arnold/pipelines/*` legacy
> duplicates are removed (delete) or relocated to `docs/archive/m5/` (archive).
> The surviving migrated roots remain under `arnold_pipelines/` or, for the two
> older core packages (`folder_audit`, `deliberation`), under `arnold/pipelines/`
> until their native backing is deleted or re-authored in M6.

Status enum: `migrate`, `delete`, `archive`, `whitelist`.

| Root | Status | Builder contract | Final location | Public | Registry ID | Docs status | M6 fate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `arnold_pipelines/megaplan` | migrate | workflow | `arnold_pipelines/megaplan` | yes | `megaplan.core` | active | keep |
| `arnold_pipelines/megaplan/pipelines/planning` | migrate | workflow | `arnold_pipelines/megaplan/pipelines/planning` | yes | `megaplan.planning` | active | keep |
| `arnold_pipelines/megaplan/pipelines/doc` | migrate | native-backed | `arnold_pipelines/megaplan/pipelines/doc` | yes | `megaplan.doc` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/megaplan/pipelines/creative` | migrate | native-backed | `arnold_pipelines/megaplan/pipelines/creative` | yes | `megaplan.creative` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/megaplan/pipelines/jokes` | migrate | native-backed | `arnold_pipelines/megaplan/pipelines/jokes` | yes | `megaplan.jokes` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/megaplan/pipelines/live_supervisor` | migrate | native-backed | `arnold_pipelines/megaplan/pipelines/live_supervisor` | yes | `megaplan.live_supervisor` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/megaplan/pipelines/select_tournament` | migrate | native-backed | `arnold_pipelines/megaplan/pipelines/select_tournament` | yes | `megaplan.select_tournament` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/megaplan/pipelines/writing_panel_strict` | migrate | native-backed | `arnold_pipelines/megaplan/pipelines/writing_panel_strict` | yes | `megaplan.writing_panel_strict` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/evidence_pack` | migrate | workflow | `arnold_pipelines/evidence_pack` | yes | `evidence_pack.verifier` | active | keep |
| `arnold_pipelines/_template` | migrate | workflow | `arnold_pipelines/_template` | yes | — | active | keep |
| `arnold/pipelines/folder_audit` | migrate | native-backed | `arnold/pipelines/folder_audit` | yes | `arnold.folder_audit` | active | keep; delete native backing/re-author to workflow |
| `arnold/pipelines/deliberation` | migrate | native-backed | `arnold/pipelines/deliberation` | yes | `arnold.deliberation` | active | keep; delete native backing/re-author to workflow |
| `arnold_pipelines/megaplan/pipelines/epic_blitz.py` | archive | — | `docs/archive/m5/epic_blitz.py` | no | — | archival | delete |
| `arnold_pipelines/megaplan/pipelines/epic-blitz` | archive | — | `docs/archive/m5/epic-blitz` | no | — | archival | delete |
| `arnold/pipelines/megaplan` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/jokes` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/creative` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/doc` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/live_supervisor` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/select_tournament` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/writing_panel_strict.py` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/writing_panel_strict` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/simplify_writing` | archive | — | `docs/archive/m5/simplify_writing` | no | — | archival | delete |
| `arnold/pipelines/vibecomfy_executor` | archive | — | `docs/archive/m5/vibecomfy_executor` | no | — | archival | delete |
| `arnold/pipelines/epic_blitz` | archive | — | `docs/archive/m5/epic_blitz` | no | — | archival | delete |
| `arnold/pipelines/_deliberation_example` | archive | — | `docs/archive/m5/_deliberation_example` | no | — | archival | delete |
| `arnold/pipelines/briefs` | archive | — | `docs/archive/m5/briefs` | no | — | archival | delete |
| `arnold/pipelines/evidence_pack` | delete | — | — | no | — | deleted | delete |
| `arnold/pipelines/_template` | delete | — | — | no | — | deleted | delete |

## Notes

- `migrate` roots must expose `build_pipeline()` and a `pipeline_ids.json` entry by M6.
- `migrate` rows whose builder contract is `workflow` must return `arnold.workflow.Pipeline`.
- `migrate` rows whose builder contract is `native-backed` remain projected native `arnold.pipeline.Pipeline` shells during the M5 transition window. They are recorded here as native-backed compatibility with an M6 deletion plan: the native backing is deleted and the pipeline is either re-authored to `arnold.workflow.Pipeline` or removed.
- `delete` roots are legacy duplicates kept only to avoid breaking M4 callers; they are removed in M6.
- `archive` roots are preserved as read-only migration notes under `docs/archive/m5/` in M6.
- `whitelist` rows are not present in this milestone; every shipped root has a deterministic disposition.
- The legacy runtime shells inside migrated roots (`steps.py`, `prompts/__init__.py`, etc.) are retained until M6 and are excluded from the forbidden-pattern scan via the inventory allowlist.
