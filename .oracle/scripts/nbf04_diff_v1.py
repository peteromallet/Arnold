#!/usr/bin/env python3
"""Emit the deterministic NBF04-DIFF-V1 identity for an explicit manifest.

The manifest is UTF-8, sorted, unique, relative POSIX paths with one final
newline.  Tracked paths use ``git diff`` against BASE; untracked paths use
``git diff --no-index /dev/null PATH``.  The script runs from the repository
root and supplies fixed prefixes, so Git cannot put an absolute checkout path
in a header.  Absolute-header normalization is therefore intentionally not
performed: an unexpected absolute header fails closed instead of being
silently rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path


MAGIC = b"NBF04-DIFF-V1\0"
_ABS_HEADER = re.compile(rb"(?:^|[ \t])(?:a|b)/(?:/(?!dev/null(?:[ \t]|$))|[A-Za-z]:[\\/])")


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    return env


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "-c",
            "diff.external=",
            "-c",
            "diff.renames=false",
            *args,
        ],
        check=False,
        capture_output=True,
        env=_env(),
    )


def _manifest(path: Path) -> tuple[list[str], bytes]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        raise SystemExit("manifest must be newline-terminated")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"manifest is not UTF-8: {exc}") from exc
    paths = text.splitlines()
    if not paths or any(not item for item in paths):
        raise SystemExit("manifest contains an empty path")
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise SystemExit("manifest must be sorted and unique")
    for item in paths:
        candidate = Path(item)
        if candidate.is_absolute() or "\\" in item or item != candidate.as_posix():
            raise SystemExit(f"manifest path is not relative POSIX: {item!r}")
    return paths, raw


def _tracked(path: str) -> bool:
    result = _git("ls-files", "--error-unmatch", "--", path)
    return result.returncode == 0


def _raw_diff(base: str, path: str, tracked: bool) -> tuple[str, bytes]:
    common = (
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--src-prefix=a/",
        "--dst-prefix=b/",
    )
    if tracked:
        result = _git(*common, base, "--", path)
        if result.returncode != 0:
            raise SystemExit(f"tracked diff failed for {path}: {result.stderr.decode(errors='replace')}")
        status = "T"
    else:
        result = _git(*common, "--no-index", "/dev/null", path)
        if result.returncode not in (0, 1):
            raise SystemExit(f"untracked diff failed for {path}: {result.stderr.decode(errors='replace')}")
        status = "U"
    if _ABS_HEADER.search(result.stdout):
        raise SystemExit(f"absolute diff header found for {path}; refusing normalization")
    return status, result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="explicit Git base object")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    paths, manifest_bytes = _manifest(args.manifest)
    aggregate = hashlib.sha256(MAGIC)
    records: list[dict[str, object]] = []
    total = 0
    for path in paths:
        status, data = _raw_diff(args.base, path, _tracked(path))
        path_bytes = path.encode("utf-8")
        aggregate.update(struct.pack(">Q", len(path_bytes)))
        aggregate.update(path_bytes)
        aggregate.update(status.encode("ascii"))
        aggregate.update(struct.pack(">Q", len(data)))
        aggregate.update(data)
        total += len(data)
        records.append(
            {
                "path": path,
                "status": status,
                "diff_bytes": len(data),
                "diff_sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    version = _git("--version")
    git_version = version.stdout.decode("utf-8").strip()
    output = {
        "format": "NBF04-DIFF-V1",
        "git_version": git_version,
        "base": args.base,
        "manifest": {
            "path": args.manifest.as_posix(),
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "bytes": len(manifest_bytes),
            "count": len(paths),
        },
        "framing": {
            "magic_hex": MAGIC.hex(),
            "path_length": "uint64_be",
            "status": {"tracked": "T", "untracked": "U"},
            "diff_length": "uint64_be",
            "absolute_header_normalization": "none; fail closed",
        },
        "paths": records,
        "total_diff_bytes": total,
        "aggregate_sha256": aggregate.hexdigest(),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
