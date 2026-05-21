"""Cloud deployment spec loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace
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
VALID_PROVIDERS = ("railway", "local", "ssh")
FUTURE_PROVIDERS = ("fly",)
KNOWN_TOOLCHAIN_ALIASES = ("rust", "go", "java")
VALID_CODEX_REASONING = ("minimal", "low", "medium", "high")


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
    chain_session: str | None = None


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
    environment: str | None = None


@dataclass(frozen=True)
class LocalSpec:
    compose_project: str = "megaplan-cloud"
    workdir: str = "workspace"


@dataclass(frozen=True)
class SshSpec:
    host: str
    user: str | None = None
    port: int = 22
    identity_file: str | None = None
    remote_dir: str = "/tmp/megaplan-cloud"
    container: str = "megaplan-cloud-agent"


@dataclass(frozen=True)
class ToolchainSpec:
    name: str
    install: str


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
    local: LocalSpec | None = None
    ssh: SshSpec | None = None
    toolchains: list[ToolchainSpec] | None = None
    extra_repos: list[str] = field(default_factory=list)


def apply_repo_overrides(
    spec: CloudSpec,
    *,
    repo_url: str | None = None,
    repo_branch: str | None = None,
    repo_workspace: str | None = None,
) -> CloudSpec:
    """Return an in-memory spec copy with resident/CLI repo overrides applied."""
    if repo_url is None and repo_branch is None and repo_workspace is None:
        return spec
    workspace = spec.repo.workspace
    if repo_workspace is not None:
        workspace = _absolute_posix(repo_workspace, "repo.workspace")
    return replace(
        spec,
        repo=replace(
            spec.repo,
            url=repo_url or spec.repo.url,
            branch=repo_branch or spec.repo.branch,
            workspace=workspace,
        ),
    )


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


def _positive_port(raw: Any, label: str, *, default: int) -> int:
    if raw is None:
        return default
    if not isinstance(raw, int) or raw <= 0:
        raise _invalid(f"`{label}` must be a positive integer")
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


def _toolchains(raw: Any) -> list[ToolchainSpec]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _invalid("`toolchains` must be a list")
    toolchains: list[ToolchainSpec] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            if item not in KNOWN_TOOLCHAIN_ALIASES:
                known = ", ".join(KNOWN_TOOLCHAIN_ALIASES)
                raise _invalid(f"Unknown toolchain alias {item!r}; expected one of: {known}")
            toolchains.append(ToolchainSpec(name=item, install=item))
            continue
        if not isinstance(item, dict):
            raise _invalid(f"`toolchains[{index}]` must be a string alias or mapping")
        name = _string(item.get("name"), f"toolchains[{index}].name")
        install = _string(item.get("install"), f"toolchains[{index}].install")
        toolchains.append(ToolchainSpec(name=name, install=install))
    return toolchains


def load_spec(path: Path) -> CloudSpec:
    raw = _load_yaml(path)

    provider = _string(raw.get("provider"), "provider", default="railway")
    if provider in FUTURE_PROVIDERS:
        future = ", ".join(FUTURE_PROVIDERS)
        raise CliError(
            "future_provider",
            f"provider {provider!r} is reserved for a future release; future providers: {future}",
        )
    if provider not in VALID_PROVIDERS:
        raise _invalid(
            f"provider must be one of {', '.join((*VALID_PROVIDERS, *FUTURE_PROVIDERS))}; got {provider!r}"
        )

    repo_raw = _mapping(raw.get("repo"), "repo")
    repo = RepoSpec(
        url=_string(repo_raw.get("url"), "repo.url"),
        branch=_string(repo_raw.get("branch"), "repo.branch", default="main"),
        workspace=_absolute_posix(repo_raw.get("workspace", "/workspace/app"), "repo.workspace"),
    )

    codex_raw = _mapping(raw.get("codex"), "codex")
    codex_reasoning = _string(codex_raw.get("reasoning"), "codex.reasoning", default="high")
    if codex_reasoning not in VALID_CODEX_REASONING:
        raise _invalid(
            f"codex.reasoning must be one of {', '.join(VALID_CODEX_REASONING)}; got {codex_reasoning!r}"
        )
    codex = CodexSpec(
        model=_string(codex_raw.get("model"), "codex.model", default="gpt-5.4"),
        reasoning=codex_reasoning,
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
        environment=_optional_string(railway_raw.get("environment"), "railway.environment"),
    )

    local_raw = _mapping(raw.get("local"), "local")
    local = LocalSpec(
        compose_project=_string(
            local_raw.get("compose_project"),
            "local.compose_project",
            default="megaplan-cloud",
        ),
        workdir=_string(local_raw.get("workdir"), "local.workdir", default="workspace"),
    ) if provider == "local" or local_raw else None

    ssh_raw = _mapping(raw.get("ssh"), "ssh")
    ssh = SshSpec(
        host=_string(ssh_raw.get("host"), "ssh.host"),
        user=_optional_string(ssh_raw.get("user"), "ssh.user"),
        port=_positive_port(ssh_raw.get("port"), "ssh.port", default=22),
        identity_file=_optional_string(ssh_raw.get("identity_file"), "ssh.identity_file"),
        remote_dir=_absolute_posix(
            ssh_raw.get("remote_dir", "/tmp/megaplan-cloud"),
            "ssh.remote_dir",
        ),
        container=_string(
            ssh_raw.get("container"),
            "ssh.container",
            default="megaplan-cloud-agent",
        ),
    ) if provider == "ssh" or ssh_raw else None

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
            chain_session=_optional_string(
                chain_raw.get("chain_session"), "chain.chain_session"
            ),
        )

    # Parse top-level ``extra_repos`` as a list of non-empty strings.
    extra_repos_raw = raw.get("extra_repos")
    extra_repos: list[str] = []
    if extra_repos_raw is not None:
        if not isinstance(extra_repos_raw, list):
            raise _invalid("`extra_repos` must be a list of strings")
        for i, item in enumerate(extra_repos_raw):
            if not isinstance(item, str) or not item.strip():
                raise _invalid(
                    f"`extra_repos[{i}]` must be a non-empty string"
                )
            extra_repos.append(item)

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
        local=local,
        ssh=ssh,
        toolchains=_toolchains(raw.get("toolchains")),
        extra_repos=extra_repos,
    )
