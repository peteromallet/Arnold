"""Cloud deployment template rendering and staging."""

from __future__ import annotations

import json
import shlex
import stat
from urllib.parse import urlsplit, urlunsplit
from importlib import resources
from pathlib import Path, PurePosixPath
from string import Template

from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    COMPATIBILITY_ONLY_KEY,
    DEPENDENCY_GENERATION_KEYS,
    EPIC_REQUIRED,
    MANIFEST_SCHEMA_VERSION,
    TOP_LEVEL_REQUIRED,
)
from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RepoSpec, ToolchainSpec
from arnold_pipelines.megaplan.profiles import (
    DEFAULT_AGENT_ROUTING,
    effective_premium_vendor,
)
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

_IDLE_RUNNER = Template(
    """tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l" """
)

_ZERO_RECOVERY_ENTRYPOINT = """#!/usr/bin/env bash
set -euo pipefail

if [[ "${MEGAPLAN_ZERO_RECOVERY_CANARY:-}" != "1" ]]; then
  echo "zero-recovery canary requires MEGAPLAN_ZERO_RECOVERY_CANARY=1" >&2
  exit 64
fi
export MEGAPLAN_ZERO_RECOVERY_CANARY=1
exec python3 /usr/local/bin/healthserver.py
"""

_ISOLATED_CHAIN_RUNNER_ENTRYPOINT = """#!/usr/bin/env bash
set -euo pipefail

if [[ "${MEGAPLAN_ISOLATED_CHAIN_RUNNER:-}" != "1" ]]; then
  echo "isolated chain runner requires MEGAPLAN_ISOLATED_CHAIN_RUNNER=1" >&2
  exit 64
fi
export MEGAPLAN_ISOLATED_CHAIN_RUNNER=1
exec python3 /usr/local/bin/healthserver.py
"""


def _entrypoint_template() -> Template:
    text = (
        resources.files("arnold_pipelines.megaplan.cloud.templates")
        .joinpath("entrypoint.sh.tmpl")
        .read_text(encoding="utf-8")
    )
    return Template(text)


def _render_resource_template(name: str, values: dict[str, str]) -> str:
    text = (
        resources.files("arnold_pipelines.megaplan.cloud.templates")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
    return Template(text).safe_substitute(values)


def _dockerfile_template() -> Template:
    text = (
        resources.files("arnold_pipelines.megaplan.cloud.templates")
        .joinpath("Dockerfile")
        .read_text(encoding="utf-8")
    )
    return Template(text)


def _quoted(script: str) -> str:
    return shlex.quote(script.strip())


def _sanitise_git_url(url: str) -> str:
    """Strip URL userinfo before a rendered clone can expose credentials.

    On-box Git receives authentication through the file-backed helper
    environment.  Userinfo is therefore both unnecessary and unsafe in the
    shell command (which is also captured by process-adapter evidence).
    SCP-style ``git@host:path`` URLs are intentionally left alone; ``git`` is
    the transport user there, not a password-bearing URL.
    """
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https", "ssh"} or "@" not in parsed.netloc:
        return url
    host_netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, host_netloc, parsed.path, parsed.query, parsed.fragment))


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
                f"{shlex.quote(_sanitise_git_url(repo.url))} {shlex.quote(repo.workspace)}; "
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


def _managed_run_prelude(
    *, session: str, workspace: str, remote_spec: str, run_kind: str
) -> str:
    """Materialize the canonical marker/env contract for image entrypoints."""

    marker_dir = "/workspace/.megaplan/cloud-sessions"
    marker_path = str(PurePosixPath(marker_dir) / f"{session}.json")
    script = f"""
import json, os, pathlib, tempfile, uuid
from datetime import datetime, timezone

path = pathlib.Path({marker_path!r})
payload = {{
    "session": {session!r},
    "workspace": {workspace!r},
    "remote_spec": {remote_spec!r},
    "run_kind": {run_kind!r},
    "run_id": str(uuid.uuid4()),
    "started_at": datetime.now(timezone.utc).isoformat(),
}}
path.parent.mkdir(parents=True, exist_ok=True)
fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True)
    handle.write("\\n")
    handle.flush()
    os.fsync(handle.fileno())
os.replace(tmp_name, path)
"""
    return (
        "unset ARNOLD_LIVENESS_OWNER_PID ARNOLD_LIVENESS_OWNER_PROCESS_START\n"
        "export ARNOLD_REPAIR_QUEUE_ROOT=${ARNOLD_REPAIR_QUEUE_ROOT:-/workspace/.megaplan/repair-queue}\n"
        f"export ARNOLD_REPAIR_MARKER_DIR={shlex.quote(marker_dir)}\n"
        f"export ARNOLD_REPAIR_SESSION={shlex.quote(session)}\n"
        f"export ARNOLD_REPAIR_RUN_KIND={shlex.quote(run_kind)}\n"
        f"python3 - <<'MEGAPLAN_MANAGED_RUN_MARKER'\n{script.strip()}\n"
        "MEGAPLAN_MANAGED_RUN_MARKER"
    )


def _pinned_manifest_field_read(field: str) -> str:
    """Shell command substitution reading one ``epic`` field from the pinned
    runtime manifest (``$PINNED_RUNTIME_MANIFEST``).

    Stdlib JSON only, silent on absent/corrupt manifests — the caller's
    unconditional manifest-pin checks fail closed on an empty read.  The
    field is a module constant (``runtime_root`` / ``expected_head``), never
    caller input.

    G6 round-9 finding 1: the read is gated on the CANONICAL manifest
    schema and rejects ``compatibility_only`` pointers.  The emitted script
    prints the field only when the pinned file is a schema-valid runtime
    manifest — ``schema`` equals ``MANIFEST_SCHEMA_VERSION``, both the
    canonical top-level and ``epic`` required key sets are present, and the
    ``compatibility_only`` marker is not set (a pointer is NON-AUTHORITATIVE
    telemetry and can never select a runtime).  The key sets and schema
    version are generated from runtime_manifest's own constants, so the
    shell gate can never drift from the schema definition.  A present-but-
    schema-invalid manifest (schema-less, wrong schema version, missing
    required sections) or a ``compatibility_only`` pointer yields an EMPTY
    read, so the pin gate fails closed with exit 24 instead of deriving a
    dirty ENGINE_DIR from it.
    """
    return (
        '$(env -u PYTHONHOME PYTHONSAFEPATH=1 python -P -c \'import json,sys; '
        f"d=json.load(open(sys.argv[1])); R={json.dumps(TOP_LEVEL_REQUIRED)}; "
        f"E={json.dumps(EPIC_REQUIRED)}; "
        f"e=d.get(\"epic\") if isinstance(d,dict) and d.get(\"schema\")=={json.dumps(MANIFEST_SCHEMA_VERSION)} and d.get({json.dumps(COMPATIBILITY_ONLY_KEY)}) is not True and all(k in d for k in R) else None; "
        f"print(e.get(\"{field}\",\"\")) if isinstance(e,dict) and all(k in e for k in E) else None\' "
        '"$PINNED_RUNTIME_MANIFEST" 2>/dev/null || true)'
    )


def _pinned_manifest_generation_interpreter_read() -> str:
    """Shell command substitution reading the dependency-generation
    interpreter from the pinned runtime manifest (T-0301).

    Same canonical-schema + compatibility_only gates as
    :func:`_pinned_manifest_field_read`, PLUS the generation-proof
    completeness gate: ``epic.dependency_generation`` must carry the full
    required key set (:data:`DEPENDENCY_GENERATION_KEYS`).  An absent,
    partial, or schema-invalid proof yields an EMPTY read, so the auto
    entrypoint fails closed with exit 24 — a runtime without a verifiable
    immutable dependency generation is never launched (G10).
    """
    return (
        '$(env -u PYTHONHOME PYTHONSAFEPATH=1 python -P -c \'import json,sys; '
        f"d=json.load(open(sys.argv[1])); R={json.dumps(TOP_LEVEL_REQUIRED)}; "
        f"E={json.dumps(EPIC_REQUIRED)}; G={json.dumps(DEPENDENCY_GENERATION_KEYS)}; "
        f"e=d.get(\"epic\") if isinstance(d,dict) and d.get(\"schema\")=={json.dumps(MANIFEST_SCHEMA_VERSION)} and d.get({json.dumps(COMPATIBILITY_ONLY_KEY)}) is not True and all(k in d for k in R) else None; "
        f"g=e.get(\"dependency_generation\") if isinstance(e,dict) and all(k in e for k in E) else None; "
        f"print(g.get(\"interpreter_path\",\"\")) if isinstance(g,dict) and all(k in g for k in G) else None\' "
        '"$PINNED_RUNTIME_MANIFEST" 2>/dev/null || true)'
    )


def _auto_command(spec: CloudSpec) -> str:
    assert spec.auto is not None
    plan_dir = f"{spec.repo.workspace}/.megaplan/plans/{spec.auto.plan_name}"
    manifest_pin = (
        """# Explicit per-session manifest pin (T-0021): the auto bootstrap derives its
# engine dir ONLY from ARNOLD_RUNTIME_MANIFEST (epic.runtime_root) and fails
# closed (exit 24, isolated_chain_runtime_binding_drift) when the manifest is
# absent, unreadable, schema-invalid, a compatibility_only pointer, or
# disagrees with the active imports.  The container env may carry the
# per-session pin; the canonical bootstrap manifest path is the explicit
# default.  There is NO fixed-path shared-root fallback (no megaplan.src_path
# read, no /workspace/arnold) and the pin is enforced BEFORE the session
# marker write, init, or any state load.
export ARNOLD_RUNTIME_MANIFEST="${ARNOLD_RUNTIME_MANIFEST:-/workspace/.megaplan/runtime-manifest.json}"
PINNED_RUNTIME_MANIFEST="${ARNOLD_RUNTIME_MANIFEST:-}"
readonly PINNED_RUNTIME_MANIFEST
if [[ -z "$PINNED_RUNTIME_MANIFEST" ]]; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: missing runtime manifest pin" >&2
  exit 24
fi
if [[ ! -r "$PINNED_RUNTIME_MANIFEST" ]]; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: runtime manifest unreadable ($PINNED_RUNTIME_MANIFEST)" >&2
  exit 24
fi
"""
        + f'ENGINE_DIR="{_pinned_manifest_field_read("runtime_root")}"\n'
        + """if [[ -z "$ENGINE_DIR" ]]; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: manifest lacks runtime_root" >&2
  exit 24
fi
"""
        + f'EXPECTED_REVISION="{_pinned_manifest_field_read("expected_head")}"\n'
        + """if [[ -z "$EXPECTED_REVISION" ]]; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: manifest lacks runtime identity" >&2
  exit 24
fi
"""
        + f'GEN_INTERPRETER="{_pinned_manifest_generation_interpreter_read()}"\n'
        + """if [[ -z "$GEN_INTERPRETER" ]]; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: manifest lacks dependency generation interpreter" >&2
  exit 24
fi
if [[ ! -x "$GEN_INTERPRETER" ]]; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: dependency generation interpreter not executable ($GEN_INTERPRETER)" >&2
  exit 24
fi
# The provenance check runs under the generation interpreter with PYTHONPATH
# set to exactly the manifest root (worktree-first: the runtime code comes
# from the pinned worktree, the frozen dependencies from the immutable
# generation) so active imports cannot resolve through an unbound shared
# checkout and cannot fall back to an editable install.
if ! env -u PYTHONHOME PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR" \
    "$GEN_INTERPRETER" -P -m arnold_pipelines.megaplan.cloud.runtime_provenance \
    --expected-root "$ENGINE_DIR" \
    --expected-revision "$EXPECTED_REVISION" >/dev/null 2>&1; then
  echo "[megaplan-launch] isolated_chain_runtime_binding_drift: active imports disagree with manifest-bound runtime" >&2
  exit 24
fi
"""
    )
    script = f"""
set -euo pipefail
{manifest_pin}{_managed_run_prelude(session="agent", workspace=spec.repo.workspace, remote_spec=plan_dir, run_kind="plan")}
PLAN_DIR={shlex.quote(plan_dir)}
if [[ ! -d "$PLAN_DIR" ]]; then
  IDEA="$(cat "$IDEA_FILE")"
  env -u PYTHONHOME PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR" "$GEN_INTERPRETER" -P -m arnold_pipelines.megaplan init --project-dir {shlex.quote(spec.repo.workspace)} --name {shlex.quote(spec.auto.plan_name)} --auto-approve --robustness {shlex.quote(spec.auto.robustness)} "$IDEA"
fi
exec arnold-supervise {shlex.quote(f"auto-{spec.auto.plan_name}")} env -u PYTHONHOME PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR" "$GEN_INTERPRETER" -P -m arnold_pipelines.megaplan auto --plan {shlex.quote(spec.auto.plan_name)} --project-dir {shlex.quote(spec.repo.workspace)}
"""
    return _quoted(script)


def _chain_command(spec: CloudSpec) -> str:
    assert spec.chain is not None
    script = f"""
set -euo pipefail
{_managed_run_prelude(session="agent", workspace=spec.repo.workspace, remote_spec=spec.chain.spec, run_kind="chain")}
# Explicit per-session manifest pin (G2 finding 1 / T-0011): arnold-chain
# derives its engine dir ONLY from ARNOLD_RUNTIME_MANIFEST and fails closed
# (exit 24) when the manifest is absent, unreadable, or disagrees with the
# active imports.  The container env may carry the per-session pin; the
# canonical bootstrap manifest path is the explicit default.
export ARNOLD_RUNTIME_MANIFEST="${{ARNOLD_RUNTIME_MANIFEST:-/workspace/.megaplan/runtime-manifest.json}}"
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
    return "\n".join(
        [
            'preferred_auth_method = "chatgpt"',
            'forced_login_method = "chatgpt"',
        ]
    )


def render_entrypoint(spec: CloudSpec) -> str:
    if spec.zero_recovery_canary:
        return _ZERO_RECOVERY_ENTRYPOINT
    if spec.isolated_chain_runner:
        return _ISOLATED_CHAIN_RUNNER_ENTRYPOINT
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
        "CODEX_AUTH_METHOD": spec.megaplan.codex_auth,
        "CODEX_AUTH_CONFIG_BLOCK": _codex_auth_config_block(spec),
        "ROBUSTNESS": spec.auto.robustness if spec.auto is not None else "standard",
        "MODE": spec.mode,
        "IDEA_FILE": spec.auto.idea_file
        if spec.auto is not None
        else "/workspace/idea.txt",
        "CHAIN_SPEC": spec.chain.spec
        if spec.chain is not None
        else "/workspace/chain.yaml",
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
    _write_text(
        dest / "healthserver.py",
        templates.joinpath("healthserver.py").read_text(encoding="utf-8"),
    )
    if spec.provider == "local" and spec.local is not None:
        _write_text(dest / "docker-compose.yaml", render_docker_compose(spec))
        (dest / spec.local.workdir).mkdir(parents=True, exist_ok=True)

    for name in (
        "mp-run",
        "mp-supervise",
        "mp-heartbeat",
        "mp-chain",
        "arnold-run",
        "arnold-supervise",
        "arnold-heartbeat",
        "arnold-chain",
        "arnold-watchdog",
        "arnold-progress-auditor",
        "arnold-supervisor-runtime",
        "arnold-supervisor-runtime-lib",
        "arnold-supervisor-gap-scan",
    ):
        _write_text(
            wrappers_dir / name,
            wrappers.joinpath(name).read_text(encoding="utf-8"),
            executable=True,
        )
