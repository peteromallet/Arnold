"""Evidence guard for mutation-safe execute model advancement."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceEntry:
    path: str
    kind: str
    mode: int
    digest: str


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    root: Path
    entries: tuple[WorkspaceEntry, ...]
    digest: str
    error: str | None = None

    @property
    def proof_available(self) -> bool:
        return self.error is None

    @classmethod
    def capture(cls, root: Path) -> "WorkspaceSnapshot":
        resolved = root.expanduser().resolve()
        try:
            proc = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "-z",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                cwd=resolved,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return cls(resolved, (), "", f"git_inventory_failed:{type(exc).__name__}")
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", errors="replace").strip()[:240]
            return cls(resolved, (), "", f"git_inventory_failed:{detail or proc.returncode}")
        try:
            status_proc = subprocess.run(
                [
                    "git",
                    "status",
                    "--porcelain=v2",
                    "-z",
                    "--untracked-files=all",
                    "--ignore-submodules=none",
                ],
                cwd=resolved,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return cls(resolved, (), "", f"git_status_failed:{type(exc).__name__}")
        if status_proc.returncode != 0:
            detail = status_proc.stderr.decode("utf-8", errors="replace").strip()[:240]
            return cls(resolved, (), "", f"git_status_failed:{detail or status_proc.returncode}")

        paths = sorted(
            {
                item.decode("utf-8", errors="surrogateescape")
                for item in proc.stdout.split(b"\0")
                if item
            }
        )
        entries: list[WorkspaceEntry] = []
        aggregate = hashlib.sha256()
        try:
            for relative in paths:
                path = resolved / relative
                if path.is_symlink():
                    kind = "symlink"
                    data = os.readlink(path).encode("utf-8", errors="surrogateescape")
                    mode = path.lstat().st_mode
                elif path.is_file():
                    kind = "file"
                    mode = path.stat().st_mode
                    file_hash = hashlib.sha256()
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            file_hash.update(chunk)
                    data = file_hash.digest()
                elif path.exists():
                    kind = "other"
                    mode = path.lstat().st_mode
                    data = b""
                else:
                    kind = "missing"
                    mode = 0
                    data = b""
                digest = hashlib.sha256(data).hexdigest()
                entry = WorkspaceEntry(relative, kind, mode, digest)
                entries.append(entry)
                aggregate.update(relative.encode("utf-8", errors="surrogateescape"))
                aggregate.update(b"\0")
                aggregate.update(kind.encode("ascii"))
                aggregate.update(b"\0")
                aggregate.update(str(mode).encode("ascii"))
                aggregate.update(b"\0")
                aggregate.update(digest.encode("ascii"))
                aggregate.update(b"\0")
            # The content inventory above catches tracked and untracked file
            # bytes. Porcelain-v2 additionally proves that index state and
            # nested submodule state did not change between attempts.
            status_digest = hashlib.sha256(status_proc.stdout).hexdigest()
            status_entry = WorkspaceEntry(
                "@git-status/index-and-submodules",
                "git-metadata",
                0,
                status_digest,
            )
            entries.append(status_entry)
            aggregate.update(status_entry.path.encode("ascii"))
            aggregate.update(b"\0git-metadata\0" + status_digest.encode("ascii") + b"\0")
        except OSError as exc:
            return cls(
                resolved,
                tuple(entries),
                aggregate.hexdigest(),
                f"workspace_hash_failed:{type(exc).__name__}:{exc}",
            )
        return cls(resolved, tuple(entries), aggregate.hexdigest())

    def compare(self, current: "WorkspaceSnapshot") -> "MutationSafetyEvidence":
        if self.root != current.root:
            return MutationSafetyEvidence(
                safe=False,
                baseline_digest=self.digest,
                current_digest=current.digest,
                changed_paths=(),
                error="workspace_root_changed",
            )
        if not self.proof_available or not current.proof_available:
            return MutationSafetyEvidence(
                safe=False,
                baseline_digest=self.digest,
                current_digest=current.digest,
                changed_paths=(),
                error=self.error or current.error or "mutation_proof_unavailable",
            )
        before = {entry.path: entry for entry in self.entries}
        after = {entry.path: entry for entry in current.entries}
        changed = tuple(
            sorted(
                path
                for path in before.keys() | after.keys()
                if before.get(path) != after.get(path)
            )
        )
        return MutationSafetyEvidence(
            safe=not changed and self.digest == current.digest,
            baseline_digest=self.digest,
            current_digest=current.digest,
            changed_paths=changed,
            error=None,
        )


@dataclass(frozen=True, slots=True)
class MutationSafetyEvidence:
    safe: bool
    baseline_digest: str
    current_digest: str
    changed_paths: tuple[str, ...]
    error: str | None = None

    def to_receipt(self) -> dict[str, object]:
        return {
            "guard": "git_workspace_and_index_content_v2",
            "safe": self.safe,
            "baseline_digest": self.baseline_digest,
            "current_digest": self.current_digest,
            "changed_paths": list(self.changed_paths),
            "error": self.error,
        }


__all__ = ["MutationSafetyEvidence", "WorkspaceEntry", "WorkspaceSnapshot"]
