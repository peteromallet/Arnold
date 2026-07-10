"""S4 Step 10 — provenance classifier for `exec_module` loader call sites.

Used by ``vibecomfy/scratchpad_loader.py`` and ``vibecomfy/registry/ready.py``
to decide, *before* ``spec.loader.exec_module(...)`` fires, whether the source
file lives under a trusted in-repo directory (``out/scratchpads/`` or the
built-in ``ready_templates/`` directory) or is an external, attacker-controlled
path.

Classification uses ``Path.resolve()`` + ``pathlib.Path.is_relative_to``
against the resolved trusted-directory paths. This defeats traversal
(``out/scratchpads/../../tmp/evil.py``) and symlink-escape attacks that a
prefix-string match would miss.
"""

from __future__ import annotations

from pathlib import Path

from vibecomfy.security.provenance import Provenance
from vibecomfy.utils import find_repo_root


def _trusted_roots() -> list[Path]:
    """Resolved trusted-directory roots for exec_module loaders.

    Returns the resolved ``repo_root / "out" / "scratchpads"`` and
    ``repo_root / "ready_templates"`` directories. Both are resolved with
    ``Path.resolve()`` so a later ``is_relative_to`` comparison catches
    traversal / symlink escapes.
    """
    repo = find_repo_root()
    roots: list[Path] = []
    for candidate in (repo / "out" / "scratchpads", repo / "ready_templates"):
        try:
            roots.append(candidate.resolve())
        except OSError:
            continue
    return roots


def _provenance_for_path(path: Path) -> Provenance:
    """Classify an exec_module source file path as trusted or untrusted.

    Returns ``"agent_authored"`` if ``path.resolve()`` is under either of the
    trusted roots, otherwise ``"untrusted_source"``. Never uses prefix-string
    matching.
    """
    try:
        resolved = Path(path).resolve()
    except OSError:
        return "untrusted_source"
    for root in _trusted_roots():
        try:
            if resolved.is_relative_to(root):
                return "agent_authored"
        except (ValueError, OSError):
            continue
    return "untrusted_source"


__all__ = ["_provenance_for_path"]
