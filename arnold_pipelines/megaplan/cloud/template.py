"""Cloud deployment template rendering and staging."""

from __future__ import annotations

import shlex
import stat
from importlib import resources
from pathlib import Path, PurePosixPath
from string import Template

from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RepoSpec, ToolchainSpec
from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, effective_premium_vendor
from arnold_pipelines.megaplan.types import (
    format_agent_spec,
    is_premium_placeholder_spec,
    resolve_premium_placeholder_spec,
)


PLACEHOLDERS = (
    "REPO_URL",
    "REPO_BRANCH",
    "WORKSPACE_PATH",
    "CODEX_MODEL",
    "CODEX_REASONING",
    "CODEX_EMAIL",
    "MEGAPLAN_REF",
    "MEGAPLAN_REPO",
    "MEGAPLAN_INSTALL_SPEC_OVERRIDE",
    "MEGAPLAN_SRC_PATH",
    "CODEX_AUTH_METHOD",
    "CODEX_AUTH_CONFIG_BLOCK",
    "ROBUSTNESS",
    "MODE",
    "IDEA_FILE",
    "CHAIN_SPEC",
    "AUTO_PLAN_NAME",
    "AGENT_ROUTING_BLOCK",
    "CLAUDE_AUTH_BLOCK",
    "ENSURE_REPO_BLOCK",
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
    text = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("entrypoint.sh.tmpl").read_text(encoding="utf-8")
    return Template(text)


def _render_resource_template(name: str, values: dict[str, str]) -> str:
    text = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath(name).read_text(encoding="utf-8")
    return Template(text).safe_substitute(values)


def _dockerfile_template() -> Template:
    text = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("Dockerfile").read_text(encoding="utf-8")
    return Template(text)


def _quoted(script: str) -> str:
    return shlex.quote(script.strip())


def render_ensure_repo_command(repo: RepoSpec) -> str:
    """Render the fixed clone-if-missing command used by cloud entrypoints."""
    workspace = PurePosixPath(repo.workspace)
    parent = str(workspace.parent)
    git_dir = str(workspace / ".git")
    return " && ".join(
        [
            f"mkdir -p {shlex.quote(parent)}",
            (
                f"if [ ! -d {shlex.quote(git_dir)} ]; then "
                f"git clone --branch {shlex.quote(repo.branch)} "
                f"{shlex.quote(repo.url)} {shlex.quote(repo.workspace)}; "
                "else true; fi"
            ),
        ]
    )


def render_ensure_repos_block(spec: CloudSpec) -> str:
    """Clone primary + every extra repo if missing, in declared order.

    Each repo lives at its own absolute workspace path so a multi-repo or
    multi-tenant volume can hold them as siblings on independent branches.
    """
    blocks = [render_ensure_repo_command(spec.repo)]
    for extra in spec.extra_repos:
        blocks.append(render_ensure_repo_command(extra))
    return "\n".join(blocks)


def _auto_command(spec: CloudSpec) -> str:
    assert spec.auto is not None
    plan_dir = f"{spec.repo.workspace}/.megaplan/plans/{spec.auto.plan_name}"
    script = f"""
set -euo pipefail
PLAN_DIR={shlex.quote(plan_dir)}
if [[ ! -d "$PLAN_DIR" ]]; then
  IDEA="$(cat "$IDEA_FILE")"
  arnold init --project-dir {shlex.quote(spec.repo.workspace)} --name {shlex.quote(spec.auto.plan_name)} --auto-approve --robustness {shlex.quote(spec.auto.robustness)} "$IDEA"
fi
exec arnold-supervise {shlex.quote(f"auto-{spec.auto.plan_name}")} arnold auto --plan {shlex.quote(spec.auto.plan_name)}
"""
    return _quoted(script)


def _chain_command(spec: CloudSpec) -> str:
    assert spec.chain is not None
    script = f"""
set -euo pipefail
exec arnold-supervise chain arnold-chain {shlex.quote(spec.chain.spec)}
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
    selected_vendor = (
        default_agent
        if default_agent in {"claude", "codex"}
        else effective_premium_vendor()
    )
    routing = {
        step: spec.agents.get(step, default_agent or fallback)
        for step, fallback in DEFAULT_AGENT_ROUTING.items()
    }
    return "\n".join(
        "arnold config set agents."
        f"{step} "
        f"{format_agent_spec(resolve_premium_placeholder_spec(agent, selected_vendor)) if is_premium_placeholder_spec(agent) else agent} "
        ">/dev/null 2>&1 || true"
        for step, agent in routing.items()
    )


def _claude_auth_block() -> str:
    # Three auth modes, in priority order:
    #
    # 1. CLAUDE_CODE_REFRESH_TOKEN (preferred — uses Max/Pro subscription, fully
    #    programmatic): install a `claude` shim at /usr/local/bin/claude that
    #    refreshes the OAuth access token on every invocation, exports it as
    #    ANTHROPIC_API_KEY, then exec's the real binary. The refresh token
    #    rotates per use and is persisted to the volume.
    #
    # 2. ANTHROPIC_API_KEY (legacy / metered API): claude --bare reads it
    #    directly; nothing to install. claude setup-token is NOT attempted
    #    because it requires interactive browser OAuth.
    #
    # 3. Neither: claude will fail at first call. Warn loudly.
    #
    # See megaplan-cloud skill for full design rationale.
    return r"""# ── Claude auth: refresh-token shim takes precedence ─────────────────
CLAUDE_CREDS_DIR=/workspace/.claude-creds
mkdir -p "$CLAUDE_CREDS_DIR"
chmod 700 "$CLAUDE_CREDS_DIR"

if [[ -n "${CLAUDE_CODE_REFRESH_TOKEN:-}" ]]; then
  # Seed the on-volume refresh token from the env on first boot (or if missing).
  if [[ ! -s "$CLAUDE_CREDS_DIR/refresh_token" ]]; then
    printf '%s' "$CLAUDE_CODE_REFRESH_TOKEN" > "$CLAUDE_CREDS_DIR/refresh_token"
    chmod 600 "$CLAUDE_CREDS_DIR/refresh_token"
  fi

  REAL_CLAUDE=$(command -v claude || true)
  if [[ -z "$REAL_CLAUDE" ]]; then
    echo "WARN: claude binary not on PATH; skipping refresh-token shim install"
  else
    # Move the real binary aside so we can shadow it (idempotent across reboots).
    if [[ ! -x /usr/local/bin/claude.real ]]; then
      cp "$REAL_CLAUDE" /usr/local/bin/claude.real
      chmod +x /usr/local/bin/claude.real
    fi

    # Refresh helper (usable standalone, and as `apiKeyHelper` via --settings).
    cat > /usr/local/bin/claude-key-helper <<'HELPER_EOF'
#!/usr/bin/env bash
# Refresh the Claude Code OAuth access token if missing/expiring, then print it
# to stdout. Refresh token rotates per use and is persisted to the volume.
set -euo pipefail
DIR=/workspace/.claude-creds
mkdir -p "$DIR"
NOW=$(date +%s)
EXP=$(cat "$DIR/expires_at" 2>/dev/null || echo 0)
if [[ ! -s "$DIR/access_token" ]] || [[ "$NOW" -ge $((EXP - 300)) ]]; then
  RT=$(cat "$DIR/refresh_token" 2>/dev/null || true)
  if [[ -z "$RT" ]]; then
    echo "claude-key-helper: no refresh token at $DIR/refresh_token" >&2
    exit 1
  fi
  CID=${CLAUDE_CODE_OAUTH_CLIENT_ID:-9d1c250a-e61b-44d9-88ed-5944d1962f5e}
  URL=${CLAUDE_CODE_OAUTH_TOKEN_URL:-https://api.anthropic.com/v1/oauth/token}
  RESP=$(curl -sS --max-time 15 -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "{\"grant_type\":\"refresh_token\",\"refresh_token\":\"$RT\",\"client_id\":\"$CID\"}")
  AT=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
  EXPIRES_IN=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("expires_in",0))' 2>/dev/null)
  NEW_RT=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("refresh_token",""))' 2>/dev/null)
  if [[ -z "$AT" ]]; then
    echo "claude-key-helper: refresh failed: $RESP" >&2
    exit 1
  fi
  printf '%s' "$AT" > "$DIR/access_token"
  echo $((NOW + EXPIRES_IN)) > "$DIR/expires_at"
  [[ -n "$NEW_RT" ]] && printf '%s' "$NEW_RT" > "$DIR/refresh_token"
  chmod 600 "$DIR/access_token" "$DIR/refresh_token" "$DIR/expires_at"
fi
cat "$DIR/access_token"
HELPER_EOF
    chmod +x /usr/local/bin/claude-key-helper

    # Claude shim: refresh on entry, export, exec real binary.
    cat > /usr/local/bin/claude <<'SHIM_EOF'
#!/usr/bin/env bash
AT=$(/usr/local/bin/claude-key-helper) || {
  echo "claude shim: refresh failed; falling back to ANTHROPIC_API_KEY (may be expired)" >&2
  exec /usr/local/bin/claude.real "$@"
}
export ANTHROPIC_API_KEY="$AT"
exec /usr/local/bin/claude.real "$@"
SHIM_EOF
    chmod +x /usr/local/bin/claude

    # Prime the cache so the first phase call doesn't pay refresh latency.
    if /usr/local/bin/claude-key-helper >/dev/null 2>&1; then
      echo "Claude auth: refresh-token shim active (cached access token ready)"
    else
      echo "WARN: claude shim installed but priming refresh FAILED — see /var/log/entrypoint.log"
    fi
  fi
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Claude auth: using ANTHROPIC_API_KEY (legacy / metered). For Max-sub usage, set CLAUDE_CODE_REFRESH_TOKEN."
else
  echo "WARN: no Claude auth configured (set CLAUDE_CODE_REFRESH_TOKEN or ANTHROPIC_API_KEY). Claude phases will fail."
fi
# ─────────────────────────────────────────────────────────────────────"""


def _codex_auth_config_block(spec: CloudSpec) -> str:
    if spec.megaplan.codex_auth == "apikey":
        return ""
    return '\n'.join(
        [
            'preferred_auth_method = "chatgpt"',
            'forced_login_method = "chatgpt"',
        ]
    )


def render_entrypoint(spec: CloudSpec) -> str:
    values = {
        "REPO_URL": spec.repo.url,
        "REPO_BRANCH": spec.repo.branch,
        "WORKSPACE_PATH": spec.repo.workspace,
        "CODEX_MODEL": spec.codex.model,
        "CODEX_REASONING": spec.codex.reasoning,
        "CODEX_EMAIL": "codex-agent@example.com",
        "MEGAPLAN_REF": spec.megaplan.ref,
        "MEGAPLAN_REPO": spec.megaplan.repo or "",
        "MEGAPLAN_INSTALL_SPEC_OVERRIDE": spec.megaplan.install_spec or "",
        "MEGAPLAN_SRC_PATH": spec.megaplan.src_path or "/workspace/arnold",
        "CODEX_AUTH_METHOD": spec.megaplan.codex_auth,
        "CODEX_AUTH_CONFIG_BLOCK": _codex_auth_config_block(spec),
        "ROBUSTNESS": spec.auto.robustness if spec.auto is not None else "standard",
        "MODE": spec.mode,
        "IDEA_FILE": spec.auto.idea_file if spec.auto is not None else "/workspace/idea.txt",
        "CHAIN_SPEC": spec.chain.spec if spec.chain is not None else "/workspace/chain.yaml",
        "AUTO_PLAN_NAME": spec.auto.plan_name if spec.auto is not None else "idle-plan",
        "AGENT_ROUTING_BLOCK": _agent_routing_block(spec),
        "CLAUDE_AUTH_BLOCK": _claude_auth_block(),
        "ENSURE_REPO_BLOCK": render_ensure_repos_block(spec),
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

    templates = resources.files("arnold_pipelines.megaplan.cloud.templates")
    wrappers = resources.files("arnold_pipelines.megaplan.cloud.wrappers")

    _write_text(dest / "Dockerfile", render_dockerfile(spec))
    _write_text(dest / "entrypoint.sh", render_entrypoint(spec), executable=True)
    _write_text(dest / "healthserver.py", templates.joinpath("healthserver.py").read_text(encoding="utf-8"))
    if spec.provider == "local" and spec.local is not None:
        _write_text(dest / "docker-compose.yaml", render_docker_compose(spec))
        (dest / spec.local.workdir).mkdir(parents=True, exist_ok=True)

    for name in ("mp-run", "mp-supervise", "mp-heartbeat", "mp-chain",
                 "arnold-run", "arnold-supervise", "arnold-heartbeat", "arnold-chain",
                 "arnold-watchdog", "arnold-kimi-goal-operator",
                 "arnold-repair-trigger", "arnold-repair-loop",
                 "arnold-meta-repair-loop", "arnold-progress-auditor",
                 "arnold-supervisor-runtime", "arnold-supervisor-runtime-lib",
                 "arnold-supervisor-gap-scan"):
        _write_text(
            wrappers_dir / name,
            wrappers.joinpath(name).read_text(encoding="utf-8"),
            executable=True,
        )
