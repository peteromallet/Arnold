"""Cloud deployment spec loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan cloud requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from megaplan.types import CliError, DEFAULT_AGENT_ROUTING, KNOWN_AGENTS


VALID_MODES = ("auto", "chain", "idle")
SUPPORTED_PROVIDER = "railway"
SPRINT_TWO_PROVIDERS = ("fly", "ssh", "local")


@dataclass(frozen=True)
class RepoSpec:
    url: str
    branch: str = "main"
    workspace: str = "/workspace/app"


@dataclass(frozen=True)
class CodexSpec:
    model: str = "gpt-5.4"
    reasoning: str = "high"


@dataclass(frozen=True)
class AutoSpec:
    plan_name: str
    idea_file: str
    robustness: str = "standard"


@dataclass(frozen=True)
class ChainSubSpec:
    spec: str


@dataclass(frozen=True)
class ResourcesSpec:
    volume: str | None = None
    port: int = 8080


@dataclass(frozen=True)
class MegaplanSpec:
    ref: str = "main"


@dataclass(frozen=True)
class RailwaySpec:
    service: str = "agent"
    session: str = "agent"
    project: str | None = None


@dataclass(frozen=True)
class CloudSpec:
    provider: str
    repo: RepoSpec
    agents: dict[str, str]
    codex: CodexSpec
    mode: str
    megaplan: MegaplanSpec
    resources: ResourcesSpec
    secrets: list[str]
    auto: AutoSpec | None = None
    chain: ChainSubSpec | None = None
    railway: RailwaySpec | None = None


def _invalid(message: str) -> CliError:
    return CliError("invalid_spec", message)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise _invalid(f"spec file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _invalid(f"YAML parse error: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _invalid("cloud spec must be a YAML mapping")
    return raw


def _mapping(raw: Any, label: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _invalid(f"`{label}` must be a mapping")
    return raw


def _string(raw: Any, label: str, *, default: str | None = None) -> str:
    if raw is None:
        if default is None:
            raise _invalid(f"`{label}` is required")
        return default
    if not isinstance(raw, str) or not raw.strip():
        raise _invalid(f"`{label}` must be a non-empty string")
    return raw


def _optional_string(raw: Any, label: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise _invalid(f"`{label}` must be a non-empty string")
    return raw


def _absolute_posix(raw: Any, label: str) -> str:
    value = _string(raw, label)
    if not PurePosixPath(value).is_absolute():
        raise _invalid(f"`{label}` must be an absolute POSIX path; got {value!r}")
    return value


def _port(raw: Any) -> int:
    if raw is None:
        return 8080
    if not isinstance(raw, int):
        raise _invalid("`resources.port` must be an integer")
    return raw


def _agents(raw: Any) -> dict[str, str]:
    mapping = _mapping(raw, "agents")
    if not mapping:
        return {"default": "codex"}
    valid_keys = ("default", *DEFAULT_AGENT_ROUTING.keys())
    for key, value in mapping.items():
        if not isinstance(key, str):
            raise _invalid(f"`agents` keys must be strings; valid keys: {', '.join(valid_keys)}")
        if key != "default" and key not in DEFAULT_AGENT_ROUTING:
            raise _invalid(f"Unknown agents key '{key}'. Valid keys: {', '.join(valid_keys)}")
        if value not in KNOWN_AGENTS:
            raise _invalid(f"Unknown agent '{value}'. Valid agents: {', '.join(KNOWN_AGENTS)}")
    return dict(mapping)


def _secrets(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw):
        raise _invalid("`secrets` must be a list of strings")
    return list(raw)


def load_spec(path: Path) -> CloudSpec:
    raw = _load_yaml(path)

    provider = _string(raw.get("provider"), "provider", default=SUPPORTED_PROVIDER)
    if provider != SUPPORTED_PROVIDER:
        future = ", ".join(SPRINT_TWO_PROVIDERS)
        raise _invalid(
            f"provider must be '{SUPPORTED_PROVIDER}' for sprint 1; sprint-2 providers: {future}"
        )

    repo_raw = _mapping(raw.get("repo"), "repo")
    repo = RepoSpec(
        url=_string(repo_raw.get("url"), "repo.url"),
        branch=_string(repo_raw.get("branch"), "repo.branch", default="main"),
        workspace=_absolute_posix(repo_raw.get("workspace", "/workspace/app"), "repo.workspace"),
    )

    codex_raw = _mapping(raw.get("codex"), "codex")
    codex = CodexSpec(
        model=_string(codex_raw.get("model"), "codex.model", default="gpt-5.4"),
        reasoning=_string(codex_raw.get("reasoning"), "codex.reasoning", default="high"),
    )

    mode = _string(raw.get("mode"), "mode", default="idle")
    if mode not in VALID_MODES:
        raise _invalid(f"mode must be one of {', '.join(VALID_MODES)}; got {mode!r}")

    agents = _agents(raw.get("agents"))

    megaplan_raw = _mapping(raw.get("megaplan"), "megaplan")
    megaplan = MegaplanSpec(ref=_string(megaplan_raw.get("ref"), "megaplan.ref", default="main"))

    resources_raw = _mapping(raw.get("resources"), "resources")
    resources = ResourcesSpec(
        volume=_optional_string(resources_raw.get("volume"), "resources.volume"),
        port=_port(resources_raw.get("port")),
    )

    railway_raw = _mapping(raw.get("railway"), "railway")
    railway = RailwaySpec(
        service=_string(railway_raw.get("service"), "railway.service", default="agent"),
        session=_string(railway_raw.get("session"), "railway.session", default="agent"),
        project=_optional_string(railway_raw.get("project"), "railway.project"),
    )

    auto_spec: AutoSpec | None = None
    if mode == "auto":
        auto_raw = _mapping(raw.get("auto"), "auto")
        auto_spec = AutoSpec(
            plan_name=_string(auto_raw.get("plan_name"), "auto.plan_name"),
            idea_file=_absolute_posix(auto_raw.get("idea_file"), "auto.idea_file"),
            robustness=_string(auto_raw.get("robustness"), "auto.robustness", default="standard"),
        )

    chain_spec: ChainSubSpec | None = None
    if mode == "chain":
        chain_raw = _mapping(raw.get("chain"), "chain")
        chain_spec = ChainSubSpec(
            spec=_absolute_posix(chain_raw.get("spec"), "chain.spec"),
        )

    return CloudSpec(
        provider=provider,
        repo=repo,
        agents=agents,
        codex=codex,
        mode=mode,
        megaplan=megaplan,
        resources=resources,
        secrets=_secrets(raw.get("secrets")),
        auto=auto_spec,
        chain=chain_spec,
        railway=railway,
    )
