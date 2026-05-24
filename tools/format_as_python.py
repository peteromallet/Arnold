"""Compatibility wrapper for the packaged ready-template Python emitter.

The live emitter implementation lives under `vibecomfy.porting`. This module
preserves the historical `tools.format_as_python` import and CLI surface used by
ready-template generation.
"""

from __future__ import annotations

import sys

from vibecomfy.porting import emitter as _emitter
from vibecomfy.porting import loader as _loader


format_as_python = _emitter.format_as_python
_build_workflow_for = _loader.build_workflow_for
main = _loader.main


__all__ = [
    "_build_workflow_for",
    "format_as_python",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
