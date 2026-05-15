from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class IndexReadError(Exception):
    def __init__(self, path: Path, cause: Exception) -> None:
        super().__init__(str(path))
        self.path = path
        self.cause = cause


def read_index_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexReadError(path, exc) from exc


def print_index_error(exc: IndexReadError) -> None:
    print(
        f"{exc.path} could not be read ({type(exc.cause).__name__}: {exc.cause}); "
        "run `vibecomfy sources sync` to rebuild indexes.",
        file=sys.stderr,
    )
