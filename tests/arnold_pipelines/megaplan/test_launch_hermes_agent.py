from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "arnold_pipelines"
    / "megaplan"
    / "skills"
    / "subagent-launcher"
    / "launch_hermes_agent.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("launch_hermes_agent_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_survives_incomplete_megaplan_namespace_without_agent_import(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    # A project-local `megaplan/` directory without `megaplan.agent` must not
    # break the omp-backed launcher: it never imports a megaplan agent runtime.
    (tmp_path / "megaplan").mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in list(sys.modules):
        if name == "megaplan" or name.startswith("megaplan."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    module = _load_module()

    # Dispatch refuses only on the missing omp binary — never on imports.
    exit_code = module.run(query="demo", omp_bin=str(tmp_path / "no-such-omp"))

    assert exit_code == 3
    assert "omp CLI not found" in capsys.readouterr().err
    assert not any(name == "megaplan.agent" for name in sys.modules)


def test_model_shortcut_normalizes_chain_hermes_provider_prefix() -> None:
    module = _load_module()

    def selector(model: str) -> str:
        translated, thinking = module._translate_model(model)
        assert thinking is None
        return translated

    assert selector("hermes:zhipu:glm-5.2") == "openrouter/z-ai/glm-latest"
    assert (
        selector(" hermes:deepseek:deepseek-v4-pro ")
        == "deepseek/deepseek-v4-pro"
    )
    assert selector("pro") == "deepseek/deepseek-v4-pro"
    assert selector("hermes:pro") == "deepseek/deepseek-v4-pro"
    assert selector("custom:model") == "custom:model"
