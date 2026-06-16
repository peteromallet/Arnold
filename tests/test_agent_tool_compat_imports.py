from concurrent.futures import ThreadPoolExecutor
import importlib


def _load_agent_tool_symbols() -> None:
    checkpoint_manager = importlib.import_module(
        "arnold.agent.tools.checkpoint_manager"
    )
    todo_tool = importlib.import_module("arnold.agent.tools.todo_tool")
    terminal_tool = importlib.import_module("arnold.agent.tools.terminal_tool")
    interrupt = importlib.import_module("tools.interrupt")

    assert checkpoint_manager.CheckpointManager
    assert todo_tool.TodoStore
    assert terminal_tool._interrupt_event is interrupt._interrupt_event


def test_agent_tool_compat_imports_are_thread_safe() -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: _load_agent_tool_symbols(), range(32)))
