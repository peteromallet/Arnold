# M4: Physical Deletion And Conformance Gates

## Outcome

Physically delete `_pipeline/`, `stages/`, compatibility shims, and any remaining bridge/forwarder surfaces, then enforce their absence in source, tests, wheel, sdist, dynamic imports, and runtime module state.

## Scope

IN:

- Delete `arnold_pipelines/megaplan/_pipeline/`.
- Delete `arnold_pipelines/megaplan/stages/`.
- Delete `_compatibility.py` and any remaining bridge/forwarder/lazy shim discovered by cleanup scans.
- Strengthen `scripts/m6_purge_gate.py` and installed-wheel absence tests to cover deleted directories, representative submodules, legacy symbols, type stubs, package data, entrypoints, and tests that keep legacy behavior alive.
- Add wheel/sdist unpack audits and post-suite `sys.modules` deleted-prefix checks.
- Remove or re-charter conformance allowlist rows that mention deleted surfaces.

OUT:

- No new architecture features.
- No broad generated-asset regeneration except gate inputs needed for deletion.
- No compatibility extension for consumers.
- No final merge-result certification; that is M5.

## Locked Decisions

- No permanent shim or alias survives for `_pipeline`, `stages`, `compile_planning_pipeline`, or `build_legacy_pipeline`.
- Source-tree success is insufficient; installed wheel and sdist contents must prove absence.
- Tests may not assert legacy surfaces remain.
- Dynamic import and `sys.modules` evidence are first-class conformance signals.

## Open Questions

- Exact deleted-prefix list for installed-wheel dynamic import tracing.
- Which allowlist rows can be removed outright versus re-chartered as non-legacy with owner and expiry.
- Whether package metadata currently includes stale package data for deleted directories.

## Constraints

- M3 import burn-down must be green before physical deletion.
- Clean build artifacts before wheel/sdist tests to avoid stale cache leakage.
- Do not use editable installs as deletion proof.
- Do not change behavior goldens to make deletion pass.

## Done Criteria

1. `test ! -e arnold_pipelines/megaplan/_pipeline`.
2. `test ! -e arnold_pipelines/megaplan/stages`.
3. No source, tests, scripts, tools, registries, generated data, entrypoints, type stubs, or package metadata import deleted paths or symbols except deliberate negative tests.
4. `scripts/m6_purge_gate.py` passes.
5. Installed-wheel import-failure tests cover top-level deleted packages, representative submodules, legacy symbols, `python -m` targets, console entrypoints, and wheel `RECORD` contents.
6. Wheel and sdist unpack audits prove no deleted `.py`, `.pyi`, `.pyc`, `py.typed`, package data, `__main__.py`, or entrypoint target survives.
7. Dynamic import tracing and final `sys.modules` enumeration prove no deleted prefix was resolved during the conformance suite.
8. Conformance allowlists contain zero legacy exceptions or re-chartered non-legacy rows with owner, expiry, and dynamic-import proof.

## Touchpoints

- `arnold_pipelines/megaplan/_pipeline/`
- `arnold_pipelines/megaplan/stages/`
- `arnold_pipelines/megaplan/_compatibility.py`
- `tests/installed_wheel/`
- `scripts/m6_purge_gate.py`
- `pyproject.toml` and package data configuration
- conformance allowlists
- dynamic import tracing utilities
- CLI entrypoint metadata
- type stubs and `py.typed` markers

## Anti-Scope

- Do not leave compatibility modules for deleted paths.
- Do not defer absence checks to final merge only.
- Do not perform general repo cleanup.
- Do not run `execute` without explicit human approval.

## Rubric

Overall plan difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`.

Rationale: deletion can look successful in source while stale packaging artifacts or dynamic imports keep the old API alive.
