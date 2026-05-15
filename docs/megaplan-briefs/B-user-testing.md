# Brief B — User testing affordances

`all-claude / standard`

## Why this sprint exists

VibeComfy is a library people build *on top of*. They write recipes (`recipes/*.py`), scratchpads (`out/scratchpads/*.py`), custom ready_templates (`ready_templates/<kind>/*.py`), and composite graphs that splice multiple templates plus patches plus blocks. Today **there is no testing story for any of that**. A user writing a recipe can:

- Call `wf.compile("api")` and inspect the dict manually
- Call `wf.validate()` and read the `ValidationReport`
- Run the recipe end-to-end on RunPod (slow, expensive, network-dependent)

There's no equivalent to `pytest` for a VibeWorkflow. No fixture helpers, no graph assertions, no dry-run runtime that records compile output, no snapshot integration. As VibeComfy's user base grows, this gap will dominate friction — every user reinvents the same ad-hoc "did my recipe build the right graph?" loop.

This sprint designs and ships a first-class testing surface for VibeComfy users. The internal test suite (Brief A) is the *floor*; this sprint raises the *ceiling*.

## What success looks like

Three deliverables, each independently usable:

### 1. `vibecomfy.testing` module — graph assertions and dry-run runtime

A new top-level subpackage exposing:

- **Assertions** on a `VibeWorkflow` or a compiled API dict. Concrete shapes to plan:
  - `assert_node_present(wf, class_type, *, count=None)` — at least one (or exactly `count`) node of that class type exists
  - `assert_edge(wf, from_node_id, to_node_id, *, to_input=None)` — given edge exists; optionally pinned to an input name
  - `assert_input_value(wf, node_id, input_name, expected)` — widget or input value matches
  - `assert_output_kind(wf, expected_kind)` — `wf.outputs` contains a `SaveImage`/`SaveVideo`/`SaveAudioMP3`/etc. of the right shape
  - `assert_input_bound(wf, input_name, *, node_id=None, field=None, default=...)` — registered input metadata matches
  - `assert_compiles_cleanly(wf, *, schema_provider=None)` — `wf.compile("api")` succeeds and the resulting dict passes validate
  - `assert_no_dangling_handles(wf)` — every handle is wired into an edge
  - Each assertion produces a readable failure message naming the workflow id, the node id, and the offending field
- **Pytest fixtures**: `vibecomfy_workflow_factory`, `vibecomfy_handle_factory`, `dry_runtime` — small builders so users don't have to construct `VibeNode` / `VibeEdge` / `Handle` by hand to test custom blocks
- **Dry-run runtime**: `vibecomfy.testing.dry_run(wf) -> DryRunResult` that returns the compiled API dict + a list of `would_invoke` records (one per node) without actually calling ComfyUI. Useful for asserting wiring on workflows that depend on models/checkpoints not present locally.

The module ships with a doctest-tested example for each assertion and a 30-line "your first VibeWorkflow test" walkthrough in `docs/testing-user-code.md`.

### 2. Snapshot integration — `vibecomfy test snapshot`

Generated workflows (compile output) are deterministic given the same inputs. Users should be able to freeze the compile output of a recipe and have CI catch regressions:

- `vibecomfy test snapshot <recipe.py>` — runs the recipe's `build()` function, computes `wf.compile("api")`, writes a snapshot file next to the recipe (`<recipe>.snapshot.json`)
- `vibecomfy test diff <recipe.py>` — re-runs the recipe and shows a structured diff against the snapshot
- `vibecomfy test verify <path-or-glob>` — checks all snapshots in a directory; exits non-zero on drift
- Snapshot format: stable JSON with sorted keys, normalized edge order, normalized node IDs (drop volatile internal IDs); design must keep diffs *human-readable*, not just machine-comparable
- Recipes can opt out of snapshot fields they know are non-deterministic (`# vibecomfy-snapshot: ignore-field cfg`); the runner respects those directives
- The 64 in-repo `ready_templates/**/*.py` files MUST work as snapshot subjects (they're the canonical "recipe" examples); a CI-style smoke that runs `vibecomfy test verify ready_templates/` is part of the deliverable

### 3. `pytest-vibecomfy` plugin

A small pytest plugin (lives in `vibecomfy/testing/_pytest_plugin.py`, registered via entry point) that:

- Discovers files matching `test_workflow_*.py` (or files containing a `@vibecomfy.testing.workflow` marker)
- Auto-collects functions that return a `VibeWorkflow`, runs them through dry-run, and asserts they compile cleanly
- Provides a `--vibecomfy-snapshot-update` flag analogous to `pytest --snapshot-update` (mirror existing conventions where possible, e.g. `syrupy`)

## How users will use this

```python
# user's recipes/my_recipe_test.py
import pytest
from vibecomfy.testing import (
    assert_node_present, assert_edge, assert_input_value, assert_compiles_cleanly,
    dry_run,
)
from recipes.my_dual_pass import build  # user's recipe

def test_my_recipe_compiles():
    wf = build()
    assert_compiles_cleanly(wf)
    assert_node_present(wf, "VAELoader", count=1)
    assert_node_present(wf, "SaveImage", count=2)  # dual-pass
    assert_input_value(wf, "12", "filename_prefix", "my_run/upscaled")

def test_dry_run_records_nodes():
    wf = build()
    result = dry_run(wf)
    assert "VAELoader" in {r.class_type for r in result.would_invoke}
```

```bash
# user CI
vibecomfy test snapshot recipes/my_dual_pass.py    # one-time
vibecomfy test verify recipes/                     # in every CI run
pytest tests/recipes/                              # via plugin
```

## What's already in the repo to build on

- `vibecomfy/workflow.py::VibeWorkflow` — IR with `nodes`, `edges`, `inputs`, `outputs`, `metadata`, `compile("api")`, `validate()`
- `vibecomfy/handles.py::Handle` — typed output references
- `vibecomfy/schema/provider.py::SchemaProvider` — pluggable schema source (the dry-run runtime can use this)
- `vibecomfy/runtime/session.py::VibeSession` Protocol — the runtime contract dry-run mocks
- `vibecomfy/lens/*`, `vibecomfy/analysis/*` — graph-traversal helpers, useful for some assertions
- 64 `ready_templates/**/*.py` files — these are the canonical "recipe" examples and serve as snapshot subjects
- `tests/test_ready_template_helpers.py`, `tests/test_workflow_core.py` — existing patterns for asserting workflow shape

## Design questions the planner must resolve

The brief is intentionally not closing these:

1. **Where does `dry_run` execute its schema lookups?** Real `SchemaProvider` makes HTTP calls in some paths. The dry-run runtime must either accept a `schema_provider=` kwarg (default `LocalSchemaProvider` from cached snapshots) or expose a stub-schema-provider helper.
2. **How are non-deterministic fields handled in snapshots?** Seed values, filename prefixes with timestamps, etc. Decide between explicit per-field opt-out (directive comment) vs. a programmatic normalization API (`@vibecomfy.testing.normalize`).
3. **CLI placement.** `vibecomfy test` adds a new top-level command. Does it live as `CommandSpec("test", ...)` in `vibecomfy/commands/`, or as a separate `vibecomfy-test` script? Prefer integration with the existing CLI for discoverability.
4. **Pytest plugin packaging.** Ship the plugin inside the `vibecomfy` wheel (entry point `pytest11`) or as a separate `pytest-vibecomfy` distribution? Single wheel is simpler; separate package signals "optional" more clearly.
5. **Snapshot file location.** Next to the recipe (`recipes/my_recipe.snapshot.json`) or in a sibling tree (`recipes/.snapshots/my_recipe.json`)? The former is more discoverable; the latter is easier to .gitignore selectively.
6. **Stability across `_node` refactors.** The compile output should not churn when internal `vibecomfy.registry.ready_template._node` is renamed. Verify by deliberately renaming a private helper after snapshots are taken.

The plan-phase output should resolve all six explicitly.

## Files most likely involved

```
vibecomfy/testing/__init__.py          # NEW — public API surface
vibecomfy/testing/assertions.py        # NEW
vibecomfy/testing/dry_run.py           # NEW
vibecomfy/testing/snapshot.py          # NEW
vibecomfy/testing/_pytest_plugin.py    # NEW — entry point
vibecomfy/commands/test.py             # NEW — vibecomfy test CLI
vibecomfy/commands/__init__.py         # registration
pyproject.toml                          # entry point declaration
tests/test_testing_assertions.py       # NEW — tests for the test framework
tests/test_testing_snapshot.py         # NEW
tests/test_testing_dry_run.py          # NEW
tests/test_testing_pytest_plugin.py    # NEW
docs/testing-user-code.md              # NEW — user-facing walkthrough
docs/testing-user-code-examples/       # NEW — three worked examples
recipes/example_tested_recipe.py       # NEW — canonical example
```

## Constraints and non-goals

- **Build on top of, don't break, the IR.** No changes to `VibeWorkflow`/`VibeNode`/`VibeEdge`/`Handle` shapes unless absolutely needed.
- **Public surface stays small.** Each module exports a tight `__all__`. Internal helpers stay private.
- **Don't ship anything that requires ComfyUI installed.** Dry-run runtime must work in a clean Python env with only `vibecomfy` and its declared deps.
- **Don't extend the internal CI workflow with user-snapshot enforcement.** Brief A handles CI; this sprint integrates with whatever CI Brief A ships but doesn't co-modify it.
- **Vendor preference is `all-claude`.** Single-vendor Claude end-to-end at default effort.

## Definition of done

```bash
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy
uv run vibecomfy test snapshot ready_templates/image/z_image.py    # writes snapshot
uv run vibecomfy test verify ready_templates/                      # exits 0
uv run python -m pytest tests/test_testing_*.py -q                 # all pass
uv run python -c "from vibecomfy.testing import assert_node_present, assert_edge, assert_input_value, assert_compiles_cleanly, dry_run; print('ok')"
```

Plus: a `docs/testing-user-code.md` page that a new VibeComfy user can read end-to-end in 10 minutes and be testing their first recipe.
