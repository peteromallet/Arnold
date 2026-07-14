from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPERS = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _text(name: str) -> str:
    return (WRAPPERS / name).read_text(encoding="utf-8")


def test_shell_supervisors_pin_validated_absolute_interpreter() -> None:
    expected = {
        "arnold-watchdog": "watchdog",
        "arnold-repair-loop": "repair-loop",
        "arnold-meta-repair-loop": "meta-repair-loop",
        "arnold-progress-auditor": "progress-auditor",
    }
    for wrapper, component in expected.items():
        text = _text(wrapper)
        assert "arnold-supervisor-runtime-lib" in text
        assert f'arnold_supervisor_runtime_init {component} ' in text


def test_runtime_library_ignores_mutating_path_python(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text("#!/usr/bin/env bash\nexit 91\n", encoding="utf-8")
    fake_python.chmod(0o755)
    script = f"""
source {str(WRAPPERS / 'arnold-supervisor-runtime-lib')!r}
arnold_supervisor_runtime_init test-component {str(REPO_ROOT)!r}
python3 -c 'import sys; print(sys.executable)'
"""
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
            "MEGAPLAN_SUPERVISOR_PYTHON": sys.executable,
            "MEGAPLAN_SUPERVISOR_RUNTIME_REQUIRED": "1",
            "MEGAPLAN_SUPERVISOR_STATUS_DIR": str(tmp_path / "status"),
        }
    )
    result = subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == Path(sys.executable).resolve()


def test_runtime_library_forces_safe_path_against_shadow_cwd(tmp_path: Path) -> None:
    shadow_pkg = tmp_path / "arnold_pipelines"
    shadow_pkg.mkdir()
    (shadow_pkg / "__init__.py").write_text("print('SHADOWED_CWD_IMPORT')\n", encoding="utf-8")
    script = f"""
source {str(WRAPPERS / 'arnold-supervisor-runtime-lib')!r}
arnold_supervisor_runtime_init test-component {str(REPO_ROOT)!r}
PYTHONPATH="{str(REPO_ROOT)}:${{PYTHONPATH:-}}" python3 -c 'import arnold_pipelines,sys; print(arnold_pipelines.__file__); print(sys.path[0])'
"""
    env = os.environ.copy()
    env.update(
        {
            "MEGAPLAN_SUPERVISOR_PYTHON": sys.executable,
            "MEGAPLAN_SUPERVISOR_RUNTIME_REQUIRED": "1",
            "MEGAPLAN_SUPERVISOR_STATUS_DIR": str(tmp_path / "status"),
        }
    )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SHADOWED_CWD_IMPORT" not in result.stdout
    stdout_lines = result.stdout.strip().splitlines()
    assert stdout_lines[0].startswith(str(REPO_ROOT / "arnold_pipelines"))
    assert stdout_lines[1] != ""


def test_runtime_library_pins_selected_source_for_downstream_python(tmp_path: Path) -> None:
    ambient = tmp_path / "ambient"
    shadow_pkg = ambient / "arnold_pipelines"
    shadow_pkg.mkdir(parents=True)
    (shadow_pkg / "__init__.py").write_text(
        "print('AMBIENT_EDITABLE_IMPORT')\n",
        encoding="utf-8",
    )
    script = f"""
source {str(WRAPPERS / 'arnold-supervisor-runtime-lib')!r}
arnold_supervisor_runtime_init test-component {str(REPO_ROOT)!r}
python3 -c 'import arnold_pipelines; print(arnold_pipelines.__file__)'
"""
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ambient),
            "MEGAPLAN_SUPERVISOR_PYTHON": sys.executable,
            "MEGAPLAN_SUPERVISOR_RUNTIME_REQUIRED": "1",
            "MEGAPLAN_SUPERVISOR_STATUS_DIR": str(tmp_path / "status"),
        }
    )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "AMBIENT_EDITABLE_IMPORT" not in result.stdout
    assert result.stdout.strip().startswith(str(REPO_ROOT / "arnold_pipelines"))


def test_watchdog_fails_before_heartbeat_when_runtime_is_not_ready(tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    env = os.environ.copy()
    env.update(
        {
            "CLOUD_WATCHDOG_ARNOLD_SRC": str(REPO_ROOT),
            "CLOUD_WATCHDOG_STATUS_DIR": str(status_dir),
            "MEGAPLAN_SUPERVISOR_PYTHON": "/bin/false",
            "MEGAPLAN_SUPERVISOR_RUNTIME_REQUIRED": "1",
            "MEGAPLAN_SUPERVISOR_STATUS_DIR": str(status_dir),
        }
    )
    result = subprocess.run(
        ["bash", str(WRAPPERS / "arnold-watchdog"), "--once"],
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 78
    artifact = json.loads((status_dir / "watchdog.supervisor-runtime-failure.json").read_text())
    assert artifact["reason"] == "readiness_import_failed"
    assert not (status_dir / "watchdog.heartbeat").exists()
    assert not (status_dir / "watchdog-sweep.started.json").exists()
    assert not (status_dir / "watchdog-sweep.completed.json").exists()


def test_watchdog_sweep_started_and_completed_are_separate_atomic_receipts(tmp_path: Path) -> None:
    text = _text("arnold-watchdog")
    start = text.index("write_watchdog_sweep_health() {")
    end = text.index("\nwatchdog_observation_runtime_check() {", start)
    function = text[start:end]
    script = f"""
{function}
STATUS_DIR={str(tmp_path)!r}
write_watchdog_sweep_health started
write_watchdog_sweep_health completed
"""
    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    started = json.loads((tmp_path / "watchdog-sweep.started.json").read_text())
    completed = json.loads((tmp_path / "watchdog-sweep.completed.json").read_text())
    assert started["phase"] == "started"
    assert completed["phase"] == "completed"
    assert not list(tmp_path.glob(".*watchdog-sweep*"))


def test_watchdog_never_reinstalls_the_interpreter_it_runs_under() -> None:
    text = _text("arnold-watchdog")
    section = text[text.index("refresh_editable_install() {") : text.index("\nensure_editable_source_checkout() {")]
    assert "pip install" not in section
    assert "without mutating interpreter" in section


def test_repair_trigger_and_systemd_use_absolute_supervisor_python() -> None:
    trigger = _text("arnold-repair-trigger")
    unit = (
        REPO_ROOT
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "systemd"
        / "megaplan-repair-trigger.service"
    ).read_text(encoding="utf-8")
    assert trigger.startswith("#!/workspace/.megaplan/supervisor-python/current/bin/python3")
    assert "_select_supervisor_interpreter()" in trigger
    assert "readiness_import_failed" in trigger
    assert "ExecStart=/workspace/.megaplan/supervisor-python/current/bin/python3 " in unit


def test_dependency_independent_gap_scan_flags_stopped_marker_without_custody(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    marker_dir.mkdir()
    workspace.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps(
            {
                "session": "demo",
                "workspace": str(workspace),
                "remote_spec": str(workspace / "chain.yaml"),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    # Legacy timestamp-only dispatch markers are not repair custody.
    (marker_dir / "demo.kimi-dispatch").write_text("2026-07-13T22:44:39Z\n", encoding="utf-8")
    output = tmp_path / "gaps.json"
    command = [
        sys.executable,
        str(WRAPPERS / "arnold-supervisor-gap-scan"),
        "--marker-dir",
        str(marker_dir),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text())
    assert payload["status"] == "unhealthy"
    assert payload["findings"][0]["reason"] == "stopped_marker_without_chain_or_repair_state"

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(command, check=True, text=True, capture_output=True)
    assert json.loads(output.read_text())["status"] == "healthy"


def test_l2_and_l3_run_dependency_independent_gap_detection_before_model_work() -> None:
    meta = _text("arnold-meta-repair-loop")
    auditor = _text("arnold-progress-auditor")
    assert "SUPERVISOR_GAP_EVIDENCE" in meta
    assert "--session \"$SESSION\"" in meta
    assert "Dependency-independent launch-gap evidence" in meta
    assert "SUPERVISOR_GAP_EVIDENCE" in auditor
    assert "_dependency_independent_launch_gap_reason" in auditor
    for text, component in ((meta, "meta-repair-loop"), (auditor, "progress-auditor")):
        scan = text.index('"$MEGAPLAN_SUPERVISOR_STDLIB_PYTHON" -P "$SUPERVISOR_GAP_SCAN"')
        readiness = text.index(f'arnold_supervisor_runtime_init {component} ')
        assert scan < readiness


def test_supervisor_wrappers_do_not_launch_python_before_runtime_init() -> None:
    expected = {
        "arnold-watchdog": "watchdog",
        "arnold-repair-loop": "repair-loop",
        "arnold-meta-repair-loop": "meta-repair-loop",
        "arnold-progress-auditor": "progress-auditor",
    }
    python_re = re.compile(r"(?m)^[^#\n]*\bpython3\b")
    for wrapper, component in expected.items():
        text = _text(wrapper)
        readiness = text.index(f"arnold_supervisor_runtime_init {component} ")
        first_python = python_re.search(text)
        assert first_python is not None
        assert first_python.start() > readiness


def test_timeout_bypasses_use_absolute_safe_supervisor_interpreter() -> None:
    repair = _text("arnold-repair-loop")
    meta = _text("arnold-meta-repair-loop")
    assert 'PYTHONSAFEPATH=1 timeout "$KIMI_TIMEOUT" "$MEGAPLAN_SUPERVISOR_PYTHON" -P -m arnold.agent.run_agent' in repair
    assert 'PYTHONSAFEPATH=1 timeout "$SUBAGENT_TIMEOUT" "$MEGAPLAN_SUPERVISOR_PYTHON" -P -c ' in meta


def test_runtime_prepare_uses_staging_and_atomic_symlink_swap() -> None:
    helper = _text("arnold-supervisor-runtime")
    assert 'mktemp -d "$ROOT/.staging.' in helper
    assert 'mv -Tf "$link_tmp" "$CURRENT"' in helper
    assert "runtime_ready \"$stage/bin/python3\"" in helper
