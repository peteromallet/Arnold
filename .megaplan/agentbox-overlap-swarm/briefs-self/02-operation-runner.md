You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality. The brief embeds local file excerpts because you do not have filesystem tools. Return: existing functionality reusable directly, functionality needing extraction/generalization, missing pieces, risks/gotchas, and a recommended first implementation slice. Keep under 900 words and cite file names/sections.\nFocus only on operation registry, tmux/process runner, logs, status, attach/stop/restart overlap.


--- FILE: docs/agentbox-persistent-machine-plan.md (1,120p) ---
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

--- FILE: docs/agentbox-persistent-machine-plan.md (335,460p) ---

```bash
git clone --bare git@github.com:org/repo.git /workspace/repos/repo.git
git --git-dir=/workspace/repos/repo.git worktree add \
  /workspace/worktrees/op-123/repo \
  -b agent/op-123 \
  origin/main
```

Reuse:

- `arnold_pipelines/megaplan/bakeoff/worktree.py`
- existing `--in-worktree` behavior from `arnold_pipelines/megaplan/cli/__init__.py`

Needed extraction:

- parameterize worktree root path instead of hardcoding `~/Documents/.megaplan-worktrees`;
- operate on named repos, not only current working directory;
- return structured metadata instead of mutating argparse only.

### 4. Credential Sync

Purpose: push selected local credentials to the remote machine.

Build:

- `agentbox creds push`
- `agentbox creds list`
- `agentbox creds test`
- `agentbox creds rotate`
- remote `/workspace/secrets` with strict permissions
- per-operation env injection

Credential classes:

- GitHub token or SSH key material;
- Codex OAuth/auth bundle;
- Claude refresh token or API key fallback;
- OpenAI/Anthropic/DeepSeek/Fireworks keys;
- Discord bot token;
- Supabase/Railway/project-specific tokens.

Reuse:

- Megaplan Cloud Codex OAuth seed logic;
- Claude refresh-token shim design from the Megaplan Cloud skill;
- Railway secret upload semantics as a reference;
- `age`, `pass`, or 1Password CLI patterns if encrypted-at-rest storage is required.

Rule: sync only explicit credentials. Do not dump the entire local environment.

### 5. Operation Registry

Purpose: every launched unit of work has a durable identity and inspectable state.

Operation record:

```yaml
id: op-20260623-foo
kind: megaplan-chain
status: running
source: discord
created_at: "2026-06-23T10:00:00Z"
repos:
  - name: megaplan
    branch: agent/op-20260623-foo
    worktree: /workspace/worktrees/op-20260623-foo/megaplan
tmux_session: op-20260623-foo
log: /workspace/runs/op-20260623-foo/log.txt
manifest: /workspace/runs/op-20260623-foo/manifest.yaml
```

Build:

- file or SQLite-backed registry;
- operation creation;
- status updates;
- mapping from tmux session to operation;
- log/event path tracking;
- PR/branch/CI metadata.

Reuse:

- Megaplan chain state model;
- Megaplan resident store patterns;
- CCManager/Rover status models;
- `.megaplan/plans` conventions where useful.

This is the product-specific core. We should expect to build it ourselves.

### 6. Process Runner

Purpose: launch, monitor, stop, restart, and attach to long-running operations.

Build:

- tmux session per operation;
- log capture to `/workspace/runs/<op>/log.txt`;
- status classifier;
- stop/restart/attach commands;
- optional resource limits later.

Reuse:

- Megaplan Cloud tmux/session/log conventions;
- Rover/CCManager agent process handling;
- systemd for long-running manager services.

### 7. Agent Adapters

Purpose: normalize how different agent or task types are launched.

Initial adapter types:

- `megaplan-chain`
- `megaplan-plan`
- `codex`
- `claude`
- `subagent`
- `test`
- `shell`

Adapter interface:

```python
class OperationAdapter:

--- FILE: arnold_pipelines/megaplan/cloud/cli.py (1,240p) ---
"""CLI entrypoints for arnold cloud commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

import yaml

from arnold_pipelines.megaplan.cloud.auth import seed_codex_oauth
from arnold_pipelines.megaplan.cloud.providers.base import (
    DeployReport,
    DeployStepReport,
    _write_redacted_output,
    get_provider,
)
from arnold_pipelines.megaplan.cloud.redact import redact
from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RailwaySpec, apply_repo_overrides, load_spec as load_cloud_spec
from arnold_pipelines.megaplan.cloud.template import materialize_deploy_dir, render_ensure_repos_block
from arnold_pipelines.megaplan.types import CliError


load_spec = load_cloud_spec

# Cloud deployments always drive phases via subprocess (remote SSH exec);
# the substrate is pinned here so the cloud CLI explicitly declares its
# execution model to _phase_command (M3 Step 12 compatibility boundary).
cloud_substrate: str = "subprocess_isolated"


def _register_cloud_subcommands(cloud_parser: argparse.ArgumentParser) -> None:
    cloud_sub = cloud_parser.add_subparsers(dest="cloud_action", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--cloud-yaml",
        default=None,
        help="Path to cloud.yaml (default: <project-root>/cloud.yaml)",
    )

    init_parser = cloud_sub.add_parser(
        "init",
        parents=[shared],
        help="Scaffold a cloud.yaml file at the project root",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing cloud.yaml",
    )

    cloud_sub.add_parser("build", parents=[shared], help="Build the cloud image")
    cloud_sub.add_parser("deploy", parents=[shared], help="Deploy the cloud runner")

    chain_parser = cloud_sub.add_parser(
        "chain",
        parents=[shared],
        help="Upload a chain spec and start it remotely",
    )
    chain_parser.add_argument("spec", help="Local chain spec path")
    chain_parser.add_argument(
        "--idea-dir",
        default=None,
        help="Directory containing local idea files referenced by the chain spec",
    )
    chain_parser.add_argument(
        "--fresh",
        "--reset",
        dest="fresh",
        action="store_true",
        help="Reset this chain's remote state before launch",
    )
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Pass --no-git-refresh to the remote `python -m arnold_pipelines.megaplan chain start`, "
            "skipping the automatic base-branch refresh."
        ),
    )
    _add_repo_override_args(chain_parser)

    bootstrap_parser = cloud_sub.add_parser(
        "bootstrap",
        parents=[shared],
        help="Upload an idea file and start arnold init remotely",
    )
    bootstrap_parser.add_argument("idea_file", help="Local idea file path")
    bootstrap_parser.add_argument("--plan-name", default=None, help="Optional remote plan name")
    bootstrap_parser.add_argument("--robustness", default="standard")
    _add_repo_override_args(bootstrap_parser)

    status_parser = cloud_sub.add_parser(
        "status",
        parents=[shared],
        help="Fetch remote `arnold status` JSON",
    )
    status_parser.add_argument(
        "--chain",
        action="store_true",
        help="Fetch remote chain_state.json and render core chain status",
    )
    status_parser.add_argument(
        "--all",
        action="store_true",
        help="List active cloud chain tmux sessions on the shared runner",
    )
    status_parser.add_argument(
        "--remote-spec",
        default=None,
        help="Explicit remote chain spec path for `cloud status --chain`",
    )
    status_parser.add_argument("--plan", help="Optional plan name to query remotely")

    attach_parser = cloud_sub.add_parser(
        "attach",
        parents=[shared],
        help="Attach to the remote tmux session",
    )
    attach_parser.add_argument(
        "--session",
        help="Override the remote tmux session name for providers that support sessions",
    )

    logs_parser = cloud_sub.add_parser(
        "logs",
        parents=[shared],
        help="Stream or fetch remote logs",
    )
    logs_parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Fetch recent logs without streaming",
    )

    cloud_sub.add_parser(
        "chains",
        parents=[shared],
        help="List active cloud chain tmux sessions on the shared runner",
    )

    exec_parser = cloud_sub.add_parser(
        "exec",
        parents=[shared],
        help="Run an arbitrary remote command",
    )
    exec_parser.add_argument("command", help="Command string to execute remotely")

    resume_parser = cloud_sub.add_parser(
        "resume",
        parents=[shared],
        help="Resume the remote plan's next step",
    )
    resume_parser.add_argument("--plan", help="Optional plan name to resume")

    cloud_sub.add_parser("down", parents=[shared], help="Pause the deployment without deleting volume")

    supervise_parser = cloud_sub.add_parser(
        "supervise",
        parents=[shared],
        help="Run a one-shot supervisor tick against a cloud chain",
    )
    supervise_parser.add_argument(
        "--chain",
        action="store_true",
        help="Supervise the remote chain (required)",
    )
    supervise_parser.add_argument(
        "--remote-spec",
        default=None,
        help="Explicit remote chain spec path for supervision",
    )

    destroy_parser = cloud_sub.add_parser(
        "destroy",
        parents=[shared],
        help="Tear down the deployment and delete the volume if configured",
    )
    destroy_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive destroy confirmation",
    )


def build_cloud_parser(subparsers: Any) -> None:
    cloud_parser = subparsers.add_parser(
        "cloud",
        help="Manage provider-backed arnold cloud runners",
    )
    _register_cloud_subcommands(cloud_parser)


def _add_repo_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-url", default=None, help="Override cloud.yaml repo.url in memory")
    parser.add_argument("--repo-branch", default=None, help="Override cloud.yaml repo.branch in memory")
    parser.add_argument("--repo-workspace", default=None, help="Override cloud.yaml repo.workspace in memory")


def run_cloud_cli(root: Path, args: argparse.Namespace) -> int:
    try:
        action = getattr(args, "cloud_action")
        if action == "init":
            return _run_init(root, args)

        spec = _load_cloud_spec(root, args)
        provider = _provider_for_action(spec, args)

        if action == "chain":
            with _materialized_deploy_dir(spec):
                return _run_chain_wrapper(root, args, spec, provider)

        if action == "bootstrap":
            with _materialized_deploy_dir(spec):
                return _run_bootstrap_wrapper(args, spec, provider)

        if action == "build":
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.build(deploy_dir)

        if action == "deploy":
            secrets = {name: os.environ.get(name, "") for name in spec.secrets}
            with _materialized_deploy_dir(spec) as deploy_dir:
                result = provider.deploy(deploy_dir, secrets=secrets)
                report = _coerce_deploy_report(result, spec=spec, deploy_dir=deploy_dir)
                report.steps = [
                    *_deploy_context_steps(deploy_dir),
                    *report.steps,

--- FILE: arnold_pipelines/megaplan/cloud/cli.py (520,760p) ---
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "remote dependency check failed").strip()
        raise CliError("provider_failed", message)
    return sorted({part for part in result.stdout.split() if part})


def _remote_repo_head(provider, workspace: str) -> dict[str, str | None]:
    command = (
        f"git -C {shlex.quote(workspace)} rev-parse --abbrev-ref HEAD 2>/dev/null && "
        f"git -C {shlex.quote(workspace)} rev-parse HEAD 2>/dev/null"
    )
    result = provider.ssh_exec(command)
    if result.returncode != 0:
        return {"branch": None, "head": None}
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "branch": lines[0] if len(lines) >= 1 else None,
        "head": lines[1] if len(lines) >= 2 else None,
    }


def _tmux_launch_status(result, *, session_name: str = "megaplan-chain") -> str:
    output = f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}"
    if "already running" in output:
        return "already_running"
    if f"started {session_name} session" in output:
        return "started"
    return "unknown"


def _resolved_phase_map_summary(preflight_summary: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for milestone in preflight_summary.get("milestones", []):
        if not isinstance(milestone, dict):
            continue
        summaries.append(
            {
                "label": milestone.get("label"),
                "profile": milestone.get("profile"),
                "explicit_phase_model": milestone.get("explicit_phase_model", []),
                "resolved_phase_map": milestone.get("resolved_phase_map", {}),
                "required_agents": milestone.get("required_agents", []),
                "runtime_commands": milestone.get("runtime_commands", []),
                "env_hints": milestone.get("env_hints", []),
                "provider_requirements": milestone.get("provider_requirements", []),
            }
        )
    return summaries


def _cloud_chain_launch_provenance(
    *,
    spec: CloudSpec,
    ctx: ChainLaunchContext,
    chain_spec,
    preflight_summary: dict[str, Any],
    uploaded_idea_count: int,
    repo_head: dict[str, str | None],
    tmux_result,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_milestone = chain_spec.milestones[0].label if chain_spec.milestones else None
    return {
        "success": True,
        "event": "cloud_chain_launched",
        "remote_spec": ctx.remote_spec_path,
        "current_milestone": current_milestone,
        "plan_name": None,
        "pr_number": None,
        "repo": {
            "url": spec.repo.url,
            "branch": spec.repo.branch,
            "workspace": ctx.workspace,
            "head": repo_head.get("head"),
            "checked_out_branch": repo_head.get("branch"),
        },
        "chain": {
            "base_branch": chain_spec.base_branch,
            "milestone_count": len(chain_spec.milestones),
            "resolved_phase_map_summary": _resolved_phase_map_summary(preflight_summary),
            "prerequisite_policy": chain_spec.prerequisite_policy,
            "validation_policy": chain_spec.validation_policy,
            "review_policy": dict(chain_spec.review_policy or {}),
        },
        "megaplan": {
            "ref": spec.megaplan.ref,
            "install_source": "cloud_image_runtime",
        },
        "uploaded_idea_count": uploaded_idea_count,
        "tmux": {
            "session": ctx.session_name,
            "status": _tmux_launch_status(tmux_result, session_name=ctx.session_name),
        },
        "log": {"chain_log": ctx.log_path},
        "launch": {
            "identity_digest": ctx.digest,
            "session_marker": ctx.marker_path,
            "derived_workspace": not spec.repo.workspace_explicit,
            "derived_session": not spec.chain_session_explicit,
        },
        "verification": verification or {},
    }


# ---------------------------------------------------------------------------
# Shared chain command helper — canonical session / log / env / quoting
# ---------------------------------------------------------------------------

CHAIN_SESSION_NAME = "megaplan-chain"
_CHAIN_LOG_RELATIVE = ".megaplan/cloud-chain.log"
_CHAIN_SESSION_MARKER_DIR = "/workspace/.megaplan/cloud-sessions"
_CHAIN_VERIFY_ATTEMPTS = 6
_CHAIN_VERIFY_SLEEP_SECONDS = 5


@dataclass(frozen=True)
class ChainLaunchContext:
    identity: str
    slug: str
    digest: str
    workspace: str
    remote_spec_path: str
    session_name: str
    log_relative: str
    log_path: str
    state_path: str
    marker_path: str


def _slugify_chain_identity(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().lower()).strip(".-")
    return slug[:48] or "chain"


def _repo_dir_name(repo_url: str) -> str:
    tail = repo_url.rstrip("/").rsplit("/", 1)[-1] or "app"
    if tail.endswith(".git"):
        tail = tail[:-4]
    return _slugify_chain_identity(tail) or "app"


def _chain_identity_for(local_spec_path: Path, chain_spec: Any) -> tuple[str, str, str]:
    labels = ",".join(m.label for m in getattr(chain_spec, "milestones", []) if getattr(m, "label", None))
    seed = getattr(chain_spec, "seed_plan", None) or ""
    identity = f"{local_spec_path.stem}:{seed}:{labels}"
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]
    return identity, _slugify_chain_identity(local_spec_path.stem), digest


def _derive_chain_launch_context(
    *,
    spec: CloudSpec,
    local_spec_path: Path,
    chain_spec: Any,
) -> ChainLaunchContext:
    from arnold_pipelines.megaplan import chain as chain_module

    identity, slug, digest = _chain_identity_for(local_spec_path, chain_spec)
    session_name = (
        spec.chain_session
        if spec.chain_session_explicit
        else f"{CHAIN_SESSION_NAME}-{slug}-{digest[:8]}"
    )
    workspace = (
        spec.repo.workspace
        if spec.repo.workspace_explicit
        else f"/workspace/{slug}-{digest[:8]}/{_repo_dir_name(spec.repo.url)}"
    )
    remote_spec_path = str(PurePosixPath(workspace) / "chain.yaml")
    state_path = str(chain_module._state_path_for(Path(remote_spec_path)))
    log_relative = f".megaplan/cloud-chain-{session_name}.log"
    log_path = str(PurePosixPath(workspace) / log_relative)
    marker_path = str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{session_name}.json")
    return ChainLaunchContext(
        identity=identity,
        slug=slug,
        digest=digest,
        workspace=workspace,
        remote_spec_path=remote_spec_path,
        session_name=session_name,
        log_relative=log_relative,
        log_path=log_path,
        state_path=state_path,
        marker_path=marker_path,
    )


def _get_provider_identity(spec: CloudSpec) -> str | None:
    """Return a stable provider-level identity for marker enrichment and
    consistency checks.

    This is the provider's *service/project identity*, never an SSH attach
    session name or chain tmux session name.
    """
    if spec.provider == "railway":
        if spec.railway is not None:
            return spec.railway.service
        return None
    if spec.provider == "local":
        if spec.local is not None:
            return spec.local.compose_project
        return None
    if spec.provider == "ssh":
        if spec.ssh is not None:
            return spec.ssh.host
        return None
    return None


def _deploy_log_hint(spec: CloudSpec) -> dict[str, Any]:
    if spec.provider == "railway":
        service = spec.railway.service if spec.railway is not None else "agent"
        return {"command": f"arnold cloud logs --no-follow", "service": service}
    if spec.provider == "local":
        return {"command": "arnold cloud logs --no-follow"}
    if spec.provider == "ssh":
        return {"command": "arnold cloud logs --no-follow"}
    return {"status": "unknown"}


def _deploy_context_steps(deploy_dir: Path) -> list[DeployStepReport]:
    steps: list[DeployStepReport] = []
    for relative in ("Dockerfile", "entrypoint.sh"):
        path = deploy_dir / relative
        if not path.exists():
            steps.append(
                DeployStepReport(
                    name=f"render {relative}",
                    status="missing",
                    detail=f"{relative} was not materialized",
                )
            )
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        steps.append(
            DeployStepReport(
                name=f"render {relative}",
                status="ok",
                detail=f"sha256={digest}",
                metadata={"path": str(path), "sha256": digest},
            )

--- FILE: arnold_pipelines/megaplan/cloud/providers/base.py (1,220p) ---
"""Abstract base classes for cloud providers.

Sprint 2 will add `init_plan(...)`-style workflows and more providers. Provider
implementations should stay stateless beyond local CLI discovery and credential
resolution so the CLI can instantiate them on demand.
"""

from __future__ import annotations

import abc
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.cloud.spec import CloudSpec
from arnold_pipelines.megaplan.types import CliError


@dataclass
class DeployStepReport:
    name: str
    status: str
    detail: str = ""
    stdout: str = ""
    stderr: str = ""
    log_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployReport:
    success: bool
    provider: str
    service: str | None
    deploy_dir: str
    steps: list[DeployStepReport] = field(default_factory=list)
    image_rebuild: str = "unknown"
    image_ref: str | None = None
    no_op: bool = False
    vars_updated: int = 0
    logs: dict[str, Any] = field(default_factory=dict)
    verdict: str = ""
    warnings: list[str] = field(default_factory=list)
    exit_code: int = 0


def _missing_cli_error(binary: str, install_url: str) -> None:
    raise CliError(
        "provider_unavailable",
        f"Missing required CLI '{binary}'. Install: {install_url}",
    )


def _logs_follow(
    argv: list[str],
    *,
    cwd: Path | None = None,
    secret_names: list[str] | tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> int:
    from arnold_pipelines.megaplan.cloud.redact import stream_redact

    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CliError("provider_failed", str(exc)) from exc

    for chunk in stream_redact(proc, secret_names, env=env):
        sys.stdout.write(chunk)

    returncode = proc.wait()
    if returncode != 0:
        raise CliError("provider_failed", f"Command failed: {' '.join(argv)}")
    return 0


def _write_redacted_output(
    result: subprocess.CompletedProcess[str],
    *,
    secret_names: list[str] | tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> None:
    from arnold_pipelines.megaplan.cloud.redact import redact

    if getattr(result, "stdout", ""):
        sys.stdout.write(redact(result.stdout, secret_names, env=env))
    if getattr(result, "stderr", ""):
        sys.stderr.write(redact(result.stderr, secret_names, env=env))


class Provider(abc.ABC):
    supports_session = False

    @abc.abstractmethod
    def build(self, deploy_dir: Path) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int | DeployReport:
        raise NotImplementedError

    @abc.abstractmethod
    def ssh_exec(self, command: str) -> subprocess.CompletedProcess:
        raise NotImplementedError

    @abc.abstractmethod
    def upload_file(self, src: Path, dest: str) -> None:
        raise CliError("not_implemented", "This provider does not support file upload")

    @abc.abstractmethod
    def read_remote_file(self, path: str) -> str:
        raise CliError("not_implemented", "This provider does not support remote file reads")

    @abc.abstractmethod
    def attach(self) -> int:
        """Attach to the remote tmux session.

        Interactive attach is intentionally not redacted line-by-line; unlike
        `logs -f`, the attached PTY is a raw interactive stream.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def logs(self, *, follow: bool = True) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    def down(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def destroy(self, *, volume: str | None = None) -> int:
        raise NotImplementedError


ProviderFactory = Callable[[CloudSpec], Provider]


def _railway_provider(spec: CloudSpec) -> Provider:
    from arnold_pipelines.megaplan.cloud.providers.railway import RailwayProvider

    return RailwayProvider(spec)


def _local_provider(spec: CloudSpec) -> Provider:
    from arnold_pipelines.megaplan.cloud.providers.local import LocalProvider

    return LocalProvider(spec)


def _ssh_provider(spec: CloudSpec) -> Provider:
    from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider

    return SshProvider(spec)


_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "railway": _railway_provider,
    "local": _local_provider,
    "ssh": _ssh_provider,
}


def get_provider(name: str, spec: CloudSpec) -> Provider:
    provider_factory = _PROVIDER_FACTORIES.get(name)
    if provider_factory is None:
        raise CliError("invalid_spec", f"Unknown cloud provider '{name}'")
    return provider_factory(spec)

--- FILE: arnold_pipelines/megaplan/cloud/providers/ssh.py (1,220p) ---
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
            command += f" --plan {shlex.quote(plan)}"
        result = self.ssh_exec(command)
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise CliError("provider_failed", "arnold status did not return a JSON object")
        return payload

    def down(self) -> int:
        self._remote_run(f"docker stop {shlex.quote(self._ssh.container)}")
        return 0

    def destroy(self, *, volume: str | None = None) -> int:
        del volume
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true && rm -rf {shlex.quote(self._ssh.remote_dir)}"
        )
        return 0

--- FILE: arnold_pipelines/megaplan/types.py (1,130p) ---
"""Type definitions, constants, and exceptions for megaplan."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from arnold.runtime.errors import ArnoldError

# Re-export AgentSpec, format_agent_spec, and parse_agent_spec from the SSoT
# so that identity holds across the megaplan/arnold.agent boundary.
from arnold.agent.contracts import AgentMode, AgentSpec, format_agent_spec, parse_agent_spec

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.planning.state import PlanCurrentState

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
DriverOutcomeStatus = Literal[
    "done",
    "finalized",
    "paused",
    "stalled",
    "escalated",
    "failed",
    "aborted",
    "cancelled",
    "cap",
    "blocked",
    "cost_cap_exceeded",
    "context_retry_exhausted",
    "worker_blocked",
    "infrastructure_error",
    "human_required",
    "awaiting_human",
    "tiebreaker_pending",
    "tiebreaker_ready",
]


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class PlanConfig(TypedDict, total=False):
    project_dir: str
    auto_approve: bool
    robustness: str
    mode: str
    output_path: str
    from_doc: str
    agents: dict[str, str]
    workers: NotRequired[dict[str, Any]]
    max_tiebreakers_per_plan: int
    tiebreaker_blocklist: list[str]
    allow_tiebreaker: bool
    tiebreaker_token_budget: int
    tiebreaker_time_budget_minutes: int
    strict_notes: NotRequired[bool]
    prep_clarify: NotRequired[bool]
    # Completion-verification contract mode: off | shadow | warn | enforce.
    # Default "shadow" = compute + persist + log a verdict, never block, never
    # run the suite. warn/enforce are not yet implemented (behave like shadow +
    # a logged WARNING). See megaplan/orchestration/completion_contract.py.
    completion_contract_mode: NotRequired[str]
    # Full-suite backstop mode: off | shadow | enforce.
    # Default "shadow" = run and record one unscoped suite before milestone
    # advance, never block. enforce blocks only on computed suite failures.
    full_suite_backstop_mode: NotRequired[str]
    # Shell command the harness uses to run the test suite (e.g. "pytest").
    test_command: NotRequired[str]
    # Timeout in seconds for the baseline-capture / verification test run.
    test_baseline_timeout: NotRequired[int]


class PlanMeta(TypedDict, total=False):
    significant_counts: list[int]
    weighted_scores: list[float]
    plan_deltas: list[float | None]
    recurring_critiques: list[str]
    total_cost_usd: float
    overrides: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    imported_decisions: list["SettledDecisionFromDoc"]
    user_approved_gate: bool


class SessionInfo(TypedDict, total=False):
    id: str
    mode: str
    created_at: str
    last_used_at: str
    refreshed: bool
    # Fingerprint of the sandbox-affecting config captured when this session
    # was created (see megaplan.workers._sandbox_fingerprint). At resume
    # time we refuse to reuse a session whose fingerprint no longer matches
    # the current invocation — otherwise codex silently keeps the old
    # sandbox when the operator toggles MEGAPLAN_TRUSTED_CONTAINER or
    # changes --work-dir, leading to repeated invisible failures.
    sandbox_hash: str


class ActivePhase(TypedDict, total=False):
    phase: str
    agent: str
    mode: str
    model: str
    run_id: str
    session_id: str
    started_at: str
    attempt: int
    last_activity_at: str
    last_activity_kind: str
    last_activity_detail: str


class PlanVersionRecord(TypedDict, total=False):
    version: int
    file: str
    hash: str
    timestamp: str


class HistoryEntry(TypedDict, total=False):
    step: str
    timestamp: str
    duration_ms: int
    cost_usd: float
    result: str
    session_mode: str
