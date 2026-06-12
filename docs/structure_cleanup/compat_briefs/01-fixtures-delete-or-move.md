# Compatibility Layer Audit 01: Fixtures Delete Or Move

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: decide what to do with `vibecomfy/fixtures.py` and `vibecomfy/testing/_fixtures.py`.

Context:
- User preference: delete shims except extreme public-contract cases.
- `vibecomfy/fixtures.py` and `vibecomfy/testing/_fixtures.py` appear byte-identical or near-identical.
- `python -m vibecomfy.fixtures` is referenced by scripts/docs.

Inspect:
- `vibecomfy/fixtures.py`
- `vibecomfy/testing/_fixtures.py`
- `vibecomfy/testing/__init__.py`
- imports/references in `tests/`, `scripts/`, `docs/`, `README.md`, `AGENTS.md`, `CLAUDE.md`

Return under 500 words:
1. Which file should own the implementation?
2. Whether `vibecomfy/fixtures.py` is a hard public CLI/API contract.
3. Whether deletion is safe now; if not, what cleanup still improves structure.
4. Exact tests/commands to verify.
