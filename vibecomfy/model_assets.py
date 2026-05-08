from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


HF_SPLIT_FILES_DIRS = {
    "text_encoders",
    "diffusion_models",
    "vae",
    "clip_vision",
    "loras",
    "latent_upscale_models",
    "controlnet",
    "checkpoints",
    "unet",
}

_CLASS_TYPE_SUBDIRS = {
    "CheckpointLoaderSimple": "checkpoints",
    "CLIPLoader": "text_encoders",
    "VAELoader": "vae",
    "LoraLoader": "loras",
    "ControlNetLoader": "controlnet",
    "UNETLoader": "diffusion_models",
    "UnetLoaderGGUF": "diffusion_models",
}

_HF_SPLIT_FILES_RE = re.compile(r"/split_files/([^/]+)/[^/]+$")


def extract_from_raw_workflow(raw: Mapping[str, Any]) -> list[dict[str, str]]:
    """Extract structured model asset entries from a ComfyUI workflow JSON object."""

    if not isinstance(raw, Mapping):
        return []
    has_nodes = bool(raw.get("nodes"))
    has_subgraphs = bool(_subgraphs(raw))
    if not has_nodes and not has_subgraphs:
        return []

    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for node in _iter_workflow_nodes(raw):
        for entry in _entries_from_node(node):
            key = (entry["name"], entry["subdir"])
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    return entries


def entries_from_scratchpad_path(path: str | Path) -> list[dict[str, str]]:
    """Read structured model assets from a materialized ready scratchpad."""

    module_ast = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    for node in module_ast.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "READY_REQUIREMENTS" for target in node.targets):
            continue
        requirements = ast.literal_eval(node.value)
        if not isinstance(requirements, Mapping):
            return []
        models = requirements.get("models", [])
        if not isinstance(models, list):
            return []
        return _normalise_requirement_entries(models)
    return []


def _entries_from_node(node: Mapping[str, Any]) -> Iterable[dict[str, str]]:
    properties = node.get("properties", {})
    if not isinstance(properties, Mapping):
        return []
    models = properties.get("models", [])
    if not isinstance(models, list):
        return []
    class_type = _node_class_type(node)
    entries: list[dict[str, str]] = []
    for model in models:
        entry = _normalise_model_entry(model, class_type=class_type)
        if entry is not None:
            entries.append(entry)
    return entries


def _normalise_requirement_entries(models: Iterable[Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for model in models:
        if not isinstance(model, Mapping):
            continue
        entry = _normalise_model_entry(model, class_type="")
        if entry is None:
            continue
        key = (entry["name"], entry["subdir"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    return entries


def _normalise_model_entry(model: Any, *, class_type: str) -> dict[str, str] | None:
    if not isinstance(model, Mapping):
        return None
    name = model.get("name")
    url = model.get("url")
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(url, str) or not url:
        return None
    subdir = _subdir_for_model(model, class_type=class_type, url=url)
    return {"name": name, "url": _strip_download_true(url), "subdir": subdir}


def _subdir_for_model(model: Mapping[str, Any], *, class_type: str, url: str) -> str:
    directory = model.get("directory")
    if isinstance(directory, str) and directory:
        return directory
    subdir = model.get("subdir")
    if isinstance(subdir, str) and subdir:
        return subdir
    split_subdir = _hf_split_files_subdir(url)
    if split_subdir is not None:
        return split_subdir
    return _CLASS_TYPE_SUBDIRS.get(class_type, "checkpoints")


def _hf_split_files_subdir(url: str) -> str | None:
    path = urlsplit(url).path
    match = _HF_SPLIT_FILES_RE.search(path)
    if not match:
        return None
    subdir = match.group(1)
    if subdir not in HF_SPLIT_FILES_DIRS:
        return None
    return subdir


def _strip_download_true(url: str) -> str:
    parsed = urlsplit(url)
    params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if not (key == "download" and value == "true")]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query and urlencode(params), parsed.fragment))


def _iter_workflow_nodes(raw: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield from _sorted_nodes(raw.get("nodes"))
    for subgraph in _subgraphs(raw):
        yield from _iter_workflow_nodes(subgraph)


def _subgraphs(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    definitions = raw.get("definitions", {})
    if not isinstance(definitions, Mapping):
        return []
    subgraphs = definitions.get("subgraphs", [])
    if not isinstance(subgraphs, list):
        return []
    return [subgraph for subgraph in subgraphs if isinstance(subgraph, Mapping)]


def _sorted_nodes(nodes: Any) -> list[Mapping[str, Any]]:
    if isinstance(nodes, Mapping):
        values = nodes.values()
    elif isinstance(nodes, list):
        values = nodes
    else:
        return []
    return sorted(
        [node for node in values if isinstance(node, Mapping)],
        key=lambda node: _node_sort_key(node.get("id")),
    )


def _node_sort_key(node_id: Any) -> tuple[int, str]:
    try:
        return (int(node_id), str(node_id))
    except (TypeError, ValueError):
        return (10**12, str(node_id))


def _node_class_type(node: Mapping[str, Any]) -> str:
    for key in ("class_type", "type"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    properties = node.get("properties", {})
    if isinstance(properties, Mapping):
        value = properties.get("Node name for S&R")
        if isinstance(value, str) and value:
            return value
    return ""


__all__ = ["HF_SPLIT_FILES_DIRS", "entries_from_scratchpad_path", "extract_from_raw_workflow"]
