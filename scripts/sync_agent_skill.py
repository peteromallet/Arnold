#!/usr/bin/env python3
"""Sync local agent skill files from the canonical CLAUDE.md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "CLAUDE.md"
BOOTSTRAP = ROOT / "AGENTS.md"
COPY_TARGETS = ()
LOCAL_COPY_TARGETS = (
    ROOT / ".claude" / "skills" / "vibecomfy" / "SKILL.md",
)
SYMLINK_TARGETS = {}
METADATA = ROOT / "agents" / "openai.yaml"
EXPECTED_METADATA = """interface:
  display_name: "VibeComfy"
  short_description: "ComfyUI workflow templates and RunPod validation"
  default_prompt: "Use $vibecomfy to load, edit, validate, or run ComfyUI workflows through Python ready templates."
policy:
  allow_implicit_invocation: true
"""


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _read_source() -> str:
    if not SOURCE.exists():
        raise SystemExit("CLAUDE.md is missing")
    content = SOURCE.read_text(encoding="utf-8")
    if not content.startswith("---\n") or "name: vibecomfy" not in content:
        raise SystemExit("CLAUDE.md must be the canonical VibeComfy skill with frontmatter")
    return content


def _check_bootstrap() -> str | None:
    if not BOOTSTRAP.exists():
        return "AGENTS.md is missing"
    content = BOOTSTRAP.read_text(encoding="utf-8")
    if "canonical long-form agent instructions" not in content or "CLAUDE.md" not in content:
        return "AGENTS.md should be a short bootstrap pointing to CLAUDE.md"
    if "name: vibecomfy" in content:
        return "AGENTS.md should not duplicate the canonical VibeComfy skill frontmatter"
    return None


def _check_copy(path: Path, expected: str) -> str | None:
    if not path.exists():
        return f"{_relative(path)} is missing"
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return f"{_relative(path)} is stale"
    return None


def _check_symlink(path: Path, expected_target: str) -> str | None:
    if not path.is_symlink():
        return f"{_relative(path)} should be a symlink to {expected_target}"
    actual = path.readlink()
    if str(actual) != expected_target:
        return f"{_relative(path)} points to {actual}, expected {expected_target}"
    return None


def check() -> int:
    source = _read_source()
    errors = []
    if error := _check_bootstrap():
        errors.append(error)
    errors.extend(error for target in COPY_TARGETS if (error := _check_copy(target, source)))
    errors.extend(error for target, link in SYMLINK_TARGETS.items() if (error := _check_symlink(target, link)))
    metadata_error = _check_copy(METADATA, EXPECTED_METADATA)
    if metadata_error:
        errors.append(metadata_error)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("Run: python3 scripts/sync_agent_skill.py --apply", file=sys.stderr)
        return 1
    print("Agent skill files are in sync.")
    return 0


def apply() -> int:
    source = _read_source()
    for target in (*COPY_TARGETS, *LOCAL_COPY_TARGETS):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        print(f"synced {_relative(target)}")
    for target, link in SYMLINK_TARGETS.items():
        if target.exists() or target.is_symlink():
            if target.is_symlink() and str(target.readlink()) == link:
                print(f"kept {_relative(target)} -> {link}")
                continue
            raise SystemExit(f"{_relative(target)} exists but is not the expected symlink")
        target.symlink_to(link)
        print(f"created {_relative(target)} -> {link}")
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    METADATA.write_text(EXPECTED_METADATA, encoding="utf-8")
    print(f"synced {_relative(METADATA)}")
    return check()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="update mirrored skill files")
    args = parser.parse_args(argv)
    return apply() if args.apply else check()


if __name__ == "__main__":
    raise SystemExit(main())
