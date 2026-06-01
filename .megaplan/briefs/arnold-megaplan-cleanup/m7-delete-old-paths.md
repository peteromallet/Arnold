# M7: Delete Old Privileged Paths

## Outcome

Remove old privileged planning paths and stale compatibility surfaces after the replacement Arnold/Megaplan plugin structure is proven.

## Scope

In:
- Delete or fully retire `_pipeline/planning.py`, `_pipeline/planning_bindings.py`, old `planning/`, old global planning prompt modules, planning-specific code under generic runtime paths, hardcoded `"planning"` defaults, and old package paths if rename is complete.
- Explicit deletion candidates include `megaplan/_pipeline/planning.py`, `megaplan/_pipeline/planning_bindings.py`, `megaplan/planning/`, planning-specific code remaining under old `_pipeline/stages/`, old global planning prompt modules, hardcoded `"planning"` defaults, and the old top-level `megaplan` package if M6 completed the rename.
- Keep plugin-owned product surfaces under `arnold.pipelines.megaplan/` unless M-1 classified them for deletion or Arnold substrate extraction.
- Verify static and string-level gates pass. Do not skip or relax any boundary test. Fix any leakage exposed by existing gates before declaring deletions complete.

Out:
- Do not delete `chain/`, `cloud/`, `supervisor/`, `resident/`, `orchestration/`, `bakeoff/`, or Megaplan-specific worker adapters merely because they used to live under the old top-level package.
- Do not add new compatibility surfaces.

## Locked Decisions

- No public `planning` identity remains except documented legacy migration behavior.
- Generic Arnold tests must pass without Megaplan installed.
- Megaplan plugin tests pass as one plugin.

## Required Outputs

- Confirmation that M6 acceptance criteria are fully met before deletions begin.
- List of docs to archive versus rewrite, with rationale.

## Constraints

- Deletions must be backed by tests and gates.
- Do not accept skipped boundary tests.

## Done Criteria

- Old privileged modules are gone.
- Static and string-level gates pass.
- Generic Arnold tests pass without Megaplan plugin.
- Megaplan plugin tests pass.
- Another non-Megaplan plugin or fixture proves reusable primitives.
- Docs no longer point users at old privileged paths.

## Touchpoints

- old `_pipeline/planning*`
- old `planning/`
- old global prompt/stage paths
- docs
- tests

## Anti-Scope

- Do not keep dead files "just in case".
- Do not merge with known policy leakage.
