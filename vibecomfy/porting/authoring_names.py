from __future__ import annotations

import keyword
import re
from typing import Iterable


def _base_constructor_name(class_type: str) -> str:
    if class_type.isidentifier() and not keyword.iskeyword(class_type):
        return class_type
    name = re.sub(r"\W", "_", class_type)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "Node"
    if name[0].isdigit():
        name = f"N_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def constructor_name_for_class_type(class_type: str) -> str:
    """Return the base Python edit-surface constructor for a ComfyUI class type."""
    return _base_constructor_name(class_type)


def constructor_aliases_for_class_types(class_types: Iterable[str]) -> dict[str, str]:
    """Return deterministic, collision-free constructor aliases by raw class type."""
    aliases: dict[str, str] = {}
    used: set[str] = set()
    for class_type in sorted({str(item) for item in class_types}):
        base = _base_constructor_name(class_type)
        alias = base
        index = 2
        while alias in used:
            alias = f"{base}_{index}"
            index += 1
        used.add(alias)
        aliases[class_type] = alias
    return aliases


def constructor_aliases_for_schema_provider(schema_provider: object | None) -> dict[str, str]:
    """Return constructor aliases for every class type visible from a schema provider."""
    from vibecomfy.schema import schemas_for

    schemas = schemas_for(schema_provider)
    if not schemas:
        return {}
    return constructor_aliases_for_class_types(str(class_type) for class_type in schemas)


def class_type_for_constructor_name(schema_provider: object | None, constructor_name: str) -> str | None:
    """Resolve an edit-surface constructor alias back to one raw Comfy class type."""
    aliases = constructor_aliases_for_schema_provider(schema_provider)
    matches = [class_type for class_type, alias in aliases.items() if alias == constructor_name]
    if len(matches) != 1:
        return None
    return matches[0]
