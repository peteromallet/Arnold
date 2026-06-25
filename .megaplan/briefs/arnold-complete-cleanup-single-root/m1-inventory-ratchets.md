# M1: Inventory And Ratchets

## Outcome

Every legacy Megaplan caller, public surface, side effect, package/discovery row, docs example, and remaining implementation file is inventoried before migration. CI or tests prevent new legacy coupling from entering while the epic runs.

## Scope

In:

- AST-scan all Python source for imports of `arnold.pipelines.megaplan` and `arnold_pipelines.megaplan`.
- Scan command strings, docs, skills, scripts, tests, generated assets, and examples for `python -m arnold.pipelines.megaplan` and path references to `arnold/pipelines/megaplan`.
- Inventory `arnold/pipelines/megaplan/_pipeline` responsibilities and direct callers.
- Snapshot public top-level exports, lazy `__getattr__` behavior, CLI commands, chain APIs, worker APIs, and discovery builder paths.
- Create a checked-in legacy-file registry with `legacy_path`, `canonical_target`, `kind`, `owner`, `removal_ticket`, `expires_milestone`, and `justification`.
- Add shrink-only tests: new legacy imports fail; legacy implementation count cannot increase; unregistered legacy files fail.

Out:

- Do not move implementation files yet except for test/support code required to create the ratchets.
- Do not add compatibility shims before the registry and shim validator exist.

## Locked Decisions

- Temporary shims are allowed only while the epic is executing.
- A shim may not contain business logic, registration side effects, conditionals, or target a missing canonical module.
- `_pipeline` is not a final canonical namespace.

## Done Criteria

- The inventory can be regenerated deterministically.
- The legacy-file registry matches the files on disk.
- Tests fail if a new untracked `arnold.pipelines.megaplan` import or implementation file appears.
- The previous dirty `_pipeline` fake-shim attempt would fail the new gates.
