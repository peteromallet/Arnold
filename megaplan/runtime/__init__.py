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
from megaplan.runtime.capacity_lease import CapacityLease
from megaplan.runtime.governor import Governor, current_governor, set_governor
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
    "CapacityLease",
    "Governor",
    "current_governor",
    "set_governor",
    "install_runtime_governor",
    "uninstall_runtime_governor",
]


def uninstall_runtime_governor(gov) -> None:
    """M4 T9: tear down the ContextVar state seated by install_runtime_governor.

    Resets the per-call tokens stashed on ``gov`` by install_runtime_governor —
    both the pipeline-side ``_envelope_ctx`` and the observability-side
    ``_envelope_ctx`` carriers.  Safe to call once; idempotent (subsequent calls
    are no-ops).  Provided so call sites that want strict enter/exit semantics
    (e.g. a try/finally around a run) can clear the carriers; the executor
    install seam may also call this on pipeline exit in a later task.
    """
    if gov is None:
        return
    tokens = getattr(gov, "_install_tokens", None) or []
    setattr(gov, "_install_tokens", [])
    for reset_fn, token in tokens:
        try:
            reset_fn(token)
        except Exception:
            pass


def install_runtime_governor(envelope, *, ledger_path=None):
    """M4 T2: install a tree-scoped :class:`Governor` for *envelope*.

    Creates a fresh ``Governor()`` with sentinel/disabled caps, attaches it to
    the current :class:`contextvars.ContextVar` scope via :func:`set_governor`,
    and seats *envelope* into the pipeline's ``_envelope_ctx`` so in-process
    consumers (KeyPool, fan-out pattern code) can observe it.

    ``ledger_path`` is reserved for the Effect-Ledger wiring landing in a
    later M4 step; it is accepted today but unused so the call sites do not
    need to change again when the ledger plumbing lands.

    Returns the installed :class:`Governor` so callers can mutate caps or
    inspect counters in tests.
    """

    gov = Governor()
    set_governor(gov)
    tokens: list = []
    if envelope is not None:
        from contextvars import ContextVar as _CV  # noqa: F401
        from megaplan._pipeline.envelope import _envelope_ctx as _pipeline_env_ctx
        from megaplan.observability.events import _envelope_ctx as _events_env_ctx

        # Seat envelope into BOTH carriers and stash the reset tokens on the
        # governor so a paired uninstall_runtime_governor(gov) can clear them
        # symmetrically on exit (M4 T9: "set on enter, clear on exit").
        tokens.append((_pipeline_env_ctx.reset, _pipeline_env_ctx.set(envelope)))
        tokens.append((_events_env_ctx.reset, _events_env_ctx.set(envelope)))
    setattr(gov, "_install_tokens", tokens)
    return gov
