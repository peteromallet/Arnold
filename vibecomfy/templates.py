from __future__ import annotations

import warnings
from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_input, bind_output, ready_node, ready_workflow
from vibecomfy.workflow import VibeInput, VibeWorkflow
from vibecomfy.custom_node_refs import normalize_custom_node_requirements


_OUTPUT_KIND_HEURISTIC: dict[str, str] = {
    "SaveImage": "image",
    "PreviewImage": "image",
    "SaveVideo": "video",
    "VHS_VideoCombine": "video",
    "CreateVideo": "video",
    "SaveAudio": "audio",
    "SaveAudioMP3": "audio",
    "PreviewAudio": "audio",
}

_MODEL_DISAGREEMENT_WARNED = False


def _category_qualified_template_id(template_id: str, source_path: str | None) -> str:
    if "/" in template_id or not source_path:
        return template_id
    path = Path(source_path)
    if path.parent.name and path.parent.parent.name == "ready_templates":
        return f"{path.parent.name}/{template_id}"
    return template_id


def _derive_output_kind(class_type: str | None) -> str | None:
    if not class_type:
        return None
    if class_type in _OUTPUT_KIND_HEURISTIC:
        return _OUTPUT_KIND_HEURISTIC[class_type]
    lowered = class_type.lower()
    if "video" in lowered:
        return "video"
    if "audio" in lowered:
        return "audio"
    if "image" in lowered:
        return "image"
    return None


def new_workflow(metadata: Mapping[str, Any], *, source_path: str | None = None) -> VibeWorkflow:
    """Create a ready-template workflow and apply module metadata.

    Convenience wrapper for template authoring; for runtime use see
    ``vibecomfy.registry.ready_template``. Generated templates should pass
    ``source_path=__file__`` because the fallback here is this helper module.
    """
    raw_workflow_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    workflow_id = _category_qualified_template_id(raw_workflow_id, source_path)
    metadata = dict(metadata)
    metadata["ready_template"] = workflow_id
    metadata["workflow_template"] = workflow_id.rsplit("/", 1)[-1]
    provenance = metadata.get("provenance")
    wf = ready_workflow(
        workflow_id,
        source_path=source_path or __file__,
        provenance=provenance if isinstance(provenance, Mapping) else None,
    )
    wf.metadata.update(metadata)
    return wf


def node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str | None = None,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a ready-template node.

    Supports both legacy ``node(wf, class_type, source_id, ...)`` and the
    v2.5 id-free ``node(wf, class_type, ...)`` form. When a source id is
    supplied it is preserved as the runtime node id for back-compat.
    """
    explicit_outputs = kwargs.pop("_outputs", None)
    outputs = tuple(explicit_outputs) if explicit_outputs is not None else _normalized_output_names(class_type)
    return ready_node(wf, class_type, source_id=str(_id) if _id is not None else None, outputs=outputs or None, extras=_extras, **kwargs)


def _at(
    wf: VibeWorkflow,
    _id: str,
    class_type: str,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Narrative-form alias of ``node`` with ``_id`` in position 2.

    .. deprecated::
        Prefer ``node(wf, class_type, _id, ...)``.  ``_at`` is retained as a
        compatibility alias for hand-authored templates that use the older
        ``_at(wf, ID["role"], "Class", ...)`` calling convention.  Generated
        ready-templates always use ``node``.

    Semantically identical to ``node(wf, class_type, _id, ...)``.
    """
    return node(wf, class_type, _id, _extras=_extras, **kwargs)


def _normalized_output_names(class_type: str) -> tuple[str, ...]:
    try:
        from vibecomfy.porting.object_info.consume import output_names
    except ImportError:
        return ()
    return tuple(name.strip().replace(" ", "_").upper() for name in output_names(class_type) if name)


@dataclass(frozen=True)
class SymbolicNodeRef:
    """Module-level public-input binding resolved from build() locals."""

    label: str

    def resolve(self, namespace: Mapping[str, Any], wf: VibeWorkflow) -> str:
        value = namespace.get(self.label)
        node_id = _node_id_from_binding(value)
        if node_id is None or node_id not in wf.nodes:
            raise ValueError(
                f"SymbolicNodeRef({self.label!r}) could not be resolved to a node "
                f"in workflow {wf.id!r}"
            )
        wf.metadata.setdefault("id_map", {})[self.label] = node_id
        return node_id


def ref(label: str) -> SymbolicNodeRef:
    return SymbolicNodeRef(label)


def _node_id_from_binding(value: Any) -> str | None:
    node = getattr(value, "node", None)
    if node is not None and hasattr(node, "id"):
        return str(node.id)
    if hasattr(value, "id"):
        return str(value.id)
    if isinstance(value, str):
        return value
    return None


@dataclass(frozen=True)
class InputSpec:
    node: str | SymbolicNodeRef | Any
    field: str
    default: Any
    type: str
    required: bool = False
    aliases: tuple[str, ...] = ()
    description: str | None = None
    media_semantics: str | None = None

    def register(self, wf: VibeWorkflow, name: str, namespace: Mapping[str, Any] | None = None) -> None:
        node_id = self.resolve_node_id(wf, namespace=namespace)
        node = wf.nodes.get(node_id)
        if node is None:
            raise ValueError(
                f"InputSpec.register({name!r}): target node {node_id!r} does not exist "
                f"in workflow {wf.id!r}"
            )
        if self.field in node.inputs:
            value = node.inputs[self.field]
        elif self.field in node.widgets:
            value = node.widgets[self.field]
        else:
            raise ValueError(
                f"InputSpec.register({name!r}): field {self.field!r} not found in "
                f"node {node_id!r} ({node.class_type}) inputs or widgets"
            )
        wf.register_input(
            name,
            node_id,
            self.field,
            value,
            type=self.type,
            default=self.default,
            required=self.required,
            aliases=self.aliases,
            media_semantics=self.media_semantics,
        )
        for alias in self.aliases:
            if alias in wf.inputs:
                continue
            wf.inputs[alias] = VibeInput(
                name=alias,
                node_id=node_id,
                field=self.field,
                value=value,
                type=self.type,
                default=self.default,
                required=self.required,
                aliases=(),
                media_semantics=self.media_semantics,
            )

    def resolve_node_id(self, wf: VibeWorkflow, namespace: Mapping[str, Any] | None = None) -> str:
        if isinstance(self.node, SymbolicNodeRef):
            return self.node.resolve(namespace or {}, wf)
        node_id = _node_id_from_binding(self.node)
        if node_id is None:
            node_id = str(self.node)
        return node_id


@dataclass(frozen=True)
class ModelAsset:
    filename: str
    url: str
    subdir: str
    target_path: str | None = None
    sha256: str | None = None
    hf_revision: str | None = None
    size_bytes: int | None = None


class ReadyMetadata:
    @classmethod
    def build(
        cls,
        *,
        template_id: str,
        capability: str,
        inputs: dict[str, InputSpec],
        models: dict[str, ModelAsset],
        output_prefix: str,
        edit_guide_extra: str | None = None,
        requirements: Mapping[str, Any] | None = None,
        **extras: Any,
    ) -> dict[str, Any]:
        model_assets = [
            _model_asset_metadata(model)
            for model in models.values()
        ]
        derived_requirements = _requirements_with_models(requirements, model_assets)
        metadata: dict[str, Any] = {
            "ready_template": template_id,
            "workflow_template": template_id.rsplit("/", 1)[-1],
            "capability": capability,
            "output_prefix": output_prefix,
            "unbound_inputs": {
                name: spec.default
                for name, spec in inputs.items()
            },
            "model_assets": model_assets,
            "edit_guide": _derive_edit_guide(inputs, edit_guide_extra),
            "requirements": derived_requirements,
        }
        provenance = extras.get("provenance")
        if isinstance(provenance, Mapping):
            metadata.update({
                key: value
                for key, value in provenance.items()
                if key not in metadata
            })
        metadata.update({
            key: value
            for key, value in extras.items()
            if value is not None
        })
        return metadata


def finalize(
    wf: VibeWorkflow,
    inputs: dict[str, InputSpec],
    metadata: dict[str, Any],
    *,
    output_node: str,
    output_kind: str | None = None,
    **bind_kwargs: Any,
) -> VibeWorkflow:
    """Finalize ready-template metadata, public inputs, and output binding.

    When ``output_kind`` is omitted, it is inferred best-effort from the
    explicit ``output_node`` class type, then from ``output_type`` if present.
    The output node itself stays explicit; this helper never graph-walks to
    choose which node should be returned.
    """
    source_path = bind_kwargs.pop("source_path", None)
    requirements = bind_kwargs.pop("requirements", None)
    if source_path is None:
        source_path = wf.source.path or str(Path.cwd())

    # Merge metadata['requirements'] custom_nodes into explicit requirements.
    meta_reqs = metadata.get("requirements")
    if isinstance(meta_reqs, dict) and (meta_reqs.get("custom_nodes") or meta_reqs.get("custom_node_refs")):
        meta_normalized, _warnings = normalize_custom_node_requirements(meta_reqs)
        meta_custom = list(meta_normalized["custom_nodes"])
        if requirements is None:
            requirements = {}
        existing_custom = list(requirements.get("custom_nodes") or [])
        requirements["custom_nodes"] = sorted(set(existing_custom + meta_custom))
        if meta_normalized.get("custom_node_refs"):
            existing_refs = list(requirements.get("custom_node_refs") or [])
            requirements["custom_node_refs"] = [*existing_refs, *meta_normalized["custom_node_refs"]]

    # Fall back to metadata output_prefix when filename_prefix not provided.
    if "filename_prefix" not in bind_kwargs:
        output_prefix_fallback = metadata.get("output_prefix")
        if output_prefix_fallback is not None:
            bind_kwargs["filename_prefix"] = output_prefix_fallback

    output_class_type = wf.nodes.get(str(output_node)).class_type if str(output_node) in wf.nodes else None
    derived_output_kind = output_kind or _derive_output_kind(output_class_type)
    if derived_output_kind is None:
        derived_output_kind = _derive_output_kind(str(bind_kwargs.get("output_type") or ""))

    requirements = _requirements_with_models(requirements, metadata.get("model_assets", []))
    caller_locals = _caller_build_locals()

    wf.finalize_metadata()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        apply_ready_template_policy(wf, metadata, source_path=str(source_path), requirements=requirements)

    for name, spec in inputs.items():
        spec.register(wf, name, namespace=caller_locals)

    _assert_public_input_invariant(wf, inputs, namespace=caller_locals)

    artifact_kind = bind_kwargs.pop("artifact_kind", None) or derived_output_kind
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_output(
            wf,
            str(output_node),
            artifact_kind=artifact_kind,
            **bind_kwargs,
        )
    return wf


def _caller_build_locals() -> Mapping[str, Any]:
    frame = inspect.currentframe()
    try:
        cursor = frame.f_back if frame is not None else None
        while cursor is not None:
            if cursor.f_code.co_name == "build":
                return dict(cursor.f_locals)
            cursor = cursor.f_back
        return {}
    finally:
        del frame


def finalize_ready(
    wf: VibeWorkflow,
    metadata: Mapping[str, Any],
    *,
    source_path: str,
    requirements: Mapping[str, Any] | None = None,
) -> VibeWorkflow:
    """Finalize a hand-authored ready template without exposing legacy helpers."""
    wf.finalize_metadata()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        apply_ready_template_policy(wf, metadata, source_path=source_path, requirements=requirements)
    return wf


def template_input(wf: VibeWorkflow, name: str, node_id: str, field: str, *args: Any, **kwargs: Any) -> None:
    """Bind a public input from a hand-authored ready template."""
    if args:
        if len(args) > 1 or "default" in kwargs:
            raise TypeError("template_input accepts at most one positional default")
        kwargs["default"] = args[0]
    node = wf.nodes.get(str(node_id))
    if field == "widget_0" and node is not None and field not in node.inputs and field not in node.widgets:
        if "value" in node.inputs or "value" in node.widgets:
            field = "value"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_input(wf, name, node_id, field, **kwargs)


def template_output(wf: VibeWorkflow, node_id: str, **kwargs: Any) -> None:
    """Bind a public output from a hand-authored ready template."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_output(wf, node_id, **kwargs)


def _derive_edit_guide(inputs: Mapping[str, InputSpec], extra: str | None = None) -> str:
    if not inputs and not extra:
        return ""
    lines = ["Public inputs:"]
    for name, spec in inputs.items():
        description = spec.description or f"Controls {name}."
        lines.append(f"- {name}: {description}")
    if extra:
        lines.append(str(extra))
    return "\n".join(lines)


def _requirements_with_models(
    requirements: Mapping[str, Any] | None,
    model_assets: Any,
) -> dict[str, Any]:
    derived_models = [
        dict(asset)
        for asset in model_assets
        if isinstance(asset, Mapping)
    ]
    merged: dict[str, Any] = dict(requirements or {})
    merged, _warnings = normalize_custom_node_requirements(merged)
    existing_models = merged.get("models")
    if existing_models:
        _warn_on_model_requirement_disagreement(existing_models, derived_models)
    elif derived_models:
        merged["models"] = derived_models
    return merged


def _model_requirement_names(models: Any) -> set[str]:
    names: set[str] = set()
    for model in models or []:
        if isinstance(model, Mapping):
            name = model.get("name")
        else:
            name = model
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _warn_on_model_requirement_disagreement(existing_models: Any, derived_models: list[dict[str, Any]]) -> None:
    global _MODEL_DISAGREEMENT_WARNED
    if _MODEL_DISAGREEMENT_WARNED:
        return
    existing_names = _model_requirement_names(existing_models)
    derived_names = _model_requirement_names(derived_models)
    if existing_names != derived_names:
        warnings.warn(
            "ReadyMetadata.build requirements['models'] differs from MODELS-derived model assets",
            stacklevel=3,
        )
        _MODEL_DISAGREEMENT_WARNED = True


def _model_asset_metadata(model: ModelAsset) -> dict[str, str]:
    data: dict[str, Any] = {
        "name": model.filename,
        "url": model.url,
        "subdir": model.subdir,
    }
    if model.target_path is not None:
        data["target_path"] = model.target_path
    if model.sha256 is not None:
        data["sha256"] = model.sha256
    if model.hf_revision is not None:
        data["hf_revision"] = model.hf_revision
    if model.size_bytes is not None:
        data["size_bytes"] = model.size_bytes
    return data


def _assert_public_input_invariant(
    wf: VibeWorkflow,
    inputs: Mapping[str, InputSpec],
    namespace: Mapping[str, Any] | None = None,
) -> None:
    specs = {
        name: (spec.resolve_node_id(wf, namespace=namespace), spec.field)
        for name, spec in inputs.items()
    }
    alias_names = {
        str(alias)
        for spec in inputs.values()
        for alias in spec.aliases
    }
    for name, (node_id, field) in specs.items():
        registered = wf.inputs.get(name)
        if registered is None:
            raise AssertionError(f"public input {name!r} was not registered")
        if (str(registered.node_id), registered.field) != (node_id, field):
            raise AssertionError(
                f"public input {name!r} target drift: "
                f"expected {node_id}.{field}, got {registered.node_id}.{registered.field}"
            )

    unexpected = {
            name
            for name, registered in wf.inputs.items()
            if name not in specs
            and name not in alias_names
            and (str(registered.node_id), registered.field) in set(specs.values())
        }
    if unexpected:
        raise AssertionError(
            "registered inputs target PUBLIC_INPUTS nodes but are not declared: "
            + ", ".join(sorted(unexpected))
        )


__all__ = [
    "InputSpec",
    "ModelAsset",
    "ReadyMetadata",
    "_at",
    "_derive_output_kind",
    "finalize",
    "finalize_ready",
    "new_workflow",
    "node",
    "template_input",
    "template_output",
]
