"""Runtime infrastructure helpers grouped under ``megaplan.runtime``.

Bundles four leaf modules that sit at the bottom of the dependency graph:

- :mod:`megaplan.runtime.sandbox` — terminal/patch/write validators wired into Claude tool hooks.
- :mod:`megaplan.runtime.key_pool` — hermes API key rotation and model resolution.
- :mod:`megaplan.runtime.capabilities` — agent-capability sets and routing defaults.
- :mod:`megaplan.runtime.doc_assembly` — doc-mode section assembly from plan artifacts.

``megaplan.types`` and ``megaplan.flags`` deliberately remain at the top level —
they are imported from so many places that consolidating them would create
churn without organizational benefit.
"""

from megaplan.runtime import capabilities, doc_assembly, key_pool, sandbox
from megaplan.runtime.capabilities import (
    ALL_CAPABILITIES,
    CONTAINER_CAPABILITIES,
    DEFAULT_AGENT_ROUTING,
    DEFAULT_CONTAINER_CAPABILITIES,
    DEFAULT_HUMAN_CAPABILITIES,
    HUMAN_CAPABILITIES,
    get_worker_capabilities,
    union_verifies,
    validate_capabilities,
)
from megaplan.runtime.doc_assembly import (
    assemble_doc,
    extract_sections,
    extract_settled_decisions,
)
from megaplan.runtime.key_pool import (
    KeyEntry,
    KeyPool,
    acquire_key,
    has_keys,
    minimax_openrouter_model,
    report_429,
    report_failure,
    resolve_model,
)
from megaplan.runtime.sandbox import (
    SANDBOXED_EXEC_TOOLS,
    SANDBOXED_WRITE_TOOLS,
    SandboxViolation,
    install_sandbox,
    validate_terminal_command,
    validate_v4a_patch,
    validate_write_path,
)

__all__ = [
    "capabilities",
    "doc_assembly",
    "key_pool",
    "sandbox",
    "ALL_CAPABILITIES",
    "CONTAINER_CAPABILITIES",
    "DEFAULT_AGENT_ROUTING",
    "DEFAULT_CONTAINER_CAPABILITIES",
    "DEFAULT_HUMAN_CAPABILITIES",
    "HUMAN_CAPABILITIES",
    "get_worker_capabilities",
    "union_verifies",
    "validate_capabilities",
    "assemble_doc",
    "extract_sections",
    "extract_settled_decisions",
    "KeyEntry",
    "KeyPool",
    "acquire_key",
    "has_keys",
    "minimax_openrouter_model",
    "report_429",
    "report_failure",
    "resolve_model",
    "SANDBOXED_EXEC_TOOLS",
    "SANDBOXED_WRITE_TOOLS",
    "SandboxViolation",
    "install_sandbox",
    "validate_terminal_command",
    "validate_v4a_patch",
    "validate_write_path",
]
