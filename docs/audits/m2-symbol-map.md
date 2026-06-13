# M2 Symbol Map

This artifact records the current-tree helper migrations for M2. It is based on
the live inventory from batch 1 and the post-migration grep from batch 6.

## Canonical Homes

| Helper family | Canonical home | Notes |
| --- | --- | --- |
| API-link checks | `vibecomfy._graph_utils.is_api_link(...)` | Default preserves legacy numeric source-id acceptance. Tool conversion and compile-equivalence call sites use the strict string-node-id mode required by the approved plan. |
| Node-id sorting | `vibecomfy._graph_utils.node_id_sort_key(...)` | Call sites pass `allow_compound=True` or `False` explicitly. |
| UI-only class set | `vibecomfy._graph_utils.UI_ONLY_CLASS_TYPES` | Exact set remains `{"Note", "MarkdownNote"}`. |
| Git stdout / HEAD lookup | `vibecomfy._git_utils.git_stdout(...)`, `vibecomfy._git_utils.git_head(...)` | `runner=None` resolves `subprocess.run` inside the function. Migrated call sites pass explicit runners where patchability matters. |

## Migrated Live Symbols

### API-Link Helpers

| Old symbol @ old location | New home / call mode |
| --- | --- |
| `_is_link` @ `vibecomfy/analysis/graph.py` | Legacy runtime-graph mode: list links, digit-shaped source IDs after coercion, slot type unchanged. |
| `_is_link` @ `vibecomfy/ingest/normalize.py` | Legacy ingest mode: list links, digit-shaped source IDs after coercion, slot type unchanged. |
| `_is_api_link` @ `vibecomfy/schema/validate.py` | `is_api_link(value, allow_tuple=True, require_string_node_id=True, require_numeric_node_id=False, require_int_slot=True)` |
| `_is_link` @ `tools/format_as_python.py` | `is_api_link(value, allow_tuple=False, require_string_node_id=True, require_numeric_node_id=True, allow_compound_node_id=True, require_int_slot=True)` |
| `_is_link` @ `vibecomfy/porting/parity.py` | `is_api_link(value, allow_tuple=False, require_string_node_id=True, require_numeric_node_id=True, allow_compound_node_id=True, require_int_slot=True)` |
| `_is_link` @ `tests/test_ready_templates.py` | Legacy parity-test mode: list links, digit-shaped source IDs after coercion, slot type unchanged. |

### Node-Id Sort Helpers

| Old symbol @ old location | New home / call mode |
| --- | --- |
| `_id_sort_key` @ `tools/format_as_python.py` | `node_id_sort_key(node_id, allow_compound=True)` |
| `_node_sort_key` @ `vibecomfy/model_assets.py` | `node_id_sort_key(node_id, allow_compound=False)` |

### UI-Only Constants

| Old symbol @ old location | New home |
| --- | --- |
| `UI_ONLY_CLASS_TYPES` @ `tools/format_as_python.py` | `UI_ONLY_CLASS_TYPES` imported from `vibecomfy._graph_utils` |
| `UI_ONLY` @ `vibecomfy/porting/parity.py` | `UI_ONLY_CLASS_TYPES` imported from `vibecomfy._graph_utils` |

### Git Helpers

| Old symbol @ old location | New home / call mode |
| --- | --- |
| `_git_head` @ `vibecomfy/commands/doctor.py` | `git_head(pack_dir, runner=subprocess.run)` |
| `_git_head` @ `vibecomfy/commands/nodes.py` | `git_head(pack_dir, runner=subprocess.run)` |
| `_git_head` @ `vibecomfy/node_packs_install.py` | `git_head(pack_dir, runner=runner)` |

## Intentional Link-Mode Differences

The migration keeps previous behavior explicit instead of relying on the
canonical helper defaults:

- Runtime graph analysis, ingest normalization, and ready-template parity keep
  numeric source-id acceptance, including values like `[1, 0]`, and do not
  require integer slots.
- Schema validation remains stricter about source-id type and slot type:
  list/tuple links are accepted only when the source id is a string and the slot
  is an integer. It intentionally does not require numeric source ids, matching
  the previous schema helper.
- Tool conversion and compile-equivalence checks keep strict string-source,
  list-only, integer-slot behavior: they reject numeric source objects like
  `[1, 0]` while accepting numeric string and compound ids such as `"1"` and
  `"76:67"`. The current-tree call sites are `tools/format_as_python.py` and
  `vibecomfy/porting/parity.py`, and both pass `require_string_node_id=True`.

## Reviewed But Not Centralized

These sort expressions were reviewed during M2 and intentionally left outside
the duplicate-helper migration because they are not the same helper family or
need separate call-site review:

- `tools/format_as_python.py` variable-name ordering (`sorted_ids`) still uses
  an inline compound-aware expression for emitter naming heuristics.
- `vibecomfy/workflow.py` output ordering still uses an inline digit-first key.
- `vibecomfy/ingest/normalize.py` output ordering still uses an inline
  digit-first key.
- Other generic `sorted(...)` calls in CLI, analysis, metadata, registry, and
  tests are ordinary deterministic ordering and were not in scope.

## Absent Older-Tree Targets

The older M2 brief referenced helper families and files that are not present in
this checkout. They were not recreated as unused utilities:

| Older-tree target | Current status |
| --- | --- |
| `_literal_value` in older `source_map.py`, `porting/readability_inventory.py`, `registry/static_contract.py`, and `analysis/fields.py` references | No live definitions found under `vibecomfy`, `tests`, `tools`, or `scripts`. |
| `_call_name` / `_ast_call_name` in older `registry/static_contract.py` and `porting/ready.py` references | No live definitions found under `vibecomfy`, `tests`, `tools`, or `scripts`. |
| `OPAQUE_COMPONENT_CLASS_RE` in older `porting/workbench.py` and `porting/strict_ready.py` references | No live definitions found under `vibecomfy`, `tests`, `tools`, or `scripts`. |
| `_sort_key` in older `porting/widget_aliases.py` and `porting/workbench.py` references | No live definitions found under `vibecomfy`, `tests`, `tools`, or `scripts`; live sort migration was limited to `_id_sort_key` and `_node_sort_key`. |
| `vibecomfy/porting/*` and `vibecomfy/schema/call_validation.py` | Absent in this checkout; not edit targets. |
| Older `vibecomfy/testing/*` helper references | No targeted helper definitions found in the current `vibecomfy/testing/` or `tests/test_testing_api.py` files. |

## Verification Greps

- `rg -n "def _is_link|def _is_api_link|def _id_sort_key|def _node_sort_key|def _git_head" vibecomfy tests tools scripts` returned no matches after migration.
- `rg -n "def _literal_value|def _call_name|def _ast_call_name|OPAQUE_COMPONENT_CLASS_RE|vibecomfy/porting|schema/call_validation|porting/" vibecomfy tests tools scripts` returned no matches in this checkout.

## Diff Hygiene Recheck

The T10 rework expanded the final hygiene check to include the parity fixture
directory that the first pass omitted. The failed review was correct that the
old command only checked `tests/parity` through tracked diff output and did not
classify untracked `tests/parity/fixtures/*_typed.py` files.

The full dirty-worktree split is recorded in `docs/audits/m2-diff-hygiene.md`.
That artifact distinguishes chain setup, completed M1 baseline work, and the M2
helper migration so M2 is not judged as if it started from a pristine per-plan
worktree.

The final hygiene gate now uses both commands below as a pair:

- Untracked generated/unrelated scope:
  `git ls-files --others --exclude-standard ready_templates tests/snapshots tests/fixtures tests/parity/fixtures ready_templates/sources docs scripts tests/test_testing_api.py vibecomfy/testing | sort`
- Tracked generated/unrelated scope:
  `git diff --name-only -- ready_templates tests/snapshots tests/fixtures tests/parity ready_templates/sources docs scripts tests/test_testing_api.py vibecomfy/testing`

Current untracked paths under that expanded scope are classified as unrelated to
the M2 helper migration, not generated by the shared utility refactor:

| Path | Classification |
| --- | --- |
| `docs/megaplan_chains/` | Pre-existing chain planning artifacts; referenced as implementation context only and not edited by the M2 helper migration. |
| `scripts/__init__.py` | Local import-shim file for the repo's `scripts` namespace; unrelated to the helper consolidation. |
| `tests/parity/fixtures/*_typed.py` | Typed parity fixtures from the P1 typed-handle parity work; they are not emitted by the M2 helper migration and are outside the migrated helper families. |
| `tests/test_testing_api.py` | Testing API coverage from the testing surface work; unrelated to graph/git helper consolidation. |
| `vibecomfy/testing/` | Testing support package from the testing surface work; current files contain no targeted helper definitions. |

The tracked diff under the expanded generated-output scope is exactly:

- `tests/parity/test_p1_typed_handle_parity.py`

That tracked parity test belongs to the separate P1 typed-handle parity work.
There are still no tracked changes under the generated output directories that
would indicate M2 churned ready templates, snapshots, validation fixtures,
parity fixture files, or workflow corpus files:

- `ready_templates/`
- `tests/snapshots/`
- `tests/fixtures/`
- `tests/parity/fixtures/`
- `ready_templates/sources/`

The temporary reproduction script used during rework confirmed the old
untracked scope missed `tests/parity/fixtures/*_typed.py`, while the expanded
scope reports them for classification. The script was deleted after the check.
