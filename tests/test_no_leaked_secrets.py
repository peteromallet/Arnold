from __future__ import annotations

import subprocess
from pathlib import Path


LEAKED_SUPABASE_JWT_PREFIX = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSI"
)


def _repo_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        ignored_dirs = {
            ".git",
            ".megaplan",
            ".pytest_cache",
            "__pycache__",
            ".venv",
            "venv",
        }
        ignored_files = {".env", ".env.local"}
        return [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.name not in ignored_files
            and not any(part in ignored_dirs for part in path.relative_to(root).parts)
        ]

    return [root / line for line in result.stdout.splitlines() if line]


def test_leaked_supabase_service_role_jwt_prefix_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in _repo_files(root):
        try:
            content = path.read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            continue

        if LEAKED_SUPABASE_JWT_PREFIX in content:
            offenders.append(str(path.relative_to(root)))

    assert not offenders, "Leaked Supabase JWT prefix found in tracked files: " + ", ".join(offenders)
