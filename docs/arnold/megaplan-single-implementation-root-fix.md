# Megaplan Single-Implementation Root Fix

## Problem

Megaplan currently has two live Python package trees:

- `arnold_pipelines/megaplan`
- `arnold/pipelines/megaplan`

That is the root category of the recent failures. A fix can land in one tree while
the local CLI, tests, or worker process imports the other tree. The immediate
`engine_write_isolation_unverified` bug was one instance of this: the packaged
tree had the local-dev fallback behavior, while the source-tree import path did
not.

This is worse than a duplicate-file cleanup problem. The two trees contain
hundreds of overlapping files with real behavior drift. Any mirrored-runtime
model will keep producing stale-copy bugs.

## Root Decision

`arnold_pipelines.megaplan` should be the single implementation.

Reasons:

- `pyproject.toml` ships `arnold_pipelines` and excludes `arnold/pipelines/**`
  from builds.
- `arnold_pipelines/discovery.py` marks `arnold_pipelines/megaplan` as migrated
  and marks `arnold/pipelines/megaplan` as legacy/delete.
- Installed users should not depend on `arnold/pipelines/megaplan`.

The source-tree path `arnold.pipelines.megaplan` may exist temporarily while the
migration is in progress, but it is not part of the final state. Temporary shims
are allowed only as scaffolding inside a single migration branch, and every shim
must be removed before the cleanup is considered complete.

## Desired End State

There is exactly one implementation of Megaplan runtime behavior:

```text
arnold_pipelines/megaplan/
```

During migration only, the old import path may become temporary scaffolding:

```text
arnold/pipelines/megaplan/
  __init__.py       -> aliases/delegates to arnold_pipelines.megaplan
  __main__.py       -> calls arnold_pipelines.megaplan.__main__
  runtime/...       -> temporary shim modules only while callers are being moved
  workers/...       -> temporary shim modules only while callers are being moved
  prompts/...       -> temporary shim modules only while callers are being moved
```

No module under `arnold/pipelines/megaplan` should contain original business
logic during the migration. No module under `arnold/pipelines/megaplan` should
remain at all after the migration.

## Execution Plan

### Phase 0: Confirm Authority

Goal: make the package authority explicit before moving code.

Actions:

1. Record `arnold_pipelines.megaplan` as the single implementation authority in
   this doc and in any migration docs that currently disagree.
2. Change comments/docstrings in `arnold/pipelines/megaplan` that claim that tree
   is canonical.
3. Add a short temporary compatibility notice to
   `arnold/pipelines/megaplan/__init__.py` only if the package cannot be deleted
   in the same phase.

Acceptance:

- No repo documentation claims `arnold/pipelines/megaplan` is the implementation
  authority.
- `pyproject.toml`, discovery metadata, and docs all point to the same survivor:
  `arnold_pipelines.megaplan`.

Estimated time: 1-2 hours.

### Phase 1: Add Import-Drift And Deletion Tripwires

Goal: make the duplicate-runtime failure mode visible in CI before deleting code.

Actions:

1. Add a test that fails if both package trees contain non-shim implementations
   for runtime-critical modules.
2. Start with the directories that can block local execution or mutate state:

Start with these directories:

- `runtime`
- `workers`
- `prompts`
- `chain`
- `cli`
- `handlers`
- `orchestration`
- `execute`

3. Add an explicit temporary allowlist for files that are still being migrated.
4. Make the allowlist shrink-only: every PR can remove entries, but adding an
   entry requires a comment explaining why the legacy implementation must remain.
5. Define a temporary shim as a small module that imports or forwards to
   `arnold_pipelines.megaplan`, without copied implementation.
6. Add a deletion-deadline check so temporary shims are tracked explicitly and
   cannot become permanent compatibility policy by accident.

Acceptance:

- CI can distinguish a shim from a second implementation.
- Reintroducing copied runtime code under `arnold/pipelines/megaplan` fails a
  test.
- The current allowlist is checked in and visible.
- Every temporary shim is listed with an owner and removal phase.

Estimated time: 2-4 hours.

### Phase 2: Convert Runtime Blockers Away From Legacy Imports

Goal: stop local dev commands from importing stale runtime behavior, then delete
the legacy runtime surface.

Actions:

Do these first because they are the paths most likely to block local runs:

1. `arnold/pipelines/megaplan/__main__.py`
2. `arnold/pipelines/megaplan/cli/__init__.py`
3. `arnold/pipelines/megaplan/runtime/engine_isolation.py`
4. `arnold/pipelines/megaplan/workers/_impl.py`
5. `arnold/pipelines/megaplan/workers/hermes.py`
6. `arnold/pipelines/megaplan/workers/turn_cap.py`
7. `arnold/pipelines/megaplan/prompts/*.py`

Preferred action: update callers/tests so they import
`arnold_pipelines.megaplan` directly, then delete the legacy file.

Temporary fallback: if a caller cannot be migrated in the same phase, replace
the legacy file with a shim and add it to the deletion tracker.

Example pattern:

```python
"""Compatibility shim for the legacy arnold.pipelines.megaplan import path."""

from arnold_pipelines.megaplan.runtime.engine_isolation import *  # noqa: F401,F403
```

For CLI entrypoints, prefer explicit forwarding:

```python
from arnold_pipelines.megaplan.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Acceptance:

- Runtime commands use `python -m arnold_pipelines.megaplan ...`.
- `python -m arnold.pipelines.megaplan ...` is either removed or fails with a
  clear migration error, not a second implementation.
- Runtime isolation, worker launch, Hermes tool parsing, turn caps, and prompt
  rendering are not independently implemented under the legacy path.
- Existing tests either pass or are deliberately moved to the canonical import
  path.

Estimated time: 0.5-1.5 days.

### Phase 3: Make Source-Tree Commands Exercise The Real Implementation

Goal: remove developer muscle memory for the legacy module path instead of
preserving it.

Actions:

1. Update docs/scripts to call the canonical module path:

Canonical command:

```bash
python -m arnold_pipelines.megaplan status --plan <plan>
```

2. Add a legacy-path test that proves `python -m arnold.pipelines.megaplan` is no
   longer a supported command once the package is deleted.
3. If temporary shims are still present mid-migration, add tests proving they are
   only forwarding and are listed for removal.

Acceptance:

- Canonical commands produce the expected plan state.
- Repo docs and scripts no longer instruct anyone to use
  `python -m arnold.pipelines.megaplan`.
- Any temporary legacy CLI shim has a removal ticket in the same plan.

Estimated time: 2-4 hours.

### Phase 4: Move Behavior Tests Off The Legacy Path

Goal: make tests enforce the real package boundary instead of accidentally
keeping the duplicate tree alive.

Actions:

Tests should import `arnold_pipelines.megaplan`.

Allowed legacy-path tests during migration:

- deletion/migration-error tests
- temporary-shim removal tracking tests

Disallowed legacy-path tests:

- import compatibility as a permanent support contract
- CLI delegation compatibility as a permanent support contract
- worker behavior
- prompt rendering behavior
- runtime isolation behavior
- chain execution behavior
- state mutation behavior

Those behavior tests must target `arnold_pipelines.megaplan`.

Acceptance:

- Behavior tests import `arnold_pipelines.megaplan`.
- Only deletion/tracking tests import `arnold.pipelines.megaplan`.
- No test fails solely because it expected the legacy package to own behavior.

Estimated time: 0.5-1 day.

### Phase 5: Delete Duplicate Implementation Modules

Once a directory is converted, delete original implementation files from the
legacy tree instead of leaving mirrored copies.

The goal is not line parity. The goal is no second implementation.

Actions:

1. Delete migrated implementation modules from `arnold/pipelines/megaplan`.
2. Remove temporary shims after their callers are migrated.
3. Do not keep shims for known external callers unless a separate compatibility
   release policy is explicitly approved. The default is deletion.
4. Shrink the Phase 1 allowlist after each deletion batch.

Acceptance:

- `arnold/pipelines/megaplan` contains no runtime implementation and no shims.
- The drift tripwire allowlist is empty for runtime-critical directories.
- The duplicate file count for runtime-critical paths is zero.

Estimated time: 1-2 days.

### Phase 6: Update Misleading Docs And Comments

Any text claiming `arnold/pipelines/megaplan` is canonical should be changed.

In particular:

- `arnold/pipelines/megaplan/__init__.py` currently says it is canonical. During
  migration it may carry a temporary deletion notice; after migration the file
  should not exist.
- Migration docs should say `arnold_pipelines.megaplan` is the shipped
  implementation until a deliberate package-rename migration is completed.

Acceptance:

- Searching for `canonical` near `arnold/pipelines/megaplan` no longer points to
  the legacy tree as the implementation authority.
- Migration docs, package docs, and command docs describe the same import model.

Estimated time: 2-4 hours.

### Phase 7: Final Deletion

Goal: remove the old import path completely.

Actions:

1. Inventory remaining imports of `arnold.pipelines.megaplan`.
2. Migrate every internal caller to `arnold_pipelines.megaplan`.
3. Delete `arnold/pipelines/megaplan`.
4. Add a test that fails if `arnold/pipelines/megaplan` is recreated.

Acceptance:

- `arnold/pipelines/megaplan` is deleted.
- The chosen policy is documented as no legacy shim.
- CI prevents the legacy package from being recreated.

Estimated time: 0.5-1 day.

## Verification

Run these after each conversion batch:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/runtime/test_megaplan_import_path_parity.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/workers/test_hermes_tool_markup.py tests/prompts tests/test_workers_turn_cap.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/installed_wheel -q
```

Also run a real command through both import paths:

```bash
PYTHONPATH=/Users/peteromalley/Documents/Arnold python -m arnold_pipelines.megaplan status --plan <plan>
PYTHONPATH=/Users/peteromalley/Documents/Arnold python -m arnold.pipelines.megaplan status --plan <plan>
```

Both commands should report the same plan state and should not use different
runtime code paths.

## Definition Of Done

This category of error is purged when all of the following are true:

- `arnold_pipelines/megaplan` is the only Megaplan implementation.
- `arnold/pipelines/megaplan` is deleted.
- CI fails if `arnold/pipelines/megaplan` is recreated.
- Packaged-wheel tests pass.
- Source-tree CLI compatibility is intentionally removed with documented
  replacement commands.

Until then, any one-off mirror patch is only a temporary containment fix.

## Total Estimate

Expected time: 3-5 focused engineering days.

Fast path: about 2 days if callers can be moved aggressively and temporary shims
are deleted in the same branch.

Conservative path: about 1 week if many tests or internal tools depend on
implementation details under `arnold.pipelines.megaplan`.

This should not be treated as a quick find-and-delete task. The subagent measured
343 different common files, 687 files only under `arnold/pipelines/megaplan`,
and 52 files only under `arnold_pipelines/megaplan`. The safe work is to remove
runtime authority from the legacy tree in batches, with CI tripwires after the
first batch so drift cannot silently reappear.
