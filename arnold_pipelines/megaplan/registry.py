"""Pipeline registry — megaplan-owned policy authority.

The neutral Arnold registry core lives at :mod:`arnold.workflow.registry`.
This module supplies Megaplan-specific defaults (budget quota reservation,
operation-registry fallbacks, planning override catalogs) and wires the
global singleton.

Pipeline discovery (scan roots, module loading, manifest reading) has been
extracted to :mod:`arnold_pipelines.megaplan.runtime.discovery` during the
M3 burn-down.

This module was rehomed from ``arnold_pipelines.megaplan._pipeline.registry``
during the M3 burn-down (T17).

A programmatic registration is available for tests and local extensions::

    from arnold_pipelines.megaplan.registry import register_pipeline
    register_pipeline("my-pipeline", build_my_pipeline, description="…")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.workflow.discovery.manifest import (
    Manifest,
    read_manifest,
)
from arnold.workflow.registry import PipelineRegistry as ArnoldPipelineRegistry
from arnold.pipeline.types import Pipeline
from arnold.execution.operations import (
    NullOperationRegistry,
    OperationKind,
    OperationRegistry,
    OperationRequest,
    OperationResult,
)
from arnold.workflow.discovery.trust import BLESSED_ALLOWLIST, TrustGrade
from arnold_pipelines.megaplan.runtime.discovery import classify
from arnold_pipelines.megaplan.runtime.discovery import (
    CANONICAL_BUILTIN_PIPELINE,
    LEGACY_PIPELINE_ALIASES,
    PipelineBuilder,
    _coerce_supported_operations,
    _load_trusted_pipeline_module,
    _make_deferred_builder,
    _manifest_discovery_enabled,
    _manifest_metadata,
    _operation_registry_from_module,
    _package_prefix_for_module_file,
    _supported_operation_names,
    canonical_pipeline_name,
    discover_python_pipelines,
    scan_python_pipelines,
)


# ---------------------------------------------------------------------------
# Megaplan adapter — Arnold core with Megaplan defaults
# ---------------------------------------------------------------------------


def make_megaplan_registry() -> ArnoldPipelineRegistry:
    """Create an Arnold :class:`PipelineRegistry` configured with Megaplan defaults.

    Injects the Megaplan-specific scan roots (``megaplan/pipelines/``,
    ``~/.megaplan/pipelines/``), the legacy ``planning`` → ``megaplan``
    alias, and a discovery hook that delegates to this module's
    :func:`scan_python_pipelines` and :func:`discover_python_pipelines`.

    The returned registry uses the Arnold core for storage and query
    operations; Megaplan-specific methods (``operation_registry_for``,
    ``override_catalog_for``, ``read_skill_md``, quota reservation) are
    layered on top by the module-level :class:`PipelineRegistry` bridge.
    """
    from pathlib import Path as _Path

    _scan_roots = (
        _Path(__file__).resolve().parent / "pipelines",
        _Path.home() / ".megaplan" / "pipelines",
    )

    def _discovery_hook(reg: ArnoldPipelineRegistry) -> None:
        """Populate *reg* from Megaplan scan roots."""
        # Use the megaplan-specific discovery logic.
        for name, builder, meta, source_path in discover_python_pipelines():
            name = canonical_pipeline_name(name)
            if name in reg:
                continue
            reg.register(
                name,
                builder,
                description=str(meta.get("description", "") or ""),
                metadata=meta,
                module_file=source_path,
            )

    return ArnoldPipelineRegistry(
        scan_roots=_scan_roots,
        package_prefixes=("arnold_pipelines", "arnold_pipelines.megaplan.pipelines"),
        alias_map=dict(LEGACY_PIPELINE_ALIASES),
        discovery_hook=_discovery_hook,
    )


def _override_catalog_from_module(module: Any) -> dict[str, Any]:
    factory = getattr(module, "override_catalog", None)
    if not callable(factory):
        return {}
    try:
        catalog = factory()
    except Exception:  # noqa: BLE001 - helper must fail closed
        return {}
    if isinstance(catalog, Mapping):
        return dict(catalog)
    return {}


def _reserve_out_of_tree_quota(name: str, module_file: Path, meta: dict[str, Any]) -> None:
    tenant_id = meta.get("tenant_id")
    sub_budget_usd = meta.get("sub_budget_usd")
    if not isinstance(tenant_id, str) or not isinstance(sub_budget_usd, (int, float)):
        return
    from arnold_pipelines.megaplan.runtime.budget_authority import reserve_tenant_quota

    ledger_dir = os.environ.get("MEGAPLAN_BUDGET_AUTHORITY_DIR")
    reserved = reserve_tenant_quota(
        tenant_id,
        float(sub_budget_usd),
        base_dir=Path(ledger_dir) if ledger_dir else None,
        flock=True,
        metadata={"pipeline": name, "source_path": str(module_file)},
    )
    meta["quota_reserved"] = True
    meta["sub_budget_usd"] = reserved.get("sub_budget_usd", sub_budget_usd)


@dataclass
class PipelineRegistry:
    """Map names → builder callables → Pipeline values.

    Builders return a Pipeline; the registry calls them on demand so a
    registered pipeline isn't materialised until requested. This keeps
    import cost flat regardless of how many pipelines exist.

    Discovery of Python-module pipelines runs lazily on first access
    (``get`` / ``names`` / ``describe`` / ``metadata_for`` /
    ``read_skill_md``); programmatic :meth:`register` calls bypass the
    discovery pass and stay available for tests.
    """

    builders: dict[str, PipelineBuilder] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    _discovered: bool = field(default=False, init=False)
    _module_files: dict[str, Path] = field(default_factory=dict, init=False)
    _operation_registries: dict[str, OperationRegistry] = field(default_factory=dict, init=False)
    _override_catalogs: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)

    def register(
        self,
        name: str,
        builder: PipelineBuilder,
        *,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        name = canonical_pipeline_name(name)
        if name in self.builders:
            raise ValueError(f"pipeline {name!r} already registered")
        self.builders[name] = builder
        if description:
            self.descriptions[name] = description
        meta: dict[str, Any] = {}
        if description:
            meta["description"] = description
        if metadata:
            meta.update(metadata)
        if meta:
            self.metadata[name] = meta

    def _ensure_discovered(self) -> None:
        if self._discovered:
            return
        # Set flag first to avoid recursive discovery if a build_pipeline
        # callable transitively imports the registry.
        self._discovered = True

        if _manifest_discovery_enabled():
            # Manifest-first path: consume Dispositions WITHOUT re-importing.
            # Register deferred-import builders so exec_module is gated to
            # PipelineRegistry.get(name) and to the trust-tier check there.
            for d in scan_python_pipelines():
                if d.status != "discovered" or d.cli_name is None or d.manifest is None:
                    continue
                name = canonical_pipeline_name(d.cli_name)
                if name in self.builders:
                    continue
                # Resolve package_prefix for deferred import (same logic as
                # _get_scan_roots): in_tree → derived from path, else None.
                package_prefix = _package_prefix_for_module_file(d.path)
                self.builders[name] = _make_deferred_builder(
                    d.path, package_prefix=package_prefix, cli_name=name,
                )
                meta = _manifest_metadata(name, d)
                if d.origin == "user":
                    _reserve_out_of_tree_quota(name, d.path, meta)
                description = str(meta.get("description", "") or "")
                if description:
                    self.descriptions[name] = description
                self.metadata[name] = meta
                self._module_files[name] = d.path
            return

        # Flag-OFF: legacy quad-list path (re-imports modules eagerly).
        for name, builder, meta, source_path in discover_python_pipelines():
            name = canonical_pipeline_name(name)
            if name in self.builders:
                # Either a duplicate discovered earlier or a programmatic
                # re-register.
                continue
            self.builders[name] = builder
            description = str(meta.get("description", "") or "")
            if description:
                self.descriptions[name] = description
            self.metadata[name] = dict(meta)
            self.metadata[name].setdefault("source_path", str(source_path))
            self._module_files[name] = source_path

    def get(self, name: str) -> Pipeline | None:
        """Return a built Pipeline for *name*.

        Under manifest-first discovery (M6 flag-ON), exec_module is gated
        on the path-derived trust tier: AUTO_EXEC or BLESSED proceed;
        QUARANTINED returns ``None`` and emits a UserWarning rather than
        executing arbitrary out-of-tree code. Built-ins and programmatically
        registered builders are unaffected (they bypass _ensure_discovered's
        deferred-builder path).
        """
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        builder_name = name
        if builder_name not in self.builders:
            for legacy_name, canonical_name in LEGACY_PIPELINE_ALIASES.items():
                if canonical_name == name and legacy_name in self.builders:
                    builder_name = legacy_name
                    break
        if builder_name not in self.builders:
            raise KeyError(
                f"no pipeline named {name!r}; available: {sorted(self.builders)}"
            )
        builder = self.builders[builder_name]
        # Trust-gate only when manifest discovery is on AND this builder
        # came from manifest-first discovery (deferred). Built-ins and
        # programmatic registrations bypass.
        if _manifest_discovery_enabled() and getattr(builder, "_m6_deferred", False):
            module_file = self._module_files.get(builder_name)
            if module_file is not None:
                tier = classify(module_file, blessed_allowlist=BLESSED_ALLOWLIST)
                if tier not in (TrustGrade.AUTO_EXEC, TrustGrade.BLESSED):
                    import warnings
                    warnings.warn(
                        f"pipeline {name!r} at {module_file!s} is QUARANTINED "
                        f"(trust_tier={tier.value}); refusing to exec_module. "
                        f"Promote via BLESSED_ALLOWLIST to enable execution.",
                        UserWarning,
                        stacklevel=2,
                    )
                    return None
                if self.metadata.get(builder_name, {}).get("manifest_origin") == "user":
                    _reserve_out_of_tree_quota(
                        builder_name, module_file, self.metadata[builder_name]
                    )
        return builder()

    def names(self) -> tuple[str, ...]:
        self._ensure_discovered()
        return tuple(sorted(self.builders))

    def describe(self, name: str) -> str:
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        return self.descriptions.get(name, "")

    def metadata_for(self, name: str) -> dict[str, Any]:
        """Return the per-pipeline metadata dict (empty if unknown)."""
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        return dict(self.metadata.get(name, {}))

    def operation_registry_for(self, name: str) -> OperationRegistry:
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        cached = self._operation_registries.get(name)
        if cached is not None:
            return cached
        module_file = self._module_files.get(name)
        registry: OperationRegistry = NullOperationRegistry()
        if module_file is not None:
            module = _load_trusted_pipeline_module(module_file)
            if module is not None:
                registry = _operation_registry_from_module(module)
        self._operation_registries[name] = registry
        supported = _supported_operation_names(registry)
        if supported:
            self.metadata.setdefault(name, {})["supported_operations"] = supported
        return registry

    def supported_operations_for(self, name: str) -> frozenset[OperationKind]:
        registry = self.operation_registry_for(name)
        try:
            supported = registry.supported_operations()
        except Exception:  # noqa: BLE001 - helper must fail closed
            return frozenset()
        return _coerce_supported_operations(supported)

    def override_catalog_for(self, name: str) -> dict[str, Any]:
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        cached = self._override_catalogs.get(name)
        if cached is not None:
            return dict(cached)
        module_file = self._module_files.get(name)
        catalog: dict[str, Any] = {}
        if module_file is not None:
            module = _load_trusted_pipeline_module(module_file)
            if module is not None:
                catalog = _override_catalog_from_module(module)
        self._override_catalogs[name] = dict(catalog)
        return dict(catalog)

    def read_skill_md(self, name: str) -> str | None:
        """Return the SKILL.md contents for *name*, or ``None``.

        Returns ``None`` gracefully when no ``SKILL.md`` exists on
        disk — never raises ``FileNotFoundError`` (callers-2 /
        FLAG-READ-SKILL-MD-USER-PIPELINE).

        Layout:

        * Sibling-file modules → ``<module-parent>/<cli-name>/SKILL.md``
          (e.g. ``megaplan/pipelines/writing-panel-strict/SKILL.md``
          for ``writing_panel_strict.py``).
        * Package modules → ``<module-parent>/SKILL.md``.
        """
        name = canonical_pipeline_name(name)
        self._ensure_discovered()
        module_file = self._module_files.get(name)
        if module_file is None:
            return None
        parent = module_file.parent
        if module_file.name == "__init__.py":
            skill_path = parent / "SKILL.md"
        else:
            skill_path = parent / name / "SKILL.md"
        try:
            return skill_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None


_GLOBAL_REGISTRY = PipelineRegistry()


def _builtin_megaplan_builder() -> Pipeline:
    from arnold_pipelines.megaplan.pipeline import build_pipeline

    return build_pipeline()


def _ensure_builtin_pipelines_registered() -> None:
    """Reassert built-ins after tests or long-lived workers mutate global state."""

    if CANONICAL_BUILTIN_PIPELINE in _GLOBAL_REGISTRY.builders:
        return

    import arnold_pipelines.megaplan as canonical_megaplan
    from arnold_pipelines.megaplan import pipeline as pipeline_entry
    from arnold_pipelines.megaplan.workflows import planning as workflow_planning

    module_file = Path(pipeline_entry.__file__).resolve()
    manifest_file = Path(canonical_megaplan.__file__).resolve()
    description = str(getattr(canonical_megaplan, "description", "") or "")
    metadata = {
        "description": description,
        "name": CANONICAL_BUILTIN_PIPELINE,
        "source_path": str(module_file),
        "authored_source_path": str(workflow_planning.AUTHORING_SOURCE_PATH.resolve()),
        "supported_modes": tuple(getattr(canonical_megaplan, "supported_modes", ()) or ()),
        "capabilities": tuple(getattr(canonical_megaplan, "capabilities", ()) or ()),
        "arnold_api_version": str(getattr(canonical_megaplan, "arnold_api_version", "") or ""),
    }
    default_profile = getattr(canonical_megaplan, "default_profile", None)
    if default_profile:
        metadata["default_profile"] = default_profile
    if _manifest_discovery_enabled():
        manifest_result = read_manifest(manifest_file)
        if isinstance(manifest_result, Manifest):
            from arnold_pipelines.megaplan.runtime.discovery import Disposition

            metadata.update(
                _manifest_metadata(
                    CANONICAL_BUILTIN_PIPELINE,
                    Disposition(
                        path=manifest_file,
                        origin="in_tree",
                        status="discovered",
                        reason="ok (manifest)",
                        cli_name=CANONICAL_BUILTIN_PIPELINE,
                        manifest=manifest_result,
                    ),
                )
            )
            metadata["source_path"] = str(module_file)
            metadata["manifest_source_path"] = str(manifest_file)

    _GLOBAL_REGISTRY.register(
        CANONICAL_BUILTIN_PIPELINE,
        _builtin_megaplan_builder,
        description=description,
        metadata=metadata,
    )
    _GLOBAL_REGISTRY._module_files[CANONICAL_BUILTIN_PIPELINE] = module_file


def register_pipeline(
    name: str,
    builder: PipelineBuilder,
    *,
    description: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _GLOBAL_REGISTRY.register(
        name, builder, description=description, metadata=metadata,
    )


def get_pipeline(name: str) -> Pipeline | None:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.get(name)


def registered_pipelines() -> tuple[str, ...]:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.names()


def describe_pipeline(name: str) -> str:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.describe(name)


def pipeline_metadata(name: str) -> dict[str, Any]:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.metadata_for(name)


def operation_registry_for(name: str) -> OperationRegistry:
    name = canonical_pipeline_name(name)
    _ensure_builtin_pipelines_registered()
    try:
        registry = _GLOBAL_REGISTRY.operation_registry_for(name)
    except RuntimeError:
        if name == CANONICAL_BUILTIN_PIPELINE:
            from arnold_pipelines.megaplan.pipelines.planning import operation_registry

            return operation_registry()
        raise
    if name == CANONICAL_BUILTIN_PIPELINE:
        try:
            supported = registry.supported_operations()
        except Exception:
            supported = frozenset()
        if not _coerce_supported_operations(supported):
            from arnold_pipelines.megaplan.pipelines.planning import operation_registry

            registry = operation_registry()
            _GLOBAL_REGISTRY._operation_registries[name] = registry
    return registry


def supported_operations_for(name: str) -> frozenset[OperationKind]:
    name = canonical_pipeline_name(name)
    _ensure_builtin_pipelines_registered()
    try:
        supported = _GLOBAL_REGISTRY.supported_operations_for(name)
    except RuntimeError:
        if name == CANONICAL_BUILTIN_PIPELINE:
            from arnold_pipelines.megaplan.pipelines.planning import operation_registry

            return operation_registry().supported_operations()
        raise
    if name == CANONICAL_BUILTIN_PIPELINE and not supported:
        from arnold_pipelines.megaplan.pipelines.planning import operation_registry

        registry = operation_registry()
        _GLOBAL_REGISTRY._operation_registries[name] = registry
        return registry.supported_operations()
    return supported


def _unsupported_operation_result(kind: object) -> OperationResult:
    kind_value = kind.value if isinstance(kind, OperationKind) else str(kind)
    return OperationResult(ok=False, payload={}, errors=("unsupported", kind_value))


def dispatch_operation_for(
    plugin_id: str,
    request: OperationRequest,
) -> OperationResult:
    """Dispatch *request* through the canonical plugin operation registry.

    ``planning`` is only accepted as an explicit legacy alias for the
    canonical ``megaplan`` plugin identity. Unsupported operations fail
    closed with the exact neutral unsupported result rather than falling
    back to direct pipeline dispatch.
    """

    plugin_id = canonical_pipeline_name(plugin_id)
    supported = supported_operations_for(plugin_id)
    if request.kind not in supported:
        return _unsupported_operation_result(request.kind)
    payload = request.payload if isinstance(request.payload, Mapping) else {}
    return operation_registry_for(plugin_id).dispatch(
        OperationRequest(kind=request.kind, payload=dict(payload))
    )


def _bridge_payload(result: OperationResult, *, bridge_name: str) -> Mapping[str, Any]:
    payload = result.payload
    if not isinstance(payload, Mapping):
        raise ValueError(f"{bridge_name} requires OperationResult.payload to be a mapping")
    return payload


def _require_payload_key(
    payload: Mapping[str, Any],
    key: str,
    *,
    bridge_name: str,
) -> Any:
    if key not in payload:
        raise ValueError(f"{bridge_name} requires payload.{key}")
    return payload[key]


def _require_payload_str(
    payload: Mapping[str, Any],
    key: str,
    *,
    bridge_name: str,
) -> str:
    value = _require_payload_key(payload, key, bridge_name=bridge_name)
    if not isinstance(value, str):
        raise ValueError(f"{bridge_name} requires payload.{key} to be a string")
    return value


def _require_payload_int(
    payload: Mapping[str, Any],
    key: str,
    *,
    bridge_name: str,
) -> int:
    value = _require_payload_key(payload, key, bridge_name=bridge_name)
    if not isinstance(value, int):
        raise ValueError(f"{bridge_name} requires payload.{key} to be an int")
    return value


def phase_tuple_from_operation_result(result: OperationResult) -> tuple[int, str, str]:
    """Bridge an ``EXECUTE`` result back to the legacy tuple contract."""

    payload = _bridge_payload(result, bridge_name="phase_tuple_from_operation_result")
    return (
        _require_payload_int(
            payload, "exit_code", bridge_name="phase_tuple_from_operation_result"
        ),
        _require_payload_str(
            payload, "stdout", bridge_name="phase_tuple_from_operation_result"
        ),
        _require_payload_str(
            payload, "stderr", bridge_name="phase_tuple_from_operation_result"
        ),
    )


def resume_result_from_operation_result(
    result: OperationResult,
    *,
    plan: str,
    phase: str,
    resume_cursor: Mapping[str, Any],
    state: str | None = None,
) -> dict[str, Any]:
    """Bridge a ``RESUME`` result back to the legacy ``resume_plan()`` shape."""

    payload = dict(
        _bridge_payload(result, bridge_name="resume_result_from_operation_result")
    )
    args = _require_payload_key(
        payload, "args", bridge_name="resume_result_from_operation_result"
    )
    exit_code = _require_payload_int(
        payload, "exit_code", bridge_name="resume_result_from_operation_result"
    )
    stdout = _require_payload_str(
        payload, "stdout", bridge_name="resume_result_from_operation_result"
    )
    stderr = _require_payload_str(
        payload, "stderr", bridge_name="resume_result_from_operation_result"
    )
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError(
            "resume_result_from_operation_result requires payload.args to be a list[str]"
        )

    bridged: dict[str, Any] = {
        "success": result.ok and exit_code == 0,
        "step": "resume",
        "plan": plan,
        "phase": phase,
    }
    if bridged["success"]:
        bridged["command"] = list(args)
        if state is not None:
            bridged["state"] = state
    else:
        bridged["resume_cursor"] = dict(resume_cursor)
        bridged["exit_code"] = exit_code
        bridged["stdout"] = stdout
        bridged["stderr"] = stderr
    for key, value in payload.items():
        bridged.setdefault(key, value)
    return bridged


def control_status_result_from_operation_result(
    result: OperationResult,
    *,
    require_valid_targets: bool = False,
    require_recover_targets: bool = False,
) -> dict[str, Any]:
    """Bridge a ``STATUS_PROJECTION`` result for legacy control/status callers."""

    bridge_name = "control_status_result_from_operation_result"
    if not result.ok:
        raise ValueError(
            f"{bridge_name} requires ok=True, got errors={result.errors!r}"
        )
    payload = dict(_bridge_payload(result, bridge_name=bridge_name))
    _require_payload_key(payload, "binding", bridge_name=bridge_name)
    _require_payload_key(payload, "state_view", bridge_name=bridge_name)
    if require_valid_targets:
        _require_payload_key(payload, "valid_targets", bridge_name=bridge_name)
    if require_recover_targets:
        _require_payload_key(payload, "recover_targets", bridge_name=bridge_name)
    payload.setdefault("valid_targets", ())
    payload.setdefault("recover_targets", ())
    payload.setdefault("diagnostics", ())
    return payload


def override_catalog_for(name: str) -> dict[str, Any]:
    name = canonical_pipeline_name(name)
    _ensure_builtin_pipelines_registered()
    try:
        return _GLOBAL_REGISTRY.override_catalog_for(name)
    except RuntimeError:
        if name == CANONICAL_BUILTIN_PIPELINE:
            from arnold_pipelines.megaplan.pipelines.planning import override_catalog

            return override_catalog()
        raise


def read_pipeline_skill_md(name: str) -> str | None:
    _ensure_builtin_pipelines_registered()
    return _GLOBAL_REGISTRY.read_skill_md(name)
