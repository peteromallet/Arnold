"""Cloud deployment template rendering and staging."""

from __future__ import annotations

import shlex
import stat
from importlib import resources
from pathlib import Path
from string import Template

from megaplan.cloud.spec import CloudSpec, ToolchainSpec
from megaplan.types import DEFAULT_AGENT_ROUTING


PLACEHOLDERS = (
    "REPO_URL",
    "REPO_BRANCH",
    "WORKSPACE_PATH",
    "CODEX_MODEL",
    "CODEX_REASONING",
    "CODEX_EMAIL",
    "MEGAPLAN_REF",
    "ROBUSTNESS",
    "MODE",
    "IDEA_FILE",
    "CHAIN_SPEC",
    "AUTO_PLAN_NAME",
    "AGENT_ROUTING_BLOCK",
    "CLAUDE_AUTH_BLOCK",
    "RUNNER_LAUNCH_BLOCK",
)

_TOOLCHAIN_RECIPES = {
    "rust": """# Toolchain: rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH=/root/.cargo/bin:${PATH}""",
    "go": """# Toolchain: go
RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz | tar -C /usr/local -xz
ENV PATH=/usr/local/go/bin:${PATH}""",
    "java": """# Toolchain: java
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    PATH=${JAVA_HOME}/bin:${PATH}""",
}

_AUTO_RUNNER = Template(
    """if [ ! -f "$IDEA_FILE" ]; then
  echo 'WARN: idea file missing, dropping to idle'
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l"
else
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -lc ${AUTO_COMMAND}"
fi"""
)

_CHAIN_RUNNER = Template(
    """if [ ! -f "$CHAIN_SPEC" ]; then
  echo 'WARN: chain spec missing, dropping to idle'
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l"
else
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -lc ${CHAIN_COMMAND}"
fi"""
)

_IDLE_RUNNER = Template("""tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l" """)


def _entrypoint_template() -> Template:
    text = resources.files("megaplan.cloud.templates").joinpath("entrypoint.sh.tmpl").read_text(encoding="utf-8")
    return Template(text)


def _render_resource_template(name: str, values: dict[str, str]) -> str:
    text = resources.files("megaplan.cloud.templates").joinpath(name).read_text(encoding="utf-8")
    return Template(text).safe_substitute(values)


def _dockerfile_template() -> Template:
    text = resources.files("megaplan.cloud.templates").joinpath("Dockerfile").read_text(encoding="utf-8")
    return Template(text)


def _quoted(script: str) -> str:
    return shlex.quote(script.strip())


def _auto_command(spec: CloudSpec) -> str:
    assert spec.auto is not None
    plan_dir = f"{spec.repo.workspace}/.megaplan/plans/{spec.auto.plan_name}"
    script = f"""
set -euo pipefail
PLAN_DIR={shlex.quote(plan_dir)}
if [[ ! -d "$PLAN_DIR" ]]; then
  IDEA="$(cat "$IDEA_FILE")"
  megaplan init --project-dir {shlex.quote(spec.repo.workspace)} --name {shlex.quote(spec.auto.plan_name)} --auto-approve --robustness {shlex.quote(spec.auto.robustness)} "$IDEA"
fi
exec mp-supervise {shlex.quote(f"auto-{spec.auto.plan_name}")} megaplan auto --plan {shlex.quote(spec.auto.plan_name)}
"""
    return _quoted(script)


def _chain_command(spec: CloudSpec) -> str:
    assert spec.chain is not None
    script = f"""
set -euo pipefail
exec mp-supervise chain mp-chain {shlex.quote(spec.chain.spec)}
"""
    return _quoted(script)


def _runner_block(spec: CloudSpec) -> str:
    values = {"WORKSPACE_PATH": shlex.quote(spec.repo.workspace)}
    if spec.mode == "auto":
        return _AUTO_RUNNER.safe_substitute(
            values | {"AUTO_COMMAND": _auto_command(spec)}
        )
    if spec.mode == "chain":
        return _CHAIN_RUNNER.safe_substitute(
            values | {"CHAIN_COMMAND": _chain_command(spec)}
        )
    return _IDLE_RUNNER.safe_substitute(values)


def _agent_routing_block(spec: CloudSpec) -> str:
    default_agent = spec.agents.get("default")
    routing = {
        step: spec.agents.get(step, default_agent or fallback)
        for step, fallback in DEFAULT_AGENT_ROUTING.items()
    }
    return "\n".join(
        f'megaplan config set agents.{step} {agent} >/dev/null 2>&1 || true'
        for step, agent in routing.items()
    )


def _claude_auth_block() -> str:
    # Newer claude CLI versions hang on `setup-token` waiting for OAuth/tty
    # input even when stdin is piped. Wrap in a timeout so a hang doesn't
    # stall the entrypoint indefinitely; claude will still pick up
    # ANTHROPIC_API_KEY from env at call time.
    return """if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Authenticating claude with ANTHROPIC_API_KEY"
  if ! timeout 15 bash -c 'printf "%s\\n" "$ANTHROPIC_API_KEY" | claude setup-token' >/dev/null 2>&1; then
    echo "WARN: Claude token auth failed or timed out; continuing — claude CLI will use ANTHROPIC_API_KEY env var directly"
  fi
fi"""


def render_entrypoint(spec: CloudSpec) -> str:
    values = {
        "REPO_URL": spec.repo.url,
        "REPO_BRANCH": spec.repo.branch,
        "WORKSPACE_PATH": spec.repo.workspace,
        "CODEX_MODEL": spec.codex.model,
        "CODEX_REASONING": spec.codex.reasoning,
        "CODEX_EMAIL": "codex-agent@example.com",
        "MEGAPLAN_REF": spec.megaplan.ref,
        "ROBUSTNESS": spec.auto.robustness if spec.auto is not None else "standard",
        "MODE": spec.mode,
        "IDEA_FILE": spec.auto.idea_file if spec.auto is not None else "/workspace/idea.txt",
        "CHAIN_SPEC": spec.chain.spec if spec.chain is not None else "/workspace/chain.yaml",
        "AUTO_PLAN_NAME": spec.auto.plan_name if spec.auto is not None else "idle-plan",
        "AGENT_ROUTING_BLOCK": _agent_routing_block(spec),
        "CLAUDE_AUTH_BLOCK": _claude_auth_block(),
        "RUNNER_LAUNCH_BLOCK": _runner_block(spec),
    }
    rendered = _entrypoint_template().safe_substitute(values)
    missing = [name for name in PLACEHOLDERS if f"${{{name}}}" in rendered]
    if missing:
        raise RuntimeError(f"Unreplaced entrypoint placeholders: {', '.join(missing)}")
    return rendered


def _toolchain_block(toolchains: list[ToolchainSpec] | None) -> str:
    if not toolchains:
        return ""
    blocks: list[str] = []
    for toolchain in toolchains:
        if toolchain.install in _TOOLCHAIN_RECIPES:
            blocks.append(_TOOLCHAIN_RECIPES[toolchain.install])
            continue
        blocks.append(f"# Toolchain: {toolchain.name}\n{toolchain.install}")
    return "\n\n".join(blocks)


def render_dockerfile(spec: CloudSpec) -> str:
    rendered = _dockerfile_template().safe_substitute(
        {"TOOLCHAIN_BLOCK": _toolchain_block(spec.toolchains)}
    )
    if "${TOOLCHAIN_BLOCK}" in rendered:
        raise RuntimeError("Unreplaced Dockerfile placeholders: TOOLCHAIN_BLOCK")
    return rendered


def render_docker_compose(spec: CloudSpec) -> str:
    local = spec.local
    if local is None:
        raise RuntimeError("docker-compose rendering requires spec.local")
    return _render_resource_template(
        "docker-compose.yaml.tmpl",
        {
            "WORKSPACE_PATH": spec.repo.workspace,
            "LOCAL_WORKDIR": local.workdir,
            "PORT": str(spec.resources.port),
        },
    )


def _write_text(path: Path, content: str, *, executable: bool = False) -> None:
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def materialize_deploy_dir(spec: CloudSpec, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    wrappers_dir = dest / "wrappers"
    wrappers_dir.mkdir(parents=True, exist_ok=True)

    templates = resources.files("megaplan.cloud.templates")
    wrappers = resources.files("megaplan.cloud.wrappers")

    _write_text(dest / "Dockerfile", render_dockerfile(spec))
    _write_text(dest / "entrypoint.sh", render_entrypoint(spec), executable=True)
    _write_text(dest / "healthserver.py", templates.joinpath("healthserver.py").read_text(encoding="utf-8"))
    _write_text(
        dest / "railway.toml",
        _render_resource_template("railway.toml.tmpl", {}),
    )
    if spec.provider == "local" and spec.local is not None:
        _write_text(dest / "docker-compose.yaml", render_docker_compose(spec))
        (dest / spec.local.workdir).mkdir(parents=True, exist_ok=True)

    for name in ("mp-run", "mp-supervise", "mp-heartbeat", "mp-chain"):
        _write_text(
            wrappers_dir / name,
            wrappers.joinpath(name).read_text(encoding="utf-8"),
            executable=True,
        )
