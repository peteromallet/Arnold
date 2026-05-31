"""Runtime infrastructure helpers grouped under ``megaplan.runtime``."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULE_EXPORTS = {
    "capabilities": "megaplan.runtime.capabilities",
    "doc_assembly": "megaplan.runtime.doc_assembly",
    "key_pool": "megaplan.runtime.key_pool",
    "sandbox": "megaplan.runtime.sandbox",
}

_SYMBOL_EXPORTS = {
    "ALL_CAPABILITIES": "megaplan.runtime.capabilities",
    "CONTAINER_CAPABILITIES": "megaplan.runtime.capabilities",
    "DEFAULT_AGENT_ROUTING": "megaplan.runtime.capabilities",
    "DEFAULT_CONTAINER_CAPABILITIES": "megaplan.runtime.capabilities",
    "DEFAULT_HUMAN_CAPABILITIES": "megaplan.runtime.capabilities",
    "HUMAN_CAPABILITIES": "megaplan.runtime.capabilities",
    "get_worker_capabilities": "megaplan.runtime.capabilities",
    "union_verifies": "megaplan.runtime.capabilities",
    "validate_capabilities": "megaplan.runtime.capabilities",
    "assemble_doc": "megaplan.runtime.doc_assembly",
    "extract_sections": "megaplan.runtime.doc_assembly",
    "extract_settled_decisions": "megaplan.runtime.doc_assembly",
    "KeyEntry": "megaplan.runtime.key_pool",
    "KeyPool": "megaplan.runtime.key_pool",
    "acquire_key": "megaplan.runtime.key_pool",
    "has_keys": "megaplan.runtime.key_pool",
    "minimax_openrouter_model": "megaplan.runtime.key_pool",
    "report_429": "megaplan.runtime.key_pool",
    "report_failure": "megaplan.runtime.key_pool",
    "resolve_model": "megaplan.runtime.key_pool",
    "SANDBOXED_EXEC_TOOLS": "megaplan.runtime.sandbox",
    "SANDBOXED_WRITE_TOOLS": "megaplan.runtime.sandbox",
    "SandboxViolation": "megaplan.runtime.sandbox",
    "install_sandbox": "megaplan.runtime.sandbox",
    "validate_terminal_command": "megaplan.runtime.sandbox",
    "validate_v4a_patch": "megaplan.runtime.sandbox",
    "validate_write_path": "megaplan.runtime.sandbox",
}

__all__ = [*_MODULE_EXPORTS, *_SYMBOL_EXPORTS]


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        value = import_module(_MODULE_EXPORTS[name])
        globals()[name] = value
        return value
    if name in _SYMBOL_EXPORTS:
        module = import_module(_SYMBOL_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
