"""Resource lookup helpers for checkout and installed-package conformance tests."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[3]


def checkout_path(*parts: str) -> Path:
    """Return a source checkout path for negative filesystem-only checks."""

    return REPO_ROOT.joinpath(*parts)


def resource_text(package: str, name: str) -> str:
    """Read a package resource without assuming a checkout path."""

    return resources.files(package).joinpath(name).read_text(encoding="utf-8")


@contextmanager
def resource_path(package: str, name: str) -> Iterator[Path]:
    """Yield a concrete path for resources that APIs need as files."""

    traversable = resources.files(package).joinpath(name)
    with resources.as_file(traversable) as path:
        yield path


def resource_exists(package: str, name: str) -> bool:
    """Return whether a package resource exists."""

    return resources.files(package).joinpath(name).is_file()
