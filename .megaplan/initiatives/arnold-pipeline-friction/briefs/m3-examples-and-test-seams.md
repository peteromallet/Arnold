# M3: Validate examples and expose test seams

## Outcome
Example pipelines cannot rot in CI, and authors can run a token-free `arnold run --dry-run` that deterministically renders resolved prompts and writes useful artifacts without API calls.

## Scope

IN:
- Fix `arnold/pipelines/megaplan/pipelines/jokes/__init__.py` to import from the public `arnold.pipeline` surface (after M1 lands).
- Add `tests/pipelines/megaplan/test_examples_load.py` that iterates every directory under `arnold/pipelines/megaplan/pipelines/` with a `build_pipeline` callable, calls it, and runs the existing structural validator.
- Add `arnold run --dry-run`. If `arnold pipelines walk` is already a real command, prefer adding `--dry-run` there; otherwise put it on `arnold run`.
- Make the Megaplan no-worker path render resolved prompts and input interpolation deterministically (not a placeholder like `[AgentStep X] prompt: ref`).
- Ship `arnold/pipelines/testing.py` exporting `MockWorker` / `make_mock_worker` utilities.
- Add tests for the dry-run path and the mock worker.
- Wire the example-load test into CI.

OUT:
- Do not rewrite every example pipeline; only fix what the validator catches.
- Do not invent a new `PipelineBackend` protocol.

## Locked decisions
- The M1.5 dry-run artifact contract defines what `--dry-run` produces.
- Example validation is a pytest test, not a new CLI flag.
- Mock workers are plain callables keyed by step name / prompt.

## Open questions
- Which existing graph pipelines fail the validator today, and why?
- Does `arnold pipelines walk` exist?

## Constraints
- Example validation must be fast and require no API keys.
- The dry-run path must produce deterministic artifacts without network calls.

## Done criteria
- `pytest tests/pipelines/megaplan/test_examples_load.py` passes and catches any example that cannot build.
- `arnold run my-pipeline --input query=foo --dry-run` completes with no API calls and writes rendered prompts.
- A newly generated pipeline includes a mock-worker test scaffold.
- CI runs the example-load test on every PR.

## Touchpoints
- `arnold/pipelines/megaplan/pipelines/jokes/__init__.py`
- `arnold/pipelines/megaplan/_pipeline/run_cli.py` or `arnold/cli/*`
- `arnold/pipelines/megaplan/_pipeline/executor.py`
- `arnold/pipeline/steps/agent.py`
- `arnold/pipelines/megaplan/_pipeline/steps/agent.py` (Megaplan AgentStep no-worker path)
- New `arnold/pipelines/testing.py`
- New `tests/pipelines/megaplan/test_examples_load.py`
- `.github/workflows/tests.yml`

## Anti-scope
- Do not add AST import scanning; validator-based loading is enough.
- Do not require every example to have a README in this sprint.
