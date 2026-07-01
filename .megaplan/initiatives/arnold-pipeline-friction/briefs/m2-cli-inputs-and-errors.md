# M2: Harden CLI input parsing and failure reporting

## Outcome
`arnold run` validates and coerces inputs against the external input contract defined in M1.5, and every pipeline failure surfaces the stage name, exception type, message, and traceback path without requiring `--verbose`.

## Scope

IN:
- Replace the comma-splitting `_parse_inputs` in `arnold/pipelines/megaplan/_pipeline/run_cli.py` with a repeatable `--input KEY=VALUE` flag; keep `--inputs` as a deprecated alias.
- Stop blindly casting all input values to `Path`; keep values as strings until the M1.5 external-input contract declares the expected type.
- Implement the M1.5 external input declaration convention on `PortRef`/`Stage`/`Step` (e.g. `external=True`, `optional=True`, CLI name mapping) if it does not already exist.
- Add a validation gate after argument parsing that walks `pipeline.stages` and their external `consumes` declarations to check for missing required inputs and type mismatches **before** execution.
- Expand `_record_error` in both `arnold/pipelines/megaplan/_pipeline/executor.py` and the duplicate in `hooks.py` to persist `error_type`, `message`, `traceback`, `inputs`, `state_keys`, and `run_id`.
- Update the `arnold run` exception handler to read the structured `error.json` artifact and print stage name, exception type, message, and artifact path to stderr.
- Add regression tests.

OUT:
- Do not change `build_pipeline()` return type.
- Do not add a full structured-logging/TUI rewrite.

## Locked decisions
- Input validation derives from the M1.5 external input contract.
- Values default to `str`; path conversion happens only when the contract declares a path/file type.
- Error artifacts are the source of truth for CLI failure rendering.

## Open questions
- Does the external-input contract use `ReadRef`/`BindingRef` semantics or extend `PortRef`?
- Is there an existing type-casting helper for port values?

## Constraints
- Existing single-key `--inputs query=hello` invocations continue to work.
- Natural-language queries containing commas must work via `--input query="..."`.
- No behavioral change for successful runs.

## Done criteria
- `arnold run my-pipeline --input query="Hello, what can you do?"` succeeds with the comma intact.
- Running without a required external input fails before any stage executes with a message naming the missing input.
- A deliberate stage failure prints `Pipeline 'X' failed at stage 'Y': ValueError: ...` and the path to `error.json`.
- `error.json` contains a full traceback.

## Touchpoints
- `arnold/pipelines/megaplan/_pipeline/run_cli.py`
- `arnold/pipelines/megaplan/_pipeline/executor.py`
- `arnold/pipelines/megaplan/_pipeline/hooks.py`
- `arnold/pipeline/types.py` (PortRef / consumes / external input declaration)
- Regression tests

## Anti-scope
- Do not add `--inputs-file` JSON batch mode in this sprint (fast follow).
- Do not add a `STAGE_FAILED` event kind to the observability event system.
