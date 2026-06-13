# M1 Duplication Inventory

Date: 2026-05-24

Scope: repo-wide helper duplication search across `vibecomfy/`, `tests/`, `tools/`, and root `scripts/`.

## Reproducible Search

```bash
rg -n "_literal_value|_call_name|_is_link|_sort_key|_node_sort_key|_git_head|UI_ONLY_CLASS_TYPES|OPAQUE_COMPONENT_CLASS_RE" \
  vibecomfy tests tools scripts \
  --glob '!out/**' \
  --glob '!**/__pycache__/**' \
  --glob '!*.pyc' \
  --glob '!**/.venv/**' \
  --glob '!**/vendor/**' \
  --glob '!**/node_modules/**'
```

Total current matches: 32.

## Inventory

### `_literal_value`

Count: 0.

Entries: none.

Divergence note: no current helper family exists under the required search roots.

### `_call_name`

Count: 0.

Entries: none.

Divergence note: no current helper family exists under the required search roots.

### `_is_link`

Count: 16 matches, including 5 local definitions.

Entries:

```text
tools/format_as_python.py:74:def _is_link(value: Any) -> bool:
tools/format_as_python.py:151:            if _is_link(value):
tools/format_as_python.py:265:        if _is_link(value):
tools/format_as_python.py:272:        if _is_link(value):
tools/format_as_python.py:417:            if _is_link(value):
vibecomfy/porting/parity.py:25:def _is_link(value: Any) -> bool:
vibecomfy/porting/parity.py:78:            if _is_link(value):
vibecomfy/porting/parity.py:94:            if not _is_link(value):
tests/test_ready_templates.py:195:            if _is_link(value):
tests/test_ready_templates.py:208:            if not _is_link(value):
tests/test_ready_templates.py:218:def _is_link(value: object) -> bool:
vibecomfy/ingest/normalize.py:93:            if _is_link(value):
vibecomfy/ingest/normalize.py:115:            if _is_link(value):
vibecomfy/ingest/normalize.py:122:def _is_link(value: Any) -> bool:
vibecomfy/analysis/graph.py:185:    return {key: deepcopy(value) for key, value in merged.items() if not _is_link(value)}
vibecomfy/analysis/graph.py:299:def _is_link(value: Any) -> bool:
```

Divergence note: `tools/format_as_python.py` and `vibecomfy/porting/parity.py` accept compound node IDs such as `"238:231"` and require integer slots; `vibecomfy/ingest/normalize.py`, `vibecomfy/analysis/graph.py`, and `tests/test_ready_templates.py` only accept digit-only node IDs and do not enforce integer slot type.

### `_sort_key` / `_node_sort_key`

Count: 5 matches, including 2 local definitions.

Entries:

```text
tools/format_as_python.py:127:def _id_sort_key(nid: str) -> tuple:
tools/format_as_python.py:162:            key=_id_sort_key,
tools/format_as_python.py:166:            out.extend(sorted(pending, key=_id_sort_key))
vibecomfy/model_assets.py:174:        key=lambda node: _node_sort_key(node.get("id")),
vibecomfy/model_assets.py:178:def _node_sort_key(node_id: Any) -> tuple[int, str]:
```

Divergence note: naming and domain differ (`_id_sort_key` for formatter node ordering, `_node_sort_key` for asset extraction ordering), but both implement numeric-first node ID ordering as local helpers.

### `_git_head`

Count: 9 matches, including 3 local definitions.

Entries:

```text
vibecomfy/node_packs_install.py:34:    sha = _git_head(install_dir, runner)
vibecomfy/node_packs_install.py:42:    sha = _git_head(install_dir, runner)
vibecomfy/node_packs_install.py:49:        if _git_head(install_dir, runner) == entry.git_commit_sha: return InstallResult(entry.name, "refreshed", entry.git_commit_sha, None)
vibecomfy/node_packs_install.py:60:    sha = _git_head(install_dir, runner)
vibecomfy/node_packs_install.py:71:def _git_head(pack_dir: Path, runner: Runner) -> str | None: return (_git(pack_dir, ["rev-parse", "HEAD"], runner) or "").strip() or None
vibecomfy/commands/doctor.py:159:        actual = _git_head(pack_dir)
vibecomfy/commands/doctor.py:190:def _git_head(pack_dir: Path) -> str | None:
vibecomfy/commands/nodes.py:154:            git_commit_sha = _git_head(pack_dir) or git_commit_sha
vibecomfy/commands/nodes.py:190:def _git_head(pack_dir: Path) -> str | None:
```

Divergence note: `node_packs_install.py` has a runner-injected helper for testable install operations, while `commands/doctor.py` and `commands/nodes.py` each shell out directly with nearly duplicated subprocess handling.

### `UI_ONLY_CLASS_TYPES`

Count: 2 matches, including 1 local definition.

Entries:

```text
tools/format_as_python.py:49:UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset(
tools/format_as_python.py:399:        if node.class_type not in UI_ONLY_CLASS_TYPES
```

Divergence note: this is currently a single tool-local constant, not a duplicated helper family in the required search roots.

### `OPAQUE_COMPONENT_CLASS_RE`

Count: 0.

Entries: none.

Divergence note: no current helper family exists under the required search roots.
