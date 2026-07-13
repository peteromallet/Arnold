from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG = (
    REPO_ROOT
    / "arnold_pipelines"
    / "megaplan"
    / "cloud"
    / "wrappers"
    / "arnold-watchdog"
)


def _shell_function(name: str) -> str:
    lines = WATCHDOG.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"{name}() {{")
    depth = 0
    selected: list[str] = []
    for line in lines[start:]:
        selected.append(line)
        depth += line.count("{") - line.count("}")
        if depth == 0:
            break
    return "\n".join(selected)


def _write_chain_state(spec_path: Path, *, paused: bool) -> None:
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    state_path = (
        spec_path.parents[3]
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{spec_path.stem}-{digest}.json"
    )
    state_path.parent.mkdir(parents=True)
    metadata = {"operator_pause": {"active": True}} if paused else {}
    state_path.write_text(json.dumps({"metadata": metadata}), encoding="utf-8")


def test_durable_operator_pause_probe_reads_chain_authority(tmp_path: Path) -> None:
    spec_path = tmp_path / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_chain_state(spec_path, paused=True)

    script = "\n".join(
        [
            _shell_function("durable_operator_pause_active"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"durable_operator_pause_active {str(spec_path)!r}",
        ]
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_meta_dispatch_checks_pause_before_recording_dispatch() -> None:
    text = WATCHDOG.read_text(encoding="utf-8")
    dispatch = _shell_function("dispatch_meta_repair")
    assert dispatch.index('durable_operator_pause_active "$remote_spec"') < dispatch.index(
        "# Binary must exist and be executable"
    )
    assert 'REPAIR_DISPATCH_RESULT="paused"' in dispatch
    assert '"paused" "meta_repair"' in dispatch
    assert "durable operator pause active; meta-repair not dispatched" in dispatch
    assert text.count("meta-repair background-dispatched") > 0
