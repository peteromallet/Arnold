from __future__ import annotations

import ast
import importlib
import json
import keyword
import pprint
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.porting.widget_aliases import resolve_widget_name
from vibecomfy.porting.object_info import class_defaults, class_has_list_output, class_output_count
from vibecomfy.porting.object_info import output_names as class_output_names
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

# -- readability warning codes ------------------------------------------------
READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT = "avoidable_positional_output"
READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY = "output_name_ambiguity"
READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED = "schema_backed_widget_alias_not_resolved"
READABILITY_WARNING_HIDDEN_MODEL_FILENAME = "hidden_model_filename"
READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE = "local_helper_copy_in_strict_template"
READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL = "long_one_line_node_call"
READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED = "generated_template_not_formatted"
READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG = "generated_variable_name_too_long"

READABILITY_WARNING_CODES: frozenset[str] = frozenset(
    {
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
        READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
        READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
        READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
        READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
        READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    }
)

EmissionSeverity = Literal["error", "warning", "info"]


@dataclass(slots=True)
class EmissionDiagnostic:
    """A readability diagnostic recorded during emission.

    These are always *warnings* (or info) - hard errors are surfaced through
    `PortConvertValidation` parity / schema failures, not here.
    """

    code: str
    message: str
    severity: EmissionSeverity = "warning"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _PublicInputBinding:
    name: str
    node_id: str
    field: str
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    media_semantics: str | None = None


@dataclass(frozen=True, slots=True)
class _PublicInputSpec:
    name: str
    node_ref: str
    field: str
    default_expr: str
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    media_semantics: str | None = None


GENERATED_HEADER = (
    "# vibecomfy: generated - converted by tools/convert_ready_templates.py\n"
    "# Edits will be overwritten on regeneration. Put the manual opt-out\n"
    "# marker on the first line if hand-editing is required.\n"
)

UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})
FALLBACK_CLASS_TYPES: frozenset[str] = frozenset({
    "SetNode",
    "GetNode",
    "Note",
    "MarkdownNote",
    "Reroute",
    "PrimitiveNode",
})
RESERVED_WRAPPER_INPUT_NAMES: frozenset[str] = frozenset({"class", "from", "type"})

_WRAPPER_MODULES: tuple[str, ...] = (
    "core",
    "kjnodes",
    "ltxvideo",
    "videohelpersuite",
    "controlnet_aux",
    "depthanythingv2",
    "wanvideowrapper",
    "qwentts",
    "qwen3tts",
    "gguf",
    "rgthree",
    "sam2",
    "wananimatepreprocess",
)

_CURATED_SCHEMA_DEFAULTS: dict[str, dict[str, Any]] = {
    "UNETLoader": {"weight_dtype": "default"},
    "CLIPLoader": {"device": "default"},
    "VAELoader": {},
    "KSampler": {"scheduler": "simple", "denoise": 1},
    "KSamplerAdvanced": {"scheduler": "simple"},
    "EmptyLatentImage": {"batch_size": 1},
    "EmptySD3LatentImage": {"batch_size": 1},
    "EmptyFlux2LatentImage": {"batch_size": 1},
    "ImageScale": {"crop": "none"},
    "ImageResizeKJv2": {"crop": "none"},
    "VHS_VideoCombine": {"format": "auto", "codec": "auto"},
    "WanVideoSampler": {"shift": 8},
}

LTX2_3_TAIL_PATCHES: tuple[str, ...] = (
    "from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram",
    "from vibecomfy.patches.requirements import ensure_custom_nodes",
    "from vibecomfy.patches.resolution import resolution",
)


_WRAPPER_CLASS_TO_MODULE: dict[str, str] | None = None


def _wrapper_class_to_module() -> dict[str, str]:
    global _WRAPPER_CLASS_TO_MODULE
    if _WRAPPER_CLASS_TO_MODULE is not None:
        return _WRAPPER_CLASS_TO_MODULE
    mapping: dict[str, str] = {}
    for module_name in _WRAPPER_MODULES:
        try:
            module = importlib.import_module(f"vibecomfy.nodes._generated.{module_name}")
        except ImportError:
            continue
        exported = getattr(module, "__all__", ())
        for name in exported:
            if isinstance(name, str):
                mapping.setdefault(name, module_name)
    _WRAPPER_CLASS_TO_MODULE = mapping
    return mapping


def _wrapper_module_for_class(class_type: str) -> str | None:
    if class_type in FALLBACK_CLASS_TYPES or class_type in UI_ONLY_CLASS_TYPES:
        return None
    return _wrapper_class_to_module().get(class_type)


def _wrapper_imports_for_nodes(workflow_nodes: dict[str, Any]) -> dict[str, list[str]]:
    imports: dict[str, set[str]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        module_name = _wrapper_module_for_class(class_type)
        if module_name is not None:
            imports.setdefault(module_name, set()).add(class_type)
    return {module: sorted(names) for module, names in imports.items()}

# -- node role classification for section comments ---------------------------

_ROLE_CLASSIFICATION: dict[str, str] = {
    "LoadImage": "Inputs",
    "PrimitiveInt": "Inputs",
    "PrimitiveFloat": "Inputs",
    "PrimitiveString": "Inputs",
    "CLIPLoader": "Loaders",
    "VAELoader": "Loaders",
    "DualCLIPLoader": "Loaders",
    "DualCLIPLoaderGGUF": "Loaders",
    "CLIPVisionLoader": "Loaders",
    "StyleModelLoader": "Loaders",
    "UNETLoader": "Loaders",
    "CheckpointLoaderSimple": "Loaders",
    "CLIPTextEncode": "Conditioning",
    "CLIPTextEncodeFlux": "Conditioning",
    "CLIPTextEncodeSD3": "Conditioning",
    "FluxGuidance": "Conditioning",
    "CFGGuider": "Conditioning",
    "MultimodalGuider": "Conditioning",
    "ConditioningSetTimestepRange": "Conditioning",
    "KSampler": "Sampling",
    "KSamplerAdvanced": "Sampling",
    "SamplerCustomAdvanced": "Sampling",
    "BasicScheduler": "Sampling",
    "Flux2Scheduler": "Sampling",
    "KSamplerSelect": "Sampling",
    "EmptySD3LatentImage": "Sampling",
    "EmptyFlux2LatentImage": "Sampling",
    "EmptyLTXVLatentVideo": "Sampling",
    "EmptyHunyuanLatentVideo": "Sampling",
    "VAEDecode": "Decode",
    "VAEDecodeTiled": "Decode",
    "LTXVDecoder": "Decode",
    "SaveImage": "Outputs",
    "SaveVideo": "Outputs",
    "VHS_VideoCombine": "Outputs",
    "PreviewImage": "Outputs",
    "SaveAudio": "Outputs",
    "SaveAudioMP3": "Outputs",
}

_SECTION_ORDER: tuple[str, ...] = (
    "Inputs",
    "Loaders",
    "Conditioning",
    "Sampling",
    "Decode",
    "Outputs",
)

_SECTION_NODE_THRESHOLD: int = 8

# --- constant hoisting patterns ---------------------------------------------

_MODEL_FILE_SUFFIXES: tuple[str, ...] = (
    ".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".gguf", ".onnx",
)

# Fields whose values are classified as prompts
_PROMPT_INPUT_FIELDS: frozenset[str] = frozenset({"text", "prompt", "positive_prompt"})

# Fields whose values are classified as negative prompts
_NEGATIVE_PROMPT_INPUT_FIELDS: frozenset[str] = frozenset({"negative_prompt"})

# Fields whose values are classified as seeds
_SEED_INPUT_FIELDS: frozenset[str] = frozenset({"seed", "noise_seed"})

# Fields whose values are output prefixes
_OUTPUT_PREFIX_FIELDS: frozenset[str] = frozenset({"filename_prefix"})

# Fields whose values are dimensions
_DIMENSION_INPUT_FIELDS: frozenset[str] = frozenset({"resolution", "resolutions"})

# Fields whose values are FPS
_FPS_INPUT_FIELDS: frozenset[str] = frozenset({"fps"})

# Fields whose values are frame counts
_FRAMES_INPUT_FIELDS: frozenset[str] = frozenset({"length", "frames", "num_frames"})

# Fields whose values are guide strengths
_GUIDE_INPUT_FIELDS: frozenset[str] = frozenset({"cfg", "guidance", "strength_model", "strength_clip"})

# Fields whose values are model names (by field name pattern, not just suffix)
_MODEL_FIELD_PATTERNS: tuple[str, ...] = (
    "ckpt_name", "clip_name", "clip_name1", "clip_name2",
    "vae_name", "unet_name", "lora_name", "model_name",
    "checkpoint", "model",
)

# --- constant hoisting -------------------------------------------------------


def _classify_value_category(
    field: str,
    value: Any,
    node_class_type: str,
) -> str | None:
    """Classify a value into a constant category for hoisting.

    Returns one of: 'prompt', 'negative_prompt', 'seed', 'model', 'output_prefix',
    'size', 'fps', 'frames', 'guide', 'preset', or None (do not hoist).
    """
    if not isinstance(value, (str, int, float)):
        return None

    # Model filenames - check suffix patterns
    if isinstance(value, str):
        if value.endswith(_MODEL_FILE_SUFFIXES):
            return "model"
        if field in _MODEL_FIELD_PATTERNS:
            return "model"

    # Prompts - long text strings
    if isinstance(value, str):
        if field in _PROMPT_INPUT_FIELDS and len(value) > 30:
            return "prompt"
        if field in _NEGATIVE_PROMPT_INPUT_FIELDS and len(value) > 10:
            return "negative_prompt"

    # Seeds
    if isinstance(value, int) and field in _SEED_INPUT_FIELDS:
        return "seed"

    # Output prefixes
    if isinstance(value, str) and field in _OUTPUT_PREFIX_FIELDS:
        return "output_prefix"

    # Dimensions
    if isinstance(value, str) and field in _DIMENSION_INPUT_FIELDS:
        return "size"

    # FPS
    if isinstance(value, (int, float)) and field in _FPS_INPUT_FIELDS:
        return "fps"

    # Frames
    if isinstance(value, int) and field in _FRAMES_INPUT_FIELDS:
        return "frames"

    # Guide strengths
    if isinstance(value, (int, float)) and field in _GUIDE_INPUT_FIELDS:
        return "guide"

    return None


def _classify_node_role(node: Any) -> str | None:
    """Return the section role for a node, or None if unclassified."""
    return _ROLE_CLASSIFICATION.get(node.class_type)


def _build_section_groups(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> dict[str, list[str]]:
    """Group node IDs by section role using topological order.

    Only returns groups when the workflow has >= _SECTION_NODE_THRESHOLD nodes.
    Groups are ordered by _SECTION_ORDER.
    """
    if len(workflow_nodes) < _SECTION_NODE_THRESHOLD:
        return {}

    topo_order = _topological_node_order(workflow_nodes, edges_in)
    groups: dict[str, list[str]] = {}

    for nid in topo_order:
        node = workflow_nodes.get(nid)
        if node is None:
            continue
        role = _classify_node_role(node)
        if role is not None:
            groups.setdefault(role, []).append(nid)

    # Filter out groups with fewer than 2 nodes for readability
    # (single-node groups don't need section comments)
    return {role: ids for role, ids in groups.items() if len(ids) >= 1}


def _hoist_constants(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """Scan workflow nodes for hoistable constants.

    Returns (constant_lines, constant_map) where:
    - constant_lines: list of "NAME = value" lines to emit in the constants section
    - constant_map: mapping from (node_id, translated_field) to constant name
    """
    # Collect candidates: (node_id, translated_field, value, category)
    candidates: list[tuple[str, str, Any, str]] = []

    # Also track value occurrence count across all nodes for the "repeated" heuristic
    value_counts: Counter[tuple[str, Any]] = Counter()

    for nid, node in workflow_nodes.items():
        cls = node.class_type
        schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
        node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
        input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or _ui_widget_aliases(node)

        for key, value in node.inputs.items():
            if _is_link(value):
                continue
            translated = _translate_widget_for_key(key, input_aliases, cls)
            if translated is None:
                continue
            category = _classify_value_category(translated, value, cls)
            if category is not None:
                candidates.append((nid, translated, value, category))
                value_counts[(category, str(value))] += 1

        for key, value in node.widgets.items():
            if _is_link(value):
                continue
            translated = _translate_widget_for_key(key, input_aliases, cls)
            if translated is None:
                continue
            category = _classify_value_category(translated, value, cls)
            if category is not None:
                candidates.append((nid, translated, value, category))
                value_counts[(category, str(value))] += 1

    if not candidates:
        return [], {}

    # Decide what to hoist:
    # 1. Always hoist: model, prompt, negative_prompt, seed, output_prefix, size, fps, frames, guide
    #    (these are public defaults by definition)
    # 2. Hoist presets that appear 2+ times
    # 3. Hoist any value of a recognized category that appears 2+ times

    # Build constant names deterministically
    category_counters: dict[str, int] = {}
    constant_defs: dict[str, tuple[Any, str]] = {}  # name -> (value, category)
    constant_map: dict[tuple[str, str], str] = {}  # (nid, field) -> name

    # Pre-defined name patterns by category
    _CATEGORY_NAMES: dict[str, str] = {
        "prompt": "DEFAULT_PROMPT",
        "negative_prompt": "DEFAULT_NEGATIVE",
        "seed": "DEFAULT_SEED",
        "model": "MODEL_NAME",
        "output_prefix": "OUTPUT_PREFIX",
        "size": "DEFAULT_SIZE",
        "fps": "DEFAULT_FPS",
        "frames": "DEFAULT_FRAMES",
        "guide": "GUIDE_STRENGTH",
    }

    # Value dedup: same category + same value string -> same constant name
    value_to_name: dict[tuple[str, str], str] = {}  # (category, str(value)) -> name

    for nid, field, value, category in candidates:
        value_key = (category, str(value))
        count = value_counts[value_key]

        # Always hoist categories that represent public defaults
        always_hoist = category in ("model", "prompt", "negative_prompt", "seed",
                                    "output_prefix", "size", "fps", "frames", "guide")
        should_hoist = always_hoist or count >= 2

        if not should_hoist:
            continue

        if value_key in value_to_name:
            name = value_to_name[value_key]
        else:
            base = _CATEGORY_NAMES.get(category, "CONSTANT")
            category_counters[base] = category_counters.get(base, 0) + 1
            cnt = category_counters[base]
            name = base if cnt == 1 else f"{base}_{cnt}"
            value_to_name[value_key] = name
            constant_defs[name] = (value, category)

        constant_map[(nid, field)] = name

    # Also check for repeated presets (non-categorized values appearing 2+ times)
    # Scan for string values that appear 2+ times and hoist them
    all_values: Counter[tuple[str, Any]] = Counter()
    for nid, node in workflow_nodes.items():
        cls = node.class_type
        node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
        input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or _ui_widget_aliases(node)
        for key, value in {**node.inputs, **node.widgets}.items():
            if _is_link(value):
                continue
            translated = _translate_widget_for_key(key, input_aliases, cls)
            if translated is None:
                continue
            # Only track string values that are not already categorized
            if not isinstance(value, str):
                continue
            cat = _classify_value_category(translated, value, cls)
            if cat is not None:
                continue  # already handled above
            all_values[(translated, value)] += 1

    for (field, value), count in all_values.items():
        if count >= 2:
            # This is a repeated preset
            value_key = ("preset", str(value))
            if value_key in value_to_name:
                continue  # already named
            # Deterministic name: field name ALL_CAPS_ style
            sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", field.upper())
            if not sanitized or sanitized[0].isdigit():
                sanitized = f"P_{sanitized}"
            category_counters[sanitized] = category_counters.get(sanitized, 0) + 1
            cnt = category_counters[sanitized]
            name = sanitized if cnt == 1 else f"{sanitized}_{cnt}"
            value_to_name[value_key] = name
            constant_defs[name] = (value, "preset")
            # Map all occurrences
            for nid, node in workflow_nodes.items():
                if (nid, field) in constant_map:
                    continue
                # Check if this node has this value at this field
                node_val = node.inputs.get(field, node.widgets.get(field))
                if node_val == value:
                    constant_map[(nid, field)] = name

    # Build constant lines, sorted by name for determinism
    constant_lines: list[str] = []
    for name in sorted(constant_defs.keys()):
        value, category = constant_defs[name]
        constant_lines.append(f"{name} = {_format_value(value)}")

    return constant_lines, constant_map


def _translate_widget_for_key(
    key: str,
    input_aliases: list[str | None] | None,
    class_type: str,
) -> str | None:
    """Translate a widget_N key to its named field, or None if it should be dropped."""
    if not key.startswith("widget_"):
        return key
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return key
    if isinstance(input_aliases, (list, tuple)) and 0 <= idx < len(input_aliases):
        alias = input_aliases[idx]
        return alias  # may be None (UI-only)
    return resolve_widget_name(class_type, idx)


def _drop_output_prefix_constants(
    constant_lines: list[str],
    constant_map: dict[tuple[str, str], str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """Keep filename prefixes inline; READY_METADATA owns the public output prefix."""
    output_prefix_names = {
        line.split("=", 1)[0].strip()
        for line in constant_lines
        if line.split("=", 1)[0].strip().startswith("OUTPUT_PREFIX")
    }
    if not output_prefix_names:
        return constant_lines, constant_map
    return (
        [
            line
            for line in constant_lines
            if line.split("=", 1)[0].strip() not in output_prefix_names
        ],
        {
            key: value
            for key, value in constant_map.items()
            if value not in output_prefix_names
        },
    )


def _public_input_specs(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    *,
    registered_inputs: dict[str, tuple[str, str]] | None,
    constant_map: dict[tuple[str, str], str],
) -> list[_PublicInputSpec]:
    specs: list[_PublicInputSpec] = []
    used_names: set[str] = set()

    def add(binding: _PublicInputBinding) -> None:
        if binding.name in used_names:
            return
        node = workflow_nodes.get(str(binding.node_id))
        if node is None:
            return
        field_values = _resolved_field_values(node)
        if binding.field not in field_values:
            return
        default_expr = constant_map.get((str(binding.node_id), binding.field))
        if default_expr is None:
            default_expr = _format_value(field_values[binding.field])
        node_var = _first_output_var(output_var_names.get(str(binding.node_id))) or var_names.get(str(binding.node_id))
        node_ref = f"ref({node_var!r})" if node_var is not None else repr(str(binding.node_id))
        specs.append(
            _PublicInputSpec(
                name=binding.name,
                node_ref=node_ref,
                field=binding.field,
                default_expr=default_expr,
                type=binding.type,
                required=binding.required,
                aliases=binding.aliases,
                media_semantics=binding.media_semantics,
            )
        )
        used_names.add(binding.name)
        used_names.update(binding.aliases)

    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        resolved_field = field
        if field.startswith("widget_") and old_id in workflow_nodes:
            cls = workflow_nodes[old_id].class_type
            try:
                idx = int(field.split("_", 1)[1])
                resolved_field = resolve_widget_name(cls, idx)
            except (ValueError, IndexError):
                pass
        add(_PublicInputBinding(name=input_name, node_id=str(old_id), field=resolved_field))

    inferred = _infer_public_input_bindings(workflow_nodes, edges_in, reserved_names=used_names)
    for binding in inferred:
        add(binding)
    return specs


def _format_public_inputs_block(specs: list[_PublicInputSpec]) -> list[str]:
    if not specs:
        return ["PUBLIC_INPUTS = {}"]
    lines = ["PUBLIC_INPUTS = {"]
    for spec in specs:
        args = [
            f"node={spec.node_ref}",
            f"field={spec.field!r}",
            f"default={spec.default_expr}",
        ]
        if spec.type is not None:
            args.append(f"type={spec.type!r}")
        if spec.required:
            args.append("required=True")
        if spec.aliases:
            args.append(f"aliases={spec.aliases!r}")
        if spec.media_semantics is not None:
            args.append(f"media_semantics={spec.media_semantics!r}")
        lines.append(f"    {spec.name!r}: InputSpec({', '.join(args)}),")
    lines.append("}")
    return lines


def _model_assets_for_emit(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    def usable(asset: Mapping[str, Any]) -> bool:
        return bool(asset.get("url"))

    raw_assets = metadata.get("model_assets")
    if isinstance(raw_assets, list):
        return [dict(asset) for asset in raw_assets if isinstance(asset, Mapping) and usable(asset)]
    raw_requirement_models = requirements.get("models") if isinstance(requirements, Mapping) else None
    if isinstance(raw_requirement_models, list):
        return [dict(asset) for asset in raw_requirement_models if isinstance(asset, Mapping) and usable(asset)]
    return []


def _model_key(asset: Mapping[str, Any], used: set[str]) -> str:
    raw_name = str(asset.get("name") or asset.get("filename") or "model")
    base = re.sub(r"[^0-9a-zA-Z_]+", "_", raw_name.rsplit(".", 1)[0]).strip("_").lower() or "model"
    if base[0].isdigit():
        base = f"model_{base}"
    if keyword.iskeyword(base):
        base = f"{base}_model"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _format_models_block(model_assets: list[Mapping[str, Any]]) -> list[str]:
    if not model_assets:
        return ["MODELS = {}"]
    lines = ["MODELS = {"]
    used: set[str] = set()
    for asset in model_assets:
        key = _model_key(asset, used)
        filename = asset.get("filename", asset.get("name"))
        subdir = asset.get("subdir") or asset.get("directory") or "checkpoints"
        args: list[str] = []
        if filename is not None and not _filename_is_url_derived(str(filename), asset.get("url")):
            args.append(f"filename={_format_value(filename)}")
        for field_name in ("url", "target_path", "sha256", "hf_revision", "size_bytes"):
            value = asset.get(field_name)
            if value is not None:
                args.append(f"{field_name}={_format_value(value)}")
        if subdir is not None:
            args.append(f"subdir={_format_value(subdir)}")
        lines.append(f"    {key!r}: ModelAsset({', '.join(args)}),")
    lines.append("}")
    return lines


def _filename_is_url_derived(filename: str, url: Any) -> bool:
    if not isinstance(url, str) or not url:
        return False
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not path:
        return False
    return Path(path).name == filename


def _metadata_extras_for_emit(metadata: Mapping[str, Any]) -> dict[str, Any]:
    derived_keys = {
        "ready_template",
        "workflow_template",
        "capability",
        "output_prefix",
        "unbound_inputs",
        "model_assets",
        "edit_guide",
        "requirements",
        "id_map",
        "ready_template_path",
        "python_policy_applied",
        "source_role",
        "source_workflow",
        "vibecomfy_version",
        "comfy_core",
        "coverage_tier",
        "custom_node_packs",
    }
    extras = {
        str(key): value
        for key, value in metadata.items()
        if key not in derived_keys and value is not None
    }
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping) and not _is_derivable_provenance(provenance):
        extras["provenance"] = dict(provenance)
    return extras


def _is_derivable_provenance(provenance: Mapping[str, Any]) -> bool:
    """Return true when ReadyMetadata.build can recreate the provenance."""

    return set(provenance).issubset({"source_workflow", "source_role"})


def _requirements_expr_for_emit(requirements: Mapping[str, Any], *, has_models: bool) -> str | None:
    retained: dict[str, Any] = {}
    for key, value in dict(requirements).items():
        if key == "models" and has_models:
            continue
        if value:
            retained[str(key)] = value
    if not retained:
        return None
    return _format_value(retained)


def _lock_entries_by_class(lockfile_path: Path = Path("custom_nodes.lock")) -> dict[str, LockEntry]:
    by_class: dict[str, LockEntry] = {}
    try:
        entries = read_lockfile(lockfile_path)
    except (OSError, ValueError):
        return {}
    for entry in entries:
        for class_type in entry.class_set:
            by_class.setdefault(str(class_type), entry)
    return by_class


def _custom_node_packs_for_emit(
    workflow_nodes: Mapping[str, Any],
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    explicit = metadata.get("custom_node_packs")
    if isinstance(explicit, Mapping):
        return {str(key): dict(value) for key, value in explicit.items() if isinstance(value, Mapping)}

    by_class = _lock_entries_by_class()
    if not by_class:
        return {}

    requirement_names = {
        str(item)
        for key in ("custom_nodes", "custom_node_refs")
        for item in (requirements.get(key) or [])
        if item
    }
    grouped: dict[str, dict[str, Any]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        entry = by_class.get(class_type)
        if entry is None:
            continue
        commit = entry.commit or entry.git_commit_sha
        if not commit:
            continue
        row = grouped.setdefault(
            entry.name,
            {
                "commit": commit,
                "url": entry.url,
                "class_schema_sha256": entry.class_schema_sha256 or entry.schema_hash,
                "classes_used": [],
                "pip_packages": list(entry.pip_packages),
                "status": "pinned" if entry.name in requirement_names or entry.slug in requirement_names else "discovered",
            },
        )
        if class_type not in row["classes_used"]:
            row["classes_used"].append(class_type)

    for row in grouped.values():
        row["classes_used"] = sorted(row["classes_used"])
        row["pip_packages"] = sorted(row["pip_packages"])
        for key in ("url", "class_schema_sha256"):
            if row.get(key) is None:
                row.pop(key, None)
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def _format_ready_metadata_build(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    has_models: bool,
    custom_node_packs: Mapping[str, Any] | None = None,
) -> list[str]:
    template_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    capability = str(metadata.get("capability") or "unknown")
    output_prefix = str(metadata.get("output_prefix") or template_id)
    lines = [
        "READY_METADATA = ReadyMetadata.build(",
        f"    capability={capability!r},",
        "    inputs=PUBLIC_INPUTS,",
        "    models=MODELS,",
    ]
    if output_prefix != template_id:
        lines.append(f"    output_prefix={output_prefix!r},")
    requirements_expr = _requirements_expr_for_emit(requirements, has_models=has_models)
    if requirements_expr is not None:
        lines.append(f"    requirements={requirements_expr},")
    if custom_node_packs:
        lines.append(f"    custom_node_packs={_format_value(dict(custom_node_packs))},")
    for key, value in _metadata_extras_for_emit(metadata).items():
        lines.append(f"    {key}={_format_value(value)},")
    lines.append(")")
    return lines


def emit_ready_template_python(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> str:
    metadata = dict(ready_metadata)
    requirements = dict(ready_requirements)
    if apply_overrides:
        for key, value in (apply_overrides.get("metadata_overrides") or {}).items():
            metadata[key] = value

    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides)
    has_ltx_tail = _has_ltx_lowvram_tail(template_id)

    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    var_names = prepared["var_names"]

    # Hoist constants and build section groups
    constant_lines, constant_map = _hoist_constants(workflow_nodes, edges_in, var_names)
    constant_lines, constant_map = _drop_output_prefix_constants(constant_lines, constant_map)
    section_groups = _build_section_groups(workflow_nodes, edges_in)
    wrapper_imports = _wrapper_imports_for_nodes(workflow_nodes)
    output_var_names = prepared["output_var_names"]
    public_inputs = _public_input_specs(
        workflow_nodes,
        edges_in,
        var_names,
        output_var_names,
        registered_inputs=registered_inputs,
        constant_map=constant_map,
    )
    model_assets = _model_assets_for_emit(metadata, requirements)
    custom_node_packs = _custom_node_packs_for_emit(workflow_nodes, metadata, requirements)

    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append('"""Auto-generated ready_template - see tools/convert_ready_templates.py."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append(
        "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref"
    )
    for module_name, names in sorted(wrapper_imports.items()):
        out_lines.append(f"from vibecomfy.nodes.{module_name} import {', '.join(names)}")
    if has_ltx_tail:
        out_lines.extend(LTX2_3_TAIL_PATCHES)
    out_lines.append("")
    # -- constants section ----------------------------------------------------
    if constant_lines:
        out_lines.append("")
        out_lines.extend(constant_lines)
        out_lines.append("")
    out_lines.append("")
    out_lines.extend(_format_models_block(model_assets))
    out_lines.append("")
    out_lines.extend(_format_public_inputs_block(public_inputs))
    out_lines.append("")
    out_lines.extend(
        _format_ready_metadata_build(
            metadata,
            requirements,
            has_models=bool(model_assets),
            custom_node_packs=custom_node_packs,
        )
    )
    out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr="READY_METADATA",
            source_path_expr="__file__",
            source_type="ready_template",
            source_provenance=None,
            registered_inputs=registered_inputs,
            public_inputs=public_inputs,
            tail_lines=_ready_template_tail_lines(
                has_ltx_tail,
                workflow_nodes,
                edges_in,
                var_names,
                output_var_names,
                metadata,
            ),
            diagnostics=diagnostics,
            use_shared_helpers=True,
            constant_map=constant_map,
            section_groups=section_groups,
        )
    )
    out_lines.append("")

    combined = "\n".join(out_lines) + "\n"

    # -- readability diagnostic: generated_template_not_formatted -------------
    if diagnostics is not None:
        _check_template_formatting(combined, workflow_nodes, section_groups, diagnostics)

    # Validate syntax with ast.parse
    try:
        ast.parse(combined)
    except SyntaxError as exc:
        raise RuntimeError(f"Generated ready-template code failed syntax check: {exc}") from exc
    return combined


def emit_scratchpad_python(
    workflow,
    *,
    workflow_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> str:
    workflow_id = workflow_id or getattr(workflow, "id", "scratchpad")
    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides)
    source_path_expr = repr(source_path) if source_path is not None else "__file__"

    out_lines: list[str] = []
    out_lines.append("# vibecomfy: generated scratchpad")
    out_lines.append('"""Auto-generated VibeComfy scratchpad."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append("from vibecomfy.workflow import VibeWorkflow, WorkflowSource")
    out_lines.append("")
    out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr=repr(workflow_id),
            source_path_expr=source_path_expr,
            source_type="scratchpad",
            source_provenance=provenance or {},
            registered_inputs=registered_inputs,
            public_inputs=None,
            tail_lines=["    wf.finalize_metadata()"],
            diagnostics=diagnostics,
        )
    )
    out_lines.append("")
    out_lines.append(_NODE_HELPER_SOURCE)
    return "\n".join(out_lines) + "\n"


def _prepare_workflow_for_emit(workflow: Any, *, apply_overrides: dict[str, Any] | None) -> dict[str, Any]:
    workflow_nodes = {
        nid: node
        for nid, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES
    }
    edges_in: dict[str, list[Any]] = {}
    for edge in workflow.edges:
        if edge.from_node not in workflow_nodes or edge.to_node not in workflow_nodes:
            continue
        edges_in.setdefault(edge.to_node, []).append(edge)

    if apply_overrides:
        _apply_overrides(workflow_nodes, edges_in, apply_overrides.get("patches") or [])

    from vibecomfy.workflow import VibeEdge as _Edge

    extracted_edges_for_naming: list[Any] = []
    for nid, node in workflow_nodes.items():
        for key, value in {**node.inputs, **node.widgets}.items():
            if _is_link(value):
                extracted_edges_for_naming.append(_Edge(str(value[0]), str(value[1]), str(nid), key))

    var_names = _compute_variable_names(
        workflow_nodes,
        [edge for edges in edges_in.values() for edge in edges] + extracted_edges_for_naming,
    )
    output_var_names = _compute_output_variable_names(
        workflow_nodes,
        var_names,
        [edge for edges in edges_in.values() for edge in edges] + extracted_edges_for_naming,
    )
    return {
        "nodes": workflow_nodes,
        "edges_in": edges_in,
        "var_names": var_names,
        "output_var_names": output_var_names,
    }


def _infer_public_input_bindings(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    reserved_names: set[str] | None = None,
) -> list[_PublicInputBinding]:
    bindings: list[_PublicInputBinding] = []
    used_names: set[str] = set(reserved_names or set())

    def add(
        name: str,
        node_id: str,
        field: str,
        *,
        type: str | None = None,
        required: bool = False,
        aliases: tuple[str, ...] = (),
        media_semantics: str | None = None,
    ) -> None:
        candidate_names = {name, *aliases}
        if candidate_names & used_names:
            return
        node = workflow_nodes.get(node_id)
        if node is None:
            return
        fields = _resolved_field_values(node)
        available = set(fields)
        incoming = {str(getattr(edge, "to_input", "")) for edge in edges_in.get(node_id, [])}
        if field not in available or field in incoming:
            return
        used_names.update(candidate_names)
        bindings.append(
            _PublicInputBinding(
                name=name,
                node_id=node_id,
                field=field,
                type=type,
                required=required,
                aliases=aliases,
                media_semantics=media_semantics,
            )
        )

    prompt_candidate: tuple[str, str] | None = None
    negative_candidate: tuple[str, str] | None = None
    for node_id, node in sorted(workflow_nodes.items(), key=lambda item: _id_sort_key(item[0])):
        fields = _resolved_field_values(node)
        class_type = str(getattr(node, "class_type", ""))
        title = _node_title(node).lower()

        if class_type in {"CLIPTextEncode", "CLIPTextEncodeFlux", "CLIPTextEncodeSD3", "CLIPTextEncodeSDXL", "TextEncodeQwenImageEdit"}:
            value = fields.get("text")
            if isinstance(value, str):
                if "negative" in title:
                    negative_candidate = negative_candidate or (str(node_id), "text")
                elif value.strip():
                    prompt_candidate = prompt_candidate or (str(node_id), "text")
        if class_type in {"PrimitiveStringMultiline", "PrimitiveString"} and isinstance(fields.get("value"), str):
            prompt_candidate = prompt_candidate or (str(node_id), "value")
        if class_type == "LoadImage" and "image" in fields:
            add("image", str(node_id), "image", type="IMAGE", required=True, aliases=("input_image",), media_semantics="image")
        if "seed" in fields and isinstance(fields["seed"], int) and not isinstance(fields["seed"], bool):
            add("seed", str(node_id), "seed", type="INT")
        if "noise_seed" in fields and isinstance(fields["noise_seed"], int) and not isinstance(fields["noise_seed"], bool):
            add("seed", str(node_id), "noise_seed", type="INT")
        if "width" in fields and isinstance(fields["width"], int):
            add("width", str(node_id), "width", type="INT")
        if "height" in fields and isinstance(fields["height"], int):
            add("height", str(node_id), "height", type="INT")
        if "length" in fields and isinstance(fields["length"], int):
            add("frames", str(node_id), "length", type="INT")
        if "frames" in fields and isinstance(fields["frames"], int):
            add("frames", str(node_id), "frames", type="INT")
        if "fps" in fields and isinstance(fields["fps"], (int, float)):
            add("fps", str(node_id), "fps", type="FLOAT")

    if prompt_candidate is not None:
        add("prompt", prompt_candidate[0], prompt_candidate[1], type="STRING", required=True, media_semantics="text")
    if negative_candidate is not None:
        add("negative_prompt", negative_candidate[0], negative_candidate[1], type="STRING", aliases=("negative",), media_semantics="text")
    return bindings


def _node_title(node: Any) -> str:
    ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(ui, dict):
        title = ui.get("title")
        if isinstance(title, str):
            return title
    return ""


def _resolved_field_values(node: Any) -> dict[str, Any]:
    class_type = str(getattr(node, "class_type", ""))
    aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
    values: dict[str, Any] = {}
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        translated = _translate_widget_for_key(str(key), aliases, class_type)
        if translated is not None:
            values[translated] = value
    return values


def _ui_widget_aliases(node: Any) -> list[str | None] | None:
    ui = getattr(node, "metadata", {}).get("_ui")
    if not isinstance(ui, dict):
        return None
    inputs = ui.get("inputs")
    if not isinstance(inputs, list):
        return None
    aliases: list[str | None] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        widget = item.get("widget")
        if not isinstance(widget, dict):
            continue
        name = widget.get("name")
        aliases.append(str(name) if isinstance(name, str) and name else None)
    widget_indices: list[int] = []
    for key in getattr(node, "widgets", {}):
        key_str = str(key)
        if not key_str.startswith("widget_"):
            continue
        try:
            widget_indices.append(int(key_str.split("_", 1)[1]))
        except ValueError:
            continue
    if widget_indices and len(aliases) <= max(widget_indices):
        return None
    return aliases or None


def _emit_build_function(
    prepared: dict[str, Any],
    *,
    workflow_id_expr: str,
    source_path_expr: str,
    source_type: str,
    source_provenance: dict[str, Any] | None,
    registered_inputs: dict[str, tuple[str, str]] | None,
    public_inputs: list[_PublicInputSpec] | None,
    tail_lines: list[str],
    diagnostics: list[EmissionDiagnostic] | None = None,
    use_shared_helpers: bool = False,
    constant_map: dict[tuple[str, str], str] | None = None,
    section_groups: dict[str, list[str]] | None = None,
) -> list[str]:
    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    var_names = prepared["var_names"]
    output_var_names = prepared.get("output_var_names", {}) if use_shared_helpers else {}

    if constant_map is None:
        constant_map = {}
    if section_groups is None:
        section_groups = {}
    var_to_nid = {var: nid for nid, var in var_names.items()}
    for output_nid, slot_vars in output_var_names.items():
        for output_var in slot_vars.values():
            var_to_nid[str(output_var)] = str(output_nid)
    public_preserve_fields: dict[str, set[str]] = {}
    for spec in public_inputs or []:
        node_ref = spec.node_ref
        if not node_ref.startswith("ref("):
            continue
        try:
            ref_name = ast.literal_eval(node_ref[4:-1])
        except Exception:
            continue
        nid = var_to_nid.get(str(ref_name))
        if nid is not None:
            public_preserve_fields.setdefault(nid, set()).add(spec.field)

    # Build a set of node IDs covered by section groups for fast lookup
    section_nids: set[str] = set()
    for nids in section_groups.values():
        section_nids.update(nids)

    # Build ordered list of (section_name, nid) for topological-sorted nodes
    topo_order = _topological_node_order(workflow_nodes, edges_in)
    section_order_map: dict[str, str] = {}  # nid -> section_name
    for section_name in _SECTION_ORDER:
        for nid in section_groups.get(section_name, []):
            section_order_map[nid] = section_name

    out_lines: list[str] = []
    out_lines.append("def build() -> VibeWorkflow:")
    out_lines.append('    """Build the workflow (auto-generated)."""')
    provenance_part = ""
    if source_provenance is not None:
        provenance_part = f",\n            provenance={_format_value(source_provenance)}"

    if use_shared_helpers:
        out_lines.append(f"    with new_workflow({workflow_id_expr}, source_path={source_path_expr}) as wf:")
        body_indent = "        "
        continuation_indent = "            "
    else:
        out_lines.append(
            "    wf = VibeWorkflow(\n"
            f"        {workflow_id_expr},\n"
            "        WorkflowSource(\n"
            f"            id={workflow_id_expr},\n"
            f"            path={source_path_expr},\n"
            f"            source_type={source_type!r}"
            f"{provenance_part},\n"
            "        ),\n"
            "    )"
        )
        body_indent = "    "
        continuation_indent = "        "
    out_lines.append("")

    last_section: str | None = None
    for nid in topo_order:
        node = workflow_nodes[nid]
        var = var_names[nid]

        # -- readability diagnostic: variable name too long -------------------
        if diagnostics is not None and len(var) > 40:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
                    message=(
                        f"Variable name {var!r} ({len(var)} chars) exceeds 40-character threshold; "
                        f"consider a shorter semantic name."
                    ),
                    severity="warning",
                    node_id=str(nid),
                    class_type=node.class_type,
                    detail={"variable_name": var, "length": len(var)},
                )
            )

        # Emit section comment if entering a new section group
        section = section_order_map.get(nid)
        if section is not None and section != last_section:
            if out_lines and out_lines[-1] != "":
                out_lines.append("")
            out_lines.append(f"{body_indent}# {section}")
            last_section = section

        wrapper_module = _wrapper_module_for_class(str(node.class_type)) if use_shared_helpers else None
        preserve_fields = {
            field
            for old_id, field in (registered_inputs or {}).values()
            if old_id == nid
        }
        preserve_fields.update(public_preserve_fields.get(nid, set()))
        kwargs = _node_kwargs(
            node, edges_in, var_names,
            workflow_nodes=workflow_nodes,
            output_var_names=output_var_names,
            diagnostics=diagnostics,
            constant_map=constant_map,
            use_ui_widget_aliases=use_shared_helpers,
            strip_schema_defaults=use_shared_helpers,
            omit_single_output_metadata=use_shared_helpers,
            bare_single_output_refs=use_shared_helpers,
            emit_reserved_keyword_args=wrapper_module is not None,
            preserve_fields=preserve_fields,
        )

        if use_shared_helpers:
            use_wrapper = wrapper_module is not None
            ready_kwargs: list[tuple[str, str]] = []
            outputs_expr: str | None = None
            extras_expr: str | None = None
            for key, expr in kwargs:
                if key == "_outputs":
                    outputs_expr = expr
                elif key == "_extras":
                    extras_expr = expr
                else:
                    ready_kwargs.append((key, expr))

            if use_wrapper:
                all_args = []
                all_args.extend((_wrapper_kwarg_name(key), expr) for key, expr in ready_kwargs)
                # v2.6.4 Fix 3: drop _outputs= for schema-known typed wrappers.
                # The wrapper class already knows its output names from the
                # generated schema (vibecomfy/nodes/_generated/<pack>.py). Only
                # raw_call (UUID fallback, no schema) needs explicit _outputs.
                if extras_expr is not None:
                    all_args.append(("**", extras_expr))
                call_name = str(node.class_type)
                assignment_target = _assignment_target(var, output_var_names.get(str(nid)))
            else:
                all_args = []
                if outputs_expr is not None:
                    all_args.append(("_outputs", outputs_expr))
                all_args.extend(ready_kwargs)
                if extras_expr is not None:
                    all_args.append(("_extras", extras_expr))
                call_name = "node"
                assignment_target = var

            # Multi-line formatting: use multi-line when >3 kwargs or any line would exceed ~88 chars
            kwarg_lines = [f"**{expr}" if key == "**" else f"{key}={expr}" for key, expr in all_args]
            if use_wrapper:
                call_args = ", ".join(kwarg_lines)
                single_line = f"{body_indent}{assignment_target} = {call_name}({call_args})"
            else:
                call_args = ", ".join([repr(node.class_type), repr(nid), *kwarg_lines])
                single_line = f"{body_indent}{assignment_target} = raw_call(wf, {call_args})"

            # -- readability diagnostic: long one-line node call ----------
            if diagnostics is not None and len(single_line) > 120:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
                        message=(
                            f"node call for {node.class_type!r} (node {nid}) would be a single "
                            f"line of {len(single_line)} chars (>120); multi-line formatting preferred."
                        ),
                        severity="warning",
                        node_id=str(nid),
                        class_type=node.class_type,
                        detail={"line_length": len(single_line)},
                    )
                )

            if len(all_args) > 3 or len(single_line) > 88:
                # v2.6.4 Fix 2: ensure blank line BEFORE multi-line statements
                # (not after) for consistent vertical rhythm regardless of what
                # came before. Single-line statements pack together. Section
                # comments stay attached to the statement they introduce.
                prev = out_lines[-1] if out_lines else ""
                is_section_comment = prev.lstrip().startswith("# ")
                if out_lines and prev != "" and not is_section_comment:
                    out_lines.append("")
                if use_wrapper:
                    lines = [f"{body_indent}{assignment_target} = {call_name}("]
                else:
                    lines = [f"{body_indent}{assignment_target} = raw_call(wf, {node.class_type!r}, {nid!r},"]
                for key, expr in all_args:
                    if key == "**":
                        lines.append(f"{continuation_indent}**{expr},")
                    else:
                        lines.append(f"{continuation_indent}{key}={expr},")
                lines.append(f"{body_indent})")
                out_lines.extend(lines)
            else:
                out_lines.append(single_line)
        else:
            head = f"    {var} = _node(wf, {node.class_type!r}, {nid!r}"
            if not kwargs:
                out_lines.append(f"{head})")
            else:
                out_lines.append(f"{head},")
                for key, expr in kwargs:
                    out_lines.append(f"        {key}={expr},")
                out_lines.append("    )")

    if use_shared_helpers:
        if out_lines and out_lines[-1] != "":
            out_lines.append("")
        tail_lines = _with_id_map_tail_line(tail_lines, var_names)
        out_lines.extend("    " + line if line else line for line in tail_lines)
        return out_lines
    out_lines.append("")
    out_lines.extend(tail_lines)
    if registered_inputs:
        for input_name, (old_id, field) in registered_inputs.items():
            resolved_field = field
            if field.startswith("widget_") and old_id in workflow_nodes:
                cls = workflow_nodes[old_id].class_type
                try:
                    idx = int(field.split("_", 1)[1])
                    resolved_field = resolve_widget_name(cls, idx)
                except (ValueError, IndexError):
                    pass
            descriptor_kwargs: list[str] = []
            if old_id in workflow_nodes:
                node = workflow_nodes[old_id]
                if resolved_field in node.inputs:
                    descriptor_kwargs.append(f"default={_format_value(node.inputs[resolved_field])}")
                elif resolved_field in node.widgets:
                    descriptor_kwargs.append(f"default={_format_value(node.widgets[resolved_field])}")
            if use_shared_helpers:
                suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                out_lines.append(f"    bind_input(wf, {input_name!r}, {_node_binding_expr(old_id, var_names)}, {resolved_field!r}{suffix})")
            else:
                suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                out_lines.append(
                    f"    wf.register_input({input_name!r}, {old_id!r}, {resolved_field!r}, "
                    f"wf.nodes[{old_id!r}].inputs.get({resolved_field!r}, wf.nodes[{old_id!r}].widgets.get({resolved_field!r})){suffix})"
                )

    out_lines.append("    return wf")
    return out_lines


def _with_id_map_tail_line(tail_lines: list[str], var_names: dict[str, str]) -> list[str]:
    # v2.6.4 fix: id_map is derived at runtime via wf.id_map() (returns
    # {ClassType#N: node_id}). The build() source is the authoritative
    # variable-name binding; storing it again at runtime via _set_id_map
    # was bloat that scaled linearly with node count (60+ entry one-line
    # dicts on LTX templates). Drop the emission entirely.
    return tail_lines


_OUTPUT_CLASSES: dict[str, tuple[str, str]] = {
    "SaveImage": ("image", "image/png"),
    "PreviewImage": ("image", "image/png"),
    "SaveVideo": ("video", "video/mp4"),
    "VHS_VideoCombine": ("video", "video/mp4"),
    "SaveAudio": ("audio", "audio/wav"),
    "SaveAudioMP3": ("audio", "audio/mpeg"),
}


def _ready_template_tail_lines(
    has_ltx_tail: bool,
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> list[str]:
    finalize_args = _finalize_args(workflow_nodes, edges_in, var_names, output_var_names, metadata)
    call = f"    return wf.finalize(PUBLIC_INPUTS{finalize_args})"
    if has_ltx_tail:
        return [
            "    apply_ltx_lowvram(wf)",
            "    resolution(384, 256, 9).apply(wf)",
            "    ensure_custom_nodes(wf, READY_METADATA.get(\"requirements\", {}).get(\"custom_nodes\", []))",
            call,
        ]
    return [call]


def _finalize_args(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> str:
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    args: list[str] = []
    selected_id: str | None = output_node_ids[0] if output_node_ids else None
    if len(output_node_ids) > 1 and selected_id is not None:
        output_var = _first_output_var(output_var_names.get(selected_id))
        args.append(f"output_node={output_var or var_names.get(selected_id, repr(selected_id))}")
    if selected_id is not None:
        node = workflow_nodes[selected_id]
        output_contract = _OUTPUT_CLASSES.get(str(node.class_type))
        if output_contract is not None:
            artifact_kind, mime_type = output_contract
            args.append(f"output_type={node.class_type!r}")
            args.append(f"name={artifact_kind!r}")
            args.append(f"artifact_kind={artifact_kind!r}")
            args.append(f"mime_type={mime_type!r}")
            args.append("expected_cardinality='one'")
        prefix_raw = node.inputs.get("filename_prefix", node.widgets.get("filename_prefix"))
        if prefix_raw is not None and prefix_raw != metadata.get("output_prefix"):
            args.append(f"filename_prefix={_format_value(prefix_raw)}")
    if not args:
        return ""
    return ", " + ", ".join(args)


def _terminal_output_node_ids(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> list[str]:
    outgoing = {
        str(edge.from_node)
        for edges in edges_in.values()
        for edge in edges
    }
    candidates = [
        nid
        for nid, node in workflow_nodes.items()
        if nid not in outgoing and _is_output_class(str(node.class_type))
    ]
    return sorted(candidates, key=_id_sort_key)


def _is_output_class(class_type: str) -> bool:
    if class_type in _OUTPUT_CLASSES:
        return True
    lowered = class_type.lower()
    return lowered.startswith(("save", "preview", "create")) or "save" in lowered or "preview" in lowered


def _node_binding_expr(node_id: str, var_names: dict[str, str]) -> str:
    var = var_names.get(str(node_id))
    if var is not None and _wrapper_module_for_class(var.split("_", 1)[0]) is not None:
        return f"{var}.node.id"
    if var is not None:
        return f"{var}.node.id"
    return repr(str(node_id))


def _wrapper_kwarg_name(name: str) -> str:
    return f"{name}_" if name in RESERVED_WRAPPER_INPUT_NAMES or keyword.iskeyword(name) else name


def _check_template_formatting(
    combined: str,
    workflow_nodes: dict[str, Any],
    section_groups: dict[str, list[str]],
    diagnostics: list[EmissionDiagnostic],
) -> None:
    """Check generated template for section comments and indentation hygiene.

    Two checks:
    1. If the workflow has >=8 nodes and section_groups are non-empty but no
       section comment lines appear in the output.
    2. If any line in the tail (after the build function body) is un-indented
       (does not start with 4 spaces, '#', blank, or a string-like line).
    """
    lines = combined.split("\n")

    # Check 1: missing section comments for large workflows
    if len(workflow_nodes) >= _SECTION_NODE_THRESHOLD and section_groups:
        has_section_comment = any(
            line.strip().startswith("# ") and any(
                line.strip().endswith(f"# {sec}")
                or line.strip() == f"# {sec}"
                or line.strip().startswith(f"# {sec}")
                for sec in _SECTION_ORDER
            )
            for line in lines
        )
        if not has_section_comment:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
                    message=(
                        f"Generated template has {len(workflow_nodes)} nodes but lacks section "
                        f"comments (e.g. # Inputs, # Loaders, # Conditioning). "
                        f"Section comments improve readability for large workflows."
                    ),
                    severity="warning",
                    detail={
                        "node_count": len(workflow_nodes),
                        "section_groups_present": bool(section_groups),
                    },
                )
            )

    # Check 2: un-indented tail lines (after build function)
    # Find the return wf line and check everything after it
    in_build = False
    past_return = False
    for line in lines:
        stripped = line.strip()
        if stripped == "def build() -> VibeWorkflow:":
            in_build = True
            continue
        if in_build and stripped.startswith("return wf"):
            past_return = True
            continue
        if past_return:
            # After return wf, lines should be empty or start with 4+ spaces
            # (internal to the build function) or be completely blank
            if stripped and not line.startswith("    ") and not stripped.startswith("#"):
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
                        message=(
                            f"Generated template has un-indented tail line: {stripped!r}. "
                            f"Lines after return wf should be blank or properly indented."
                        ),
                        severity="warning",
                        detail={"unindented_line": stripped},
                    )
                )
                break  # One diagnostic is enough


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


def _safe_var(class_type: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", class_type.lower())
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _connection_role_name(workflow_nodes: dict[str, Any], edges_out: dict[str, list[tuple[str, str]]]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for src_node_id, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        for to_node, to_input in edges_out.get(src_node_id, []):
            target = workflow_nodes.get(to_node)
            if target is None:
                continue
            if target.class_type == "KSampler" and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
            if target.class_type in ("CFGGuider", "MultimodalGuider") and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
    return roles


def _empty_text_role(workflow_nodes: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        text_value = node.inputs.get("text", node.widgets.get("text", node.widgets.get("widget_0")))
        if isinstance(text_value, str) and text_value.strip() == "":
            roles.setdefault(nid, "negative")
    return roles


def _id_sort_key(nid: str) -> tuple[Any, ...]:
    parts = str(nid).split(":")
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, str(nid))


def _topological_node_order(nodes: dict[str, Any], edges_in: dict[str, list[Any]]) -> list[str]:
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if _is_link(value):
                src = str(value[0])
                if src in nodes:
                    deps[nid].add(src)

    pending = set(nodes.keys())
    out: list[str] = []
    while pending:
        ready = sorted((nid for nid in pending if not (deps[nid] - set(out))), key=_id_sort_key)
        if not ready:
            out.extend(sorted(pending, key=_id_sort_key))
            break
        for nid in ready:
            out.append(nid)
            pending.discard(nid)
    return out


def _format_value(value: Any) -> str:
    return repr(value)


def _is_schema_default(class_type: str, key: str, value: Any, node_metadata: Mapping[str, Any] | dict[str, Any]) -> bool:
    keep = node_metadata.get("keep_defaults") or node_metadata.get("keep_kwargs") or ()
    if key in set(str(item) for item in keep):
        return False
    defaults = dict(_CURATED_SCHEMA_DEFAULTS.get(class_type, {}))
    try:
        defaults.update(class_defaults(class_type))
    except Exception:
        pass
    return key in defaults and value == defaults[key]


def _compute_variable_names(workflow_nodes: dict[str, Any], edges: list[Any]) -> dict[str, str]:
    edges_out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        edges_out.setdefault(edge.from_node, []).append((edge.to_node, edge.to_input))

    role_conn = _connection_role_name(workflow_nodes, edges_out)
    role_empty = _empty_text_role(workflow_nodes)
    sorted_ids = sorted(workflow_nodes.keys(), key=_id_sort_key)

    used: dict[str, int] = {}
    var_names: dict[str, str] = {}
    for nid in sorted_ids:
        node = workflow_nodes[nid]
        base = role_conn.get(nid) or role_empty.get(nid) or _safe_var(node.class_type)
        used[base] = used.get(base, 0) + 1
        var_names[nid] = base if used[base] == 1 else f"{base}_{used[base]}"
    return var_names


def _compute_output_variable_names(
    workflow_nodes: dict[str, Any],
    var_names: dict[str, str],
    edges: list[Any],
) -> dict[str, dict[int, str]]:
    unpackable: dict[str, list[str]] = {}
    for nid, node in sorted(workflow_nodes.items(), key=lambda item: _id_sort_key(item[0])):
        if _wrapper_module_for_class(str(node.class_type)) is None:
            continue
        names = _schema_output_names_for_unpack(node)
        if len(names) <= 1:
            continue
        if _has_out_of_range_edge(str(nid), len(names), edges):
            continue
        unpackable[str(nid)] = names

    used = {
        var
        for nid, var in var_names.items()
        if str(nid) not in unpackable
    }
    output_vars: dict[str, dict[int, str]] = {}
    for nid, names in unpackable.items():
        node = workflow_nodes[nid]
        suffix = _class_collision_suffix(str(node.class_type))
        slot_vars: dict[int, str] = {}
        for index, name in enumerate(names):
            base = _safe_var(str(name).lower())
            candidate = base
            if candidate in used:
                candidate = f"{base}_{suffix}"
            if candidate in used:
                ordinal = 2
                while f"{candidate}_{ordinal}" in used:
                    ordinal += 1
                candidate = f"{candidate}_{ordinal}"
            used.add(candidate)
            slot_vars[index] = candidate
        output_vars[nid] = slot_vars
    return output_vars


def _schema_output_names_for_unpack(node: Any) -> list[str]:
    metadata_names = _node_output_names(node)
    if metadata_names:
        return metadata_names
    try:
        return [str(name) for name in class_output_names(str(node.class_type)) if str(name)]
    except Exception:
        return []


def _has_out_of_range_edge(node_id: str, output_count: int, edges: list[Any]) -> bool:
    for edge in edges:
        if str(getattr(edge, "from_node", "")) != node_id:
            continue
        try:
            slot = int(getattr(edge, "from_output"))
        except (TypeError, ValueError):
            return True
        if slot < 0 or slot >= output_count:
            return True
    return False


def _class_collision_suffix(class_type: str) -> str:
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", class_type)
    return _safe_var(parts[0] if parts else class_type)


def _assignment_target(var: str, output_vars: dict[int, str] | None) -> str:
    if not output_vars:
        return var
    return ", ".join(output_vars[index] for index in sorted(output_vars))


def _first_output_var(output_vars: dict[int, str] | None) -> str | None:
    if not output_vars:
        return None
    first_slot = min(output_vars)
    return output_vars[first_slot]


def _node_kwargs(
    node: Any,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    *,
    workflow_nodes: dict[str, Any] | None = None,
    output_var_names: dict[str, dict[int, str]] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    constant_map: dict[tuple[str, str], str] | None = None,
    use_ui_widget_aliases: bool = False,
    strip_schema_defaults: bool = False,
    omit_single_output_metadata: bool = False,
    bare_single_output_refs: bool = False,
    emit_reserved_keyword_args: bool = False,
    preserve_fields: set[str] | None = None,
) -> list[tuple[str, str]]:
    cls = node.class_type
    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    # Per-node widget alias metadata populated by the schema provider during
    # convert_to_vibe_format.  Prefer this over the static WIDGET_SCHEMA so
    # that schema-source evidence wins - the static table is only a fallback.
    node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
    input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or (
        _ui_widget_aliases(node) if use_ui_widget_aliases else None
    )

    if constant_map is None:
        constant_map = {}
    if preserve_fields is None:
        preserve_fields = set()

    incoming: dict[str, tuple[str, int]] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str) -> str | None:
        if not key.startswith("widget_"):
            return key
        try:
            idx = int(key.split("_", 1)[1])
        except ValueError:
            return key
        # 1. Per-node schema-source evidence (input_aliases from provider).
        if isinstance(input_aliases, (list, tuple)) and 0 <= idx < len(input_aliases):
            alias = input_aliases[idx]
            if alias is not None:
                return alias
            # None -> UI-only widget, drop it.
            return None
        # 2. Static WIDGET_SCHEMA fallback (lowest priority).
        return resolve_widget_name(cls, idx)

    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        elif key not in raw_inputs:
            raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key)
        if translated is None:
            continue
        if translated != key and translated not in raw_inputs and translated not in static_inputs and translated not in incoming:
            static_inputs[translated] = value
        else:
            static_inputs[key] = value

    if schema:
        ordered_static_keys = [key for key in schema if key in static_inputs]
        ordered_static_keys += sorted(key for key in static_inputs if key not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    def _format_static_value(key: str, value: Any) -> str:
        """Format a static value, substituting constant name if hoisted."""
        nid = getattr(node, "id", None)
        if nid is not None:
            const_name = constant_map.get((str(nid), key))
            if const_name is not None:
                return const_name
        return _format_value(value)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    output_names = _node_output_names(node)
    if output_names and not (omit_single_output_metadata and _is_schema_confirmed_single_output(cls, output_names)):
        out.append(("_outputs", _format_value(tuple(output_names))))
    for key in ordered_static_keys:
        if key in incoming:
            continue
        if key not in preserve_fields and strip_schema_defaults and _is_schema_default(cls, key, static_inputs[key], node_metadata):
            continue
        if not _is_python_ident(key) and not (emit_reserved_keyword_args and key in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((key, _format_static_value(key, static_inputs[key])))
            continue
        out.append((key, _format_static_value(key, static_inputs[key])))

    if schema:
        ordered_incoming = [key for key in schema if key in incoming]
        ordered_incoming += sorted(key for key in incoming if key not in schema_set)
    else:
        ordered_incoming = sorted(incoming.keys())

    for to_input in ordered_incoming:
        from_node, from_slot = incoming[to_input]
        from_node_str = str(from_node)
        if from_node_str in var_names:
            unpacked_ref = (output_var_names or {}).get(from_node_str, {}).get(from_slot)
            if unpacked_ref is not None:
                expr = unpacked_ref
            elif bare_single_output_refs and _is_single_output_ref(workflow_nodes, from_node_str, from_slot):
                expr = var_names[from_node_str]
            else:
                safe_name = _safe_output_name(workflow_nodes, from_node_str, from_slot)
                if safe_name is not None:
                    expr = f"{var_names[from_node_str]}.out({safe_name!r})"
                else:
                    expr = f"{var_names[from_node_str]}.out({from_slot})"
                    if diagnostics is not None and workflow_nodes is not None:
                        _output_fallback_diagnostic(
                            diagnostics, workflow_nodes, from_node_str, from_slot,
                            target_node=node, target_input=to_input,
                        )
        else:
            expr = f"[{from_node_str!r}, {from_slot}]"
        if not _is_python_ident(to_input) and not (emit_reserved_keyword_args and to_input in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((to_input, expr))
            continue
        out.append((to_input, expr))

    # -- readability diagnostics: positional output detection ------------
    if diagnostics is not None:
        emit_diags = _collect_emission_diagnostics(node, output_names, incoming, var_names)
        diagnostics.extend(emit_diags)

    if extras:
        extras_repr = "{" + ", ".join(f"{key!r}: {value}" for key, value in extras) + "}"
        out.append(("_extras", extras_repr))
    return out


def _collect_emission_diagnostics(
    node: Any,
    output_names: list[str],
    incoming: dict[str, tuple[str, int]],
    var_names: dict[str, str],
) -> list[EmissionDiagnostic]:
    """Collect readability diagnostics for a single node during emission.

    This is called from `_node_kwargs` when a diagnostics collector is
    provided.  Currently flags:

    * **avoidable_positional_output** - the node has output names available
      (from schema metadata) but the emitter is using numeric `.out(n)`
      because one or more names are unsafe (blank, duplicate, conflicted).

    * **output_name_ambiguity** - output name is duplicated within the
      same node, forcing a numeric fallback.

    * **schema_backed_widget_alias_not_resolved** - one or more
      `widget_N` keys remain positional because no alias mapping could
      be resolved from schema / widget table evidence.
    """
    diags: list[EmissionDiagnostic] = []
    nid = getattr(node, "id", None)
    ctype = getattr(node, "class_type", None)
    metadata = getattr(node, "metadata", {}) or {}
    node_input_aliases = metadata.get("input_aliases")

    # 1. avoidable_positional_output / output_name_ambiguity
    if output_names:
        safe_names: set[str] = set()
        has_unsafe = False
        has_duplicate = False
        seen: set[str] = set()
        for name in output_names:
            if not name:
                has_unsafe = True
            elif name in seen:
                has_unsafe = True
                has_duplicate = True
            else:
                seen.add(name)
                safe_names.add(name)
        if has_unsafe:
            if has_duplicate:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
                        message=f"Node {nid} ({ctype}) has duplicate output names; falling back to numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
            else:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
                        message=f"Node {nid} ({ctype}) has partial/blank output names; some outputs use numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
    else:
        # No output names at all - check if schema has input_aliases available
        if not node_input_aliases:
            # Check if there are widget_N keys that could be aliased
            widget_keys = [
                k for k in getattr(node, "widgets", {}).keys()
                if k.startswith("widget_")
            ] + [
                k for k in getattr(node, "inputs", {}).keys()
                if k.startswith("widget_")
            ]
            if widget_keys:
                schema_source = metadata.get("schema_source")
                schema_available = schema_source is not None
                if schema_available:
                    diags.append(
                        EmissionDiagnostic(
                            code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                            message=f"Node {nid} ({ctype}) has {len(set(widget_keys))} unresolved widget_N keys despite schema being available.",
                            severity="warning",
                            node_id=str(nid) if nid is not None else None,
                            class_type=ctype,
                            detail={
                                "widget_keys": list(set(widget_keys)),
                                "schema_source": schema_source,
                            },
                        )
                    )

    # 3. schema_backed_widget_alias_not_resolved - when widget_N keys remain
    #    positional even though input_aliases could potentially cover them, or
    #    when the fallback to static WIDGET_SCHEMA was used.
    if node_input_aliases:
        # We have input_aliases - check if any widget_N index falls outside
        # the aliases list, forcing a fallback.
        widget_indices: list[int] = []
        for k in list(getattr(node, "widgets", {}).keys()) + list(getattr(node, "inputs", {}).keys()):
            if k.startswith("widget_"):
                try:
                    widget_indices.append(int(k.split("_", 1)[1]))
                except ValueError:
                    pass
        if widget_indices:
            max_idx = max(widget_indices)
            if max_idx >= len(node_input_aliases):
                unresolved = [
                    f"widget_{i}" for i in widget_indices
                    if i >= len(node_input_aliases)
                ]
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                        message=(
                            f"Node {nid} ({ctype}) has {len(unresolved)} widget_N key(s) "
                            f"({', '.join(unresolved)}) outside input_aliases range "
                            f"(len={len(node_input_aliases)}); keeping positional."
                        ),
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={
                            "unresolved_widgets": unresolved,
                            "input_aliases_length": len(node_input_aliases),
                        },
                    )
                )

    return diags


def _node_output_names(node: Any) -> list[str]:
    """Return output names for `_outputs` emission, preserving partial evidence.

    Unlike the old all-truthy gate, this always returns the full list from
    metadata so that `_outputs` is emitted even when some names are blank.
    The per-slot safety decision for `.out('name')` is made separately by
    `_safe_output_name` during incoming edge formatting.
    """
    output_names = getattr(node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return []
    result: list[str] = []
    for name in output_names:
        if isinstance(name, str) and name:
            result.append(name)
        else:
            result.append("")
    return result


def _safe_output_name(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> str | None:
    """Return the safe output name for a slot, or `None` if numeric fallback is needed.

    A name is *safe* for `.out('name')` when all of these hold:

    * *slot in range:* `from_slot` is a valid index into the source node's
      `output_names` metadata list.
    * *name non-empty:* the name at that index is a non-blank string.
    * *name unique:* the name appears exactly once in the source node's
      `output_names` list (no duplicates).
    * *name not conflicted:* the source node's metadata does not list the name
      in a `conflicted_outputs` key.
    """
    if workflow_nodes is None:
        return None
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return None
    output_names = getattr(src_node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return None
    if from_slot < 0 or from_slot >= len(output_names):
        return None
    name = output_names[from_slot]
    if not isinstance(name, str) or not name:
        return None
    # Duplicate check: the name must appear exactly once.
    if list(output_names).count(name) > 1:
        return None
    # Conflicted check: the name must not be in the conflicted_outputs list.
    conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
    if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
        return None
    return name


def _output_fallback_diagnostic(
    diagnostics: list[EmissionDiagnostic],
    workflow_nodes: dict[str, Any],
    from_node: str,
    from_slot: int,
    *,
    target_node: Any,
    target_input: str,
) -> None:
    """Record a diagnostic explaining why `.out(n)` was used instead of `.out('name')`.

    Only fires when the source node *has* output_names metadata - otherwise
    numeric fallback is expected and not an avoidable concern.
    """
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return

    output_names = getattr(src_node, "metadata", {}).get("output_names")
    # If the source node has no output_names metadata at all, numeric fallback
    # is the only option - no diagnostic warranted.
    if not isinstance(output_names, (list, tuple)):
        return

    src_ctype = getattr(src_node, "class_type", None)
    tgt_nid = getattr(target_node, "id", None)
    tgt_ctype = getattr(target_node, "class_type", None)

    reason_parts: list[str] = []
    if from_slot < 0 or from_slot >= len(output_names):
        reason_parts.append(
            f"slot {from_slot} out of range (source has {len(output_names)} output(s))"
        )
    else:
        name = output_names[from_slot]
        if not isinstance(name, str) or not name:
            reason_parts.append(f"output_names[{from_slot}] is blank")
        elif list(output_names).count(name) > 1:
            reason_parts.append(
                f"output_names[{from_slot}]={name!r} is duplicated in source output_names"
            )
        else:
            conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
            if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is marked conflicted"
                )
            else:
                # Should not reach here - _safe_output_name would have succeeded.
                # Log it anyway as a safety net.
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is not safe for named emission"
                )

    reason = "; ".join(reason_parts)
    diagnostics.append(
        EmissionDiagnostic(
            code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
            message=(
                f"Edge from {from_node} ({src_ctype}).out({from_slot}) to "
                f"{tgt_nid} ({tgt_ctype}).{target_input} uses numeric .out({from_slot}) "
                f"because: {reason}"
            ),
            severity="warning",
            node_id=str(tgt_nid) if tgt_nid is not None else None,
            class_type=tgt_ctype,
            detail={
                "from_node": from_node,
                "from_slot": from_slot,
                "target_input": target_input,
                "reason": reason,
                "output_names": list(output_names),
            },
        )
    )


def _format_metadata_dict(name: str, value: dict[str, Any]) -> str:
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


def _is_schema_confirmed_single_output(class_type: str, output_names: list[str] | tuple[str, ...]) -> bool:
    try:
        return class_output_count(class_type) == 1 and not class_has_list_output(class_type)
    except Exception:
        return len(output_names) == 1


def _is_single_output_ref(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> bool:
    if from_slot != 0 or workflow_nodes is None:
        return False
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return False
    output_names = _node_output_names(src_node)
    return _is_schema_confirmed_single_output(str(src_node.class_type), output_names)


def _has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


def _apply_overrides(nodes: dict[str, Any], edges_in: dict[str, list[Any]], patches: list[dict[str, Any]]) -> None:
    for patch in patches:
        match = patch.get("match", {})
        target_ids: list[str] = []
        if "node_id" in match:
            target_ids = [str(match["node_id"])]
        elif "class_type" in match:
            class_target = match["class_type"]
            ordinal = match.get("node_index")
            matches = [nid for nid, node in nodes.items() if node.class_type == class_target]
            if ordinal is not None and 0 <= ordinal < len(matches):
                target_ids = [matches[ordinal]]
            else:
                target_ids = matches

        for tid in target_ids:
            node = nodes.get(tid)
            if node is None:
                continue
            for old, new in (patch.get("rename_inputs") or {}).items():
                if old in node.widgets:
                    node.widgets[new] = node.widgets.pop(old)
                if old in node.inputs:
                    node.inputs[new] = node.inputs.pop(old)
            for key, value in (patch.get("set_inputs") or {}).items():
                if key in node.widgets:
                    node.widgets[key] = value
                else:
                    node.inputs[key] = value
            for key in patch.get("remove_inputs") or []:
                node.widgets.pop(key, None)
                node.inputs.pop(key, None)


_NODE_HELPER_SOURCE = '''
def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    **kwargs,
):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _outputs is not None:
        builder.node.metadata["output_names"] = list(_outputs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
'''


__all__ = [
    "emit_ready_template_python",
    "emit_scratchpad_python",
    "EmissionDiagnostic",
    "EmissionSeverity",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME",
    "READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE",
    "READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL",
    "READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED",
    "READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG",
    "READABILITY_WARNING_CODES",
]
