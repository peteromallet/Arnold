"""Behavioral identity manifest for realized pipeline graphs (M5a).

:data:`ManifestHash` is a deterministic SHA-256 hex digest over seven
canonically framed identity components.  Each component is prefixed with
its 4-byte big-endian byte-length before concatenation
(length-prefix framing).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Final, Iterable, NewType

from megaplan._pipeline.types import Port

ManifestHash = NewType("ManifestHash", str)

# M5-eval: Arnold SDK behavioral identity surface.
ARNOLD_API_VERSION: Final[int] = 1

logger = logging.getLogger(__name__)

_MISSING_PROMPT_BODY_PREFIX = b"<missing_prompt_body>"
_UNREGISTERED = b"<unregistered>"


def _frame(data: bytes) -> bytes:
    """Prefix *data* with its 4-byte big-endian length."""
    return len(data).to_bytes(4, "big") + data


def _resolve_export_name(step: Any) -> str:
    """Return the node-registry export name for *step*, keyed on (step.kind, step.name).

    M5a: returns ``step.name`` directly.  M2/M3 will formalize the
    ``(kind, name)`` → export-name mapping once typed Ports stabilize.
    """
    return str(getattr(step, "name", ""))


def _hash_step(step: Any, abi_version: str, node_registry: dict[str, Any]) -> bytes:
    """Return the source bytes representing *step*'s behavioral identity.

    Unregistered steps (name not in *node_registry*) return the sentinel
    ``b'<unregistered>'``.  Registered steps attempt ``inspect.getsource``
    on the bound ``run`` method; on ``OSError | TypeError`` the fallback
    ``'{module}.{qualname}@v{abi_version}'`` is used and a ``WARNING``
    is logged.
    """
    export_name = _resolve_export_name(step)
    if export_name not in node_registry:
        return _UNREGISTERED
    run_method = getattr(step, "run", None)
    if run_method is None:
        return _UNREGISTERED
    try:
        src = inspect.getsource(run_method)
        return src.encode()
    except (OSError, TypeError):
        module = getattr(type(step), "__module__", "<unknown>")
        qualname = getattr(type(step), "__qualname__", type(step).__name__)
        fallback = f"{module}.{qualname}@v{abi_version}"
        logger.warning(
            "behavioral_manifest: falling back to name-based hash for %s",
            fallback,
        )
        return fallback.encode()


def behavioral_manifest(realized_graph: Any, run_config: Any) -> ManifestHash:
    """Compute the behavioral identity hash for a realized pipeline graph.

    Returns a :data:`ManifestHash` (SHA-256 hex string) over the deterministic
    4-byte big-endian length-prefixed framing of seven identity components:
    ``topology``, ``step_codes``, ``prompt_bodies``, ``routing_taken``,
    ``port_set``, ``abi_version``, ``dep_closure``.

    **Pipeline→GraphAdapter is M3 scope.**  In M5a this function accepts a
    plain :class:`~megaplan._pipeline.types.Pipeline` (or any object with a
    ``.stages`` mapping) for topology extraction.  The ``realized_graph`` type
    will be narrowed to ``GraphAdapter`` in M3.

    Step code hashing (in order):

    1. If :func:`_resolve_export_name` returns a name **not** found in
       :data:`~megaplan._pipeline.patterns._NODE_REGISTRY`, the step hashes
       to the sentinel ``b'<unregistered>'``.
    2. Otherwise ``inspect.getsource(step.run)`` is attempted; on
       ``OSError | TypeError`` the fallback
       ``'{module}.{qualname}@v{abi_version}'`` is used and a ``WARNING``
       is logged.

    Missing prompt bodies hash as
    ``b'<missing_prompt_body>' + key.encode()``.
    """
    from megaplan._pipeline.patterns import _NODE_REGISTRY, arnold_api_version

    stages: dict[str, Any] = dict(getattr(realized_graph, "stages", {}) or {})
    sorted_names = sorted(stages.keys())

    # 1. topology — stage names + sorted edge descriptors
    topo_parts: list[str] = []
    for sn in sorted_names:
        stage = stages[sn]
        edges = getattr(stage, "edges", ()) or ()
        edge_strs = sorted(
            f"{getattr(e, 'label', '')}→{getattr(e, 'target', '')}:{getattr(e, 'kind', 'normal')}"
            for e in edges
        )
        topo_parts.append(f"{sn}:[{','.join(edge_strs)}]")
    topology_bytes = ";".join(topo_parts).encode()

    # 2. step_codes — per-registered-step source hash
    step_code_parts: list[bytes] = []
    for sn in sorted_names:
        stage = stages[sn]
        step = getattr(stage, "step", None)
        if step is not None:
            step_code_parts.append(
                _hash_step(step, arnold_api_version, _NODE_REGISTRY)
            )
    step_codes_bytes = b"||".join(step_code_parts)

    # 3. prompt_bodies — per-step prompt content
    prompts: Any = getattr(run_config, "prompts", None) or {}
    prompt_parts: list[bytes] = []
    for sn in sorted_names:
        stage = stages[sn]
        step = getattr(stage, "step", None)
        if step is None:
            continue
        prompt_key = getattr(step, "prompt_key", None)
        if not prompt_key:
            continue
        body = (
            prompts.get(prompt_key) if isinstance(prompts, dict)
            else getattr(prompts, prompt_key, None)
        )
        if body is None:
            prompt_parts.append(_MISSING_PROMPT_BODY_PREFIX + prompt_key.encode())
        else:
            prompt_parts.append(str(body).encode())
    prompt_bodies_bytes = b"||".join(prompt_parts)

    # 4. routing_taken — recorded routing decisions
    routing: Any = getattr(run_config, "routing_taken", None) or {}
    routing_bytes = ";".join(
        sorted(
            f"{k}={v}"
            for k, v in (routing.items() if isinstance(routing, dict) else [])
        )
    ).encode()

    # 5. port_set — consumes/produces from _NODE_REGISTRY
    port_set_bytes = ";".join(
        f"{n}:{','.join(sorted(str(x) for x in m.get('consumes', ())))}→"
        f"{','.join(sorted(str(x) for x in m.get('produces', ())))}"
        for n, m in sorted(_NODE_REGISTRY.items())
    ).encode()

    # 6. abi_version
    abi_version_bytes = arnold_api_version.encode()

    # 7. dep_closure — package version info
    try:
        import megaplan as _mg
        _ver = getattr(_mg, "__version__", "unknown")
    except Exception:
        _ver = "unknown"
    dep_closure_bytes = f"megaplan:{_ver}".encode()

    framed = (
        _frame(topology_bytes)
        + _frame(step_codes_bytes)
        + _frame(prompt_bodies_bytes)
        + _frame(routing_bytes)
        + _frame(port_set_bytes)
        + _frame(abi_version_bytes)
        + _frame(dep_closure_bytes)
    )
    return ManifestHash(hashlib.sha256(framed).hexdigest())


# ---------------------------------------------------------------------------
# M5-eval: NodeSpec registry + manifest_hash recipe
# ---------------------------------------------------------------------------


def _canonical_json_dumps(obj: Any) -> str:
    """Deterministic canonical JSON (sorted keys, compact separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def manifest_hash(
    *,
    step_code_source: str,
    resolved_rubric_body: str,
    model_identity: str,
    port_set: Iterable[Port],
    abi_version: int,
) -> str:
    """SHA-256 over canonical \\x00-joined identity inputs.

    Each Port in ``port_set`` is serialized via ``_canonical_json_dumps`` of
    ``{"name", "content_type"}`` — mirrors the recipe used by
    ``observability/events.py:compute_model_identity`` and the typed-port
    contract recipe planned for ``_pipeline/contracts.py:37-46``.
    """
    port_blob = ",".join(
        _canonical_json_dumps({"name": p.name, "content_type": p.content_type})
        for p in port_set
    )
    parts = [
        step_code_source,
        resolved_rubric_body,
        model_identity,
        port_blob,
        str(int(abi_version)),
    ]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NodeSpec:
    """Registered behavioral identity of a pipeline node.

    ``judge_version`` is the manifest_hash signature for the node's port
    set computed with empty rubric_body/model_identity — a stable handle
    used by `pipelines check` to populate NODE_REGISTRY without importing
    each node's implementation module.
    """

    consumes: tuple[Port, ...]
    produces: tuple[Port, ...]
    arnold_api_version: int
    judge_version: str


NODE_REGISTRY: dict[str, NodeSpec] = {}


def register_node(name: str, spec: NodeSpec) -> None:
    """Register a NodeSpec under ``name``. Raises ValueError on duplicate."""
    if name in NODE_REGISTRY:
        raise ValueError(f"node already registered: {name!r}")
    NODE_REGISTRY[name] = spec


# ── Built-in: judge.default ────────────────────────────────────────────
# Registered at module-import time so `pipelines check` can populate
# NODE_REGISTRY without importing megaplan._pipeline.judge_piece (mirrors
# the registry.py:586–595 built-in pattern).
_JUDGE_DEFAULT_CONSUMES: tuple[Port, ...] = (
    Port(name="judged-artifact", content_type="text/markdown"),
)
_JUDGE_DEFAULT_PRODUCES: tuple[Port, ...] = (
    Port(name="evaluand-record", content_type="application/x-evaluand+json"),
)

register_node(
    "judge.default",
    NodeSpec(
        consumes=_JUDGE_DEFAULT_CONSUMES,
        produces=_JUDGE_DEFAULT_PRODUCES,
        arnold_api_version=ARNOLD_API_VERSION,
        judge_version=manifest_hash(
            step_code_source="",
            resolved_rubric_body="",
            model_identity="",
            port_set=_JUDGE_DEFAULT_CONSUMES,
            abi_version=ARNOLD_API_VERSION,
        ),
    ),
)
