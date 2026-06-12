#!/usr/bin/env python3
"""Check and optionally install the canonical VibeComfy agent skill."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "agent-skill" / "SKILL.md"
CLAUDE_BOOTSTRAP = ROOT / "CLAUDE.md"
BOOTSTRAP = ROOT / "AGENTS.md"
COPY_TARGETS = ()
LOCAL_COPY_TARGETS = ()
SYMLINK_TARGETS = {}
USER_SKILL_SOURCE = SOURCE.parent
USER_SKILL_TARGET_DIRS = (
    Path.home() / ".claude" / "skills",
    Path.home() / ".codex" / "skills",
    Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "skills",
)
CODEX_AGENTS = Path.home() / ".codex" / "AGENTS.md"
SKILLSINKER_BEGIN = "<!-- vibecomfy:skillsinker:begin -->"
SKILLSINKER_END = "<!-- vibecomfy:skillsinker:end -->"
CLAUDE_BOOTSTRAP_TEXT = """# VibeComfy Agent Guide

The canonical VibeComfy agent skill lives at
[`docs/agent-skill/SKILL.md`](docs/agent-skill/SKILL.md).

Run `python scripts/sync_agent_skill.py --apply` after editing it to refresh this
bootstrap, and `python scripts/sync_agent_skill.py --install-user` to symlink the
skill into local Claude, Codex, and Hermes skill directories.
"""


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _read_source() -> str:
    if not SOURCE.exists():
        raise SystemExit("docs/agent-skill/SKILL.md is missing")
    content = SOURCE.read_text(encoding="utf-8")
    if not content.startswith("---\n") or "name: vibecomfy" not in content:
        raise SystemExit("docs/agent-skill/SKILL.md must be the canonical VibeComfy skill with frontmatter")
    return content


def _check_bootstrap() -> str | None:
    if not BOOTSTRAP.exists():
        return "AGENTS.md is missing"
    content = BOOTSTRAP.read_text(encoding="utf-8")
    if "canonical long-form agent instructions" not in content or "docs/agent-skill/SKILL.md" not in content:
        return "AGENTS.md should be a short bootstrap pointing to docs/agent-skill/SKILL.md"
    if "name: vibecomfy" in content:
        return "AGENTS.md should not duplicate the canonical VibeComfy skill frontmatter"
    return None


def _check_claude_bootstrap() -> str | None:
    if not CLAUDE_BOOTSTRAP.exists():
        return "CLAUDE.md bootstrap is missing"
    content = CLAUDE_BOOTSTRAP.read_text(encoding="utf-8")
    if content != CLAUDE_BOOTSTRAP_TEXT:
        return "CLAUDE.md bootstrap is stale"
    if "name: vibecomfy" in content:
        return "CLAUDE.md should not duplicate the canonical VibeComfy skill frontmatter"
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
    if error := _check_claude_bootstrap():
        errors.append(error)
    errors.extend(error for target in COPY_TARGETS if (error := _check_copy(target, source)))
    errors.extend(error for target, link in SYMLINK_TARGETS.items() if (error := _check_symlink(target, link)))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("Run: python3 scripts/sync_agent_skill.py --apply", file=sys.stderr)
        return 1
    print("Agent skill files are in sync.")
    return 0


def apply() -> int:
    source = _read_source()
    CLAUDE_BOOTSTRAP.write_text(CLAUDE_BOOTSTRAP_TEXT, encoding="utf-8")
    print(f"synced {_relative(CLAUDE_BOOTSTRAP)}")
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
    return check()


class SkillSinker:
    """Install the VibeComfy skill into local agent harness surfaces."""

    def __init__(self, source: Path, codex_agents: Path) -> None:
        self.source = source
        self.codex_agents = codex_agents

    def install(self) -> None:
        self._link_skill_dirs()
        self._rewrite_codex_agents()

    def _link_skill_dirs(self) -> None:
        if not self.source.exists():
            raise SystemExit(f"{_relative(self.source)} is missing")
        for target_dir in USER_SKILL_TARGET_DIRS:
            if not target_dir.exists():
                print(f"skipped {target_dir} (parent missing)")
                continue
            target = target_dir / "vibecomfy"
            if target.is_symlink() and target.resolve() == self.source.resolve():
                print(f"kept {target} -> {self.source}")
                continue
            if target.exists() or target.is_symlink():
                raise SystemExit(f"{target} exists; remove it or install manually")
            target.symlink_to(self.source, target_is_directory=True)
            print(f"linked {target} -> {self.source}")

    def _rewrite_codex_agents(self) -> None:
        if not self.codex_agents.parent.exists():
            print(f"skipped {self.codex_agents} (parent missing)")
            return
        block = self._render_codex_block()
        existing = self.codex_agents.read_text(encoding="utf-8") if self.codex_agents.exists() else ""
        updated = self._merge_block(existing, block)
        if updated == existing:
            print(f"kept {self.codex_agents} SkillSinker block")
            return
        self.codex_agents.write_text(updated, encoding="utf-8")
        print(f"updated {self.codex_agents} SkillSinker block")

    def _render_codex_block(self) -> str:
        return (
            f"{SKILLSINKER_BEGIN}\n"
            "# VibeComfy skill\n\n"
            f"- `vibecomfy` ({self.source}): Use VibeComfy to load, edit, validate, port, and run ComfyUI workflows through Python ready templates.\n"
            f"{SKILLSINKER_END}"
        )

    @staticmethod
    def _merge_block(existing: str, block: str) -> str:
        if SKILLSINKER_BEGIN in existing and SKILLSINKER_END in existing:
            before, _, rest = existing.partition(SKILLSINKER_BEGIN)
            _, _, after = rest.partition(SKILLSINKER_END)
            return f"{before}{block}{after}"
        if not existing:
            return block + "\n"
        suffix = "" if existing.endswith("\n") else "\n"
        return f"{existing}{suffix}\n{block}\n"


def install_user() -> int:
    apply_result = apply()
    if apply_result != 0:
        return apply_result
    SkillSinker(USER_SKILL_SOURCE, CODEX_AGENTS).install()
    return check()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="update mirrored skill files")
    parser.add_argument(
        "--install-user",
        action="store_true",
        help="use SkillSinker to symlink the local skill into detected harnesses and update Codex AGENTS.md",
    )
    args = parser.parse_args(argv)
    if args.install_user:
        return install_user()
    return apply() if args.apply else check()


if __name__ == "__main__":
    raise SystemExit(main())
