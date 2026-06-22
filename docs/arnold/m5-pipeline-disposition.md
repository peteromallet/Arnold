<!-- M5 Phase 1 inventory: pipeline disposition. -->

# M5 Pipeline Disposition

Status enum: `migrate`, `delete`, `archive`, `whitelist`.

| Root | Status | Final location | Public | Registry ID | Docs status | M6 fate |
| --- | --- | --- | --- | --- | --- | --- |
| `arnold_pipelines/megaplan/pipelines/planning` | migrate | `arnold_pipelines/megaplan/pipelines/planning` | yes | `megaplan.planning` | active | keep |
| `arnold_pipelines/megaplan/pipelines/doc` | migrate | `arnold_pipelines/megaplan/pipelines/doc` | yes | `megaplan.doc` | active | keep |
| `arnold_pipelines/megaplan/pipelines/creative` | migrate | `arnold_pipelines/megaplan/pipelines/creative` | yes | `megaplan.creative` | active | keep |
| `arnold_pipelines/megaplan/pipelines/jokes` | migrate | `arnold_pipelines/megaplan/pipelines/jokes` | yes | `megaplan.jokes` | active | keep |
| `arnold_pipelines/megaplan/pipelines/live_supervisor` | migrate | `arnold_pipelines/megaplan/pipelines/live_supervisor` | yes | `megaplan.live_supervisor` | active | keep |
| `arnold_pipelines/megaplan/pipelines/select-tournament` | migrate | `arnold_pipelines/megaplan/pipelines/select-tournament` | yes | `megaplan.select_tournament` | active | keep |
| `arnold_pipelines/megaplan/pipelines/writing-panel-strict` | migrate | `arnold_pipelines/megaplan/pipelines/writing-panel-strict` | yes | `megaplan.writing_panel_strict` | active | keep |
| `arnold_pipelines/megaplan/pipelines/epic_blitz.py` | archive | `docs/archive/m5/epic_blitz.py` | no | — | archival | delete |
| `arnold_pipelines/megaplan/pipelines/writing_panel_strict.py` | migrate | `arnold_pipelines/megaplan/pipelines/writing_panel_strict.py` | yes | `megaplan.writing_panel_strict` | active | keep |
| `arnold/pipelines/megaplan` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/jokes` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/creative` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/doc` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/live_supervisor` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/select_tournament` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/simplify_writing` | archive | `docs/archive/m5/simplify_writing` | no | — | archival | delete |
| `arnold/pipelines/vibecomfy_executor` | archive | `docs/archive/m5/vibecomfy_executor` | no | — | archival | delete |
| `arnold/pipelines/writing_panel_strict.py` | delete | — | no | — | deleted | delete |
| `arnold/pipelines/epic_blitz` | archive | `docs/archive/m5/epic_blitz` | no | — | archival | delete |
| `arnold/pipelines/evidence_pack` | migrate | `arnold_pipelines/evidence_pack` | yes | `evidence_pack.verifier` | active | keep |
| `arnold/pipelines/folder_audit` | archive | `docs/archive/m5/folder_audit` | no | — | archival | delete |
| `arnold/pipelines/deliberation` | archive | `docs/archive/m5/deliberation` | no | — | archival | delete |
| `arnold/pipelines/_deliberation_example` | archive | `docs/archive/m5/_deliberation_example` | no | — | archival | delete |
| `arnold/pipelines/briefs` | archive | `docs/archive/m5/briefs` | no | — | archival | delete |
| `arnold/pipelines/_template` | migrate | `arnold_pipelines/_template` | yes | — | active | keep |

## Notes

- `migrate` roots must expose `build_pipeline() -> arnold.workflow.Pipeline` and a `pipeline_ids.json` entry by M6.
- `delete` roots are legacy duplicates kept only to avoid breaking M4 callers; they are removed in M6.
- `archive` roots are preserved as read-only migration notes under `docs/archive/m5/` in M6.
- `whitelist` rows are not present in this milestone; every shipped root has a deterministic disposition.
