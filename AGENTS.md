# AGENTS.md

## Project Context

VibeComfy is a Python package for discovering, converting, validating, and running ComfyUI workflows from Python scratchpads and JSON workflow inputs. The primary package lives in `vibecomfy/`, tests live in `tests/`, documentation lives in `docs/`, and ready workflow examples live in `ready_templates/`.

## Working Rules

- Work from the repository root: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.
- Treat the worktree as shared. Do not revert, overwrite, or clean up edits you did not make.
- Keep changes scoped to the requested task. Avoid unrelated refactors, generated-output churn, and broad formatting changes.
- Prefer explicit, local registries and small modules over implicit discovery unless a task specifically asks for discovery.
- Do not change runtime behavior, templates, workflow corpus files, or generated snapshots unless the task explicitly covers those areas.
- If a change needs coordination with another interface or parallel task, document the integration note instead of guessing across ownership boundaries.

## Common Commands

- Run the full test suite with `pytest`.
- Run focused tests with `pytest tests/test_cli.py` or the relevant test file.
- Exercise the CLI locally with `python -m vibecomfy.cli ...`.
- Sync indexes only when a task or test requires it: `python -m vibecomfy.cli sources sync`.

## CLI Guidance

- The console entrypoint is `vibecomfy = "vibecomfy.cli:main"`.
- Top-level command registration belongs in `vibecomfy/commands/__init__.py`.
- Individual command modules should expose `register(subparsers)` and keep command execution in private `_cmd_*` helpers.
- Keep command registration explicit. Do not add plugin discovery or dynamic filesystem scanning unless the task asks for it.

## Testing Expectations

- Add or update focused tests when changing command routing, parser behavior, workflow conversion, validation, search, or runtime-facing code.
- Prefer subprocess CLI smoke tests only when behavior depends on process-level invocation or current working directory.
- Keep tests deterministic and avoid requiring ComfyUI, RunPod, network access, or local model files unless the test is explicitly marked or scoped for that environment.
