from __future__ import annotations

import asyncio
import ast
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from vibecomfy.runtime.client import ComfyClient
from vibecomfy.runtime.server import comfy_server

from .cache import load_object_info_cache, object_info_cache_path, write_object_info_cache


@dataclass(frozen=True)
class InputSpec:
    type: str | None = None
    required: bool = False
    default: Any = None
    choices: list[Any] | None = None
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class OutputSpec:
    type: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class NodeSchema:
    class_type: str
    pack: str | None
    inputs: dict[str, InputSpec]
    outputs: list[OutputSpec]


class SchemaIndexError(ValueError):
    def __init__(self, path: Path, cause: Exception) -> None:
        super().__init__(f"{path} could not be read: {type(cause).__name__}: {cause}")
        self.path = path
        self.cause = cause


@runtime_checkable
class SchemaProvider(Protocol):
    def get_schema(self, class_type: str) -> NodeSchema | None: ...


def schema_for(provider: object | None, class_type: str) -> object | None:
    if provider is None:
        return None
    getter = getattr(provider, "get_schema", None) or getattr(provider, "get", None)
    if not callable(getter):
        return None
    return getter(class_type)


def schema_registry_empty(provider: object | None) -> bool:
    try:
        schemas = schemas_for(provider)
    except Exception:
        return False
    return schemas is not None and len(schemas) == 0


def schemas_for(provider: object | None) -> dict[str, object] | None:
    schemas = getattr(provider, "schemas", None)
    if not callable(schemas):
        return None
    return schemas()


class LocalSchemaProvider:
    def __init__(self, index_path: str | Path = "node_index.json") -> None:
        self.index_path = Path(index_path)
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            self._schemas = self._load()
        return self._schemas

    def _load(self) -> dict[str, NodeSchema]:
        if not self.index_path.exists():
            return {}
        try:
            rows = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SchemaIndexError(self.index_path, exc) from exc
        if isinstance(rows, dict):
            rows = list(rows.values())
        if not isinstance(rows, list):
            return {}
        schemas: dict[str, NodeSchema] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            schema = _schema_from_index_row(row)
            if schema is not None:
                schemas[schema.class_type] = schema
        return schemas


class SourceSchemaProvider:
    """Best-effort INPUT_TYPES reader for installed custom-node source trees."""

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        self.roots = [Path(root) for root in (roots or _default_source_roots())]
        self._schemas: dict[str, NodeSchema | None] = {}

    def get(self, class_type: str) -> NodeSchema | None:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type not in self._schemas:
            self._schemas[class_type] = self._find_schema(class_type)
        return self._schemas[class_type]

    def _find_schema(self, class_type: str) -> NodeSchema | None:
        for path in _candidate_python_files(self.roots, class_type):
            schema = _schema_from_python_source(path, class_type)
            if schema is not None:
                return schema
        return None


class CompositeSchemaProvider:
    def __init__(self, *providers: SchemaProvider) -> None:
        self.providers = providers

    def get(self, class_type: str) -> NodeSchema | None:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        for provider in self.providers:
            schema = provider.get_schema(class_type)
            if schema is not None:
                return schema
        return None


class RuntimeSchemaProvider:
    def __init__(
        self,
        *,
        server_url: str | None = None,
        cache_dir: str | Path = "out/cache",
        log_path: str | Path | None = None,
    ) -> None:
        self.server_url = server_url
        self.cache_path = object_info_cache_path(server_url=server_url, cache_dir=cache_dir)
        self.log_path = log_path
        self._object_info: dict[str, Any] | None = None
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            self._schemas = {
                class_type: _schema_from_object_info(class_type, info)
                for class_type, info in self.object_info().items()
                if isinstance(info, dict)
            }
        return self._schemas

    def object_info(self) -> dict[str, Any]:
        if self._object_info is None:
            cached = load_object_info_cache(self.cache_path)
            if cached is not None:
                self._object_info = cached
            else:
                self._object_info = _run_async(self.object_info_async())
        return self._object_info

    async def object_info_async(self) -> dict[str, Any]:
        cached = load_object_info_cache(self.cache_path)
        if cached is not None:
            return cached
        async with comfy_server(server_url=self.server_url, log_path=self.log_path) as active_url:
            data = await ComfyClient(active_url).object_info()
        write_object_info_cache(self.cache_path, data)
        return data


def get_schema_provider(
    prefer: Literal["runtime", "local", "auto"] = "auto",
    *,
    server_url: str | None = None,
) -> RuntimeSchemaProvider | LocalSchemaProvider | CompositeSchemaProvider:
    if prefer == "runtime":
        return RuntimeSchemaProvider(server_url=server_url)
    if prefer == "local":
        return LocalSchemaProvider()
    if prefer != "auto":
        raise ValueError(f"Unknown schema provider preference: {prefer}")
    if server_url:
        return RuntimeSchemaProvider(server_url=server_url)
    if Path("node_index.json").exists():
        return LocalSchemaProvider()
    if shutil.which("comfyui"):
        return RuntimeSchemaProvider(server_url=server_url)
    return LocalSchemaProvider()


def _schema_from_object_info(class_type: str, info: dict[str, Any]) -> NodeSchema:
    inputs: dict[str, InputSpec] = {}
    input_groups = info.get("input", {})
    if isinstance(input_groups, dict):
        for group_name, group in input_groups.items():
            required = group_name == "required"
            if isinstance(group, dict):
                for name, spec in group.items():
                    inputs[str(name)] = _parse_input_spec(spec, required=required)
    outputs = _parse_outputs(info)
    pack = _first_string(info, "pack", "package", "category")
    return NodeSchema(class_type=class_type, pack=pack, inputs=inputs, outputs=outputs)


def _schema_from_index_row(row: dict[str, Any]) -> NodeSchema | None:
    class_type = _first_string(row, "class_type", "class_name", "name", "id", "node", "display_name")
    if not class_type:
        return None
    pack = _first_string(row, "pack", "package", "source", "category")
    inputs: dict[str, InputSpec] = {}
    raw_inputs = row.get("inputs") or row.get("input")
    if isinstance(raw_inputs, dict):
        if "required" in raw_inputs or "optional" in raw_inputs:
            for group_name, group in raw_inputs.items():
                if isinstance(group, dict):
                    for name, spec in group.items():
                        inputs[str(name)] = _parse_input_spec(spec, required=group_name == "required")
        else:
            for name, spec in raw_inputs.items():
                inputs[str(name)] = _parse_input_spec(spec, required=False)
    elif isinstance(raw_inputs, list):
        for item in raw_inputs:
            if isinstance(item, str):
                inputs[item] = InputSpec(required=False)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                inputs[item["name"]] = _parse_input_spec(item, required=bool(item.get("required", False)))
    return NodeSchema(class_type=class_type, pack=pack, inputs=inputs, outputs=_parse_index_outputs(row))


def _parse_index_outputs(row: dict[str, Any]) -> list[OutputSpec]:
    output_types = row.get("output_types") or row.get("outputs") or row.get("output")
    if isinstance(output_types, str):
        parts = [part.strip() for part in output_types.split(",")]
        return [OutputSpec(type=part) for part in parts if part]
    if isinstance(output_types, list):
        outputs: list[OutputSpec] = []
        for item in output_types:
            if isinstance(item, dict):
                outputs.append(OutputSpec(type=_first_string(item, "type"), name=_first_string(item, "name")))
            elif item is not None:
                outputs.append(OutputSpec(type=str(item)))
        return outputs
    return []


def _parse_input_spec(raw: Any, *, required: bool) -> InputSpec:
    typ: Any = None
    attrs: dict[str, Any] = {}
    choices: list[Any] | None = None
    if isinstance(raw, (list, tuple)) and raw:
        typ = raw[0]
        if isinstance(typ, list):
            choices = list(typ)
            typ = "CHOICE"
        if len(raw) > 1 and isinstance(raw[1], dict):
            attrs = raw[1]
    elif isinstance(raw, dict):
        typ = raw.get("type")
        attrs = raw
        if isinstance(raw.get("choices"), list):
            choices = list(raw["choices"])
    elif isinstance(raw, str):
        typ = raw
    return InputSpec(
        type=str(typ) if typ is not None else None,
        required=required,
        default=attrs.get("default"),
        choices=choices,
        min=attrs.get("min"),
        max=attrs.get("max"),
    )


def _parse_outputs(info: dict[str, Any]) -> list[OutputSpec]:
    raw_outputs = info.get("output") or []
    names = info.get("output_name") or info.get("output_names") or []
    outputs: list[OutputSpec] = []
    if isinstance(raw_outputs, (list, tuple)):
        for index, raw in enumerate(raw_outputs):
            name = names[index] if isinstance(names, (list, tuple)) and index < len(names) else None
            outputs.append(OutputSpec(type=str(raw) if raw is not None else None, name=str(name) if name else None))
    return outputs


def _default_source_roots() -> list[Path]:
    roots = [
        Path("custom_nodes"),
        Path("vendor") / "ComfyUI",
    ]
    tmp = Path("/tmp")
    if tmp.exists():
        roots.extend(sorted(path for path in tmp.glob("ComfyUI-*") if path.is_dir()))
    return roots


def _candidate_python_files(roots: list[Path], class_type: str) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        direct = root / f"{class_type}.py"
        if direct.is_file():
            candidates.append(direct)
        try:
            for path in root.rglob("*.py"):
                if any(part in {".git", "__pycache__", "venv", ".venv"} for part in path.parts):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if f"class {class_type}" in text or f'"{class_type}"' in text or f"'{class_type}'" in text:
                    candidates.append(path)
        except OSError:
            continue
    return sorted(dict.fromkeys(candidates))


def _schema_from_python_source(path: Path, class_type: str) -> NodeSchema | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_type:
            class_values = _class_literal_values(node)
            input_types = _input_types_return(node, class_values)
            if not isinstance(input_types, dict):
                return None
            return _schema_from_object_info(
                class_type,
                {
                    "pack": path.parent.name,
                    "input": input_types,
                    "output": _class_literal_attr(node, "RETURN_TYPES") or [],
                    "output_name": _class_literal_attr(node, "RETURN_NAMES") or [],
                },
            )
    return None


def _class_literal_values(node: ast.ClassDef) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for stmt in node.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.target is not None:
            targets = [stmt.target]
            value = stmt.value
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                parsed = _literal_eval_node(value, values)
                if parsed is not _UNPARSEABLE:
                    values[target.id] = parsed
    return values


def _class_literal_attr(node: ast.ClassDef, name: str) -> Any:
    values = _class_literal_values(node)
    return values.get(name)


def _input_types_return(node: ast.ClassDef, class_values: dict[str, Any]) -> Any:
    for stmt in node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name != "INPUT_TYPES":
            continue
        for child in ast.walk(stmt):
            if isinstance(child, ast.Return) and child.value is not None:
                parsed = _literal_eval_node(child.value, class_values)
                return None if parsed is _UNPARSEABLE else parsed
    return None


_UNPARSEABLE = object()


def _literal_eval_node(node: ast.AST, class_values: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        values = [_literal_eval_node(item, class_values) for item in node.elts]
        return _UNPARSEABLE if _UNPARSEABLE in values else values
    if isinstance(node, ast.Tuple):
        values = [_literal_eval_node(item, class_values) for item in node.elts]
        return _UNPARSEABLE if _UNPARSEABLE in values else tuple(values)
    if isinstance(node, ast.Dict):
        out: dict[Any, Any] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=False):
            if key_node is None:
                return _UNPARSEABLE
            key = _literal_eval_node(key_node, class_values)
            value = _literal_eval_node(value_node, class_values)
            if key is _UNPARSEABLE:
                return _UNPARSEABLE
            if value is _UNPARSEABLE:
                continue
            out[key] = value
        return out
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.attr in class_values:
        return class_values[node.attr]
    if isinstance(node, ast.Name):
        return class_values.get(node.id, _UNPARSEABLE)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_eval_node(node.operand, class_values)
        if isinstance(value, (int, float)):
            return -value
    return _UNPARSEABLE


def _first_string(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise RuntimeError("RuntimeSchemaProvider synchronous access cannot run inside an active event loop; use object_info_async().")
