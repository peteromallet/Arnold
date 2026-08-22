from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


LAUNCHER = (
    Path(__file__).resolve().parents[1]
    / "arnold_pipelines"
    / "megaplan"
    / "skills"
    / "subagent-launcher"
    / "launch_hermes_agent.py"
)


def _load_launcher():
    spec = importlib.util.spec_from_file_location("test_launch_hermes_agent_module", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_runtime_falls_through_incomplete_megaplan_namespace(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    # A project-local `megaplan/` directory without `megaplan.agent` must not
    # break the omp-backed launcher: dispatch never imports a megaplan agent
    # runtime, so the incomplete namespace is simply ignored.
    (tmp_path / "megaplan").mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in list(sys.modules):
        if name == "megaplan" or name.startswith("megaplan."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    launcher = _load_launcher()
    exit_code = launcher.run(query="demo", omp_bin=str(tmp_path / "no-such-omp"))

    assert exit_code == 3
    assert "omp CLI not found" in capsys.readouterr().err
    assert not any(name == "megaplan.agent" for name in sys.modules)
