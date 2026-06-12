# Compatibility Layer Audit 07: Tests And Contracts

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: identify tests that encode compatibility-layer import contracts and how to update them.

Inspect:
- `tests/test_cli_debug.py`
- fixture tests
- diagnostics/schema tests
- CLI tests that exercise `python -m vibecomfy.fixtures`, `vibecomfy debug`, validate/doctor output.

Return under 500 words:
1. Tests likely affected by deleting/moving each candidate.
2. Which tests protect intentional public API versus accidental compatibility.
3. Minimal focused test command after cleanup.
