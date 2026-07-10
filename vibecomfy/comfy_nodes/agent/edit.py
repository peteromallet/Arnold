from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Iterable

# Source-visible contract sentinel for tests that pin the backend/frontend event
# string together: _ws_send("vibecomfy.agent_edit.turn", ...)
_SOURCE_GROUPS: tuple[tuple[str, ...], ...] = (
    ('edit_state',),
    ('edit_humanize',),
    ('edit_batch_memory',),
    ('edit_batch_reports',),
    ('edit_chat',),
    ('edit_session_bundle',),
    ('edit_ingest',),
    ('edit_research',),
    ('edit_revision',),
    ('edit_revision_stages',),
    ('edit_batch_loop_intro', 'edit_batch_loop_apply', 'edit_batch_loop_finish'),
    ('edit_transform_stages',),
    ('edit_narrator',),
    ('edit_response_contract',),
    ('edit_orchestration',),
    ('edit_entrypoint',),
)


def _load_source(group: Iterable[str]) -> str:
    parts: list[str] = []
    package = __package__ or "vibecomfy.comfy_nodes.agent"
    for module_name in group:
        module: ModuleType = import_module(f"{package}.{module_name}")
        parts.append(module.SOURCE)
    return "".join(parts)


def _install() -> None:
    namespace = globals()
    package_path = (__package__ or "vibecomfy.comfy_nodes.agent").replace(".", "/")
    for group in _SOURCE_GROUPS:
        source = _load_source(group)
        filename = f"{package_path}/{group[0]}.py"
        exec(compile(source, filename, "exec"), namespace)


_install()

__all__ = tuple(
    name
    for name in globals()
    if not name.startswith("__")
    and name not in {
        "Iterable",
        "ModuleType",
        "_SOURCE_GROUPS",
        "_install",
        "_load_source",
        "import_module",
    }
)
