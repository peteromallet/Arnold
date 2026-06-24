"""AgentBox canonical repository registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from agentbox.config import AgentBoxConfig


REPOS_REGISTRY_FILENAME = "repos.json"
_REPO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class AgentBoxRepoError(ValueError):
    """Raised when a registered repository is invalid."""


class AgentBoxRepoNotFound(KeyError):
    """Raised when a registered repository name is unknown."""


@dataclass(frozen=True)
class RegisteredRepo:
    """Persistent metadata for one canonical checkout."""

    name: str
    path: Path
    default_ref: str = "HEAD"
    remote_url: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RegisteredRepo":
        return cls(
            name=str(data["name"]),
            path=Path(str(data["path"])),
            default_ref=str(data.get("default_ref") or "HEAD"),
            remote_url=(
                None if data.get("remote_url") is None else str(data["remote_url"])
            ),
        )


@dataclass(frozen=True)
class RepoStatus:
    """CLI-ready validation projection for a registered repo."""

    name: str
    path: str
    default_ref: str
    remote_url: str | None
    valid: bool
    reason: str | None = None
    head_sha: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def repos_registry_path(config: AgentBoxConfig) -> Path:
    """Return the JSON registry path for ``config``."""

    return config.workspace_root / REPOS_REGISTRY_FILENAME


def register_repo(
    config: AgentBoxConfig,
    name: str,
    *,
    path: Path | str | None = None,
    default_ref: str = "HEAD",
    remote_url: str | None = None,
) -> RegisteredRepo:
    """Validate and persist one canonical checkout under ``repos_root``."""

    repo_path = Path(path) if path is not None else config.repos_root / name
    record = RegisteredRepo(
        name=name,
        path=_validate_canonical_checkout(config, name, repo_path),
        default_ref=default_ref,
        remote_url=remote_url,
    )
    records = {repo.name: repo for repo in list_repos(config)}
    records[name] = record
    _write_registry(config, records)
    return record


def get_repo(config: AgentBoxConfig, name: str) -> RegisteredRepo:
    """Load one registered repo by name."""

    for repo in list_repos(config):
        if repo.name == name:
            return repo
    raise AgentBoxRepoNotFound(name)


def list_repos(config: AgentBoxConfig) -> tuple[RegisteredRepo, ...]:
    """List registered repos sorted by name."""

    path = repos_registry_path(config)
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise AgentBoxRepoError("repos.json must be a JSON object")
    repos = raw.get("repos", [])
    if not isinstance(repos, list):
        raise AgentBoxRepoError("repos.json field 'repos' must be a list")
    return tuple(
        sorted(
            (RegisteredRepo.from_json(item) for item in repos),
            key=lambda repo: repo.name,
        )
    )


def repo_status(config: AgentBoxConfig, name: str) -> RepoStatus:
    """Return a validation/status projection for a registered repo."""

    repo = get_repo(config, name)
    try:
        canonical_path = _validate_canonical_checkout(config, repo.name, repo.path)
    except AgentBoxRepoError as exc:
        return RepoStatus(
            name=repo.name,
            path=str(repo.path),
            default_ref=repo.default_ref,
            remote_url=repo.remote_url,
            valid=False,
            reason=str(exc),
        )
    return RepoStatus(
        name=repo.name,
        path=str(canonical_path),
        default_ref=repo.default_ref,
        remote_url=repo.remote_url,
        valid=True,
        head_sha=_git(canonical_path, "rev-parse", "HEAD"),
    )


def list_repo_statuses(config: AgentBoxConfig) -> tuple[RepoStatus, ...]:
    """Return validation/status projections for all registered repos."""

    return tuple(repo_status(config, repo.name) for repo in list_repos(config))


def _write_registry(
    config: AgentBoxConfig,
    records: Mapping[str, RegisteredRepo],
) -> None:
    path = repos_registry_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repos": [
            records[name].to_json()
            for name in sorted(records)
        ]
    }
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _validate_canonical_checkout(
    config: AgentBoxConfig,
    name: str,
    path: Path,
) -> Path:
    if not name or not _REPO_NAME_PATTERN.fullmatch(name):
        raise AgentBoxRepoError(f"invalid repo name: {name!r}")
    if not path.is_absolute():
        raise AgentBoxRepoError(f"repo path must be absolute: {path}")

    repos_root = config.repos_root.resolve()
    try:
        canonical = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise AgentBoxRepoError(f"repo path does not exist: {path}") from exc

    if canonical == repos_root or repos_root not in canonical.parents:
        raise AgentBoxRepoError(f"repo path must be under repos_root: {canonical}")
    if not (canonical / ".git").is_dir():
        raise AgentBoxRepoError(f"repo must be a normal checkout with a .git directory: {canonical}")

    inside_work_tree = _git(canonical, "rev-parse", "--is-inside-work-tree")
    bare = _git(canonical, "rev-parse", "--is-bare-repository")
    top_level = Path(_git(canonical, "rev-parse", "--show-toplevel")).resolve()
    if inside_work_tree != "true" or bare != "false" or top_level != canonical:
        raise AgentBoxRepoError(f"repo must be a canonical normal checkout: {canonical}")
    return canonical


def _git(cwd: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        reason = (exc.stderr or exc.stdout or str(exc)).strip()
        raise AgentBoxRepoError(reason) from exc
    return completed.stdout.strip()


__all__ = [
    "AgentBoxRepoError",
    "AgentBoxRepoNotFound",
    "REPOS_REGISTRY_FILENAME",
    "RegisteredRepo",
    "RepoStatus",
    "get_repo",
    "list_repo_statuses",
    "list_repos",
    "register_repo",
    "repo_status",
    "repos_registry_path",
]
