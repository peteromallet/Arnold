"""Runtime infrastructure helpers grouped under ``megaplan.runtime``."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULE_EXPORTS = {
    "capabilities": "arnold_pipelines.megaplan.runtime.capabilities",
    "doc_assembly": "arnold_pipelines.megaplan.runtime.doc_assembly",
    "key_pool": "arnold_pipelines.megaplan.runtime.key_pool",
    "sandbox": "arnold_pipelines.megaplan.runtime.sandbox",
}

_SYMBOL_EXPORTS = {
    "ALL_CAPABILITIES": "arnold_pipelines.megaplan.runtime.capabilities",
    "CONTAINER_CAPABILITIES": "arnold_pipelines.megaplan.runtime.capabilities",
    "DEFAULT_AGENT_ROUTING": "arnold_pipelines.megaplan.profiles.policy",
    "DEFAULT_CONTAINER_CAPABILITIES": "arnold_pipelines.megaplan.runtime.capabilities",
    "DEFAULT_HUMAN_CAPABILITIES": "arnold_pipelines.megaplan.runtime.capabilities",
    "HUMAN_CAPABILITIES": "arnold_pipelines.megaplan.runtime.capabilities",
    "get_worker_capabilities": "arnold_pipelines.megaplan.runtime.capabilities",
    "union_verifies": "arnold_pipelines.megaplan.runtime.capabilities",
    "validate_capabilities": "arnold_pipelines.megaplan.runtime.capabilities",
    "assemble_doc": "arnold_pipelines.megaplan.runtime.doc_assembly",
    "extract_sections": "arnold_pipelines.megaplan.runtime.doc_assembly",
    "extract_settled_decisions": "arnold_pipelines.megaplan.runtime.doc_assembly",
    "KeyEntry": "arnold_pipelines.megaplan.runtime.key_pool",
    "KeyPool": "arnold_pipelines.megaplan.runtime.key_pool",
    "acquire_key": "arnold_pipelines.megaplan.runtime.key_pool",
    "has_keys": "arnold_pipelines.megaplan.runtime.key_pool",
    "minimax_openrouter_model": "arnold_pipelines.megaplan.runtime.key_pool",
    "report_429": "arnold_pipelines.megaplan.runtime.key_pool",
    "report_failure": "arnold_pipelines.megaplan.runtime.key_pool",
    "resolve_model": "arnold_pipelines.megaplan.runtime.key_pool",
    "CapacityLease": "arnold_pipelines.megaplan.runtime.capacity_lease",
    "Governor": "arnold_pipelines.megaplan.runtime.governor",
    "current_governor": "arnold_pipelines.megaplan.runtime.governor",
    "set_governor": "arnold_pipelines.megaplan.runtime.governor",
    "SANDBOXED_EXEC_TOOLS": "arnold_pipelines.megaplan.runtime.sandbox",
    "SANDBOXED_WRITE_TOOLS": "arnold_pipelines.megaplan.runtime.sandbox",
    "SandboxViolation": "arnold_pipelines.megaplan.runtime.sandbox",
    "install_sandbox": "arnold_pipelines.megaplan.runtime.sandbox",
    "validate_terminal_command": "arnold_pipelines.megaplan.runtime.sandbox",
    "validate_v4a_patch": "arnold_pipelines.megaplan.runtime.sandbox",
    "validate_write_path": "arnold_pipelines.megaplan.runtime.sandbox",
}

__all__ = [
    *_MODULE_EXPORTS,
    *_SYMBOL_EXPORTS,
    "install_runtime_governor",
    "uninstall_runtime_governor",
]


def uninstall_runtime_governor(gov: Any) -> None:
    """Reset ContextVar tokens installed by ``install_runtime_governor``."""

    if gov is None:
        return
    tokens = getattr(gov, "_install_tokens", None) or []
    setattr(gov, "_install_tokens", [])
    for reset_fn, token in tokens:
        try:
            reset_fn(token)
        except Exception:
            pass


def install_runtime_governor(envelope: Any, *, ledger_path: Any = None) -> Any:
    """Install a tree-scoped Governor and seat the envelope in runtime contexts."""

    del ledger_path
    from arnold_pipelines.megaplan._pipeline.envelope import _envelope_ctx as _pipeline_env_ctx
    from arnold_pipelines.megaplan.observability.events import _envelope_ctx as _events_env_ctx
    from arnold_pipelines.megaplan.runtime.governor import Governor, set_governor

    gov = Governor()
    set_governor(gov)
    tokens: list[Any] = []
    if envelope is not None:
        tokens.append((_pipeline_env_ctx.reset, _pipeline_env_ctx.set(envelope)))
        tokens.append((_events_env_ctx.reset, _events_env_ctx.set(envelope)))
    setattr(gov, "_install_tokens", tokens)
    return gov


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
