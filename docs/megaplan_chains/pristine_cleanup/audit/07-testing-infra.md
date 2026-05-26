# Testing Infrastructure Audit — LENS 7

**HIGH**

1. **Public-API fixture stubs never replaced with real imports.** `vibecomfy/testing/__init__.py:76-80` assigns `_not_yet_implemented` stubs for `vibecomfy_workflow_factory`, `vibecomfy_handle_factory`, `dry_runtime`, `make_workflow_factory`, `make_handle_factory` — all five raise `NotImplementedError` when accessed via `from vibecomfy.testing import ...`. Yet `__all__` (lines 50-54) advertises them, and real implementations live in `vibecomfy/testing/fixtures.py:43-52`. The `# T4` comment on line 49 says "Fixtures (filled in by T4)" but the re-export lines were never added. Tests survive only because they import directly from `vibecomfy.testing.fixtures`.

2. **`_is_link` duplicated 3× inside `vibecomfy/testing/`.** `dry_run.py:49`, `canonical.py:42`, and `snapshot.py:61` each define an identical `_is_link(value) -> bool` helper. Across the full package it appears **8 times** (`analysis/graph.py:299`, `ingest/normalize.py:170`, `porting/emitter.py:2516`, `porting/parity.py:46`, `schema/call_validation.py:163`). Meanwhile `_helpers.py:56` adds yet another variant called `is_api_link`. No shared utility.

**MEDIUM**

3. **`test_agentic_affordances.py` name is a lie.** The file tests CLI port commands (`_cmd_port_validate_call`, `_cmd_nodes_compatible_with`, `plan_eval_node`, etc.) and diagnostic error propagation. Nothing tests agentic behavior, affordances, or LLM-mediated workflows. The name implies a feature that doesn't exist in tests.

4. **`test_sisypy_integration.py:11` does a bare `import sisypy` at module level with no `pytest.importorskip`.** If the sibling `sisypy` package isn't installed, pytest can't even collect the module — hard `ImportError` crash. Contrast with `test_fixtures.py:12` which properly uses `pytest.importorskip("av")`.

5. **Private workflow helpers duplicated between test files.** `test_testing_assertions.py:18` (`_basic_wf`) and `test_testing_dry_run.py:11` (`_simple_wf`) both build a 2-node CheckpointLoaderSimple→SaveImage workflow manually with `VibeNode`/`VibeEdge`. Neither uses the shipped `make_workflow_factory` fixture pattern that `assertions.py` doctests themselves demonstrate (line 54).

6. **`_runtime_session_helpers.py:37,184` defines `@pytest.fixture` inside an underscore-prefixed module.** Pytest can't discover these fixtures; the split `test_runtime_session_*.py` files rely on importing the module by name so the fixture leaks into their namespace. Pytest supports this incidentally, but the pattern is fragile: rename the module and fixtures vanish silently.

**LOW**

7. **`snapshot_registry.py` maps 9 stems but parity fixtures cover only 3.** `STEM_TO_READY_ID` declares 9 ready-template→stem mappings (lines 18-28), implying snapshot coverage for all. But `tests/parity/fixtures/` contains only 3 typed-handle parity fixtures (`z_image_typed.py`, `flux2_klein_4b_t2i_typed.py`, `ace_step_1_5_t2a_song_typed.py`). The registry promises coverage not backed by parity tests.

8. **`_pytest_plugin.py` loads 3 fixture names (lines 76-80) that shadow the broken `__init__.py` stubs.** The plugin re-exports `dry_runtime`, `vibecomfy_handle_factory`, `vibecomfy_workflow_factory` from `vibecomfy.testing.fixtures` — the only reason they work at all when accessed via the plugin. But `make_workflow_factory` and `make_handle_factory` are missing from the plugin re-exports, so they're only reachable via the direct `fixtures` import path.

---

**Worst thing:** #1 — the `__init__.py` stub shadowing. Five names in the public testing API surface (`__all__`) raise `NotImplementedError` at call time. Real implementations exist one module away but were never wired in. This is an outright broken public contract.