# Dead Module Audit 03: `vibecomfy/router.py`

## Finding: ✅ VERIFIED SHADOWED — SAFE TO DELETE

`vibecomfy/router.py` is shadowed by the `vibecomfy/router/` package.
All Python import resolution prefers the package (`router/__init__.py`)
over the top-level module file.

## Evidence

### 1. Import Resolution

| Import | Resolves To | Proof |
|---|---|---|
| `from vibecomfy.router import pick` (ops/image.py, ops/video.py) | `vibecomfy/router/__init__.py` (package) | Python prefers directories w/ `__init__.py` |
| `from vibecomfy import router` (tests/test_router.py, CLAUDE.md, docs/authoring.md) | `vibecomfy/router/` (package) | Same rule |
| `from . import ... router` (vibecomfy/__init__.py) | `vibecomfy/router/` (package) | — |
| `import vibecomfy.router` (direct module) | 0 occurrences | — |

### 2. Content Duplicated

`vibecomfy/router.py` (51 LOC) is functionally identical to
`vibecomfy/router/_core.py` (51 LOC). The sole difference:
- Dead file: `from vibecomfy.router_rules import rules`
- Live file: `from ._rules import rules`

### 3. Zero External Dependents

- No code imports `vibecomfy/router.py` as a file path.
- No tests import it directly.
- No CI configs, shell scripts, `.importlinter`, or `pyproject.toml`
  reference the file path.
- All doc references to `router.pick` / `from vibecomfy import router`
  work identically after deletion (they resolve to the package).

### 4. Sister Issue (Out of Scope)

`vibecomfy/router_rules.py` and `vibecomfy/router/_rules.py` are 100%
identical duplicates. See audit 07-blocks-patches-ops-router.txt for
resolution options. This does not block deleting `router.py`.

## Action

- [x] **DELETE `vibecomfy/router.py`** — shadowed, duplicated, zero dependents.
- [x] **Docs/repairs needed: None** — all references are to the package API.
