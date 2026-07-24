"""Arnold runtime error base class.

This module defines the minimal, opinion-free error carrier that any
Arnold runtime component (and any plugin — including Megaplan) can
raise or catch without importing plugin-specific vocabulary.

``ArnoldError`` carries only ``code``, ``message``, and ``exit_code``.
Plugin-specific fields such as ``valid_next`` and ``extra`` belong on
plugin-owned subclasses (e.g. ``CliError``), **not** on this base.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

__all__ = ["ArnoldError"]


class ArnoldError(Exception):
    """Minimal runtime error carrier.

    Explicit attributes (no hidden ``args`` tuple)::

        * ``code``       — stable machine-readable error code (``str``).
        * ``message``    — human-readable diagnostic.
        * ``exit_code``  — suggested process exit code (default ``1``).

    Plugin subclasses (e.g. ``CliError``) may add further attributes
    but **must** forward ``code``, ``message``, and ``exit_code`` to
    this constructor so the base contract is always honoured.
    """

    def __init__(self, code: str, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
