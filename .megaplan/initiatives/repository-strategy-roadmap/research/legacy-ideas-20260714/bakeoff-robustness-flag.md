# Add `--robustness` flag to `megaplan bakeoff run`

## Problem

`megaplan bakeoff run` has no `--robustness` flag. Inside the orchestrator, `_init_profile` runs `megaplan init` without passing robustness, so every profile gets the default robustness regardless of what the user wants. This was discovered live — a "light" bakeoff request silently ran at default (standard) robustness.

## Fix

Thread `--robustness` through the call chain:

1. **CLI layer** (`megaplan/bakeoff/cli.py`): add `--robustness` argument with the same choices as `megaplan init` accepts (`tiny`, `light`, `standard`, `robust`, `superrobust`). Default to `None` so the underlying `megaplan init` falls back to its own default if unspecified — preserves current behavior when the flag is omitted.

2. **Orchestrator entry** (`megaplan/bakeoff/orchestrator.py`): accept the robustness argument in `run_bakeoff()` and `_run_with_optional_status()`. Pass it to `_init_profile`.

3. **`_init_profile`** (`megaplan/bakeoff/orchestrator.py`): when `robustness` is not None, append `--robustness <value>` to the `megaplan init` subprocess command. When None, omit the flag entirely.

## Validation

- Unit test: `_init_profile` builds the right subprocess command when robustness is `"light"` (`--robustness light` appended) and when None (no `--robustness` flag).
- Integration test: a `run_bakeoff(..., robustness="light")` call propagates "light" through to the spawned init subprocess command. Easiest assertion: monkey-patch `asyncio.create_subprocess_exec` and inspect the args list.
- CLI smoke: `megaplan bakeoff run --help` shows `--robustness` with the choices.

## Out of scope

- Per-profile robustness (different robustness for each profile in one bakeoff). One robustness for the whole bakeoff is enough for v1.
- Plumbing robustness into bakeoff's `compare`/`pick`/`merge` (those don't run megaplan phases).
- Updating bakeoff's archived comparison schema to record robustness used.

## Success criteria

1. `megaplan bakeoff run --help` lists `--robustness` with the documented choices.
2. `megaplan bakeoff run --idea-file foo.md --profiles standard --robustness light` runs the profile at light robustness (verifiable from the worktree's `state.json` config).
3. Omitting `--robustness` preserves current behavior (no regression).
4. Test suite stays green.
