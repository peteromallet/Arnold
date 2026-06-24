"""Static behavioral identity projection for pipeline modules.

This module intentionally mirrors the manifest-first discovery constraint:
pipeline modules are parsed, never imported.  The projection is therefore a
static source identity, not runtime topology.  Trusted callers that need
runtime topology should build that as a separate projection after explicitly
allowing imports.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold.pipeline.discovery.manifest import (
    Manifest,
    ManifestError,
    read_manifest,
)
from arnold.pipelines.megaplan._pipeline import registry as _registry


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StaticBehavioralInput:
    """A file or literal input included in static behavioral identity."""

    role: str
    logical_path: str
    sha256: str


@dataclass(frozen=True)
class UnresolvedDynamicInput:
    """A source expression that could not be resolved without importing."""

    role: str
    location: str
    detail: str


@dataclass(frozen=True)
class StaticBehavioralManifest:
    """No-import, canonical static source identity for a pipeline."""

    schema_version: int
    pipeline_name: str
    source_path: Path
    manifest_hash: str
    arnold_api_version: str
    driver: object
    entrypoint: str
    capabilities: tuple[str, ...]
    files: tuple[StaticBehavioralInput, ...]
    declared_inputs: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    unresolved_dynamic_inputs: tuple[UnresolvedDynamicInput, ...] = field(default_factory=tuple)
    canonical_bytes: bytes = b""
    static_behavioral_hash: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "projection": "megaplan.static-behavioral-manifest",
            "pipeline_name": self.pipeline_name,
            "manifest_hash": self.manifest_hash,
            "arnold_api_version": self.arnold_api_version,
            "driver": self.driver,
            "entrypoint": self.entrypoint,
            "capabilities": list(self.capabilities),
            "files": [
                {
                    "role": item.role,
                    "logical_path": item.logical_path,
                    "sha256": item.sha256,
                }
                for item in self.files
            ],
            "declared_inputs": [dict(item) for item in self.declared_inputs],
            "unresolved_dynamic_inputs": [
                {
                    "role": item.role,
                    "location": item.location,
                    "detail": item.detail,
                }
                for item in self.unresolved_dynamic_inputs
            ],
        }


class StaticBehavioralManifestError(ValueError):
    """Raised when the static behavioral projection cannot be built."""


class RuntimeTopologyProjectionError(ValueError):
    """Raised when runtime topology projection is not explicitly trusted."""


@dataclass(frozen=True)
class RuntimeTopologyProjection:
    """Canonical topology projection built from an already-trusted Pipeline."""

    schema_version: int
    pipeline_name: str | None
    entry: str
    stages: tuple[Mapping[str, object], ...]
    edges: tuple[Mapping[str, object], ...]
    ports: Mapping[str, object]
    binding_map: tuple[Mapping[str, object], ...]
    canonical_bytes: bytes = b""
    runtime_topology_hash: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "projection": "megaplan.runtime-topology",
            "pipeline_name": self.pipeline_name,
            "entry": self.entry,
            "stages": [dict(stage) for stage in self.stages],
            "edges": [dict(edge) for edge in self.edges],
            "ports": self.ports,
            "binding_map": [dict(item) for item in self.binding_map],
        }


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Return stable JSON bytes for identity projections."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def static_behavioral_manifest_for_pipeline(
    name_or_pipeline: str | Path,
    *,
    source_path: Path | None = None,
) -> StaticBehavioralManifest:
    """Build a no-import behavioral source identity for a pipeline module.

    ``name_or_pipeline`` may be a registry CLI name or a module path.  Passing
    ``source_path`` avoids registry scanning and is preferred for tests.  This
    helper never calls ``exec_module`` and never calls a pipeline builder.
    """

    module_file = _resolve_source_path(name_or_pipeline, source_path=source_path)
    manifest = read_manifest(module_file)
    if isinstance(manifest, ManifestError):
        raise StaticBehavioralManifestError(
            f"cannot build static behavioral manifest for {module_file}: {manifest.reason}"
        )

    projection = _build_static_projection(manifest)
    payload = projection.as_dict()
    canonical = canonical_json_bytes(payload)
    digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return StaticBehavioralManifest(
        schema_version=projection.schema_version,
        pipeline_name=projection.pipeline_name,
        source_path=projection.source_path,
        manifest_hash=projection.manifest_hash,
        arnold_api_version=projection.arnold_api_version,
        driver=projection.driver,
        entrypoint=projection.entrypoint,
        capabilities=projection.capabilities,
        files=projection.files,
        declared_inputs=projection.declared_inputs,
        unresolved_dynamic_inputs=projection.unresolved_dynamic_inputs,
        canonical_bytes=canonical,
        static_behavioral_hash=digest,
    )


def runtime_topology_projection_for_pipeline(
    pipeline_or_name: Any,
    *,
    allow_import: bool = False,
) -> RuntimeTopologyProjection:
    """Build a trusted runtime topology projection.

    Passing a pipeline object is already explicit trust: the caller built or
    obtained it.  Passing a name would require importing and executing pipeline
    module code through the registry, so that path refuses unless
    ``allow_import=True`` is set by the caller.
    """

    pipeline_name: str | None = None
    if isinstance(pipeline_or_name, str):
        pipeline_name = pipeline_or_name
        if not allow_import:
            raise RuntimeTopologyProjectionError(
                "name-based runtime topology projection requires allow_import=True"
            )
        pipeline = _registry.get_pipeline(pipeline_or_name)
        if pipeline is None:
            raise RuntimeTopologyProjectionError(
                f"pipeline {pipeline_or_name!r} could not be built"
            )
    else:
        pipeline = pipeline_or_name

    projection = _build_runtime_topology_projection(
        pipeline,
        pipeline_name=pipeline_name,
    )
    payload = projection.as_dict()
    canonical = canonical_json_bytes(payload)
    digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return RuntimeTopologyProjection(
        schema_version=projection.schema_version,
        pipeline_name=projection.pipeline_name,
        entry=projection.entry,
        stages=projection.stages,
        edges=projection.edges,
        ports=projection.ports,
        binding_map=projection.binding_map,
        canonical_bytes=canonical,
        runtime_topology_hash=digest,
    )


def capsule_definition_identity_projection(
    *,
    static_behavioral_hash: str,
    runtime_topology_hash: str | None = None,
) -> dict[str, object]:
    """Return the canonical Capsule Definition identity inputs.

    Runtime topology is intentionally additive.  Static-only definitions keep
    the static source identity but are marked non-replay-ready until a trusted
    runtime topology hash is available.
    """

    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "projection": "megaplan.capsule-definition-identity",
        "static_behavioral_hash": static_behavioral_hash,
        "runtime_topology_hash": runtime_topology_hash,
        "identity_mode": "static+runtime-topology"
        if runtime_topology_hash
        else "static-only",
        "replay_ready": bool(runtime_topology_hash),
    }
    canonical = canonical_json_bytes(payload)
    return {
        **payload,
        "canonical_bytes": canonical,
        "definition_identity_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }


def _resolve_source_path(name_or_pipeline: str | Path, *, source_path: Path | None) -> Path:
    if source_path is not None:
        return Path(source_path)
    candidate = Path(name_or_pipeline)
    if candidate.suffix == ".py" or candidate.name == "__init__.py":
        return candidate

    wanted = str(name_or_pipeline)
    for root, package_prefix in _registry._get_scan_roots():
        for cli_name, module_file in _registry._scan_dir_for_pipeline_modules(
            root,
            package_prefix=package_prefix,
        ):
            if cli_name == wanted:
                return module_file
    raise StaticBehavioralManifestError(f"no pipeline source found for {wanted!r}")


def _build_runtime_topology_projection(
    pipeline: Any,
    *,
    pipeline_name: str | None,
) -> RuntimeTopologyProjection:
    stages: list[Mapping[str, object]] = []
    edges: list[Mapping[str, object]] = []
    stage_ports: dict[str, dict[str, object]] = {}

    for stage_name, stage in sorted(pipeline.stages.items()):
        # Duck-type parallel vs single-step stages so the projection works
        # for both neutral (arnold.pipeline) and legacy megaplan stages.
        is_parallel = hasattr(stage, "steps") and hasattr(stage, "join")
        is_single = hasattr(stage, "step")
        stage_kind = "parallel" if is_parallel else "stage"
        step_entries: list[Mapping[str, object]]
        if is_parallel:
            step_entries = [_step_projection(step) for step in stage.steps]  # type: ignore[attr-defined]
            join = _callable_name(stage.join)  # type: ignore[attr-defined]
            max_workers = getattr(stage, "max_workers", None)
        elif is_single:
            step_entries = [_step_projection(stage.step)]  # type: ignore[attr-defined]
            join = None
            max_workers = None
        else:
            step_entries = []
            join = None
            max_workers = None

        stages.append(
            {
                "name": stage_name,
                "stage_name": getattr(stage, "name", stage_name),
                "kind": stage_kind,
                "steps": step_entries,
                "join": join,
                "max_workers": max_workers,
            }
        )
        stage_ports[stage_name] = {
            "produces": [_port_projection(port) for port in getattr(stage, "produces", ())],
            "consumes": [_port_ref_projection(ref) for ref in getattr(stage, "consumes", ())],
        }
        for edge in getattr(stage, "edges", ()) or ():
            edges.append(
                {
                    "source": stage_name,
                    "label": edge.label,
                    "target": edge.target,
                    "kind": edge.kind,
                    "recommendation": edge.recommendation,
                }
            )

    return RuntimeTopologyProjection(
        schema_version=SCHEMA_VERSION,
        pipeline_name=pipeline_name,
        entry=pipeline.entry,
        stages=tuple(stages),
        edges=tuple(
            sorted(
                edges,
                key=lambda item: tuple(
                    str(item.get(k)) for k in ("source", "label", "target", "kind")
                ),
            )
        ),
        ports=stage_ports,
        binding_map=_binding_map_projection(pipeline.binding_map),
    )


def _step_projection(step: object) -> Mapping[str, object]:
    return {
        "class": f"{type(step).__module__}.{type(step).__qualname__}",
        "name": getattr(step, "name", None),
        "kind": getattr(step, "kind", None),
        "prompt_key": getattr(step, "prompt_key", None),
        "slot": getattr(step, "slot", None),
        "produces": [_port_projection(port) for port in getattr(step, "produces", ())],
        "consumes": [_port_ref_projection(ref) for ref in getattr(step, "consumes", ())],
    }


def _port_projection(port: object) -> Mapping[str, object]:
    return {
        "name": getattr(port, "name", None),
        "content_type": getattr(port, "content_type", None),
        "taint": sorted(str(item) for item in (getattr(port, "taint", ()) or ())),
    }


def _port_ref_projection(ref: object) -> Mapping[str, object]:
    return {
        "port_name": getattr(ref, "port_name", None),
        "content_type": getattr(ref, "content_type", None),
    }


def _binding_map_projection(binding_map: Any) -> tuple[Mapping[str, object], ...]:
    if not binding_map:
        return ()
    rows: list[Mapping[str, object]] = []
    for key, value in binding_map.items():
        stage_name, port_name = key
        source_stage, source_port = value
        rows.append(
            {
                "stage": stage_name,
                "port": port_name,
                "source_stage": source_stage,
                "source_port": source_port,
            }
        )
    return tuple(
        sorted(rows, key=lambda item: tuple(str(item.get(k)) for k in ("stage", "port")))
    )


def _callable_name(value: object) -> str:
    return f"{getattr(value, '__module__', '')}.{getattr(value, '__qualname__', repr(value))}"


def _build_static_projection(manifest: Manifest) -> StaticBehavioralManifest:
    source_path = manifest.path
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    skill_path = _skill_path_for(source_path)

    resolver = _StaticResolver(source_path)
    resolver.visit(tree)

    file_inputs: dict[tuple[str, str], StaticBehavioralInput] = {}
    _add_file_input(
        file_inputs,
        role="pipeline_source",
        path=source_path,
        logical_path=_logical_path(source_path, source_path),
    )
    _add_file_input(
        file_inputs,
        role="skill",
        path=skill_path,
        logical_path=_logical_path(skill_path, source_path),
    )

    for helper_path in resolver.helper_paths:
        _add_file_input(
            file_inputs,
            role="helper",
            path=helper_path,
            logical_path=_logical_path(helper_path, source_path),
        )
    for resource_path in resolver.resource_paths:
        _add_file_input(
            file_inputs,
            role="resource",
            path=resource_path,
            logical_path=_logical_path(resource_path, source_path),
        )

    return StaticBehavioralManifest(
        schema_version=SCHEMA_VERSION,
        pipeline_name=manifest.name,
        source_path=source_path,
        manifest_hash=manifest.manifest_hash,
        arnold_api_version=manifest.arnold_api_version,
        driver=manifest.driver,
        entrypoint=manifest.entrypoint,
        capabilities=manifest.capabilities,
        files=tuple(
            sorted(
                file_inputs.values(),
                key=lambda item: (item.role, item.logical_path),
            )
        ),
        declared_inputs=tuple(
            sorted(resolver.declared_inputs, key=lambda item: str(item.get("name", "")))
        ),
        unresolved_dynamic_inputs=tuple(
            sorted(
                resolver.unresolved,
                key=lambda item: (item.role, item.location, item.detail),
            )
        ),
    )


def _add_file_input(
    out: dict[tuple[str, str], StaticBehavioralInput],
    *,
    role: str,
    path: Path,
    logical_path: str,
) -> None:
    if not path.is_file():
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    out[(role, logical_path)] = StaticBehavioralInput(
        role=role,
        logical_path=logical_path,
        sha256=digest,
    )


def _skill_path_for(module_file: Path) -> Path:
    if module_file.name == "__init__.py":
        return module_file.parent / "SKILL.md"
    resource_dir_skill = module_file.parent / module_file.stem.replace("_", "-") / "SKILL.md"
    if resource_dir_skill.is_file():
        return resource_dir_skill
    return module_file.parent / "SKILL.md"


def _logical_path(path: Path, module_file: Path) -> str:
    path = path.resolve()
    module_file = module_file.resolve()
    root = module_file.parent if module_file.name == "__init__.py" else module_file.parent
    if module_file.name != "__init__.py":
        resource_root = module_file.parent / module_file.stem.replace("_", "-")
        try:
            return path.relative_to(resource_root.resolve()).as_posix()
        except ValueError:
            pass
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


class _StaticResolver(ast.NodeVisitor):
    """Best-effort AST resolver for files and literals used by builders."""

    def __init__(self, module_file: Path) -> None:
        self.module_file = module_file
        self.env: dict[str, object] = {"__file__": module_file}
        self.helper_paths: set[Path] = set()
        self.resource_paths: set[Path] = set()
        self.declared_inputs: list[dict[str, object]] = []
        self.unresolved: list[UnresolvedDynamicInput] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for path in _resolve_imported_module_paths(node, self.module_file):
            if path != self.module_file and path.is_file():
                self.helper_paths.add(path)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        value = self._eval(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name) and value is not _UNRESOLVED:
                self.env[target.id] = value
                if isinstance(value, Path):
                    self._record_path_if_file(value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and isinstance(node.target, ast.Name):
            value = self._eval(node.value)
            if value is not _UNRESOLVED:
                self.env[node.target.id] = value
                if isinstance(value, Path):
                    self._record_path_if_file(value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
        if attr == "input":
            self._record_builder_input(node)
        elif attr in {"agent", "panel"}:
            self._record_step_call_inputs(node, role=f"{attr}_inputs")
        for resource in self._resource_paths_from_call(node):
            self.resource_paths.add(resource)
        self.generic_visit(node)

    def _record_builder_input(self, node: ast.Call) -> None:
        if not node.args:
            self._unresolved("declared_input", node, "missing literal input name")
            return
        name = self._eval(node.args[0])
        if not isinstance(name, str):
            self._unresolved("declared_input", node, "input name is dynamic")
            return
        file_value: object = False
        for kw in node.keywords:
            if kw.arg == "file":
                file_value = self._eval(kw.value)
        self.declared_inputs.append({"name": name, "file": bool(file_value)})

    def _record_step_call_inputs(self, node: ast.Call, *, role: str) -> None:
        for kw in node.keywords:
            if kw.arg != "inputs":
                continue
            refs = self._eval(kw.value)
            if isinstance(refs, (list, tuple)) and all(isinstance(ref, str) for ref in refs):
                self.declared_inputs.append(
                    {
                        "name": f"{role}@{self._location(node)}",
                        "refs": list(refs),
                    }
                )
                return
            self._unresolved(role, kw.value, "inputs argument is dynamic")

    def _resource_paths_from_call(self, node: ast.Call) -> Iterable[Path]:
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
        if attr not in {"agent", "panel"}:
            return ()
        paths: list[Path] = []
        for kw in node.keywords:
            if kw.arg == "prompt":
                value = self._eval(kw.value)
                if isinstance(value, str):
                    path = Path(value)
                    if path.is_file():
                        paths.append(path)
                else:
                    self._unresolved("resource", kw.value, "prompt path is dynamic")
            if kw.arg == "reviewers":
                reviewers = self._eval(kw.value)
                if isinstance(reviewers, (list, tuple)):
                    for item in reviewers:
                        if (
                            isinstance(item, (list, tuple))
                            and len(item) >= 2
                            and isinstance(item[1], str)
                        ):
                            path = Path(item[1])
                            if path.is_file():
                                paths.append(path)
                        else:
                            self._unresolved("resource", kw.value, "reviewer prompt is dynamic")
                else:
                    self._unresolved("resource", kw.value, "reviewers argument is dynamic")
        return paths

    def _record_path_if_file(self, value: Path) -> None:
        if value.is_file() and value != self.module_file:
            self.resource_paths.add(value)

    def _eval(self, node: ast.AST) -> object:
        try:
            return ast.literal_eval(node)
        except (ValueError, SyntaxError):
            pass

        if isinstance(node, ast.Name):
            return self.env.get(node.id, _UNRESOLVED)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Call):
            return self._eval_call(node)
        if isinstance(node, ast.Attribute):
            base = self._eval(node.value)
            if isinstance(base, Path) and node.attr == "parent":
                return base.parent
            if isinstance(base, Path) and node.attr == "name":
                return base.name
            if isinstance(base, Path) and node.attr == "stem":
                return base.stem
            return _UNRESOLVED
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = self._eval(node.left)
            right = self._eval(node.right)
            if isinstance(left, Path) and isinstance(right, str):
                return left / right
            if isinstance(left, Path) and isinstance(right, Path):
                return left / right
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [self._eval(elt) for elt in node.elts]
            if any(value is _UNRESOLVED for value in values):
                return _UNRESOLVED
            return values if isinstance(node, ast.List) else tuple(values)
        return _UNRESOLVED

    def _eval_call(self, node: ast.Call) -> object:
        if isinstance(node.func, ast.Name) and node.func.id == "Path":
            if len(node.args) == 1:
                value = self._eval(node.args[0])
                if isinstance(value, (str, Path)):
                    return Path(value)
            return _UNRESOLVED
        if isinstance(node.func, ast.Name) and node.func.id == "str" and len(node.args) == 1:
            value = self._eval(node.args[0])
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, str):
                return value
            return _UNRESOLVED
        return _UNRESOLVED

    def _unresolved(self, role: str, node: ast.AST, detail: str) -> None:
        self.unresolved.append(
            UnresolvedDynamicInput(
                role=role,
                location=self._location(node),
                detail=detail,
            )
        )

    def _location(self, node: ast.AST) -> str:
        return f"{self.module_file.name}:{getattr(node, 'lineno', '?')}"


class _Unresolved:
    pass


_UNRESOLVED = _Unresolved()


def _resolve_imported_module_paths(node: ast.ImportFrom, module_file: Path) -> tuple[Path, ...]:
    module = node.module or ""
    if node.level > 0:
        base = module_file.parent
        for _ in range(max(0, node.level - 1)):
            base = base.parent
        parts = module.split(".") if module else []
        module_base = base.joinpath(*parts)
    elif module.startswith("arnold.pipelines.megaplan.pipelines."):
        root = _repo_root(module_file)
        module_base = root.joinpath(*module.split("."))
    else:
        return ()

    candidates: list[Path] = []
    if module_base.with_suffix(".py").is_file():
        candidates.append(module_base.with_suffix(".py"))
    if (module_base / "__init__.py").is_file():
        candidates.append(module_base / "__init__.py")
    for alias in node.names:
        child = module_base / f"{alias.name}.py"
        if child.is_file():
            candidates.append(child)
    return tuple(dict.fromkeys(candidates))


def _repo_root(path: Path) -> Path:
    for parent in (path.resolve(), *path.resolve().parents):
        if (parent / "megaplan").is_dir():
            return parent
    return Path.cwd()


__all__ = [
    "StaticBehavioralInput",
    "StaticBehavioralManifest",
    "StaticBehavioralManifestError",
    "RuntimeTopologyProjection",
    "RuntimeTopologyProjectionError",
    "UnresolvedDynamicInput",
    "capsule_definition_identity_projection",
    "canonical_json_bytes",
    "runtime_topology_projection_for_pipeline",
    "static_behavioral_manifest_for_pipeline",
]
