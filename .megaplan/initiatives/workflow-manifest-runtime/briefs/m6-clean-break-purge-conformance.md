# M6: Clean-Break Purge And Conformance

## Outcome

Make the clean-break end state true by deleting obsolete public/native/compatibility surfaces and enforcing installed-wheel, import graph, docs/scaffold, golden behavior, and runtime-contract conformance gates.

The reviewer should be able to install the package and verify old public surfaces fail while the new Arnold workflow and `arnold_pipelines.megaplan` surfaces pass smoke, golden, and conformance tests.

## Operating Philosophy

M6 makes the clean break physically true. Passing source-tree tests is not enough: deleted surfaces must be absent from installed artifacts, entrypoints, docs, generated data, type surfaces, caches, runtime imports, filesystem reads, and the final merge result. If a compatibility path still works, teaches, ships, or remains necessary for behavior, the purge is not done.

## Scope

IN:

- Delete the top-level `megaplan` console entrypoint and any remaining `import megaplan` paths if the clean-break policy remains authoritative. If no top-level package exists, the package deletion gate is recorded as not applicable and the import-failure gate still runs.
- Delete `arnold/pipelines/megaplan/`, `_pipeline`, bridge, compatibility, `_forward_m2_m3`, package-local builder/executor/types/patterns/subloop, native hooks, native runner, and stale relocation copies.
- Delete or privatize `arnold/pipeline/native/` and old public `PipelineBuilder`, `Stage`, `Edge`, `ParallelStage`, and `run_pipeline` exports.
- Delete or explicitly re-charter old `arnold/runtime/` modules so there is no second public runtime surface beside `arnold.execution`/`arnold.kernel`.
- Delete or explicitly re-charter compatibility namespaces and dynamic import shims including `agent/__init__.py`, legacy `arnold.agent` Megaplan-forwarding adapters, `arnold/pipeline/__init__.py` re-exports, `arnold/pipelines/megaplan/__init__.py`, `_core/__init__.py`, package-local builder/executor/type exports, and any old `__main__`/CLI forwarding modules.
- Delete `tests/_pipeline/` or convert remaining tests to new workflow/runtime coverage.
- Enforce AST/import graph scans, docs/scaffold scans, pipeline discovery scans, installed-wheel import tests, golden behavior parity, hook parity matrix, and IR contract tests.
- Enforce package metadata/entrypoint checks, public type-surface checks, generated-skill/projection checks, M5-to-M6 inventory traceability, and final merge-result conformance.
- Enforce generated-artifact freshness, script/tool import scans, legacy-test conversion scans, conformance allowlist burn-down, built wheel and sdist contents checks, and unresolved-drift/inventory blockers.
- Enforce generated-artifact semantic conformance: every shipped generated skill, composed rule, projection doc, scaffold template, package-disposition entry, and pipeline registry row must pass provenance freshness, import-surface scan, compile/fake-run of embedded examples, and regeneration diff against current generators.
- Build from a clean tree before conformance: remove build/dist/egg-info caches, rebuild wheel and sdist, unpack both artifacts, inspect wheel `RECORD`, install into a fresh environment, and run conformance against that installed distribution rather than editable source.
- Audit bytecode/cache and type artifacts: deleted package roots must have no surviving `__pycache__`, `.pyc`, `.pyi`, stale `py.typed`, or type-stub sidecar in the working tree, wheel, or sdist.
- Audit CLI entrypoints from the installed artifact: console metadata, `python -m` package entrypoints, package `__main__.py`, nested subcommand `--help`, shell completion/help output, and lazy dispatch functions must not target deleted modules.
- Enforce the M5 disposition of `arnold pipelines describe`: if retained or migrated, prove it passes installed-wheel smoke and targets only surviving modules; if deleted, prove `arnold pipelines describe <module>` fails from the installed wheel.
- Instrument the full installed-wheel conformance suite to fail on runtime import resolution of deleted paths through `importlib.import_module`, `__import__`, package `__getattr__`, entrypoint loading, lazy registries, `pkg_resources`, `eval`, or `exec`.
- Instrument filesystem reads during conformance so surviving runtime/operator/CLI code cannot read old `.megaplan` state, locks, old-format `state.json`, or legacy-format skill/docs/discovery/template files outside explicit migration/projection modules with sunset and owner.
- Produce a final manifest-identity ledger that resolves every pipeline ID, discovery row, trust classification, tenant derivation, generated-artifact reference, registry hash, and surviving resume-cursor manifest hash to a final-tree `build_pipeline()` compile result.
- Resolve every surviving judge-manifest sidecar (`piece_version`, `judge_version`, `rubric_hash`) against either the compiler's `manifest_hash` if absorbed or a locked regeneration gate if orthogonal. Stale judge-manifest hashes fail M6 with the same severity as stale pipeline registry hashes.
- Audit xfail/skip markers, root-level tests, `conftest.py`, test helpers, oracle/characterization harnesses, generators, scripts, and tools for references to deleted modules, old state authority, or skipped parity checks.
- If deletion/conformance work discovers a manifest/kernel/runtime contract gap that was masked by legacy surfaces, update M1/M2/M3 contract tests and `workflow-manifest-amendments.md`; do not silently widen contracts during purge.
- Static AST scans are insufficient: conformance must also catch string-based/dynamic imports, lazy import maps, `importlib.import_module`, package `__getattr__`, `__all__`, console entrypoints, type stubs, generated docs/skills, and installed-wheel contents.
- Update final migration docs and branch-retirement notes with what was removed and how to migrate callers.
- Produce branch/worktree retirement notes for quarry and migration branches/worktrees, classified as `landed`, `delete`, or `parked`. Do not delete branches/worktrees automatically as part of this milestone.

OUT:

- No new architecture features.
- No new shipped-pipeline migrations except blockers discovered by deletion gates.
- No compatibility policy change unless explicitly approved before deletion.
- No branch/stash cleanup beyond migration artifacts required for this epic.

## Locked Decisions

- No shims is the target: no public `megaplan`, no `arnold.pipelines.megaplan`, no `_pipeline`, no compatibility re-exports.
- `arnold_pipelines.megaplan` survives as the permanent product package. `arnold.pipelines.megaplan` does not.
- Temporary bridge/deprecation/shadow-run scaffolding from M4/M5 must be gone by M6 unless the clean-break decision is explicitly changed.
- All runtime execution traverses the Arnold workflow manifest substrate.
- Public authoring is `arnold.workflow` and `arnold.patterns`.
- Behavior parity was established before deletion; M6 should remove obsolete surfaces, not rediscover behavior.

## Resolved Execution Decisions

- Clean-break policy is reaffirmed by M6 unless explicitly changed before deletion. External consumers discovered through M4/M5 evidence receive migrate/delete/transition rows; they do not justify permanent old import paths by default.
- Remaining old modules are deleted unless an M5/M6 inventory row proves zero public surface, non-legacy purpose, owner, expiry, independent review, and dynamic-import proof. Accidental public surface blocks M6.
- Generated docs, skills, registries, package metadata, parser/help snapshots, scaffolds, and package-disposition files are regenerated after deletion from the post-deletion tree and audited against the final installed wheel.
- Real in-flight runs keep only manifest-coordinate aliases or explicit quarantine records. Old resume aliases cannot survive as runtime authority after M6.
- M4 deprecation warnings, shadow-run drift reports, external-consumer evidence, CLI inventories, branch/worktree notes, and drift reports are M6 blockers until each row is migrate/delete/archive/quarantine/re-charter with rationale.
- The final reaffirmation happens through M6 done criteria and post-merge conformance: old public surfaces fail from the installed wheel/sdist, new surfaces pass, and no deleted path is resurrected.

## Constraints

- Delete only after scanner/golden/hook gates identify no unresolved blockers.
- Installed-wheel tests are required; editable-only success is insufficient.
- Source-tree success is insufficient: M6 must pass from a clean wheel and from an sdist-built install with no repo root, editable `.pth`, stale build cache, or local `PYTHONPATH` leakage.
- Do not change behavior goldens to make deletion pass.
- Avoid destructive git cleanup commands unrelated to the migration.
- Run the final deletion/conformance suite against the merge result or a merge-equivalent checkout, not only the feature branch.
- M6 deletion is allowed only for entries traced to M5 inventories and M4 bridge/state inventories.
- M6 cannot start while any M4 shadow/canary drift report, Megaplan command mapping row, M5 CLI mapping row, generated-artifact row, script/tool row, legacy-test row, package-disposition row, or conformance allowlist row is unresolved.
- Every conformance allowlist row must be either removed or re-chartered with owner, expiry, and non-legacy rationale; dynamic-import exceptions count as unresolved blockers unless re-chartered.
- M6 cannot start while any M5 whitelist row still protects old native semantics; whitelist rows must burn down to migrate/delete or be independently re-chartered as non-public, non-legacy internal coverage before purge.
- M6 cannot close if any `skip`/`xfail`, whitelist, allowlist, or re-chartered row references a deleted module, class, function, CLI command, old state file, or runtime path without independent review and dynamic-import proof of zero legacy contact.

## Done Criteria

1. `import megaplan` fails in installed-wheel tests unless the clean-break decision is explicitly changed.
2. `import arnold.pipelines.megaplan` fails after relocation.
3. `from arnold.pipeline import Stage`, `Edge`, `ParallelStage`, `PipelineBuilder`, and public `run_pipeline` fail.
4. No production code imports `._pipeline`, old native public APIs, bridge files, or lazy compatibility maps.
4. No production code or compatibility namespace dynamically imports deleted surfaces through `importlib`, lazy `__getattr__`, `__all__`, console dispatch, or type-only shims.
5. Docs/scaffolds contain no public examples of old builder/native APIs.
6. Generated skills, composed rules, projection docs, package authoring docs, package disposition data, package metadata, and CLI entrypoints contain no references to deleted surfaces.
7. Package-disposition validation passes against the final file tree with no rows pointing to deleted paths.
8. Discovery trust classification tests pass with no hardcoded path fragments pointing to deleted directories.
9. Public type-surface checks prove no stale re-exports, `__all__` entries, `py.typed` markers, or type stubs leak deleted APIs.
10. Conformance allowlists are burned down to zero legacy exceptions or re-chartered with owner, expiry, and non-legacy rationale.
10a. Every allowlist glob or broad-spectrum pattern, including `/**` and `fnmatch` wildcards, is expanded to its concrete file set against the final tree. Each matched file receives an individual migrate/delete/re-charter disposition. No glob entry survives M6 unless every concrete match is independently classified with owner and non-legacy rationale.
11. Built wheel and sdist contain `arnold_pipelines`, required `py.typed` markers, package data, generated assets, and no deleted package data.
12. `git ls-files` plus AST/import scans cover code, tests, scripts, tools, generators, docs, package metadata, and generated artifacts.
13. Generated-artifact freshness check passes after regenerating docs/skills/registries/disposition/scaffolds.
14. M6 deletion list is a closed subset of M5 migrate/delete/whitelist outcomes plus M4 bridge/state inventories.
15. Golden behavior parity, hook parity, IR contract, semantic manifest diffs, characterization-trace comparison, resume/replay, pipeline discovery, live smoke, installed-wheel, installed-wheel CLI, built wheel/sdist, and merge-result conformance gates all pass.
16. No stale-format state files remain in migrated `.megaplan` plan data except explicitly excluded fixtures or archived blobs with rationale.
17. Branch/worktree retirement notes classify quarry/migration branches and worktrees without deleting them automatically.
18. Final docs explain the new public surface and migration path.
19. M1, M2, and M3 contract/runtime tests pass against the final installed wheel without importing any path deleted by M6.
20. Surviving `arnold workflow` CLI status/trace/inspect/override outputs match locked semantic fixtures derived from manifest events/artifacts/control transitions.
21. Conformance allowlist rows have no legacy import surface. Any re-chartered non-legacy row has independent review, owner, expiry, and dynamic-import proof.
22. A clean wheel/sdist contents audit proves no deleted `.py`, `.pyi`, `.pyc`, `py.typed`, package data, `__main__.py`, entrypoint metadata, or namespace path survives in distribution artifacts.
22a. Every surviving CLI command's `--help` text, shell-completion output, and nested subcommand dispatch chain is captured from the installed wheel and scanned. No deleted module path, package name, command name, or old public API surface appears in any help text, usage line, or dispatch target.
23. Installed-wheel import-failure tests cover every deleted package, subpackage, dotted symbol path, `python -m` entrypoint, and old console command target, not only top-level imports.
24. Dynamic runtime import tracing over the full conformance suite proves no deleted path is resolved through direct import, lazy import, registry lookup, entrypoint loading, `TYPE_CHECKING` stub, `eval`, or `exec`.
24a. Installed-wheel conformance enumerates all `sys.modules` keys after the full suite runs. Any key resolving to a deleted package, subpackage, or dotted path fails M6, regardless of whether a dynamic import was intercepted during tracing.
25. Every `module:qualname` string in manifests, registries, capability maps, policy tables, CLI dispatch tables, config files, and generated artifacts resolves against the surviving installed-wheel graph, and its full import closure contains no deleted surface.
26. Every registered prompt builder, policy, reducer, capability handler, control transition, adapter registration path, and callback recovery path is exercised with import tracing enabled.
27. Generator scripts, operator tools, sync utilities, templates, data files, code fences, composed rules, and every `SKILL.md` pass semantic deleted-surface scans after regeneration from the post-deletion tree.
28. The historical-state filesystem-read trace proves no surviving runtime/operator path reads old `.megaplan` authority, old-format `state.json`, or legacy-format skill/docs/discovery/template files outside sunset-expired migration/projection modules; old locks and untranslated old resume cursors are absent or quarantined.
29. The final manifest-identity ledger proves every surviving registry/discovery/trust/tenant/generated/resume reference matches `compiler(build_pipeline(final_tree, id)).manifest_hash`; stale or orphaned hashes fail M6.
30. Every `skip`/`xfail` marker in the merge-result test tree has a non-legacy reason, and no marker masks import failure or behavior gaps for deleted surfaces.
31. Merge-result conformance runs after all milestone branches are integrated: deleted files from M4/M5 inventories are still absent, generated artifacts regenerate cleanly from the merged tree, canonical manifest hashes match final compiler output, and all installed-wheel gates pass from the merged checkout.

## Touchpoints

- `megaplan/`
- `arnold/pipelines/megaplan/`
- `arnold/pipeline/native/`
- `arnold/runtime/`
- `arnold/pipeline/__init__.py`
- `tests/_pipeline/`
- `tests/arnold/conformance/`
- `tests/installed_wheel/` or equivalent wheel smoke tests
- `docs/arnold/`
- packaging and entrypoint metadata
- generated skills, composed rules, projection docs, package disposition data, and type-surface metadata
- discovery trust gates and pipeline ID registry artifacts
- scripts, tools, root generators, sync scripts, and operator utilities
- conformance allowlists
- dynamic-import/lazy-export scans
- wheel/sdist unpack audits, entrypoint metadata, `__main__.py`, type stubs, `__pycache__`, and stale build artifacts
- filesystem-read instrumentation for old `.megaplan` state authority
- final manifest-identity ledger and post-merge conformance report
- branch/worktree retirement notes

## Anti-Scope

- Do not leave permanent alias modules for old import paths.
- Do not delete baseline/parity evidence.
- Do not introduce new user-facing workflow syntax.
- Do not perform general repository cleanup outside the migration.

## Suggested Run

`partnered-5/thorough/high`

This sprint deletes public surfaces and compatibility paths; a bad plan can pass local tests while breaking installed consumers or resume contracts.
