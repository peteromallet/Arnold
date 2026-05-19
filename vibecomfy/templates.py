from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_output, ready_node, ready_workflow
from vibecomfy.workflow import VibeWorkflow


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
    workflow_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    provenance = metadata.get("provenance")
    wf = ready_workflow(
        workflow_id,
        source_path=source_path or __file__,
        provenance=provenance if isinstance(provenance, Mapping) else None,
    )
    wf.metadata.update(dict(metadata))
    return wf


def node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a ready-template node while preserving the source graph id.

    Convenience wrapper for template authoring; it delegates to
    ``vibecomfy.registry.ready_template.ready_node`` to keep id-rewrite and
    edge-rewrite behavior centralized.
    """
    outputs = _normalized_output_names(class_type)
    return ready_node(wf, class_type, source_id=str(_id), outputs=outputs or None, extras=_extras, **kwargs)


def _at(
    wf: VibeWorkflow,
    _id: str,
    class_type: str,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Narrative-form alias of ``node`` with ``_id`` in position 2.

    Generated ready templates call ``_at(wf, ID["role"], "Class", ...)`` so the
    role/id sits visually adjacent to ``wf`` in every line. Semantically
    identical to ``node(wf, class_type, _id, ...)``.
    """
    return node(wf, class_type, _id, _extras=_extras, **kwargs)


def _normalized_output_names(class_type: str) -> tuple[str, ...]:
    try:
        from vibecomfy.porting.object_info.consume import output_names
    except ImportError:
        return ()
    return tuple(name.strip().replace(" ", "_").upper() for name in output_names(class_type) if name)


@dataclass(frozen=True)
class InputSpec:
    node: str
    field: str
    default: Any
    type: str
    required: bool = False
    aliases: tuple[str, ...] = ()
    description: str | None = None
    media_semantics: str | None = None

    def register(self, wf: VibeWorkflow, name: str) -> None:
        node_id = str(self.node)
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


@dataclass(frozen=True)
class ModelAsset:
    filename: str
    url: str
    subdir: str
    target_path: str | None = None


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

    output_class_type = wf.nodes.get(str(output_node)).class_type if str(output_node) in wf.nodes else None
    derived_output_kind = output_kind or _derive_output_kind(output_class_type)
    if derived_output_kind is None:
        derived_output_kind = _derive_output_kind(str(bind_kwargs.get("output_type") or ""))

    requirements = _requirements_with_models(requirements, metadata.get("model_assets", []))

    wf.finalize_metadata()
    apply_ready_template_policy(wf, metadata, source_path=str(source_path), requirements=requirements)

    for name, spec in inputs.items():
        spec.register(wf, name)

    _assert_public_input_invariant(wf, inputs)

    artifact_kind = bind_kwargs.pop("artifact_kind", None) or derived_output_kind
    bind_output(
        wf,
        str(output_node),
        artifact_kind=artifact_kind,
        **bind_kwargs,
    )
    return wf


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
    data = {
        "name": model.filename,
        "url": model.url,
        "subdir": model.subdir,
    }
    if model.target_path is not None:
        data["target_path"] = model.target_path
    return data


def _assert_public_input_invariant(wf: VibeWorkflow, inputs: Mapping[str, InputSpec]) -> None:
    specs = {
        name: (str(spec.node), spec.field)
        for name, spec in inputs.items()
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
    "_derive_output_kind",
    "finalize",
    "new_workflow",
    "node",
]
