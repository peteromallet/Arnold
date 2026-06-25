from __future__ import annotations


def test_execute_toolsets_expose_terminal_and_file_tools(monkeypatch):
    monkeypatch.setenv("TERMINAL_ENV", "local")

    from arnold.agent.model_tools import get_tool_definitions
    from arnold.pipelines.megaplan.workers.hermes import _toolsets_for_phase

    tools = get_tool_definitions(
        enabled_toolsets=_toolsets_for_phase("execute"),
        quiet_mode=True,
    )
    tool_names = {tool["function"]["name"] for tool in tools}

    assert {
        "terminal",
        "process",
        "read_file",
        "write_file",
        "patch",
        "search_files",
    } <= tool_names


def test_terminal_tool_module_exports_runtime_hooks(monkeypatch):
    monkeypatch.setenv("TERMINAL_ENV", "local")

    import arnold.agent.tools.terminal_tool as terminal_tool

    assert terminal_tool.check_terminal_requirements() is True
    assert callable(terminal_tool.terminal_tool)
    assert callable(terminal_tool.register_task_env_overrides)
    assert isinstance(terminal_tool._active_environments, dict)
