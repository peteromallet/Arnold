"""JSON-Schema-based validator for TimelineConfig.

`strict=False` is the only Sprint 1 mode (SD-015 strict-mode lands Sprint 5).
This shells through to `jsonschema` against the artifact emitted by Zod.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = Path(__file__).with_name("timeline.schema.json")


@functools.lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    if not _SCHEMA_PATH.is_file():
        raise FileNotFoundError(
            f"timeline.schema.json missing at {_SCHEMA_PATH}; run `npm run build`"
        )
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_timeline(config: Any, *, strict: bool = False) -> None:
    """Validate a TimelineConfig payload against the shared JSON Schema.

    `strict=False` is the documented Sprint 1 mode; the canonical schema permits
    Banodoco-extension fields that Reigh's runtime ignores. `strict=True` is a
    placeholder for Sprint 5's tightening.
    """
    schema = load_schema()
    if strict:
        # Sprint 5 will add additional registry-level checks here.
        jsonschema.validate(config, schema)
        return
    jsonschema.validate(config, schema)
