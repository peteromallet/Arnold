# Tests Layer Audit 03: Agentic Tests

Audit tests that exercise the `agentic/` harness or agent-facing workflows.

Questions:
- Which files belong in `tests/agentic*`, `tests/intent*`, or related dirs?
- Are any agentic evidence artifacts checked in or duplicated under `tests/`?
- Are helper modules colocated with tests where they should be in `tests/support/`?
- What path contracts prevent moving these files?

Prefer documentation/index recommendations over behavior changes.
