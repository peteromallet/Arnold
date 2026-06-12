# Package Layer Audit 01: Public API And Root Modules

Audit `vibecomfy/__init__.py` and root-level modules in `vibecomfy/`.

Questions:
- Which modules are public API, CLI-facing, or documented import paths?
- Which root modules are private helpers, legacy compatibility, or misplaced?
- Are there generated/cache files under the package that should be documented or ignored?
- What must not move because tests/docs/users import it?

Return safe first actions only.
