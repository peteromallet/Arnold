<!-- M5 Phase 1 inventory: generated artifacts. -->

# M5 Generated Artifact Manifest

| Artifact | Generator command | Current location | Final location | M6 disposition |
| --- | --- | --- | --- | --- |
| Codex/CLI skills | `.agents/skills/megaplan*` / manual | `.agents/skills/megaplan/` | `.agents/skills/workflow/` or project skill dir | migrate |
| Composed skill bundles | `arnold_pipelines.megaplan.cli` (setup --regen-composed) | `arnold_pipelines/megaplan/data/_composed/` | `arnold_pipelines/megaplan/data/_composed/` (survivor refs only) | migrate |
| Generated codex skills | `scripts/generate_arnold_docs.py` | `arnold_pipelines/megaplan/data/_codex_skills/` | `arnold_pipelines/megaplan/data/_codex_skills/` (workflow-only) | migrate |
| Pipeline projection docs | `scripts/generate_arnold_docs.py` | `docs/reference/arnold-projections.md` | `docs/reference/arnold-projections.md` | migrate |
| Package scaffold template | `arnold pipelines new` (legacy) | `arnold/pipelines/_template/` | `arnold_pipelines/_template/` | migrate |
| Pipeline ID registries | `scripts/check_pipeline_id_registry.py` / generator | `arnold/pipelines/**/pipeline_ids.json`, `arnold_pipelines/**/pipeline_ids.json` | `arnold_pipelines/**/pipeline_ids.json` (survivors only) | migrate |
| Disposition data | `scripts/render_package_disposition_md.py` | `docs/arnold/package-disposition.yaml` | `docs/arnold/package-disposition.yaml` | migrate |
| M5 inventory docs | manual (this plan) | `docs/arnold/m5-*.md` | `docs/arnold/m5-*.md` | archive after M6 |
| Old generated docs under `arnold/pipelines/megaplan/data/` | legacy generator | `arnold/pipelines/megaplan/data/` | — | delete |

## Generator migration notes

- `scripts/generate_arnold_docs.py` must consume `arnold.workflow` public APIs and the final shipped-pipeline discovery helper (Phase 3).
- Generated examples must compile, dry-run, and fake-run against installed public workflow imports.
- Composed rules may only reference pipeline/pattern IDs present in the surviving registry.
