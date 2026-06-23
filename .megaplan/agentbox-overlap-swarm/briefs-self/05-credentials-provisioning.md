You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality. The brief embeds local file excerpts because you do not have filesystem tools. Return: existing functionality reusable directly, functionality needing extraction/generalization, missing pieces, risks/gotchas, and a recommended first implementation slice. Keep under 900 words and cite file names/sections.\nFocus only on machine provisioning and credential sync overlap.


--- FILE: docs/agentbox-persistent-machine-plan.md (1,160p) ---
# AgentBox Persistent Machine Plan

## Goal

Build a persistent remote agent machine that can host many repositories, receive selected credentials from the user's laptop, launch and supervise many concurrent coding operations, and expose the whole system through a resident Discord control plane.

This is broader than the current Megaplan Cloud worker. Megaplan Cloud is a remote runner for plans/chains. AgentBox is a remote development and agent operations machine.

The short version:

- the user can spin up Megaplan plans or chains on the machine;
- each run gets an isolated worktree, branch, tmux session, logs, and operation record;
- a **Guardian** checks all active operations every `X` minutes and safely keeps them moving;
- a **Discord Operator** starts on user messages, has access to AgentBox state/tools, and can launch or inspect work on demand;
- both actors use the same operation registry and safety/approval system.

The core constraint is:

- one persistent machine;
- many repos on that machine;
- one canonical repo checkout or bare repo per source repo;
- one git worktree per operation per repo;
- one tmux/session/process group per operation;
- one Guardian daemon supervising all known operations;
- one Discord-triggered Operator agent for interactive control;
- Discord as the primary human control surface.

## Resident Actors

AgentBox has two primary resident actors. They share the same state, tools, and safety policy, but they wake up for different reasons.

### Guardian

The Guardian is a long-running supervisor daemon. It wakes on a fixed cadence, for example every 5, 10, or 15 minutes, and checks every active operation.

Responsibilities:

- scan the operation registry;
- inspect tmux/process liveness;
- inspect Megaplan plan or chain status;
- read recent logs and structured state;
- classify operations as running, stale, blocked, failed, completed, or awaiting approval;
- restart a missing runner when the operation type has a known-safe restart path;
- advance a chain when the next step is unambiguous;
- file or update pending approvals for risky actions;
- notify Discord when a run blocks, fails, completes, or needs human input;
- update operation state and health summaries.

The Guardian should not silently make product decisions, resolve merge conflicts, delete worktrees, merge PRs, or accept quality debt. Those become explicit pending approvals.

### Discord Operator

The Discord Operator is an on-demand agent launched by Discord messages. It is the interactive control plane.

Responsibilities:

- answer "what is running?";
- launch a Megaplan plan or chain in a fresh worktree;
- launch Codex, Claude, subagent, shell, or test operations;
- inspect logs and summarize failures;
- ask the Guardian what is stuck;
- approve or reject pending actions;
- stop, restart, or clean up operations when authorized;
- inspect repo/worktree/branch state;
- push branches or open PRs when authorized.

The Operator should have access to all AgentBox data and tools, but it should still go through the same safety policy as the Guardian. Discord messages are the trigger, not a bypass.

### Shared State

Both actors depend on the same durable records:

```text
operation id
operation kind
repo(s)
worktree(s)
branch(es)
tmux session
command
log path
current status
last check timestamp
pending approvals
Discord conversation/thread/message ids
PR/CI metadata
```

This operation registry is the center of the system. The Guardian is scheduled/autonomous; the Discord Operator is user-triggered/interactive.

## Recommendation

Use a Hetzner VM or dedicated server as the primary target. Keep Railway support for simpler one-off hosted runners, but do not force the full resident-machine model into Railway's persistent-container model.

Start with a Hetzner `CX53`-class box for the prototype:

- 16 vCPU
- 32 GB RAM
- 320 GB disk
- enough to validate several concurrent agents, tests, and repos

If the workload saturates shared CPU or disk, move the same bootstrap to a dedicated or auction server. The design should make host migration boring.

## Target Layout

```text
/workspace
  /repos
    /megaplan.git
    /reigh-app.git
    /reigh-worker.git

  /worktrees
    /op-20260623-foo
      /megaplan
      /reigh-app
    /op-20260623-bar
      /megaplan

  /runs
    /op-20260623-foo
      manifest.yaml
      state.json
      log.txt
      events.ndjson

  /secrets
    agentbox.env
    codex-auth.json
    claude-refresh-token.env

  /manager
    agentbox.db
    config.yaml
```

Each operation gets its own isolated worktree and branch. No two agents mutate the same checkout.

## Existing Megaplan Pieces To Reuse

### Worktree Mechanics

Megaplan already has the basic worktree substrate:

- `megaplan init --in-worktree NAME`
- `megaplan chain start --in-worktree NAME`
- `--worktree-from`
- `--clean-worktree`
- `--carry-dirty`
- `--fresh` for chain worktrees
- worktree metadata persisted into plan state

The shared primitives live in:

- `arnold_pipelines/megaplan/bakeoff/worktree.py`

Useful functions include:

- `validate_worktree_name`
- `ensure_no_inprogress_op`

--- FILE: docs/cloud.md (1,150p) ---
# Megaplan Cloud

`python -m arnold.pipelines.megaplan cloud` keeps cloud orchestration thin. Core megaplan owns plan, auto, and chain behavior; cloud subcommands stage files, pick a transport, and run the core commands remotely.

Examples below use `python -m arnold.pipelines.megaplan ...`; reuse that verified module launcher for every cloud command. Add `--cloud-yaml /path/to/cloud.yaml` when `cloud.yaml` is not at the project root.

## Providers

| Provider | Use case | Notes |
|---|---|---|
| `railway` | Hosted runner with Railway SSH/logs/volume primitives | Good default for shared remote runs. |
| `local` | Fast local iteration and CI-friendly smoke tests | Uses `docker compose` from a persistent deploy dir under `~/.megaplan/cloud/<compose_project>/`. |
| `ssh` | Any reachable Docker host over SSH | Syncs the deploy dir to `ssh.remote_dir` with `rsync`, or `scp -r` when `rsync` is unavailable. |

`provider: fly` remains reserved for a future release.

## Quick Start

1. Scaffold:

```bash
python -m arnold.pipelines.megaplan cloud init
```

2. Edit `cloud.yaml` for repo, provider, mode, secrets, and optional toolchains.

   See [docs/configuration.md](configuration.md) for where local config files, provider keys, cloud secrets, and database-mode environment variables are read from.

3. Export the local secrets named under `secrets:`:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...        # optional, but recommended for push/private clone
export ANTHROPIC_API_KEY=...   # optional
```

4. Build and deploy:

```bash
python -m arnold.pipelines.megaplan cloud build
python -m arnold.pipelines.megaplan cloud deploy
```

5. Start work remotely:

```bash
python -m arnold.pipelines.megaplan cloud bootstrap .megaplan/briefs/tiny-plan.md
python -m arnold.pipelines.megaplan cloud chain .megaplan/briefs/my-epic/chain.yaml
```

6. Inspect and connect:

```bash
python -m arnold.pipelines.megaplan cloud status
python -m arnold.pipelines.megaplan cloud status --chain
python -m arnold.pipelines.megaplan cloud logs
python -m arnold.pipelines.megaplan cloud attach
```

## `cloud.yaml` Reference

### Top-level fields

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `provider` | no | `railway` | One of `railway`, `local`, or `ssh`. |
| `mode` | no | `idle` | Runner mode: `auto`, `chain`, or `idle`. |
| `secrets` | no | `[]` | Local env var names uploaded during `python -m arnold.pipelines.megaplan cloud deploy` and redacted from cloud log output where possible. |
| `toolchains` | no | `[]` | Extra language toolchains layered into the image. Use aliases `rust`, `go`, `java`, or `{name, install}` mappings. |

### `repo`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `repo.url` | yes | none | Git URL cloned into the remote workspace. |
| `repo.branch` | no | `main` | Branch checked out on clone. |
| `repo.workspace` | no | `/workspace/app` | Absolute repo path used for remote `cd`, tmux, file uploads, and wrapper commands. |

### `agents`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `agents.default` | no | `codex` | Default megaplan agent for routed steps. |
| `agents.<step>` | no | inherits `default` | Optional per-step override such as `plan`, `review`, `execute`, or `loop_execute`. |

### `codex`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `codex.model` | no | `gpt-5.4` | Written into `/root/.codex/config.toml` on boot. |
| `codex.reasoning` | no | `high` | Reasoning level written into `/root/.codex/config.toml` on boot. |
| `megaplan.codex_auth` | no | `chatgpt` | `chatgpt` forces the ChatGPT-subscription OAuth (`preferred_auth_method=chatgpt`; codex uses `chatgpt.com/backend-api/codex` even when `OPENAI_API_KEY` is set) and seeds your local `~/.codex`/`~/.hermes` OAuth onto the volume. `apikey` opts into standard API-key billing. See the "Codex auth" section in the cloud skill. |

> **Codex auth gotcha:** without `codex_auth=chatgpt`, a stray `OPENAI_API_KEY` makes the codex CLI use API-key mode → `api.openai.com` billing → `ERROR: Quota exceeded. Check your plan and billing details.` even with a working ChatGPT subscription.

### `auto`

Used only when `mode: auto`.

| Field | Required in `auto` mode | Default | Meaning |
|---|---|---:|---|
| `auto.plan_name` | yes | none | Remote plan name for boot-time `python -m arnold.pipelines.megaplan auto --plan ...`. |
| `auto.idea_file` | yes | none | Absolute remote path to the idea file already staged on the workspace volume. |
| `auto.robustness` | no | `standard` | Robustness for the boot-time init fallback. |

### `chain`

Used only when `mode: chain`.

| Field | Required in `chain` mode | Default | Meaning |
|---|---|---:|---|
| `chain.spec` | yes | none | Absolute remote path to the already-staged chain spec. |

### `megaplan`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `megaplan.ref` | no | `main` | Branch, tag, or SHA installed on boot via `pip install --upgrade git+...@<ref>`. |

### `resources`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `resources.volume` | no | none | Provider-specific persistent volume name. `destroy` deletes it only when set. |
| `resources.port` | no | `8080` | Health server port exposed by the container. |

### `railway`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `railway.service` | no | `agent` | Railway service name used by `deploy`, `logs`, and `down`. |
| `railway.session` | no | `agent` | Railway SSH session name used for interactive attaches. |
| `railway.project` | no | unset | Optional project passed to Railway commands. |
| `railway.environment` | no | unset | Optional environment passed to Railway commands. |

### `local`

| Field | Required when `provider: local` | Default | Meaning |
|---|---|---:|---|
| `local.compose_project` | no | `megaplan-cloud` | Docker Compose project name used for build, logs, exec, and teardown. |
| `local.workdir` | no | `workspace` | Bind-mounted directory inside the persistent local deploy dir. |

### `ssh`

| Field | Required when `provider: ssh` | Default | Meaning |
|---|---|---:|---|
| `ssh.host` | yes | none | Remote SSH host. |
| `ssh.user` | no | unset | Optional SSH username. |
| `ssh.port` | no | `22` | SSH port. |
| `ssh.identity_file` | no | unset | Optional identity file passed to `ssh`, `scp`, and `rsync`. |

--- FILE: arnold_pipelines/megaplan/cloud/auth.py (1,260p) ---
"""Cloud auth seeding helpers."""

from __future__ import annotations

import base64
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Any

from arnold_pipelines.megaplan.cloud.spec import CloudSpec


_CODEX_SOURCE = Path(".codex/auth.json")
_HERMES_SOURCE = Path(".hermes/auth.json")


@dataclass(frozen=True)
class OAuthSeed:
    label: str
    local_relative: Path
    persistent_dest: str
    root_dest: str


OAUTH_SEEDS = (
    OAuthSeed(
        label="codex",
        local_relative=_CODEX_SOURCE,
        persistent_dest="/workspace/.creds/codex-auth.json",
        root_dest="/root/.codex/auth.json",
    ),
    OAuthSeed(
        label="hermes",
        local_relative=_HERMES_SOURCE,
        persistent_dest="/workspace/.creds/hermes-auth.json",
        root_dest="/root/.hermes/auth.json",
    ),
)


def _remote_seed_command(*, payload_b64: str, persistent_dest: str, root_dest: str) -> str:
    persistent = PurePosixPath(persistent_dest)
    root = PurePosixPath(root_dest)
    persistent_tmp = persistent.with_name(f".{persistent.name}.tmp.$$")
    root_tmp = root.with_name(f".{root.name}.tmp.$$")
    return " ".join(
        [
            "umask 077;",
            f"mkdir -p {shlex.quote(str(persistent.parent))} {shlex.quote(str(root.parent))};",
            f"AUTH_B64={shlex.quote(payload_b64)};",
            f"tmp={shlex.quote(str(persistent_tmp))};",
            'printf %s "$AUTH_B64" | base64 -d > "$tmp" &&',
            f"mv \"$tmp\" {shlex.quote(str(persistent))} &&",
            f"chmod 600 {shlex.quote(str(persistent))} &&",
            f"tmp={shlex.quote(str(root_tmp))};",
            'printf %s "$AUTH_B64" | base64 -d > "$tmp" &&',
            f"mv \"$tmp\" {shlex.quote(str(root))} &&",
            f"chmod 600 {shlex.quote(str(root))};",
            "unset AUTH_B64",
        ]
    )


def seed_codex_oauth(
    spec: CloudSpec,
    provider: Any,
    *,
    home: Path | None = None,
    writer: Callable[[str], object] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Best-effort seed of local ChatGPT Codex OAuth into the cloud box.

    The seed is written both to the persistent volume under ``/workspace/.creds``
    and to the current root home so an already-running box can use it
    immediately. Entrypoint boot copies the persistent files back into ``/root``
    after restarts.
    """
    write = writer or sys.stderr.write
    events: list[dict[str, str]] = []
    if spec.megaplan.codex_auth == "apikey":
        message = "cloud codex OAuth seed: skipped because megaplan.codex_auth=apikey\n"
        write(message)
        return {"events": [{"label": "all", "status": "skipped", "reason": "codex_auth=apikey"}]}

    root = home or Path.home()
    for seed in OAUTH_SEEDS:
        local_path = root / seed.local_relative
        if not local_path.exists():
            message = f"cloud codex OAuth seed: local {local_path} absent; skipping {seed.label}\n"
            write(message)
            events.append({"label": seed.label, "status": "skipped", "reason": "absent"})
            continue
        payload_b64 = base64.b64encode(local_path.read_bytes()).decode("ascii")
        command = _remote_seed_command(
            payload_b64=payload_b64,
            persistent_dest=seed.persistent_dest,
            root_dest=seed.root_dest,
        )
        try:
            result: subprocess.CompletedProcess[str] = provider.ssh_exec(command)
        except Exception as exc:  # pragma: no cover - defensive best-effort path
            write(f"cloud codex OAuth seed: {seed.label} seed failed: {exc}\n")
            events.append({"label": seed.label, "status": "failed", "reason": str(exc)})
            continue
        if result.returncode == 0:
            write(
                f"cloud codex OAuth seed: seeded {seed.label} auth to {seed.persistent_dest} "
                f"and {seed.root_dest}\n"
            )
            events.append({"label": seed.label, "status": "seeded"})
            continue
        reason = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        write(f"cloud codex OAuth seed: {seed.label} seed failed: {reason}\n")
        events.append({"label": seed.label, "status": "failed", "reason": reason})
    return {"events": events}

--- FILE: arnold_pipelines/megaplan/cloud/template.py (1,260p) ---
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

--- FILE: arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl (1,260p) ---
#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/entrypoint.log
exec > >(tee -a "$$LOG") 2>&1

echo "=== $$(date -Iseconds) entrypoint starting ==="

mkdir -p /workspace /root/.ssh /root/.config/megaplan /root/.codex /root/.hermes /workspace/.creds
chmod 700 /root/.ssh
chmod 700 /root/.codex /root/.hermes /workspace/.creds

REPO_URL="$${REPO_URL:-${REPO_URL}}"
REPO_BRANCH="$${REPO_BRANCH:-${REPO_BRANCH}}"
WORKSPACE_PATH="${WORKSPACE_PATH}"
MODE="${MODE}"
IDEA_FILE="${IDEA_FILE}"
CHAIN_SPEC="${CHAIN_SPEC}"
AUTO_PLAN_NAME="${AUTO_PLAN_NAME}"
CODEX_AUTH_METHOD="${CODEX_AUTH_METHOD}"
export MEGAPLAN_TRUSTED_CONTAINER=1

# Git identity
git config --global user.email "$${GIT_EMAIL:-${CODEX_EMAIL}}"
git config --global user.name "$${GIT_NAME:-Codex Agent}"
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global --add safe.directory "$$WORKSPACE_PATH"

# GitHub credential helper if token present
if [[ -n "$${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN present — configuring git credentials"
  git config --global credential.helper store
  cat > /root/.git-credentials <<EOF
https://x-access-token:$${GITHUB_TOKEN}@github.com
EOF
  chmod 600 /root/.git-credentials
fi

# Clone repo if missing (volume may already have it from a prior boot)
${ENSURE_REPO_BLOCK}

# Codex OAuth seed from persistent volume. /root is ephemeral; /workspace persists.
if [[ "$$CODEX_AUTH_METHOD" == "chatgpt" ]]; then
  if [[ -s /workspace/.creds/codex-auth.json ]]; then
    install -m 600 /workspace/.creds/codex-auth.json /root/.codex/auth.json
    echo "Codex auth: seeded ChatGPT OAuth credentials from persistent volume"
  else
    echo "Codex auth: ChatGPT OAuth selected; no persisted /workspace/.creds/codex-auth.json seed found"
  fi
  if [[ -s /workspace/.creds/hermes-auth.json ]]; then
    install -m 600 /workspace/.creds/hermes-auth.json /root/.hermes/auth.json
    echo "Hermes auth: seeded OpenAI Codex OAuth credentials from persistent volume"
  fi
fi

# Codex auth from env, only for explicit API-key billing opt-out.
if [[ "$$CODEX_AUTH_METHOD" == "apikey" ]] && [[ -n "$${OPENAI_API_KEY:-}" ]] && [[ ! -f /root/.codex/auth.json ]]; then
  echo "Authenticating codex with OPENAI_API_KEY"
  printf '%s' "$$OPENAI_API_KEY" | codex login --with-api-key 2>&1 | tail -3 || true
fi

${CLAUDE_AUTH_BLOCK}

# Codex model + reasoning config — always overwrite on boot so new tiers propagate.
# sandbox_mode = "danger-full-access" stays on because the container is the sandbox.
cat > /root/.codex/config.toml <<EOF
model = "${CODEX_MODEL}"
model_reasoning_effort = "${CODEX_REASONING}"
sandbox_mode = "danger-full-access"
approval_policy = "never"
${CODEX_AUTH_CONFIG_BLOCK}
EOF
echo "Codex model: ${CODEX_MODEL}, reasoning: ${CODEX_REASONING}, auth: $$CODEX_AUTH_METHOD, sandbox: danger-full-access (container-sandboxed)"

# Megaplan install: always re-pull on boot so entrypoint restarts pick up the
# requested ref without rebuilding the base image. The refresh helper is also
# invoked by `arnold cloud chain` before each run.
#
# MEGAPLAN_INSTALL_SPEC – runtime pip install override, verbatim. Git specs get
#   @MEGAPLAN_REF appended.
# MEGAPLAN_INSTALL_SPEC_OVERRIDE – rendered cloud.yaml megaplan.install_spec.
# MEGAPLAN_REPO – rendered cloud.yaml megaplan.repo source URL.
# MEGAPLAN_REF – git ref (branch/tag/commit) used for git installs.
MEGAPLAN_REF="$${MEGAPLAN_REF:-${MEGAPLAN_REF}}"
MEGAPLAN_REPO="$${MEGAPLAN_REPO:-${MEGAPLAN_REPO}}"
MEGAPLAN_INSTALL_SPEC_OVERRIDE="$${MEGAPLAN_INSTALL_SPEC_OVERRIDE:-${MEGAPLAN_INSTALL_SPEC_OVERRIDE}}"

mp_install_megaplan() {
  local explicit_spec="$${MEGAPLAN_INSTALL_SPEC:-$${MEGAPLAN_INSTALL_SPEC_OVERRIDE:-}}"
  if [[ -n "$$explicit_spec" ]]; then
    if [[ "$$explicit_spec" == *git+* ]] && [[ -n "$$MEGAPLAN_REF" ]]; then
      echo "Installing/upgrading arnold from explicit git spec at ref $$MEGAPLAN_REF"
      pip install --upgrade --force-reinstall --no-cache-dir "$$explicit_spec@$$MEGAPLAN_REF" 2>&1 | tail -3
    else
      echo "Installing/upgrading arnold from explicit spec"
      pip install --upgrade --force-reinstall --no-cache-dir "$$explicit_spec" 2>&1 | tail -3
    fi
    return
  fi

  if [[ -n "$$MEGAPLAN_REPO" ]]; then
    local repo="$$MEGAPLAN_REPO"
    if [[ "$$repo" == https://github.com/* ]] && [[ "$$repo" != https://*@github.com/* ]] && [[ -n "$${GITHUB_TOKEN:-}" ]]; then
      repo="https://x-access-token:$${GITHUB_TOKEN}@github.com/$${repo#https://github.com/}"
    fi
    local spec="arnold[agent] @ git+$$repo"
    echo "Installing/upgrading arnold from repo at ref $$MEGAPLAN_REF"
    pip install --upgrade --force-reinstall --no-cache-dir "$$spec@$$MEGAPLAN_REF" 2>&1 | tail -3
    return
  fi

  if [[ -n "$$MEGAPLAN_REF" ]]; then
    echo "MEGAPLAN_REF=$$MEGAPLAN_REF ignored because no git source is configured — set megaplan.repo (or a git+ megaplan.install_spec) in cloud.yaml to install from source at this ref."
  fi
  echo "Installing/upgrading arnold: arnold[agent]"
  pip install --upgrade --force-reinstall --no-cache-dir "arnold[agent]" 2>&1 | tail -3
}

{
  echo '#!/usr/bin/env bash'
  echo 'set -euo pipefail'
  printf 'MEGAPLAN_REF=$${MEGAPLAN_REF:-%q}\n' "$$MEGAPLAN_REF"
  printf 'MEGAPLAN_REPO=$${MEGAPLAN_REPO:-%q}\n' "$$MEGAPLAN_REPO"
  printf 'MEGAPLAN_INSTALL_SPEC_OVERRIDE=$${MEGAPLAN_INSTALL_SPEC_OVERRIDE:-%q}\n' "$$MEGAPLAN_INSTALL_SPEC_OVERRIDE"
  declare -f mp_install_megaplan
  echo 'mp_install_megaplan "$$@"'
} > /usr/local/bin/mp-refresh-megaplan
chmod +x /usr/local/bin/mp-refresh-megaplan

mp_install_megaplan

echo "Configuring arnold agent routing and execution defaults"
${AGENT_ROUTING_BLOCK}
arnold config set execution.auto_approve true >/dev/null 2>&1 || true
arnold config set execution.robustness "${ROBUSTNESS}" >/dev/null 2>&1 || true

echo "Runner mode: $$MODE"

# Launch heartbeat in its own tmux session.
if ! tmux has-session -t heartbeat 2>/dev/null; then
  tmux new-session -d -s heartbeat -c /workspace "bash -lc '/usr/local/bin/arnold-heartbeat'"
  echo "heartbeat watchdog running in tmux session 'heartbeat'"
fi

# Tiny health server so Railway keeps container alive
python3 /usr/local/bin/healthserver.py &
HEALTH_PID=$$!
echo "healthserver.py running as pid $$HEALTH_PID"

# Ensure tmux session 'agent' exists. The renderer injects the mode-specific
# launch block here so auto/chain can warn-and-drop-to-idle on missing inputs.
if ! tmux has-session -t agent 2>/dev/null; then
${RUNNER_LAUNCH_BLOCK}
fi
echo "tmux 'agent' session ready — attach: railway ssh --session agent"

echo "=== entrypoint idle ==="
wait "$$HEALTH_PID"

--- FILE: arnold_pipelines/megaplan/cloud/providers/ssh.py (1,180p) ---
from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from arnold_pipelines.megaplan.cloud.spec import CloudSpec, SshSpec
from arnold_pipelines.megaplan.types import CliError

from .base import Provider, _logs_follow, _missing_cli_error, _write_redacted_output


INSTALL_LINK = "Install: https://www.openssh.com/"


class SshProvider(Provider):
    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec
        self._ssh = spec.ssh or SshSpec(host="localhost")
        self._ssh_binary = shutil.which("ssh")
        self._scp_binary = shutil.which("scp")
        self._rsync_binary = shutil.which("rsync")
        if self._ssh_binary is None:
            _missing_cli_error("ssh", INSTALL_LINK.removeprefix("Install: "))
        if self._scp_binary is None and self._rsync_binary is None:
            _missing_cli_error("scp/rsync", INSTALL_LINK.removeprefix("Install: "))

    def _target(self) -> str:
        if self._ssh.user:
            return f"{self._ssh.user}@{self._ssh.host}"
        return self._ssh.host

    def _ssh_transport_argv(self) -> list[str]:
        argv = [self._ssh_binary or "ssh", "-p", str(self._ssh.port)]
        if self._ssh.identity_file:
            argv.extend(["-i", self._ssh.identity_file])
        return argv

    def _run(
        self,
        argv: list[str],
        *,
        capture_output: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            kwargs: dict[str, object] = {
                "capture_output": capture_output,
                "text": True,
                "check": False,
            }
            if input is not None:
                kwargs["input"] = input
            result = subprocess.run(argv, **kwargs)
        except FileNotFoundError as exc:
            raise CliError("provider_failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise CliError("provider_failed", stderr or f"Command failed: {' '.join(argv)}")
        return result

    def _remote_run(
        self,
        command: str,
        *,
        capture_output: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            [*self._ssh_transport_argv(), self._target(), command],
            capture_output=capture_output,
            input=input,
        )

    def _sync_deploy_dir(self, deploy_dir: Path) -> None:
        remote_dir = shlex.quote(self._ssh.remote_dir)
        if self._rsync_binary is not None:
            self._remote_run(f"mkdir -p {remote_dir}")
            self._run(
                [
                    self._rsync_binary,
                    "-az",
                    "-e",
                    shlex.join(self._ssh_transport_argv()),
                    f"{deploy_dir}/",
                    f"{self._target()}:{remote_dir}/",
                ]
            )
            return
        sys.stderr.write("WARN: rsync unavailable; falling back to scp -r\n")
        self._remote_run(f"rm -rf {remote_dir} && mkdir -p {remote_dir}")
        self._run(
            [
                self._scp_binary or "scp",
                "-r",
                "-P",
                str(self._ssh.port),
                *(["-i", self._ssh.identity_file] if self._ssh.identity_file else []),
                f"{deploy_dir}/.",
                f"{self._target()}:{remote_dir}",
            ]
        )

    def build(self, deploy_dir: Path) -> int:
        self._sync_deploy_dir(deploy_dir)
        self._remote_run(
            f"docker build -t {shlex.quote(self._ssh.container)} {shlex.quote(self._ssh.remote_dir)}"
        )
        return 0

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
        del deploy_dir
        env_path = f"{self._ssh.remote_dir}/.env"
        env_lines = [f"PORT={self._spec.resources.port}"]
        env_lines.extend(f"{name}={value}" for name, value in secrets.items())
        self._remote_run(f"cat > {shlex.quote(env_path)}", input="\n".join(env_lines) + "\n")
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true"
        )
        self._remote_run(
            " ".join(
                [
                    "docker run -d",
                    f"--name {shlex.quote(self._ssh.container)}",
                    "--restart unless-stopped",
                    f"--env-file {shlex.quote(env_path)}",
                    f"-p {self._spec.resources.port}:{self._spec.resources.port}",
                    shlex.quote(self._ssh.container),
                ]
            )
        )
        return 0

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        return self._remote_run(
            f"docker exec {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(command)}"
        )

    def upload_file(self, src: Path, dest: str) -> None:
        payload = base64.b64encode(src.read_bytes()).decode("ascii")
        parent = Path(dest).parent.as_posix()
        inner = f"mkdir -p {shlex.quote(parent)} && base64 -d > {shlex.quote(dest)}"
        self._remote_run(
            f"docker exec -i {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(inner)}",
            input=payload,
        )

    def read_remote_file(self, path: str) -> str:
        result = self._remote_run(
            f"docker exec {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(f'cat {shlex.quote(path)}')}"
        )
        return result.stdout

    def attach(self) -> int:
        self._remote_run(
            f"docker exec -it {shlex.quote(self._ssh.container)} tmux attach -t agent",
            capture_output=False,
        )
        return 0

    def logs(self, *, follow: bool = True) -> int:
        argv = f"docker logs {'-f ' if follow else '--tail 200 '}{shlex.quote(self._ssh.container)}"
        if follow:
            return _logs_follow(
                [*self._ssh_transport_argv(), self._target(), argv.strip()],
                secret_names=self._spec.secrets,
                env=os.environ,
            )
        result = self._remote_run(argv.strip())
        _write_redacted_output(result, secret_names=self._spec.secrets, env=os.environ)
        return 0

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        command = f"cd {shlex.quote(workspace)} && arnold status"
        if plan is not None:
