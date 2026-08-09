"""Phase 3A seam tests for `arnold-repair-loop --mode=reactive|proactive`.

Covers the single entry seam added by the fixer-unification design: the
--mode flag, the --dry-run path (pure read of inputs: no locks, no marker
mutation, no agent spawn, no git), the mode model policy, and the proactive
NO-OP guard.  Only safe paths are executed: --dry-run invocations plus
bash -n; everything else is asserted against the script text.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPAIR_LOOP = (
    REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-repair-loop"
)

# Test-only escape hatch documented in the wrapper: skip the immutable
# snapshot self-copy so tests execute the checked-out script directly.
_SKIP_ENV = {"ARNOLD_REPAIR_LOOP_SKIP_SELF_COPY": "1"}


def _script_text() -> str:
    return REPAIR_LOOP.read_text(encoding="utf-8")


def _run_dry_run(tmp_path: Path, *extra_args: str, skip_self_copy: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    if skip_self_copy:
        env.update(_SKIP_ENV)
    return subprocess.run(
        ["bash", str(REPAIR_LOOP), *extra_args, "--dry-run", "sess-test", str(tmp_path / "ws"), "spec.yaml"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )


def test_usage_text_documents_mode_and_dry_run() -> None:
    text = _script_text()
    assert "--mode=reactive|proactive" in text
    assert "--dry-run" in text


def test_bash_n_passes() -> None:
    result = subprocess.run(
        ["bash", "-n", str(REPAIR_LOOP)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


def test_proactive_dry_run_exits_zero_with_report(tmp_path: Path) -> None:
    result = _run_dry_run(tmp_path, "--mode=proactive")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "dry-run" in result.stdout
    assert "proactive" in result.stdout
    assert "mode=proactive" in result.stdout


def test_reactive_dry_run_exits_zero_with_report(tmp_path: Path) -> None:
    result = _run_dry_run(tmp_path, "--mode=reactive")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "dry-run" in result.stdout
    assert "mode=reactive" in result.stdout


def test_default_mode_is_reactive(tmp_path: Path) -> None:
    result = _run_dry_run(tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "mode=reactive" in result.stdout


def test_proactive_dry_run_works_with_self_copy_snapshot(tmp_path: Path) -> None:
    """The immutable-snapshot self-copy path must also reach the dry-run exit."""
    result = _run_dry_run(tmp_path, "--mode=proactive", skip_self_copy=False)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "mode=proactive" in result.stdout
    assert "dry-run" in result.stdout


def test_select_mode_models_maps_proactive_to_flash(tmp_path: Path) -> None:
    text = _script_text()
    assert "select_mode_models" in text
    assert 'PROACTIVE_MODEL="${CLOUD_WATCHDOG_PROACTIVE_MODEL:-deepseek:deepseek-v4-flash}"' in text
    # Proactive dry-run must project the Flash model set end to end.
    result = _run_dry_run(tmp_path, "--mode=proactive")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "investigator_model=deepseek:deepseek-v4-flash" in result.stdout
    assert "owner_model=deepseek:deepseek-v4-flash" in result.stdout
    # Reactive keeps today's defaults untouched.
    reactive = _run_dry_run(tmp_path, "--mode=reactive")
    assert "investigator_model=gpt-5.6-sol" in reactive.stdout
    assert "brokered_investigator_model=deepseek:deepseek-v4-pro" in reactive.stdout
    assert "owner_model=gpt-5.6-sol" in reactive.stdout


def test_proactive_noop_guard_exists_in_script() -> None:
    text = _script_text()
    assert "NOOP exit 0" in text
    assert "repair_loop_noop_decision" in text


def test_invalid_mode_rejected(tmp_path: Path) -> None:
    env = {**os.environ, "TMPDIR": str(tmp_path), **_SKIP_ENV}
    result = subprocess.run(
        ["bash", str(REPAIR_LOOP), "--mode=bogus", "--dry-run", "s", "w", "r"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert result.returncode == 64
    assert "invalid --mode" in result.stderr
