from __future__ import annotations

import builtins
import importlib.util
import sys
import types
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


def test_import_runtime_treats_megaplan_agent_missing_as_legacy_fallback(monkeypatch) -> None:
    module = _load_module()

    fake_run_agent = types.ModuleType("arnold.agent.run_agent")
    fake_run_agent.AIAgent = type("AIAgent", (), {})
    fake_state = types.ModuleType("arnold.agent.hermes_state")
    fake_state.SessionDB = type("SessionDB", (), {})
    fake_key_pool = types.ModuleType("arnold_pipelines.megaplan.runtime.key_pool")
    fake_key_pool.resolve_model = lambda value: value

    monkeypatch.setitem(sys.modules, "arnold", types.ModuleType("arnold"))
    monkeypatch.setitem(sys.modules, "arnold.agent", types.ModuleType("arnold.agent"))
    monkeypatch.setitem(sys.modules, "arnold.agent.run_agent", fake_run_agent)
    monkeypatch.setitem(sys.modules, "arnold.agent.hermes_state", fake_state)
    monkeypatch.setitem(sys.modules, "arnold_pipelines", types.ModuleType("arnold_pipelines"))
    monkeypatch.setitem(sys.modules, "arnold_pipelines.megaplan", types.ModuleType("arnold_pipelines.megaplan"))
    monkeypatch.setitem(sys.modules, "arnold_pipelines.megaplan.runtime", types.ModuleType("arnold_pipelines.megaplan.runtime"))
    monkeypatch.setitem(sys.modules, "arnold_pipelines.megaplan.runtime.key_pool", fake_key_pool)

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "megaplan.agent":
            raise ModuleNotFoundError("No module named 'megaplan.agent'", name="megaplan.agent")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    AIAgent, SessionDB, resolve_model = module._import_runtime()

    assert AIAgent is fake_run_agent.AIAgent
    assert SessionDB is fake_state.SessionDB
    assert resolve_model("demo-model") == "demo-model"
