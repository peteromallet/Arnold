#!/usr/bin/env python3
"""Deterministically frame the Batch 3 attempt-3 classified manifest.

This Oracle-only tool frames only the explicit NBF04/NBF05 manifest.  It uses
fixed Git configuration and length-prefixed path/status/raw-diff records, so
the aggregate is reproducible and cannot accidentally include Oracle output.
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

MAGIC = b"NBF-BATCH3-DIFF-V1\0"
ABS_HEADER = re.compile(rb"(?:^|[ \t])(?:a|b)/(?:/(?!dev/null(?:[ \t]|$))|[A-Za-z]:[\\/])")


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})
    return env


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-c", "diff.external=", "-c", "diff.renames=false", *args],
        capture_output=True, check=False, env=_env(),
    )


def _manifest(path: Path) -> tuple[list[tuple[str, str]], bytes]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        raise SystemExit("manifest must be newline-terminated")
    rows: list[tuple[str, str]] = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"NBF04", "NBF05"}:
            raise SystemExit(f"invalid classified manifest row {number}")
        classification, item = fields
        candidate = Path(item)
        if candidate.is_absolute() or "\\" in item or item != candidate.as_posix() or not item:
            raise SystemExit(f"manifest path is not relative POSIX: {item!r}")
        rows.append((item, classification))
    paths = [item for item, _ in rows]
    if not rows or paths != sorted(paths) or len(set(paths)) != len(paths):
        raise SystemExit("manifest paths must be sorted, unique, and non-empty")
    return rows, raw


def _tracked(path: str) -> bool:
    return _git("ls-files", "--error-unmatch", "--", path).returncode == 0


def _raw_diff(base: str, path: str, tracked: bool) -> tuple[str, bytes]:
    common = ("diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv", "--no-renames", "--src-prefix=a/", "--dst-prefix=b/")
    args = common + ((base, "--", path) if tracked else ("--no-index", "/dev/null", path))
    result = _git(*args)
    allowed = {0} if tracked else {0, 1}
    if result.returncode not in allowed:
        raise SystemExit(f"diff failed for {path}: {result.stderr.decode(errors='replace')}")
    if ABS_HEADER.search(result.stdout):
        raise SystemExit(f"absolute diff header found for {path}")
    return ("T" if tracked else "U"), result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows, manifest_bytes = _manifest(args.manifest)
    aggregate = hashlib.sha256(MAGIC)
    records = []
    total = 0
    for path, classification in rows:
        status, data = _raw_diff(args.base, path, _tracked(path))
        path_bytes = path.encode("utf-8")
        aggregate.update(struct.pack(">Q", len(path_bytes)))
        aggregate.update(path_bytes)
        aggregate.update(status.encode("ascii"))
        aggregate.update(struct.pack(">Q", len(data)))
        aggregate.update(data)
        total += len(data)
        records.append({"path": path, "classification": classification, "status": status, "diff_bytes": len(data), "diff_sha256": hashlib.sha256(data).hexdigest()})
    output = {
        "format": "NBF-BATCH3-DIFF-V1",
        "git_version": _git("--version").stdout.decode("utf-8").strip(),
        "base": args.base,
        "manifest": {"path": args.manifest.as_posix(), "sha256": hashlib.sha256(manifest_bytes).hexdigest(), "bytes": len(manifest_bytes), "count": len(rows)},
        "framing": {"magic_hex": MAGIC.hex(), "path_length": "uint64_be", "status": {"tracked": "T", "untracked": "U"}, "diff_length": "uint64_be", "absolute_header_normalization": "none; fail closed"},
        "paths": records,
        "total_diff_bytes": total,
        "aggregate_sha256": aggregate.hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
