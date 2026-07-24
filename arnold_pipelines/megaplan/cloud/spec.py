"""Cloud deployment spec loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan cloud requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, KNOWN_AGENTS
from arnold_pipelines.megaplan.types import CliError


VALID_MODES = ("auto", "chain", "idle")
VALID_PROVIDERS = ("local", "ssh")
FUTURE_PROVIDERS = ("fly",)
KNOWN_TOOLCHAIN_ALIASES = ("rust", "go", "java")
VALID_CODEX_REASONING = ("minimal", "low", "medium", "high", "xhigh", "max")
VALID_CODEX_AUTH = ("chatgpt", "apikey")


@dataclass(frozen=True)
class RepoSpec:
    url: str
    branch: str = "main"
    workspace: str = "/workspace/app"
    workspace_explicit: bool = False


@dataclass(frozen=True)
class CodexSpec:
    model: str = "gpt-5.6-sol"
    reasoning: str = "medium"


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
class DriverSpec:
    max_stall_iterations: int | None = None


@dataclass(frozen=True)
class ResourcesSpec:
    volume: str | None = None
    port: int = 8080


@dataclass(frozen=True)
class MegaplanSpec:
    ref: str = "main"
    repo: str | None = None
    install_spec: str | None = None
    src_path: str = "/workspace/arnold"
    codex_auth: str = "chatgpt"


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
    remote_dir: str = "/opt/megaplan-cloud/deploy"
    workspace_dir: str = "/opt/megaplan-cloud/workspace"
    cache_dir: str = "/opt/megaplan-cloud/cache"
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
    driver: DriverSpec | None = None
    local: LocalSpec | None = None
    ssh: SshSpec | None = None
    toolchains: list[ToolchainSpec] | None = None
    extra_repos: tuple[RepoSpec, ...] = ()
    chain_session: str = "megaplan-chain"
    chain_session_explicit: bool = False


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
            workspace_explicit=True if repo_workspace is not None else spec.repo.workspace_explicit,
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


def _optional_positive_int(raw: Any, label: str) -> int | None:
    if raw is None:
        return None
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


def _repo_from_mapping(raw: Any, label: str) -> RepoSpec:
    mapping = _mapping(raw, label)
    return RepoSpec(
        url=_string(mapping.get("url"), f"{label}.url"),
        branch=_string(mapping.get("branch"), f"{label}.branch", default="main"),
        workspace=_absolute_posix(mapping.get("workspace"), f"{label}.workspace"),
        workspace_explicit="workspace" in mapping,
    )


def _extra_repos(raw: Any, primary: RepoSpec) -> tuple[RepoSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _invalid("`extra_repos` must be a list of repo mappings")
    seen_workspaces: dict[str, str] = {primary.workspace: "repo"}
    repos: list[RepoSpec] = []
    for index, item in enumerate(raw):
        label = f"extra_repos[{index}]"
        repo = _repo_from_mapping(item, label)
        if repo.workspace in seen_workspaces:
            owner = seen_workspaces[repo.workspace]
            raise _invalid(
                f"`{label}.workspace` collides with `{owner}.workspace` ({repo.workspace!r}); "
                "each repo must have a distinct workspace path"
            )
        seen_workspaces[repo.workspace] = label
        repos.append(repo)
    return tuple(repos)


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

    provider = _string(raw.get("provider"), "provider", default="ssh")
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
        workspace_explicit="workspace" in repo_raw,
    )
    extra_repos = _extra_repos(raw.get("extra_repos"), repo)

    codex_raw = _mapping(raw.get("codex"), "codex")
    codex_reasoning = _string(codex_raw.get("reasoning"), "codex.reasoning", default="medium")
    if codex_reasoning not in VALID_CODEX_REASONING:
        raise _invalid(
            f"codex.reasoning must be one of {', '.join(VALID_CODEX_REASONING)}; got {codex_reasoning!r}"
        )
    codex = CodexSpec(
        model=_string(codex_raw.get("model"), "codex.model", default="gpt-5.6-sol"),
        reasoning=codex_reasoning,
    )

    mode = _string(raw.get("mode"), "mode", default="idle")
    if mode not in VALID_MODES:
        raise _invalid(f"mode must be one of {', '.join(VALID_MODES)}; got {mode!r}")

    agents = _agents(raw.get("agents"))

    megaplan_raw = _mapping(raw.get("megaplan"), "megaplan")
    codex_auth = _string(megaplan_raw.get("codex_auth"), "megaplan.codex_auth", default="chatgpt")
    if codex_auth not in VALID_CODEX_AUTH:
        raise _invalid(
            f"megaplan.codex_auth must be one of {', '.join(VALID_CODEX_AUTH)}; got {codex_auth!r}"
        )
    megaplan = MegaplanSpec(
        ref=_string(megaplan_raw.get("ref"), "megaplan.ref", default="main"),
        repo=_optional_string(megaplan_raw.get("repo"), "megaplan.repo"),
        install_spec=_optional_string(
            megaplan_raw.get("install_spec"),
            "megaplan.install_spec",
        ),
        src_path=_absolute_posix(
            megaplan_raw.get("src_path", "/workspace/arnold"),
            "megaplan.src_path",
        ),
        codex_auth=codex_auth,
    )

    resources_raw = _mapping(raw.get("resources"), "resources")
    resources = ResourcesSpec(
        volume=_optional_string(resources_raw.get("volume"), "resources.volume"),
        port=_port(resources_raw.get("port")),
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
            ssh_raw.get("remote_dir", "/opt/megaplan-cloud/deploy"),
            "ssh.remote_dir",
        ),
        workspace_dir=_absolute_posix(
            ssh_raw.get("workspace_dir", "/opt/megaplan-cloud/workspace"),
            "ssh.workspace_dir",
        ),
        cache_dir=_absolute_posix(
            ssh_raw.get("cache_dir", "/opt/megaplan-cloud/cache"),
            "ssh.cache_dir",
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

    driver_raw = _mapping(raw.get("driver"), "driver")
    max_stall_iterations = driver_raw.get(
        "max_stall_iterations",
        driver_raw.get("stall_threshold"),
    )
    driver = (
        DriverSpec(
            max_stall_iterations=_optional_positive_int(
                max_stall_iterations,
                "driver.max_stall_iterations",
            )
        )
        if driver_raw
        else None
    )

    chain_session_explicit = "chain_session" in raw or (
        chain_spec is not None and chain_spec.chain_session is not None
    )
    chain_session = _string(
        raw.get("chain_session"),
        "chain_session",
        default=chain_spec.chain_session if chain_spec and chain_spec.chain_session else "megaplan-chain",
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
        driver=driver,
        local=local,
        ssh=ssh,
        toolchains=_toolchains(raw.get("toolchains")),
        extra_repos=extra_repos,
        chain_session=chain_session,
        chain_session_explicit=chain_session_explicit,
    )
