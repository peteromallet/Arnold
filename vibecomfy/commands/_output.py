from __future__ import annotations

import json as json_module
from typing import Any, Callable


def emit(payload: Any, *, json: bool, text_renderer: Callable[[Any], str | None]) -> int:
    if json:
        print(json_module.dumps(payload, indent=2, sort_keys=True))
    else:
        text = text_renderer(payload)
        if text is not None:
            print(text)
    return 0


__all__ = ["emit"]
