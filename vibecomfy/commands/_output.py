from __future__ import annotations

import json as json_module
from dataclasses import asdict, is_dataclass
from typing import Any, Callable


def emit(payload: Any, *, json: bool, text_renderer: Callable[[Any], str | None]) -> int:
    payload = jsonable(payload)
    if json:
        print(json_module.dumps(payload, indent=2, sort_keys=True))
    else:
        text = text_renderer(payload)
        if text is not None:
            print(text)
    return 0


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    return value


__all__ = ["emit", "jsonable"]
