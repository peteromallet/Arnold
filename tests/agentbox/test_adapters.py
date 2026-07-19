from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import importlib
import sys
from pathlib import Path

from arnold.runtime.durable_ops import OperationRun

from agentbox.adapters import (
    get_operation_adapter,
    list_agentbox_operation_types,
    list_operation_adapters,
)
from agentbox.config import AgentBoxConfig
from agentbox.operations import list_agentbox_operations, load_agentbox_operation, open_operation_store


def test_registry_discovers_megaplan_chain_without_importing_adapter_module() -> None:
    with _temporarily_unload_megaplan_modules():
        adapter = get_operation_adapter("megaplan_chain")

        assert adapter.kind == "megaplan_chain"
        assert adapter.operation_type == "megaplan_chain"
        assert adapter.module_path == "arnold_pipelines.megaplan.agentbox_adapter"
        assert adapter.factory_name == "get_agentbox_adapter"
        assert [item.kind for item in list_operation_adapters()] == ["megaplan_chain"]
        assert "megaplan_chain" in list_agentbox_operation_types()
        assert "arnold_pipelines.megaplan.agentbox_adapter" not in sys.modules


def test_importing_agentbox_core_does_not_import_megaplan_modules() -> None:
    with _temporarily_unload_megaplan_modules():
        importlib.import_module("agentbox")
        importlib.import_module("agentbox.adapters")
        importlib.import_module("agentbox.operations")
        importlib.import_module("agentbox.cli")

        assert not any(name.startswith("arnold_pipelines.megaplan") for name in sys.modules)


def test_registered_megaplan_chain_operations_are_agentbox_managed(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    store = open_operation_store(config)
    chain = store.create_operation_run(OperationRun(id="chain", operation_type="megaplan_chain"))
    store.create_operation_run(OperationRun(id="foreign", operation_type="foreign"))

    assert list_agentbox_operations(config) == (chain,)
    assert load_agentbox_operation(config, "chain") == chain


def test_adapter_registry_source_has_no_eager_megaplan_import() -> None:
    source = (Path(__file__).resolve().parents[2] / "agentbox/adapters.py").read_text(
        encoding="utf-8"
    )

    assert "import arnold_pipelines" not in source
    assert "from arnold_pipelines" not in source


@contextmanager
def _temporarily_unload_megaplan_modules() -> Iterator[None]:
    saved = {
        name: module
        for name, module in tuple(sys.modules.items())
        if name.startswith("arnold_pipelines.megaplan")
    }
    for name in saved:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        for name in tuple(sys.modules):
            if name.startswith("arnold_pipelines.megaplan"):
                sys.modules.pop(name, None)
        sys.modules.update(saved)
