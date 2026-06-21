# M5: Shipped Pipelines, CLI, Docs, And Scaffolds

## Outcome

Migrate all remaining shipped/example pipelines, operator-facing workflow CLI commands, docs, scaffolds, and inventory checks to the explicit-node workflow system after the canonical Megaplan package is manifest-backed.

The reviewer should be able to run discovery/inventory tests and see that every shipped pipeline is authored as `arnold.workflow.Pipeline` or explicitly whitelisted as internal test coverage.

## Operating Philosophy

M5 makes the new substrate the only taught and shipped way to build pipelines. Public examples, CLIs, generated skills, docs, scaffolds, registries, scripts, and templates are part of the product contract because agents and operators learn from them. A surface is either migrated with evidence, deleted, or narrowly whitelisted as non-public internal coverage with a burn-down path.

## Scope

IN:

- Migrate shipped pipelines under the new package layout: creative, doc, jokes, select_tournament, epic_blitz, live_supervisor, writing_panel_strict, and any retained evidence_pack/folder_audit/deliberation/template examples.
- Explicitly classify current shipped/example roots before editing them: `arnold/pipelines/megaplan/pipelines/{creative,doc,epic-blitz,jokes,live_supervisor,planning,select_tournament,writing_panel_strict}`, `epic_blitz.py`, `t19-external-builder`, `t20-select-tournament`, `t19_external_builder.py`, `t20_select_tournament.py`, `arnold/pipelines/evidence_pack`, `arnold/pipelines/folder_audit`, `arnold/pipelines/deliberation`, `arnold/pipelines/_deliberation_example`, `arnold/pipelines/briefs`, and `arnold/pipelines/_template`.
- For every shipped pipeline, declare final package location, public/importable status, registry ID, docs status, generated-asset status, and M6 fate. Old `arnold/pipelines/...` paths are source-to-migrate/delete unless explicitly re-chartered.
- Default final locations are `arnold_pipelines/<pipeline_name>/` for standalone shipped pipelines and `arnold_pipelines/megaplan/pipelines/` for Megaplan-owned subpipelines. Any exception must be recorded before migration with import/docs/CLI rationale.
- Add compile, dry-run, fake-backend execution, and docs/example tests for each shipped pipeline.
- Implement or update workflow CLI commands: `arnold workflow check`, `manifest`, `dot`, `dry-run`, `run`, and `resume`.
- Classify `arnold pipelines describe` from current mainline: migrate to `arnold workflow describe`, retain as an operator command with rationale, or delete by M6. Record it in the old-to-new CLI command mapping table with transition behavior and final M6 disposition.
- Implement, update, or explicitly delete operator workflow CLI commands for `status`, `trace`, `inspect`, and `override`; every surviving command must project from manifest events/artifacts/control transitions.
- Commit an old-to-new CLI command mapping table before migration: old command, new command or deletion, transition behavior before M6, and final M6 disposition.
- Reconcile every CLI row with M4's Megaplan-specific operator command inventory; conflicts must be resolved explicitly before implementation.
- Produce a CLI dispatch-chain inventory covering `pyproject.toml` scripts, package `__main__.py` files, `python -m` entrypoints, lazy dispatch functions, parser/help text sources, shell completion/help generators, and every nested subcommand path.
- Cover `arnold pipelines describe` in parser snapshots, CLI help text, installed-wheel smoke, shell-completion generators, generated docs/skills, and the dispatch-chain inventory.
- Update docs for workflow authoring, manifest, runtime, patterns, package authoring, examples, and projections.
- Regenerate or update generated agent-facing skills under `arnold/pipelines/megaplan/data/_codex_skills/`, generated composed skills/rules, `docs/reference/arnold-projections.md`, package authoring docs, package disposition data, scaffolds, and package metadata so no public/operator artifact teaches deleted surfaces.
- Specify the final location for generated skills, composed rules, generated pipeline `SKILL.md` files, and pipeline ID registries after `arnold_pipelines.megaplan` exists; old generated assets under `arnold/pipelines/megaplan/data/` are source-to-migrate/delete, not permanent homes.
- Add or strengthen pipeline inventory scanners and docs/scaffold scanners that forbid old public authoring APIs.
- Produce a closed migration inventory mapping every shipped pipeline/example/operator surface to `migrate`, `delete`, or `whitelist with rationale`; M6 deletion must be a subset of this inventory.
- Produce pipeline ID registry JSON artifacts and package-discovery metadata for every shipped pipeline that survives.
- Configure package metadata and wheel build rules so `arnold_pipelines` namespace packages are included in installed-wheel tests.
- Produce a generated-artifact manifest covering `_codex_skills`, `_composed`, all pipeline `SKILL.md`, projection docs, package disposition, pipeline ID registries, docs generators, and scaffold templates. Each row must name owner, generator/check command, final location, and M6 disposition.
- Migrate generator code before final artifact regeneration. Generated skills/docs/scaffolds/registries/disposition rows must include provenance metadata and must fail semantic validation if embedded examples do not compile, dry-run, and fake-run against the installed public workflow/runtime surface.
- Expand generated-artifact scanning to generator source, scaffold templates, Jinja/string templates, JSON/YAML/TOML/CSV data files, composed rules, every `SKILL.md` in the repo, code fences, CLI help text, and package data that ships in wheel/sdist.
- Every code fence in generated/operator-facing docs and skills must be extracted and checked, not a curated subset. Copy-pasteable old API examples are forbidden outside archival migration notes that are excluded from agent-facing/generated surfaces.
- Composed-rule `pipeline`/`pattern` references must resolve against the final surviving pipeline ID registry and fail if they point to deleted or whitelist-only pipelines.
- Produce a script/operator-tool inventory covering `scripts/`, `tools/`, root `_gen_*`, `sync-skills.sh`, watchdog/backfill/adopt utilities, docs generators, pipeline registry checks, oracle trace/bisect helpers, corpus/golden generators, silent-failure/simulation tools, and duplicate script/tool copies. Each row must be `migrate`, `delete`, `archive`, or `whitelist with rationale`.
- Expand legacy test inventory beyond `tests/_pipeline/` to include `tests/arnold/pipeline`, `tests/arnold/pipeline/native`, `tests/arnold/runtime`, `tests/arnold/pipelines/megaplan`, `tests/pipelines`, characterization fixtures, oracle/parity fixtures, root-level `test_*.py`, legacy CLI/profile/migration shim tests, and golden trace generators that can keep deleted imports alive.
- Keep restricted-Python generator material private/context-only unless needed as explicitly whitelisted internal coverage.
- Generator and operator scripts in the M5 inventory must run to completion against an installed wheel after migration, not only against the editable checkout.
- If shipped-pipeline, CLI, doc, generated-artifact, or scaffold work discovers a manifest/kernel/runtime contract gap, update M1/M2/M3 contract tests and `workflow-manifest-amendments.md`; do not silently widen contracts.

OUT:

- No final purge of legacy public imports or wheel entrypoints; M6 handles deletion.
- No redesign of M1-M3 core contracts unless a migration bug exposes a missing invariant.
- No new YAML-as-source or native-first docs.
- No broad unrelated documentation rewrite.

## Locked Decisions

- Docs and scaffolds teach explicit-node `arnold.workflow` / `arnold.patterns`, not native decorators, `PipelineBuilder`, `Stage`, `Edge`, or public `run_pipeline`.
- Every shipped pipeline must expose a canonical `build_pipeline()` returning `workflow.Pipeline`; `WorkflowManifest` is compiler output.
- A pipeline may only be whitelisted instead of migrated if it is demonstrably non-public: no CLI entrypoint, no import by any shipped pipeline, no docs reference, no generated skill, no package registry row, and no external-facing `build_pipeline()`. Whitelists require owner, expiry before M6, independent review, and a migrate/delete plan, and must not contain or teach old-native patterns such as native decorators, `PipelineBuilder`/`Stage`/`Edge`, old import paths, or copy-pasteable legacy examples.
- Generated YAML/DOT/Markdown views are disposable outputs generated from the manifest.
- Optional restricted-Python syntax is not canonical.
- M5 may be executed as parallel workstreams: M5a for shipped pipelines and CLI, M5b for generated surfaces, docs, scaffolds, package metadata, and inventory. Both must finish before M6 starts.
- Generated skills and scaffolds are regenerated/operator-facing artifacts, not stable public Python APIs. They must be correct, but they do not expand the stable API surface unless explicitly documented.

## Resolved Execution Decisions

- Legacy example pipelines are migrated only when they have public surface or useful maintained coverage. Dead stubs, obsolete demos, and native-only examples with no public surface are deleted or archived; no dead example is migrated merely for history.
- Surviving CLI names are the `arnold workflow ...` and explicitly retained operator commands from the M5 CLI mapping. Old `megaplan` and `arnold pipeline` commands are deleted by M6 unless a transition-only row exists before M6 and burns down before M6 completes.
- Operator documentation is rewritten when it describes surviving commands or workflows; obsolete docs are archived outside generated/agent-facing surfaces and cannot contain copy-pasteable old API examples.
- Legitimate whitelist entries are zero-public-surface internal coverage only, with owner, expiry, independent review, no old-native teaching surface, and dynamic/import proof. Public pipelines cannot be whitelisted.
- Generated skills, composed rules, projection docs, package-disposition data, package metadata, scaffolds, registries, templates, and CLI help are regenerated when tied to surviving surfaces; artifacts for deleted surfaces are deleted or archived outside active/generated surfaces.
- The authoritative CLI entrypoint is the `arnold` CLI dispatching to surviving workflow/product commands. Old `arnold.pipelines.megaplan.cli.*`, old package `__main__` files, and old parser snapshots are migration sources only and M6 deletion targets unless explicitly re-chartered.
- Any shipped-pipeline native-generator pattern without an M2/M3 manifest/runtime equivalent triggers a back-propagated contract amendment before M5 can close; it cannot be hidden behind whitelist or docs-only migration.

## Constraints

- Keep CLI and docs snapshots deterministic.
- Run installed/editable smoke tests where feasible before M6.
- Pipeline inventory should fail on new un-migrated shipped pipelines.
- Do not add compatibility examples that undermine the clean-break target.
- `arnold/cli/__init__.py` and package entrypoints must be audited so they do not lazy-import paths that M6 deletes.
- Built wheel and sdist checks must prove package data, generated assets, py.typed markers, entrypoints, and namespace packages are present or absent exactly as intended.

## Done Criteria

1. Every shipped pipeline is migrated to `workflow.Pipeline` with compile/dry-run/fake-run/docs tests, or deleted. Whitelist entries are permitted only for zero-public-surface internal coverage and include owner/expiry.
2. Each migrated pipeline has compile, dry-run, fake-run, and docs/example coverage.
3. Workflow CLI commands exist and have parser/snapshot tests. `arnold pipelines describe` is explicitly dispositioned as migrate/retain/delete with parser snapshot, help text, generated-surface, and installed-wheel smoke coverage.
4. Docs and scaffolds teach only the canonical explicit-node authoring style.
5. Generated skills, composed rules, projection docs, package authoring docs, package disposition data, scaffolds, and package metadata reference only surviving public surfaces.
6. Generated-artifact manifest, script/operator-tool inventory, package-build inventory, per-pipeline disposition table, and legacy-test inventory exist with no undecided rows.
7. Inventory scanners flag old native/builder/public graph APIs in shipped code, docs, generated artifacts, scripts, tools, tests, package metadata, and scaffolds.
8. Regenerating docs/skills/registries/disposition/scaffolds yields a clean diff and every generated artifact passes provenance, import-surface, compile, dry-run, fake-run, and embedded-example checks.
9. A formal characterization method exists: old-behavior traces are locked before migration, and new event journals are compared by semantic equivalence for node outcomes, decisions, capability invocations, suspension points, and deterministic artifact hashes.
10. Pipeline identity registries are regenerated as the final M5 step, and every registry `manifest_hash` equals `compiler(build_pipeline(current_tree, id)).manifest_hash`.
11. Pipeline inventory, script/tool inventory, generated-artifact manifest, package-build inventory, CLI dispatch-chain inventory, and CLI mapping are re-run after all migration/generation steps and match the final file tree.
12. Parser snapshots, CLI help text, command docs, and CLI semantic fixtures are regenerated from the installed wheel, trace to `id + manifest_hash` where pipeline-specific, and contain no deleted command names, deleted module paths, or old public authoring APIs except archival non-executable notes.
13. M6 has a concrete deletion list with no unknown shipped-pipeline blockers, and every deletion traces to an M5 migrate/delete/whitelist outcome.

## Touchpoints

- `arnold_pipelines/megaplan/pipelines/`
- `arnold/pipelines/evidence_pack/`
- `arnold/pipelines/folder_audit/`
- `arnold/pipelines/deliberation/`
- `arnold/pipelines/_template/`
- `arnold/cli/`
- parser snapshot tests and installed-wheel CLI smoke tests
- `arnold pipelines describe` command, parser snapshot, help text, dispatch target, and generated docs/skills that reference it
- CLI dispatch-chain inventory including `__main__.py`, `python -m`, help/completion generators, and nested subcommands
- `docs/arnold/`
- `docs/arnold/examples/`
- `docs/reference/arnold-projections.md`
- `docs/arnold/package-contract.md`
- `docs/arnold/package-authoring-contract.md`
- `arnold/pipelines/megaplan/data/_codex_skills/`
- `arnold/pipelines/megaplan/data/_composed/`
- final generated asset locations under `arnold_pipelines/megaplan/`
- `arnold/pipelines/megaplan/pipeline_ids.json`
- `arnold/pipelines/evidence_pack/pipeline_ids.json`
- package metadata and entrypoints
- package disposition data
- pipeline ID registry JSON artifacts
- namespace-package wheel configuration
- generated-artifact manifest
- generator/template/data-file semantic scanners
- script/operator-tool inventory
- legacy/native/parity test inventories
- `scripts/check_workflow_pipeline_inventory.py`
- `scripts/generate_arnold_docs.py`
- `scripts/adopt_plan.py`, `scripts/backfill_step_receipts.py`, `scripts/check_pipeline_id_registry.py`, `scripts/megaplan_live_watchdog.py`, `scripts/record_workflow_next_parity.py`, oracle/corpus/golden generators, `sync-skills.sh`, and duplicate `tools/` helpers
- `tests/pipelines/`
- `tests/docs/`
- `tests/cli/`

## Anti-Scope

- Do not use this sprint to reopen DSL/runtime architecture.
- Do not keep example-only compatibility shims.
- Do not migrate dead examples just to preserve history; delete or archive when justified.
- Do not make restricted Python public.

## Suggested Run

`partnered-5/thorough/high`

This is broad and user-facing, but most architecture is locked by prior milestones; the main planning risk is coverage and migration ordering.
