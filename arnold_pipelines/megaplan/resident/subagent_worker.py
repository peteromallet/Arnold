"""Process entry point for a resident-managed provider agent supervisor.

Keeping the entry point separate prevents ``python -m`` from re-executing the
``subagent`` module after the resident package imports it for the tool surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .subagent import _run_codex_manifest, _run_managed_manifest


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--run-managed":
        return _run_managed_manifest(Path(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--run-codex":
        return _run_codex_manifest(Path(sys.argv[2]))
    raise SystemExit(
        "usage: python -m arnold_pipelines.megaplan.resident.subagent_worker "
        "--run-managed MANIFEST"
    )


if __name__ == "__main__":
    raise SystemExit(main())
