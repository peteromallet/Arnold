# M5: Generated Assets And Merge-Result Conformance

## Outcome

Regenerate all affected docs, registries, package disposition files, generated skills/assets, and manifest identity ledgers from the post-deletion tree, then prove the integrated merge result from clean wheel and sdist installs.

## Scope

IN:

- Regenerate package disposition Markdown from YAML/source data.
- Regenerate Arnold docs, registries, pipeline IDs, generated skills/composed rules, scaffolds, and any generated artifact that names Megaplan pipeline surfaces.
- Run generators twice and require a clean second diff.
- Run `scripts/chain_done_gate.py` with `.megaplan/briefs/workflow-manifest-runtime/blockers.json` or the cleanup chain's blocker list if one is created.
- Run `scripts/m6_purge_gate.py` against the integrated checkout.
- Build wheel and sdist from the merge result, install each in fresh environments, and run positive and negative installed-artifact conformance.
- Produce final manifest identity ledger proving surviving discovery/registry/generated/resume references match final compiler output.

OUT:

- No new implementation cleanup except blockers discovered by final conformance.
- No broad public API redesign.
- No branch/stash/worktree deletion.
- No final merge or push from this plan without human approval.

## Locked Decisions

- Final conformance runs from an integrated merge-result checkout, not only individual feature branches.
- Generated artifacts are outputs, not hand-edited facts.
- Review/attack findings are blockers until resolved or explicitly closed with evidence.
- Prevention controls are part of the final gate: `chain_done_gate.py`, `m6_purge_gate.py`, blocker checklist, and M7-style merge-result conformance.

## Open Questions

- Whether this cleanup chain needs its own blocker checklist or should extend `.megaplan/briefs/workflow-manifest-runtime/blockers.json`.
- Exact command set for all generators after M4 deletion.
- Whether CI should get a dedicated job for these gates or reuse existing wheel smoke jobs.

## Constraints

- No editable install may satisfy final conformance.
- Build from clean artifacts: remove stale `build/`, `dist/`, and egg-info before package tests.
- CLI/help scans must run from installed wheel.
- Any generated reference to deleted paths is a blocker.
- Any unresolved blocker item keeps the chain open.

## Done Criteria

1. Package disposition validation passes and regenerated Markdown is clean after a second render.
2. Docs, generated skills, composed rules, registries, pipeline IDs, scaffolds, and CLI help snapshots contain no deleted surfaces.
3. `scripts/chain_done_gate.py` passes against the relevant chain spec, chain state, plan states, and blocker checklist.
4. `scripts/m6_purge_gate.py` passes against the integrated checkout.
5. Wheel and sdist builds are clean, installed in fresh environments, and pass installed-artifact positive and negative conformance.
6. Positive installed smoke proves `import arnold_pipelines.megaplan`, `build_pipeline()` returns `arnold.workflow.dsl.Pipeline`, and compiler output is valid.
7. Negative installed smoke proves deleted paths, legacy constructors, `epic_blitz`, old public `Stage`/`Edge` exports, and compatibility namespaces fail.
8. Dynamic import tracing and final `sys.modules` audit show no deleted prefix.
9. Final manifest identity ledger resolves every surviving discovery, registry, generated-artifact, tenant/trust, and resume reference to current `compile_pipeline(build_pipeline()).manifest_hash`.
10. Final report lists warnings, re-chartered allowlist rows, and any human follow-up needed before merge.

## Touchpoints

- `scripts/chain_done_gate.py`
- `scripts/m6_purge_gate.py`
- `.megaplan/briefs/workflow-manifest-runtime/blockers.json`
- `.megaplan/briefs/workflow-manifest-runtime/m7-merge-result-conformance.md`
- `scripts/render_package_disposition_md.py`
- `scripts/validate_package_disposition.py`
- `scripts/check_workflow_pipeline_inventory.py`
- `scripts/check_pipeline_id_registry.py`
- `scripts/generate_arnold_docs.py`
- `docs/arnold/`
- generated skills/composed rules and package data
- wheel/sdist build metadata
- installed-wheel tests and CLI/help scans

## Anti-Scope

- Do not treat branch-local success as release success.
- Do not hand-edit generated outputs without rerunning generators.
- Do not delete branches/worktrees automatically.
- Do not run `execute` without explicit human approval.

## Rubric

Overall plan difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`.

Rationale: this is the final defense against stale generated artifacts, package-data leakage, and merge resolution resurrecting deleted legacy surfaces.
