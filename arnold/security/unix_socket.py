"""Shared Unix-domain socket diagnostics for the security broker."""

from __future__ import annotations

import errno


def is_unix_socket_path_too_long(error: OSError) -> bool:
    """Return whether *error* reports an AF_UNIX pathname limit."""

    return error.errno == errno.ENAMETOOLONG or "path too long" in str(error).lower()


__all__ = ["is_unix_socket_path_too_long"]
