"""Tests for ``arnold.runtime.dry_run`` (T9 / SC9).

Coverage
--------
* ``dry_run_report`` renders every supported setting with key/value/source.
* Errors render in a distinct ``ERRORS:`` block.
* The report is deterministic (same inputs → same output).
* Snapshot test for a representative fixture spec.
* AST guard: no ``megaplan`` imports in ``dry_run.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from arnold.runtime.dry_run import dry_run_report, _SUPPORTED_KEYS
from arnold.runtime.settings import SettingSource
from arnold.runtime.settings_resolver import ResolvedSettings, resolve_settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dry_run_module_path() -> Path:
    """Return the absolute path to dry_run.py."""
    import arnold.runtime.dry_run as mod

    return Path(str(mod.__file__)).resolve()


# ---------------------------------------------------------------------------
# Render smoke tests
# ---------------------------------------------------------------------------


class TestDryRunReportRender:
    """Smoke tests for the dry_run_report renderer."""

    def test_every_supported_key_appears_in_report(self) -> None:
        """The report must mention every key in _SUPPORTED_KEYS."""
        result = resolve_settings(
            arnold_defaults={
                "wall_timeout_s": 30.0,
                "idle_timeout_s": 10.0,
                "max_workers": 4,
                "isolation_mode": "in_process",
            },
        )
        report = dry_run_report(result)
        for key in _SUPPORTED_KEYS:
            assert key in report, f"key {key!r} missing from report"

    def test_resolved_value_and_source_appear(self) -> None:
        """A key resolved from a specific layer shows value + source."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 30.0},
        )
        report = dry_run_report(result)
        assert "30.0" in report
        assert "arnold_default" in report

    def test_unset_key_shows_placeholder(self) -> None:
        """A key with no resolved value shows '---' for value and source."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 30.0},
        )
        report = dry_run_report(result)
        # The header uses --- as separator; the unset values also use ---
        # Count occurrences: at least 3 + number_of_unset_keys
        assert report.count("---") >= 3  # header row

    def test_errors_block_renders_when_errors_present(self) -> None:
        """When errors exist, an ERRORS: block appears with [code]."""
        result = resolve_settings(
            run_overrides={
                "isolation_mode": "docker_container",
                "max_workers": 0,
            }
        )
        report = dry_run_report(result)
        assert "ERRORS:" in report
        assert "[isolation_mode_invalid]" in report
        assert "[max_workers_nonpositive]" in report

    def test_no_errors_block_when_no_errors(self) -> None:
        """When there are no errors, no ERRORS: block appears."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 30.0, "max_workers": 4},
        )
        report = dry_run_report(result)
        assert "ERRORS:" not in report

    def test_deterministic_output(self) -> None:
        """Same inputs produce identical output (deterministic)."""
        result1 = resolve_settings(
            arnold_defaults={"wall_timeout_s": 30.0, "max_workers": 4},
        )
        result2 = resolve_settings(
            arnold_defaults={"wall_timeout_s": 30.0, "max_workers": 4},
        )
        assert dry_run_report(result1) == dry_run_report(result2)


# ---------------------------------------------------------------------------
# Snapshot test
# ---------------------------------------------------------------------------


class TestDryRunSnapshot:
    """Snapshot the rendered report for a representative fixture spec."""

    def test_fixture_report_matches_snapshot(self) -> None:
        """Resolve a populated spec and snapshot the report."""
        result = resolve_settings(
            arnold_defaults={
                "wall_timeout_s": 30.0,
                "idle_timeout_s": 10.0,
                "heartbeat_interval_s": 5.0,
                "poll_cadence_s": 1.0,
                "max_workers": 4,
                "isolation_mode": "in_process",
            },
            plugin_defaults={"wall_timeout_s": 60.0},
            profile={"max_workers": 8},
            run_overrides={"wall_timeout_s": 90.0},
            env_overrides={"isolation_mode": "subprocess_isolated"},
            pipeline_stages=frozenset({"build", "test"}),
            stage_local=[
                {"stage_id": "build", "overrides": {"wall_timeout_s": 120.0}},
                {"stage_id": "test", "overrides": {"idle_timeout_s": 20.0}},
            ],
            child_scope_overrides={
                "panels": {"max_workers": 2},
            },
        )
        report = dry_run_report(result)

        # Structural assertions before snapshot comparison
        assert "wall_timeout_s" in report
        assert "90.0" in report  # run_override wins at run level
        assert "build" in report  # stage-effective block
        assert "test" in report
        assert "panels" in report  # child-scope block
        assert "120.0" in report  # build stage override
        assert "STAGE EFFECTIVE SETTINGS" in report
        assert "CHILD SCOPE EFFECTIVE SETTINGS" in report

        # Snapshot the exact output
        assert report == (
            "key                       value                 source              \n"
            "---                       ---                   ---                 \n"
            "wall_timeout_s            90.0                  run_override        \n"
            "idle_timeout_s            10.0                  arnold_default      \n"
            "heartbeat_interval_s      5.0                   arnold_default      \n"
            "poll_cadence_s            1.0                   arnold_default      \n"
            "deadline_epoch_s          ---                   ---                 \n"
            "retry_budget              ---                   ---                 \n"
            "cost_cap_usd              ---                   ---                 \n"
            "max_workers               8                     profile             \n"
            "cancellation              ---                   ---                 \n"
            "isolation_mode            subprocess_isolated   env_override        \n"
            "\n"
            "STAGE EFFECTIVE SETTINGS\n"
            "======================================================================\n"
            "  [build]\n"
            "    wall_timeout_s          120.0               run_override        \n"
            "    idle_timeout_s          10.0                arnold_default      \n"
            "    heartbeat_interval_s    5.0                 arnold_default      \n"
            "    poll_cadence_s          1.0                 arnold_default      \n"
            "    deadline_epoch_s        ---                 ---                 \n"
            "    retry_budget            ---                 ---                 \n"
            "    cost_cap_usd            ---                 ---                 \n"
            "    max_workers             8                   profile             \n"
            "    cancellation            ---                 ---                 \n"
            "    isolation_mode          subprocess_isolated  env_override        \n"
            "\n"
            "  [test]\n"
            "    wall_timeout_s          90.0                run_override        \n"
            "    idle_timeout_s          20.0                run_override        \n"
            "    heartbeat_interval_s    5.0                 arnold_default      \n"
            "    poll_cadence_s          1.0                 arnold_default      \n"
            "    deadline_epoch_s        ---                 ---                 \n"
            "    retry_budget            ---                 ---                 \n"
            "    cost_cap_usd            ---                 ---                 \n"
            "    max_workers             8                   profile             \n"
            "    cancellation            ---                 ---                 \n"
            "    isolation_mode          subprocess_isolated  env_override        \n"
            "\n"
            "CHILD SCOPE EFFECTIVE SETTINGS\n"
            "======================================================================\n"
            "  [panels]\n"
            "    wall_timeout_s          90.0                run_override        \n"
            "    idle_timeout_s          10.0                arnold_default      \n"
            "    heartbeat_interval_s    5.0                 arnold_default      \n"
            "    poll_cadence_s          1.0                 arnold_default      \n"
            "    deadline_epoch_s        ---                 ---                 \n"
            "    retry_budget            ---                 ---                 \n"
            "    cost_cap_usd            ---                 ---                 \n"
            "    max_workers             2                   run_override        \n"
            "    cancellation            ---                 ---                 \n"
            "    isolation_mode          subprocess_isolated  env_override        \n"
        )


# ---------------------------------------------------------------------------
# AST guard: no megaplan imports in dry_run.py
# ---------------------------------------------------------------------------


class TestDryRunNoMegaplanImport:
    """AST guard verifying ``dry_run.py`` has zero megaplan imports."""

    def test_dry_run_py_has_no_megaplan_import(self) -> None:
        mod_path = _dry_run_module_path()
        source = mod_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(mod_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("megaplan"), (
                        f"{mod_path.name}: import megaplan (or subpackage) found: "
                        f"import {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("megaplan"):
                    pytest.fail(
                        f"{mod_path.name}: from megaplan import found: "
                        f"from {node.module} import ..."
                    )
