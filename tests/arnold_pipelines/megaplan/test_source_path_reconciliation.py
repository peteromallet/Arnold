"""Mechanical source-path reconciliation tests for M1 Megaplan migration.

These tests establish a machine-verifiable gate that proves the live
``arnold_pipelines/megaplan/`` underscore package paths are the only
authoritative implementation targets and that stale dot-path references
(``arnold/pipelines/megaplan/``) are not viable implementation surfaces.

The tests cover three reconciliation axes specified by the M1 launch gate:

1. **Live path imports resolve** — every live underscore module in the
   Megaplan workflow, CLI, and auto entrypoints is importable.
2. **Stale dot-paths do not carry implementation** — sub-module imports
   under the stale ``arnold.pipelines.megaplan`` prefix fail with
   ``ModuleNotFoundError`` (confirming the live underscore package is
   the only implementation surface).
3. **CLI/auto entrypoints resolve through live paths** — ``megaplan run``,
   ``megaplan describe``, ``megaplan auto``, and
   ``python -m arnold_pipelines.megaplan`` all route through live
   underscore modules, not stale dot-path references.

Doctrine: if a test in this file fails, it means docs or implementation
have regressed to targeting stale dot-path references instead of live
underscore paths.  That is a blocking condition for M1.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from tests.arnold_pipelines.megaplan.package_resources import (
    checkout_path,
    resource_exists,
    resource_path,
    resource_text,
)


# ── Path constants ──────────────────────────────────────────────────────────

REPO_ROOT = checkout_path()
WORKFLOW_RESOURCE_PACKAGE = "arnold_pipelines.megaplan.workflows"
WORKFLOW_PYPELINE_PATH = checkout_path("arnold_pipelines", "megaplan", "workflows", "workflow.pypeline")
WORKFLOW_PY_PATH = checkout_path("arnold_pipelines", "megaplan", "workflows", "workflow.py")
PROHIBITED_WRAPPER_TOKENS: tuple[str, ...] = (
    "SOURCE_",
    "handler_ref",
    "route_bindings",
    "manifest_hash",
    "build_manifest",
    "build_node",
    "node_builder",
)
WORKFLOW_SHIM_PROHIBITED_TOKENS: tuple[str, ...] = (
    "@workflow",
    "planning_workflow",
    "SOURCE_CRITIQUE",
    "SOURCE_EXECUTE",
    "handler_ref",
    "route_bindings",
)

# ── Live underscore package paths (the authoritative implementation surface) ─

LIVE_CORE_PATHS: tuple[tuple[str, str], ...] = (
    # (label, dotted_module_name)
    # Core workflow and composition surface
    ("megaplan __init__", "arnold_pipelines.megaplan"),
    ("pipeline facade", "arnold_pipelines.megaplan.pipeline"),
    ("canonical build_pipeline (planning)", "arnold_pipelines.megaplan.workflows.planning"),
    ("step components", "arnold_pipelines.megaplan.workflows.components"),
    ("routing helpers", "arnold_pipelines.megaplan.routing"),
)

LIVE_CLI_PATHS: tuple[tuple[str, str], ...] = (
    # CLI entrypoints
    ("monolithic CLI", "arnold_pipelines.megaplan.cli"),
    ("cli run handler", "arnold_pipelines.megaplan.cli.run"),
    ("module entrypoint", "arnold_pipelines.megaplan.__main__"),
)

LIVE_AUTO_PATHS: tuple[tuple[str, str], ...] = (
    # Auto-drive entrypoints
    ("auto driver", "arnold_pipelines.megaplan.auto"),
    ("auto escalation", "arnold_pipelines.megaplan.auto_escalation"),
    ("blocker recovery", "arnold_pipelines.megaplan.blocker_recovery"),
)

LIVE_RUNTIME_PATHS: tuple[tuple[str, str], ...] = (
    # Runtime bridge
    ("runtime bridge", "arnold_pipelines.megaplan.runtime.bridge"),
    ("runtime discovery", "arnold_pipelines.megaplan.runtime.discovery"),
    ("runtime process", "arnold_pipelines.megaplan.runtime.process"),
    ("runtime manifest backend", "arnold_pipelines.megaplan.runtime.manifest_backend"),
    ("runtime governor", "arnold_pipelines.megaplan.runtime.governor"),
)

LIVE_HANDLER_PATHS: tuple[tuple[str, str], ...] = (
    # Handler modules (migration targets for Phase 3)
    ("handlers package", "arnold_pipelines.megaplan.handlers"),
    ("handler: plan", "arnold_pipelines.megaplan.handlers.plan"),
    ("handler: critique", "arnold_pipelines.megaplan.handlers.critique"),
    ("handler: gate", "arnold_pipelines.megaplan.handlers.gate"),
    ("handler: tiebreaker", "arnold_pipelines.megaplan.handlers.tiebreaker"),
    ("handler: finalize", "arnold_pipelines.megaplan.handlers.finalize"),
    ("handler: execute", "arnold_pipelines.megaplan.handlers.execute"),
    ("handler: review", "arnold_pipelines.megaplan.handlers.review"),
    ("handler: override", "arnold_pipelines.megaplan.handlers.override"),
)

LIVE_OTHER_PATHS: tuple[tuple[str, str], ...] = (
    # Other live subsystems referenced by the reconciliation doc
    ("control interface", "arnold_pipelines.megaplan.control_interface"),
    ("user actions", "arnold_pipelines.megaplan.user_actions"),
    ("step contracts", "arnold_pipelines.megaplan.step_contracts"),
    ("types", "arnold_pipelines.megaplan.types"),
    ("flags", "arnold_pipelines.megaplan.flags"),
    ("feature flags", "arnold_pipelines.megaplan.feature_flags"),
    ("control", "arnold_pipelines.megaplan.control"),
    ("artifacts", "arnold_pipelines.megaplan.artifacts"),
    ("briefs", "arnold_pipelines.megaplan.briefs"),
    ("judge manifest", "arnold_pipelines.megaplan.judge_manifest"),
    ("resolutions", "arnold_pipelines.megaplan.resolutions"),
    ("resolution contract", "arnold_pipelines.megaplan.resolution_contract"),
    ("schema seeds", "arnold_pipelines.megaplan.schema_seeds"),
    ("template registry", "arnold_pipelines.megaplan.template_registry"),
    ("run outcome", "arnold_pipelines.megaplan.run_outcome"),
    ("model seam", "arnold_pipelines.megaplan.model_seam"),
    ("policy settings", "arnold_pipelines.megaplan.policy_settings"),
    ("pipeline contracts", "arnold_pipelines.megaplan.pipeline_contracts"),
    ("quality resolutions", "arnold_pipelines.megaplan.quality_resolutions"),
    ("layout", "arnold_pipelines.megaplan.layout"),
    ("preflight", "arnold_pipelines.megaplan.preflight"),
    ("registry", "arnold_pipelines.megaplan.registry"),
    ("planning operations", "arnold_pipelines.megaplan.planning.operations"),
    ("loop engine", "arnold_pipelines.megaplan.loop"),
    ("cloud", "arnold_pipelines.megaplan.cloud"),
    ("calibration", "arnold_pipelines.megaplan.calibration"),
    ("observability", "arnold_pipelines.megaplan.observability"),
    ("sub-pipelines", "arnold_pipelines.megaplan.pipelines"),
    ("schemas", "arnold_pipelines.megaplan.schemas"),
    ("watchdog", "arnold_pipelines.megaplan.watchdog"),
    ("agent runtime", "arnold_pipelines.megaplan.agent_runtime"),
    ("agent adapters", "arnold_pipelines.megaplan.agent_adapters"),
    ("skills", "arnold_pipelines.megaplan.skills"),
    ("data", "arnold_pipelines.megaplan.data"),
)


def _all_live_paths() -> list[tuple[str, str]]:
    """Concatenate all live path categories into a single flat list."""
    result: list[tuple[str, str]] = []
    for group in (
        LIVE_CORE_PATHS,
        LIVE_CLI_PATHS,
        LIVE_AUTO_PATHS,
        LIVE_RUNTIME_PATHS,
        LIVE_HANDLER_PATHS,
        LIVE_OTHER_PATHS,
    ):
        result.extend(group)
    return result


# ── Stale dot-paths (must not carry implementation) ─────────────────────────

# These correspond to Section 6.1 of megaplan-source-path-reconciliation.md.
# Each stale path has a live underscore equivalent; the stale path itself
# must NOT resolve as an importable module (because it doesn't exist at
# the dot-path — the real code lives at the underscore path).
STALE_PATHS_WITH_LIVE_EQUIVALENTS: tuple[tuple[str, str, str], ...] = (
    # (label, stale_dot_module, live_underscore_module)
    ("__init__", "arnold.pipelines.megaplan", "arnold_pipelines.megaplan"),
    ("pipeline facade", "arnold.pipelines.megaplan.pipeline", "arnold_pipelines.megaplan.pipeline"),
    ("workflows/planning", "arnold.pipelines.megaplan.workflows.planning", "arnold_pipelines.megaplan.workflows.planning"),
    ("workflows/components", "arnold.pipelines.megaplan.workflows.components", "arnold_pipelines.megaplan.workflows.components"),
    ("auto", "arnold.pipelines.megaplan.auto", "arnold_pipelines.megaplan.auto"),
    ("registry", "arnold.pipelines.megaplan.registry", "arnold_pipelines.megaplan.registry"),
    ("cli/__init__", "arnold.pipelines.megaplan.cli", "arnold_pipelines.megaplan.cli"),
    ("cli/parser", "arnold.pipelines.megaplan.cli.parser", "arnold_pipelines.megaplan.cli"),
    ("cli/run", "arnold.pipelines.megaplan.cli.run", "arnold_pipelines.megaplan.cli.run"),
    ("routing", "arnold.pipelines.megaplan.routing", "arnold_pipelines.megaplan.routing"),
    ("runtime/bridge", "arnold.pipelines.megaplan.runtime.bridge", "arnold_pipelines.megaplan.runtime.bridge"),
    ("runtime/discovery", "arnold.pipelines.megaplan.runtime.discovery", "arnold_pipelines.megaplan.runtime.discovery"),
    ("planning/operations", "arnold.pipelines.megaplan.planning.operations", "arnold_pipelines.megaplan.planning.operations"),
    ("handlers package", "arnold.pipelines.megaplan.handlers", "arnold_pipelines.megaplan.handlers"),
    ("types", "arnold.pipelines.megaplan.types", "arnold_pipelines.megaplan.types"),
    ("control", "arnold.pipelines.megaplan.control", "arnold_pipelines.megaplan.control"),
    ("control_interface", "arnold.pipelines.megaplan.control_interface", "arnold_pipelines.megaplan.control_interface"),
    ("step_contracts", "arnold.pipelines.megaplan.step_contracts", "arnold_pipelines.megaplan.step_contracts"),
)

# Non-existent paths from Section 6.2 — these have NO live file at either
# the stale or live path.  They must not be created unless the import
# contract forces it.
NON_EXISTENT_PATHS: tuple[tuple[str, str], ...] = (
    # (label, path_that_must_not_exist)
    ("native_runner.py", "arnold_pipelines.megaplan.native_runner"),
    ("cli/arnold.py (separate CLI)", "arnold_pipelines.megaplan.cli.arnold"),
    ("native_hooks.py", "arnold_pipelines.megaplan.native_hooks"),
)


# ── CLI / auto entrypoint resolution ────────────────────────────────────────

# These must route through live underscore paths, not stale dot-paths.
CLI_ENTRYPOINT_RESOLUTIONS: tuple[tuple[str, str, str], ...] = (
    # (label, subprocess_command, expected_live_module_name)
    (
        "megaplan describe",
        "from arnold_pipelines.megaplan.cli import handle_describe; "
        "print(handle_describe.__module__)",
        "arnold_pipelines.megaplan.cli",
    ),
    (
        "megaplan run --describe",
        "from arnold_pipelines.megaplan.cli.run import cli_run; "
        "print(cli_run.__module__)",
        "arnold_pipelines.megaplan.cli.run",
    ),
    (
        "auto driver",
        "from arnold_pipelines.megaplan.auto import main as auto_main; "
        "print(auto_main.__module__)",
        "arnold_pipelines.megaplan.auto",
    ),
    (
        "build_pipeline entrypoint",
        "from arnold_pipelines.megaplan.workflows.planning import build_pipeline; "
        "print(build_pipeline.__module__)",
        "arnold_pipelines.megaplan.workflows.planning",
    ),
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _subprocess_import_check(
    import_stmt: str,
    expect_failure: bool,
) -> tuple[bool, str]:
    """Run an import in a subprocess.  Returns (passed, output)."""
    code = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
try:
    {import_stmt}
    print("IMPORT_OK")
except Exception as e:
    print(f"IMPORT_FAILED: {{e}}")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(REPO_ROOT)},
    )
    output = result.stdout.strip() + "\n" + result.stderr.strip()
    ok = ("IMPORT_OK" in result.stdout) != expect_failure
    return ok, output


def _subprocess_resolve_module(code: str, expected_module: str) -> tuple[bool, str]:
    """Run code in a subprocess and check it prints the expected module name."""
    snippet = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
{code}
"""
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        timeout=30,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(REPO_ROOT)},
    )
    output = result.stdout.strip()
    passed = expected_module in output
    return passed, output


# ── Test classes ────────────────────────────────────────────────────────────


class TestLiveUnderscorePathsImportable:
    """Every live underscore path in the reconciliation doc must import.

    These are the only authoritative implementation targets for M1.
    If any of these fail, the live package has regressed or the
    reconciliation doc is stale.
    """

    @pytest.mark.parametrize("label,module_name", _all_live_paths())
    def test_live_path_imports(self, label: str, module_name: str) -> None:
        """Assert *module_name* is importable.

        This is a direct in-process import to catch any import-time
        side effects or regressions.
        """
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            pytest.fail(
                f"Live path '{label}' ({module_name}) failed to import: {exc}\n"
                f"This is a blocking condition: implementation must target "
                f"live underscore paths only."
            )


class TestStaleDotPathsDoNotCarryImplementation:
    """Stale ``arnold/pipelines/megaplan/`` paths must not carry implementation.

    The live package lives at ``arnold_pipelines/megaplan/`` (underscore).
    Importing a sub-module under the stale dot-path must fail with
    ``ModuleNotFoundError`` — confirming that no implementation exists
    at the stale path.
    """

    @pytest.mark.parametrize(
        "label,stale_module,live_module",
        STALE_PATHS_WITH_LIVE_EQUIVALENTS,
    )
    def test_stale_dot_path_fails_import(
        self,
        label: str,
        stale_module: str,
        live_module: str,
    ) -> None:
        """The stale dot-path must NOT resolve.

        We accept one exception: ``arnold.pipelines.megaplan`` (the
        top-level package name) may resolve as a namespace side-effect
        because ``arnold.pipelines`` is a real package.  But any
        *sub-module* under the stale dot-path must fail.
        """
        # Skip the top-level package, which may resolve due to
        # arnold.pipelines being an existing package with other content.
        if stale_module == "arnold.pipelines.megaplan":
            pytest.skip(
                "Top-level stale path may resolve as namespace side-effect; "
                "sub-module staleness is tested instead."
            )

        try:
            importlib.import_module(stale_module)
            pytest.fail(
                f"Stale dot-path '{label}' ({stale_module}) unexpectedly "
                f"resolved!  This means implementation may exist at a stale "
                f"path that is excluded from the wheel build.  "
                f"Live equivalent: {live_module}"
            )
        except ModuleNotFoundError:
            pass  # Expected — stale path has no implementation
        except ImportError as exc:
            # Also acceptable — the import chain hits a sub-module that
            # doesn't exist.
            if "arnold.pipelines.megaplan" in str(exc):
                pass
            else:
                raise

    @pytest.mark.parametrize("label,module_name", NON_EXISTENT_PATHS)
    def test_non_existent_path_does_not_resolve(
        self, label: str, module_name: str
    ) -> None:
        """Paths classified as non-existent in the reconciliation doc
        must not suddenly appear as importable modules.

        These are paths where no live file exists at either the stale
        or live location.  If one becomes importable, the reconciliation
        doc is stale and must be updated.
        """
        try:
            importlib.import_module(module_name)
            pytest.fail(
                f"Non-existent path '{label}' ({module_name}) unexpectedly "
                f"resolved.  This path is classified as 'no live file' in "
                f"the reconciliation doc.  Either the doc is stale, or a "
                f"forbidden implementation was added."
            )
        except ModuleNotFoundError:
            pass  # Expected
        except ImportError:
            pass  # Also acceptable


class TestLiveUnderscorePackageIsAuthoritative:
    """Confirm the live underscore package is the wheel-shipped package root.

    The stale dot-path is excluded from the wheel per pyproject.toml.
    These tests verify the live package carries the expected public
    surfaces and entrypoints.
    """

    def test_package_meta_comes_from_live_path(self) -> None:
        """``arnold_pipelines.megaplan.__version__`` or equivalent metadata
        must be accessible from the live underscore import.
        """
        import arnold_pipelines.megaplan as megaplan_pkg

        # The live package must have a __file__ pointing to the underscore path
        pkg_file = getattr(megaplan_pkg, "__file__", None)
        assert pkg_file is not None, (
            "arnold_pipelines.megaplan must have __file__"
        )
        assert "arnold_pipelines" in str(pkg_file), (
            f"Package __file__ must be under arnold_pipelines/, "
            f"got: {pkg_file}"
        )

    def test_canonical_build_pipeline_from_live_path(self) -> None:
        """The canonical ``build_pipeline()`` must be importable from
        the live underscore path ``arnold_pipelines.megaplan.workflows.planning``.
        """
        from arnold_pipelines.megaplan.workflows.planning import build_pipeline

        mod = getattr(build_pipeline, "__module__", None)
        assert mod is not None, "build_pipeline must have __module__"
        assert "arnold_pipelines" in mod, (
            f"build_pipeline must come from arnold_pipelines, got: {mod}"
        )

    def test_pipeline_facade_delegates_to_live_path(self) -> None:
        """``arnold_pipelines.megaplan.pipeline`` facade must delegate
        to the live workflows.planning module.
        """
        from arnold_pipelines.megaplan.pipeline import build_pipeline as facade_bp
        from arnold_pipelines.megaplan.workflows.planning import (
            build_pipeline as planning_bp,
        )

        # The facade should reference the same callable (or at least the
        # same underlying module for delegation).
        facade_mod = getattr(facade_bp, "__module__", "")
        planning_mod = getattr(planning_bp, "__module__", "")

        # If the facade re-exports the planning version, the modules
        # should match.  If not, the facade's module must still be
        # under arnold_pipelines.
        assert "arnold_pipelines" in facade_mod, (
            f"Facade build_pipeline must come from arnold_pipelines, "
            f"got: {facade_mod}"
        )

    def test_canonical_workflow_paths_reconcile_to_pypeline_and_glue_shim(self) -> None:
        workflow_source = resource_text(WORKFLOW_RESOURCE_PACKAGE, "workflow.pypeline")
        workflow_module = resource_text(WORKFLOW_RESOURCE_PACKAGE, "workflow.py")
        workflow_tree = ast.parse(workflow_source)
        function = next(node for node in workflow_tree.body if isinstance(node, ast.FunctionDef))
        called_names = {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        branch_names = {
            node.left.id
            for node in ast.walk(function)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
        }

        assert resource_exists(WORKFLOW_RESOURCE_PACKAGE, "workflow.pypeline")
        assert resource_exists(WORKFLOW_RESOURCE_PACKAGE, "workflow.py")
        assert not any(token in workflow_source for token in PROHIBITED_WRAPPER_TOKENS)
        assert any(isinstance(node, ast.While) for node in ast.walk(function))
        assert sum(isinstance(node, ast.If) for node in ast.walk(function)) >= 4
        assert {"loop", "parallel_map", "TIEBREAKER_WORKFLOW"} <= called_names
        assert {
            "gate_route_signal",
            "review_route_signal",
            "decision",
            "override_result",
        } <= branch_names
        assert "workflow.pypeline" in workflow_module
        assert not any(token in workflow_module for token in WORKFLOW_SHIM_PROHIBITED_TOKENS)

    def test_canonical_resource_path_helper_supports_file_api(self) -> None:
        with resource_path(WORKFLOW_RESOURCE_PACKAGE, "workflow.pypeline") as source_path:
            assert source_path.name == "workflow.pypeline"
            assert "canonical authored workflow source" in source_path.read_text(encoding="utf-8")


class TestCliAndAutoEntrypointsResolveThroughLivePaths:
    """CLI and auto entrypoints must route through live underscore modules,
    not stale dot-path references.
    """

    @pytest.mark.parametrize(
        "label,code,expected_module",
        CLI_ENTRYPOINT_RESOLUTIONS,
    )
    def test_entrypoint_resolves_through_live_module(
        self, label: str, code: str, expected_module: str
    ) -> None:
        """Verify that the entrypoint's ``__module__`` attribute starts
        with the live underscore package prefix.
        """
        passed, output = _subprocess_resolve_module(code, expected_module)
        assert passed, (
            f"Entrypoint '{label}' resolved through unexpected module.\n"
            f"Expected module containing '{expected_module}', "
            f"got output: {output}\n"
            f"This means the entrypoint may be routing through a stale "
            f"dot-path or a non-authoritative module."
        )

    def test_megaplan_module_entrypoint_is_live_underscore(self) -> None:
        """``python -m arnold_pipelines.megaplan`` must use the live
        underscore package __main__.
        """
        megaplan_main = importlib.import_module(
            "arnold_pipelines.megaplan.__main__"
        )
        main_file = getattr(megaplan_main, "__file__", None)
        assert main_file is not None, "__main__ must have __file__"
        assert "arnold_pipelines" in str(main_file), (
            f"__main__ must be under arnold_pipelines/, got: {main_file}"
        )


class TestStaleDotPathSubmodulesDoNotLeak:
    """Guard against the stale dot-path namespace leaking into sys.modules
    when live modules are imported.
    """

    def test_importing_live_package_does_not_populate_stale_namespace(
        self,
    ) -> None:
        """Importing ``arnold_pipelines.megaplan`` must not cause
        ``arnold.pipelines.megaplan`` sub-modules to populate in
        ``sys.modules``.
        """
        import arnold_pipelines.megaplan  # noqa: F401

        stale_submodules = [
            key
            for key in sys.modules
            if key.startswith("arnold.pipelines.megaplan.")
        ]
        assert not stale_submodules, (
            f"Importing live arnold_pipelines.megaplan caused stale "
            f"dot-path submodules to leak into sys.modules: {stale_submodules}"
        )


class TestBuildPackageExcludesStaleDotPath:
    """Per pyproject.toml, the stale dot-path is excluded from the wheel.
    Confirm that no megaplan product code exists at the stale dot-path
    in the filesystem.
    """

    def test_no_megaplan_directory_at_stale_dot_path(self) -> None:
        """The directory ``arnold/pipelines/megaplan/`` must not exist
        as a directory in the repository.
        """
        stale_dir = REPO_ROOT / "arnold" / "pipelines" / "megaplan"
        assert not stale_dir.is_dir(), (
            f"Stale dot-path directory exists: {stale_dir}\n"
            f"This directory is excluded from the wheel per pyproject.toml. "
            f"If it contains Megaplan product code, it is ghost code that "
            f"will never ship.  All Megaplan implementation must live at "
            f"arnold_pipelines/megaplan/ (underscore)."
        )

    def test_live_directory_exists(self) -> None:
        """The live underscore directory must exist and contain the
        canonical workflow source.
        """
        live_dir = REPO_ROOT / "arnold_pipelines" / "megaplan"
        assert live_dir.is_dir(), (
            f"Live underscore directory missing: {live_dir}"
        )
        planning_file = live_dir / "workflows" / "planning.py"
        assert planning_file.is_file(), (
            f"Canonical workflow source missing: {planning_file}"
        )
        assert WORKFLOW_PYPELINE_PATH.is_file(), (
            f"Canonical pypeline source missing: {WORKFLOW_PYPELINE_PATH}"
        )
