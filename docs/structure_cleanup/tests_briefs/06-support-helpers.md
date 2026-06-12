# Tests Layer Audit 06: Support Helpers

Audit helper modules in `tests/support/`, `tests/conftest.py`, local fixtures,
and reusable test utilities.

Questions:
- Which helpers are imported cross-directory and need stable paths?
- Are there duplicated helper functions that should be centralized?
- Are support modules mixed into feature test directories?
- What cleanup can be done safely without broad imports churn?

Return exact import references for any proposed move.
