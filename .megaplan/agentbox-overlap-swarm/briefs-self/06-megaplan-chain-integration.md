You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality. The brief embeds local file excerpts because you do not have filesystem tools. Return: existing functionality reusable directly, functionality needing extraction/generalization, missing pieces, risks/gotchas, and a recommended first implementation slice. Keep under 900 words and cite file names/sections.\nFocus only on launching Megaplan plans/chains as AgentBox operations and letting Guardian/Discord Operator inspect/advance them.


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

--- FILE: docs/cloud.md (150,260p) ---
| `ssh.identity_file` | no | unset | Optional identity file passed to `ssh`, `scp`, and `rsync`. |
| `ssh.remote_dir` | no | `/tmp/megaplan-cloud` | Remote directory used for synced Docker build context and `.env`. |
| `ssh.container` | no | `megaplan-cloud-agent` | Remote container name and image tag. |

## Toolchains

Without `toolchains:`, the image is Python/Node only. Add built-in aliases or a custom install snippet:

```yaml
toolchains:
  - rust
  - go
  - name: custom
    install: |
      RUN curl -fsSL https://example.com/tool/install.sh | bash
```

## Wrapper Workflows

### `python -m arnold.pipelines.megaplan cloud bootstrap <idea-file>`

`cloud bootstrap` uploads a local idea file to `<repo.workspace>/idea.txt`, then runs:

```bash
python -m arnold.pipelines.megaplan init --project-dir <workspace> --idea-file <workspace>/idea.txt --auto-start --robustness <level>
```

`--plan-name` is optional. If omitted, cloud does **not** pass `--name`; core megaplan chooses the default slug from the idea text.

### `python -m arnold.pipelines.megaplan cloud chain <spec> [--idea-dir <dir>]`

`cloud chain` is the preferred path for remote chain runs. It:

1. Parses the local chain spec with core `megaplan.chain.load_spec(...)`.
2. Resolves each milestone idea file from `--idea-dir` or, by default, the local spec's parent directory.
3. Uploads each idea file to the remote path named in the chain spec.
4. Uploads the chain spec to `<repo.workspace>/chain.yaml`.
5. Starts remote `python -m arnold.pipelines.megaplan chain start --spec <repo.workspace>/chain.yaml` in tmux session `megaplan-chain`, logging to `<repo.workspace>/.megaplan/cloud-chain.log`.

After upload + dispatch, cloud writes a provider-independent marker:

```text
~/.megaplan/cloud/markers/<sha256(abs_path_of_cloud.yaml)[:16]>/last_chain.json
```

That marker survives Railway's ephemeral deploy dir and is used by `cloud status --chain`.

### `python -m arnold.pipelines.megaplan cloud status --chain`

`cloud status --chain` fetches remote `chain_state.json`, then reuses core chain status formatting. Remote spec resolution precedence is:

1. `--remote-spec <path>`
2. `~/.megaplan/cloud/markers/<sha>/last_chain.json`
3. `spec.chain.spec` from `cloud.yaml` when `mode: chain`
4. Otherwise `missing_remote_spec`

The command prints the structured payload on stdout and the same human-readable chain summary block that local `python -m arnold.pipelines.megaplan chain status --spec ...` prints on stderr.

### `python -m arnold.pipelines.megaplan cloud status`

Without `--chain`, `cloud status` still runs remote `python -m arnold.pipelines.megaplan status` and prints that JSON payload unchanged.

### `python -m arnold.pipelines.megaplan cloud supervise --chain`

`cloud supervise --chain` runs a **one-shot supervisor tick** against the remote chain. It observes the chain, refreshes branch/PR sync state, and makes safe progress decisions. It never invents approvals, bypasses quality gates, or runs destructive git operations.

#### One-shot tick behavior

Each invocation is a single observation + decision cycle:

1. Read remote chain status via the same path as `cloud status --chain`.
2. Refresh branch/PR sync by running `_capture_sync_state` remotely.
3. Re-read chain status after the refresh.
4. Map the refreshed `effective_status` to a safe action.
5. Execute at most one safe mutation (tmux restart, one-shot chain tick).
6. Emit a structured JSON report on **stdout** and a human-readable summary on **stderr**.

#### JSON stdout

The tick report on stdout includes these fields:

| Field | Type | Meaning |
|---|---|---|
| `success` | bool | Whether the tick completed without error. |
| `event` | string | Event label: `supervisor_tick`, `supervisor_blocked`, `supervisor_advanced`, `supervisor_restarted`, or `supervisor_error`. |
| `spec` | string | Resolved remote chain spec path. |
| `effective_status` | string | Classified chain status after sync refresh. |
| `next_action` | string | Decision: `noop`, `done`, `blocked`, `advance`, `restart`, or `none`. |
| `acted` | bool | Whether the supervisor executed a mutation this tick. |
| `refused_reason` | string\|null | Human-readable explanation when the supervisor declined to act. |
| `runner` | object | Runner liveness and session info. |
| `sync` | object | Branch/PR sync state fields. |
| `pr` | object | PR number, state, and head. |
| `logs` | object | Remote log paths and best-effort mtime/size. |

#### Stderr summary

A single line is written to stderr:

```text
supervisor tick: <event> | acted=<bool> | next_action=<action> [| refused_reason=<reason>]
```

#### Remote spec precedence

Same resolution order as `cloud status --chain`:

1. `--remote-spec <path>`
2. `~/.megaplan/cloud/markers/<sha>/last_chain.json`
3. `spec.chain.spec` from `cloud.yaml` when `mode: chain`
4. Otherwise `missing_remote_spec`

--- FILE: arnold_pipelines/megaplan/chain/__init__.py (1590,1660p) ---
        )
    chain_spec.save_chain_state(spec_path, state)
    preexisting_dirty_paths = _dirty_worktree_paths(root)
    push_enabled = not no_push and os.environ.get("MEGAPLAN_CHAIN_NO_PUSH") not in {"1", "true", "TRUE", "yes", "YES"}

    events: list[dict[str, Any]] = []

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[chain] {msg}\n")

    # ---- Seed phase ----
    if spec.seed_plan and state.current_milestone_index < 0:
        seed_state = _plan_state(root, spec.seed_plan, timeout=spec.status_timeout)
        log(f"seed plan {spec.seed_plan} state={seed_state}")
        if seed_state not in TERMINAL_SKIP_STATES:
            state.current_plan_name = spec.seed_plan
            chain_spec.save_chain_state(spec_path, state)
            outcome = _drive_plan_with_blocked_execute_recovery(
                root,
                spec.seed_plan,
                spec,
                writer=writer,
            )
            state.last_state = outcome.status
            chain_spec.save_chain_state(spec_path, state)
            decision = _handle_outcome(outcome, spec=spec, writer=writer, root=root)
            if decision == "authority_blocked":
                state.last_state = "authority_divergence"
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=f"seed plan terminal outcome lacks authority",
                )
            if decision == "stop":
                return _result("stopped", state, events, spec=spec, reason=f"seed plan {outcome.status}")
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan_with_blocked_execute_recovery(
                    root,
                    spec.seed_plan,
                    spec,
                    writer=writer,
                )
                state.last_state = outcome.status
                chain_spec.save_chain_state(spec_path, state)
                if outcome.status != "done":
                    return _result("stopped", state, events, spec=spec, reason="seed retry failed")
                authoritative, reason = _plan_terminal_completion_is_authoritative(
                    root, spec.seed_plan
                )
                if not authoritative:
                    writer(
                        f"[chain] seed retry {spec.seed_plan} outcome=done lacks authority; "
                        f"stopping: {reason}\n"
                    )
                    state.last_state = "authority_divergence"
                    chain_spec.save_chain_state(spec_path, state)
                    return _result(
                        "blocked",
                        state,
                        events,
                        spec=spec,
                        reason=f"seed retry terminal outcome lacks authority: {reason}",
                    )
            # skip / advance both proceed to milestones
        else:
            authoritative, reason = _plan_terminal_completion_is_authoritative(

--- FILE: arnold_pipelines/megaplan/chain/__init__.py (2290,2455p) ---
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
    _add_chain_worktree_args(chain_parser)
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone. Use this on developer checkouts where "
            "you do not want chain to stomp on the currently checked-out "
            "branch. Default: refresh enabled (preserves CI/orchestrator "
            "behavior)."
        ),
    )
    chain_parser.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "Disable milestone branch creation, PR creation, commits, and pushes. "
            "Also enabled by MEGAPLAN_CHAIN_NO_PUSH=1; intended for local/no-network tests."
        ),
    )
    chain_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    start_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    start_parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
    _add_chain_worktree_args(start_parser)
    start_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone."
        ),
    )
    start_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Disable branch/PR/push lifecycle for no-network runs.",
    )
    start_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    status_parser = chain_sub.add_parser(
        "status", help="Show persisted chain progress without driving"
    )
    status_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    status_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read chain state from this project directory instead of discovering from CWD.",
    )

    verify_parser = chain_sub.add_parser(
        "verify", help="Replay landed-diff completion evidence for completed milestones"
    )
    verify_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    verify_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read chain plans from this project directory instead of discovering from CWD.",
    )

    override_parser = chain_sub.add_parser(
        "override", help="Set runtime policy overrides without editing chain.yaml"
    )
    override_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    override_parser.add_argument(
        "--project-dir",
        required=False,
        help="Apply chain overrides against this project directory instead of discovering from CWD.",
    )
    override_parser.add_argument(
        "--set-prerequisite-policy",
        choices=VALID_PREREQUISITE_POLICIES,
        default=None,
        help="Set prerequisite policy at runtime (e.g. none, required)",
    )
    override_parser.add_argument(
        "--set-validation-policy",
        choices=VALID_VALIDATION_POLICIES,
        default=None,
        help="Set validation policy at runtime (e.g. none, required)",
    )
    override_parser.add_argument(
        "--set-review-clean-milestone-pr",
        choices=VALID_CLEAN_MILESTONE_PR_POLICIES,
        default=None,
        help="Set review clean_milestone_pr policy at runtime (e.g. auto, manual)",
    )


def _add_chain_worktree_args(parser: Any) -> None:
    parser.add_argument(
        "--in-worktree",
        default=None,
        metavar="NAME",
        help=(
            "Create a new git worktree at ~/Documents/.megaplan-worktrees/<name>/ "
            "on a new branch and run the whole chain inside it. Name must match "
            "^[a-z0-9][a-z0-9._-]{0,63}$. Substitutes for --project-dir."
        ),
    )
    parser.add_argument(
        "--worktree-from",
        default=None,
        metavar="GITREF",
        help=(
            "Base ref for the new worktree (default: current HEAD of the repo "
            "where `megaplan chain` was invoked). Only valid with --in-worktree."
        ),
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help=(
            "With --in-worktree: remove an existing registered worktree/branch "
            "for this name before creating the new chain worktree."
        ),
    )
    parser.add_argument(
        "--clean-worktree",
        action="store_true",
        default=False,
        help=(
            "With --in-worktree: fork from a clean base ref and leave any "
            "uncommitted state behind in the source repo (no carry)."
        ),
    )
    parser.add_argument(
        "--carry-dirty",
        action="store_true",
        default=False,
        help=(
            "With --in-worktree: explicitly opt into carrying uncommitted state "
            "from the source repo into the new worktree. Mutually exclusive "
            "with --clean-worktree."
        ),
    )


def run_chain_cli(root: Path, args: argparse.Namespace, *, writer=sys.stderr.write) -> int:
    action = getattr(args, "chain_action", None)
    spec_arg = getattr(args, "spec", None)
    if not spec_arg:
        sys.stderr.write("megaplan chain: --spec is required\n")
        return 64
    spec_path = Path(spec_arg).expanduser().resolve()

    if action == "override":
        set_prereq = getattr(args, "set_prerequisite_policy", None)
        set_valid = getattr(args, "set_validation_policy", None)

--- FILE: arnold_pipelines/megaplan/chain/spec.py (500,650p) ---
        )


@dataclass
class ChainState:
    """Persisted progress for a chain run."""

    current_milestone_index: int = -1
    current_plan_name: str | None = None
    current_milestone_base_sha: str | None = None
    last_state: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)
    branch_head: str | None = None
    pr_head: str | None = None
    last_pushed_commit: str | None = None
    dirty_flag: bool = False
    sync_state: str | None = None
    extra_repos: list[str] = field(default_factory=list)
    chain_session: str | None = None
    resolved_workspace: str | None = None
    extra_repo_sync: list[dict[str, Any]] = field(default_factory=list)
    completion_contract_mode: str = "shadow"
    full_suite_backstop_mode: str = "shadow"
    retry_counts: dict[str, int] = field(default_factory=dict)
    ladder_stage: dict[str, str] = field(default_factory=dict)
    profile_bumps: dict[str, str] = field(default_factory=dict)
    robustness_bumps: dict[str, str] = field(default_factory=dict)
    depth_bumps: dict[str, str] = field(default_factory=dict)
    enforce_revise_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_milestone_index": self.current_milestone_index,
            "current_plan_name": self.current_plan_name,
            "current_milestone_base_sha": self.current_milestone_base_sha,
            "last_state": self.last_state,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
            "completed": list(self.completed),
            "branch_head": self.branch_head,
            "pr_head": self.pr_head,
            "last_pushed_commit": self.last_pushed_commit,
            "dirty_flag": self.dirty_flag,
            "sync_state": self.sync_state,
            "extra_repos": list(self.extra_repos),
            "chain_session": self.chain_session,
            "resolved_workspace": self.resolved_workspace,
            "extra_repo_sync": list(self.extra_repo_sync),
            "completion_contract_mode": self.completion_contract_mode,
            "full_suite_backstop_mode": self.full_suite_backstop_mode,
            "retry_counts": dict(self.retry_counts),
            "ladder_stage": dict(self.ladder_stage),
            "profile_bumps": dict(self.profile_bumps),
            "robustness_bumps": dict(self.robustness_bumps),
            "depth_bumps": dict(self.depth_bumps),
            "enforce_revise_counts": dict(self.enforce_revise_counts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainState":
        extra_repos = raw.get("extra_repos")
        if not isinstance(extra_repos, list) or any(
            not isinstance(item, str) or not item for item in extra_repos
        ):
            extra_repos = []

        chain_session = raw.get("chain_session")
        if chain_session is not None and (
            not isinstance(chain_session, str) or not chain_session.strip()
        ):
            chain_session = None

        resolved_workspace = raw.get("resolved_workspace")
        if resolved_workspace is not None and (
            not isinstance(resolved_workspace, str) or not resolved_workspace.strip()
        ):
            resolved_workspace = None

        extra_repo_sync = raw.get("extra_repo_sync")
        if not isinstance(extra_repo_sync, list):
            extra_repo_sync = []

        from arnold_pipelines.megaplan.orchestration.completion_contract import normalize_contract_mode
        from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
            normalize_full_suite_backstop_mode,
        )

        completion_contract_mode = normalize_contract_mode(
            raw.get("completion_contract_mode")
        )
        full_suite_backstop_mode = normalize_full_suite_backstop_mode(
            raw.get("full_suite_backstop_mode")
        )

        def _str_int_map(value: Any) -> dict[str, int]:
            if not isinstance(value, dict):
                return {}
            out: dict[str, int] = {}
            for key, val in value.items():
                if isinstance(key, str):
                    try:
                        out[key] = int(val)
                    except (TypeError, ValueError):
                        continue
            return out

        def _str_str_map(value: Any) -> dict[str, str]:
            if not isinstance(value, dict):
                return {}
            return {
                key: val
                for key, val in value.items()
                if isinstance(key, str) and isinstance(val, str)
            }

        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            current_milestone_index=int(raw.get("current_milestone_index", -1)),
            current_plan_name=raw.get("current_plan_name"),
            current_milestone_base_sha=raw.get("current_milestone_base_sha"),
            last_state=raw.get("last_state"),
            pr_number=int(raw["pr_number"]) if raw.get("pr_number") is not None else None,
            pr_state=raw.get("pr_state"),
            completed=list(raw.get("completed") or []),
            branch_head=raw.get("branch_head"),
            pr_head=raw.get("pr_head"),
            last_pushed_commit=raw.get("last_pushed_commit"),
            dirty_flag=bool(raw.get("dirty_flag", False)),
            sync_state=raw.get("sync_state"),
            extra_repos=extra_repos,
            chain_session=chain_session,
            resolved_workspace=resolved_workspace,
            extra_repo_sync=extra_repo_sync,
            completion_contract_mode=completion_contract_mode,
            full_suite_backstop_mode=full_suite_backstop_mode,
            retry_counts=_str_int_map(raw.get("retry_counts")),
            ladder_stage=_str_str_map(raw.get("ladder_stage")),
            profile_bumps=_str_str_map(raw.get("profile_bumps")),
            robustness_bumps=_str_str_map(raw.get("robustness_bumps")),
            depth_bumps=_str_str_map(raw.get("depth_bumps")),
            enforce_revise_counts=_str_int_map(raw.get("enforce_revise_counts")),
            metadata=dict(metadata),
        )

--- FILE: arnold_pipelines/megaplan/cloud/cli.py (240,520p) ---
                    *report.steps,
                ]
            if report.exit_code == 0:
                seed_messages: list[str] = []
                seed_result = seed_codex_oauth(spec, provider, writer=seed_messages.append)
                report.steps.append(
                    DeployStepReport(
                        name="seed Codex OAuth",
                        status="ok",
                        detail=_oauth_seed_detail(seed_result),
                        stderr="".join(seed_messages),
                        metadata=seed_result,
                    )
                )
            _emit_deploy_report(report, secret_names=spec.secrets, env=os.environ)
            return report.exit_code

        if action == "status":
            if bool(getattr(args, "all", False)):
                return _run_cloud_chains(spec, provider)
            if bool(getattr(args, "chain", False)):
                return _run_chain_status(root, args, spec, provider)
            payload = cloud_status_payload(args, spec, provider)
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
            return 0

        if action == "attach":
            return provider.attach()

        if action == "logs":
            return provider.logs(follow=not bool(getattr(args, "no_follow", False)))

        if action == "chains":
            return _run_cloud_chains(spec, provider)

        if action == "exec":
            result = provider.ssh_exec(args.command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "resume":
            payload = provider.status_payload(
                plan=getattr(args, "plan", None),
                workspace=spec.repo.workspace,
            )
            next_step = payload.get("next_step")
            if not isinstance(next_step, str) or not next_step:
                raise CliError("invalid_status", "Remote status did not include a next_step")
            from arnold_pipelines.megaplan.auto import _phase_command

            argv = list(_phase_command(next_step, substrate=cloud_substrate))
            if getattr(args, "plan", None):
                argv.extend(["--plan", args.plan])
            command = f"cd {shlex.quote(spec.repo.workspace)} && arnold {shlex.join(argv)}"
            result = provider.ssh_exec(command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "down":
            return provider.down()

        if action == "supervise":
            if bool(getattr(args, "chain", False)):
                return _run_supervise_tick(root, args, spec, provider)
            raise CliError(
                "invalid_args",
                "`cloud supervise` requires --chain. Try `arnold cloud supervise --chain`.",
            )

        if action == "destroy":
            if not bool(getattr(args, "yes", False)) and not _confirm_destroy(spec):
                return 1
            result = provider.destroy(volume=spec.resources.volume)
            _clear_persistent_deploy_dir(spec)
            return result

        raise CliError("invalid_args", f"Unknown cloud action: {action}")
    except CliError as exc:
        return _emit_error(exc)


def _cloud_yaml_path(root: Path, args: argparse.Namespace) -> Path:
    raw = getattr(args, "cloud_yaml", None)
    if not raw:
        return root / "cloud.yaml"
    return Path(raw).expanduser().resolve()


def _load_cloud_spec(root: Path, args: argparse.Namespace) -> CloudSpec:
    spec = load_spec(_cloud_yaml_path(root, args))
    return apply_repo_overrides(
        spec,
        repo_url=getattr(args, "repo_url", None),
        repo_branch=getattr(args, "repo_branch", None),
        repo_workspace=getattr(args, "repo_workspace", None),
    )


def _provider_for_action(spec: CloudSpec, args: argparse.Namespace):
    # Gate session overrides on provider capability, not on a provider-name special case.
    base_provider = get_provider(spec.provider, spec)
    session_name = getattr(args, "session", None)
    if not session_name:
        return base_provider
    supports_session = base_provider.supports_session
    if not supports_session:
        raise CliError("invalid_args", "--session is only supported for provider: railway")
    railway = spec.railway or RailwaySpec()
    overridden = replace(spec, railway=replace(railway, session=session_name))
    return get_provider(overridden.provider, overridden)


def _ensure_repo_command(spec: CloudSpec) -> str:
    # Clone the primary repo AND every declared `extra_repos` sibling. The
    # container entrypoint clones the full set at boot, but boot only runs once
    # per `cloud deploy`. A `cloud chain` launched against a container that
    # pre-dates an `extra_repos` edit would otherwise silently leave siblings
    # missing on the persistent volume, blocking any milestone that depends on
    # them.
    return render_ensure_repos_block(spec)


def _ensure_repo_checkout(spec: CloudSpec, provider, *, relay: bool = True) -> None:
    result = provider.ssh_exec(_ensure_repo_command(spec))
    if relay:
        _relay_output(result, secret_names=spec.secrets, env=os.environ)
    if result.returncode != 0:
        repos = [spec.repo, *spec.extra_repos]
        targets = ", ".join(f"{r.url}@{r.branch} into {r.workspace}" for r in repos)
        raise CliError(
            "provider_failed",
            f"ensure repo checkout failed for {targets} (exit {result.returncode})",
        )


def _run_init(root: Path, args: argparse.Namespace) -> int:
    target = _cloud_yaml_path(root, args)
    if target.exists() and not bool(getattr(args, "force", False)):
        raise CliError(
            "invalid_args",
            f"cloud spec already exists: {target}. Use --force to overwrite.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    template = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("cloud.yaml.tmpl")
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    sys.stdout.write(json.dumps({"success": True, "cloud_yaml": str(target)}, indent=2) + "\n")
    return 0


def _relative_remote_path(*, workspace: str, remote_path: str) -> Path:
    remote = PurePosixPath(remote_path)
    workspace_path = PurePosixPath(workspace)
    if remote == workspace_path:
        return Path()
    elif str(remote).startswith(f"{workspace_path}/"):
        return Path(*remote.relative_to(workspace_path).parts)
    elif remote.is_absolute():
        return Path(*remote.parts[1:])
    return Path(*remote.parts)


def _append_unique_path(paths: list[Path], candidate: Path) -> None:
    if candidate not in paths:
        paths.append(candidate)


def _local_idea_source_candidates(*, root: Path, idea_dir: Path, workspace: str, remote_path: str) -> list[Path]:
    relative_remote = _relative_remote_path(workspace=workspace, remote_path=remote_path)
    candidates: list[Path] = []
    _append_unique_path(candidates, idea_dir / relative_remote)
    _append_unique_path(candidates, root / relative_remote)

    try:
        idea_dir_tail = idea_dir.relative_to(root)
    except ValueError:
        idea_dir_tail = None
    if idea_dir_tail is not None:
        try:
            deduped_tail = relative_remote.relative_to(idea_dir_tail)
        except ValueError:
            deduped_tail = None
        if deduped_tail is not None:
            _append_unique_path(candidates, idea_dir / deduped_tail)

    remote = PurePosixPath(remote_path)
    if remote.is_absolute() and not str(remote).startswith(f"{PurePosixPath(workspace)}/"):
        _append_unique_path(candidates, idea_dir / remote.name)
    return candidates


def _resolve_local_idea_source(*, root: Path, idea_dir: Path, workspace: str, remote_path: str) -> tuple[Path | None, list[Path]]:
    candidates = _local_idea_source_candidates(root=root, idea_dir=idea_dir, workspace=workspace, remote_path=remote_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate, candidates
    return None, candidates


def _read_chain_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _chain_spec_has_explicit_base_branch(path: Path) -> bool:
    return "base_branch" in _read_chain_yaml(path)


def _rewrite_remote_workspace_path(remote_path: str, *, source_workspace: str, target_workspace: str) -> str:
    source = PurePosixPath(source_workspace)
    target = PurePosixPath(target_workspace)
    path = PurePosixPath(remote_path)
    if path == source:
        return str(target)
    if path.is_absolute() and str(path).startswith(f"{source}/"):
        return str(target / path.relative_to(source))
    return remote_path


def _normalized_chain_upload_spec(
    local_spec_path: Path,
    *,
    base_branch: str,
    source_workspace: str | None = None,
    target_workspace: str | None = None,
    driver_overrides: dict[str, Any] | None = None,
) -> Path:
    raw = _read_chain_yaml(local_spec_path)
    workspace_changed = (
        bool(source_workspace)
        and bool(target_workspace)
        and source_workspace != target_workspace
    )
    if "base_branch" in raw and not workspace_changed and not driver_overrides:
        return local_spec_path
    normalized = dict(raw)
    if "base_branch" not in normalized:
        normalized["base_branch"] = base_branch
    if driver_overrides:
        driver = normalized.get("driver")
        driver_mapping = dict(driver) if isinstance(driver, dict) else {}
        driver_mapping.update(driver_overrides)
        normalized["driver"] = driver_mapping
    if workspace_changed and isinstance(normalized.get("milestones"), list):
        rewritten: list[Any] = []
        for item in normalized["milestones"]:
            if isinstance(item, dict) and isinstance(item.get("idea"), str):
                copied = dict(item)
                copied["idea"] = _rewrite_remote_workspace_path(
                    copied["idea"],
                    source_workspace=source_workspace or "",
                    target_workspace=target_workspace or "",
                )
                rewritten.append(copied)
            else:
                rewritten.append(item)
        normalized["milestones"] = rewritten
    with NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        yaml.safe_dump(normalized, handle, sort_keys=False)
        return Path(handle.name)


def _missing_configured_secrets(spec: CloudSpec, env: dict[str, str]) -> list[str]:
    return sorted(name for name in spec.secrets if not env.get(name))


def _remote_dependency_check_command(commands: list[str]) -> str:
    quoted_commands = " ".join(shlex.quote(command) for command in commands)
    return (
        "missing=''; "
        f"for cmd in {quoted_commands}; do "
        'if ! command -v "$cmd" >/dev/null 2>&1; then missing="$missing $cmd"; fi; '
        "done; "
        'printf "%s\\n" "$missing"'
    )


def _run_remote_dependency_check(provider, commands: list[str]) -> list[str]:
    if not commands:
        return []
    result = provider.ssh_exec(_remote_dependency_check_command(commands))
    if result.returncode != 0:

--- FILE: arnold_pipelines/megaplan/resident/cloud.py (1,240p) ---
"""Constrained Megaplan cloud operation wrappers for resident tools."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
from typing import Literal, Protocol

from arnold_pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli

CloudClassification = Literal["running", "blocked", "failed", "gate-needed", "completed", "unknown"]
CloudOperation = Literal[
    "cloud_status",
    "cloud_status_chain",
    "cloud_start_chain",
    "cloud_bootstrap",
    "cloud_resume",
    "cloud_logs",
]


@dataclass(frozen=True)
class CloudToolRequest:
    operation: CloudOperation
    target_id: str | None = None
    arguments: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False


@dataclass(frozen=True)
class CloudToolResult:
    classification: CloudClassification
    summary: str
    details: dict[str, object] = field(default_factory=dict)


class CloudToolBackend(Protocol):
    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        """Execute one constrained cloud operation."""


class CloudCliBackend:
    """Default resident backend that dispatches through existing cloud CLI code."""

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        argv = _argv_for_request(request)
        root = Path(request.arguments.get("project_root") or ".").expanduser().resolve()
        parser = argparse.ArgumentParser()
        build_cloud_parser(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["cloud", *argv])
        stdout = StringIO()
        stderr = StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_cloud_cli(root, args)
        output = stdout.getvalue().strip()
        error_output = stderr.getvalue().strip()
        payload = _json_payload(output)
        classification = classify_cloud_payload(payload or {"returncode": code, "stderr": error_output})
        ok = code == 0
        summary = _summary_for_payload(request.operation, classification, payload, ok=ok)
        return CloudToolResult(
            classification=classification if ok else "failed",
            summary=summary,
            details={
                "returncode": code,
                "stdout": output,
                "stderr": error_output,
                "payload": payload,
                "argv": argv,
            },
        )


def classify_cloud_payload(payload: object) -> CloudClassification:
    """Classify status/chain payloads without depending on provider-specific text."""
    flat = " ".join(str(value).lower() for value in _walk_values(payload))
    if not flat.strip():
        return "unknown"
    if any(token in flat for token in ("gate-needed", "gate_needed", "gate pending", "gate_pending", "state_gated")):
        return "gate-needed"
    if any(token in flat for token in ("failed", "failure", "error", "state_failed", "traceback")):
        return "failed"
    if any(token in flat for token in ("blocked", "execution_blocked", "state_blocked")):
        return "blocked"
    if any(token in flat for token in ("completed", "complete", "done", "success", "state_done", "plan_done")):
        return "completed"
    if any(token in flat for token in ("running", "starting", "queued", "in_progress", "state_executing", "state_planning")):
        return "running"
    if isinstance(payload, dict) and payload.get("next_step"):
        return "running"
    return "unknown"


def progress_kind_for_classification(classification: CloudClassification) -> str:
    if classification == "completed":
        return "plan_done"
    if classification == "failed":
        return "plan_failed"
    if classification == "gate-needed":
        return "gate_pending"
    if classification == "blocked":
        return "execution_blocked"
    if classification == "running":
        return "phase_start"
    return "phase_end"


def cloud_run_status_for_classification(classification: CloudClassification) -> str:
    """Map resident cloud classifications onto CloudRun.status values."""
    if classification == "completed":
        return "completed"
    if classification == "failed":
        return "failed"
    if classification == "blocked":
        return "blocked"
    if classification == "gate-needed":
        return "gate-needed"
    if classification == "running":
        return "running"
    return "unknown"


def _argv_for_request(request: CloudToolRequest) -> list[str]:
    args = request.arguments
    cloud_yaml = args.get("cloud_yaml")
    argv: list[str] = []
    if request.operation == "cloud_status":
        argv = ["status"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_status_chain":
        argv = ["status", "--chain"]
        if remote_spec := args.get("remote_spec"):
            argv.extend(["--remote-spec", remote_spec])
    elif request.operation == "cloud_start_chain":
        spec = args.get("spec")
        if not spec:
            raise ValueError("cloud_start_chain requires spec")
        argv = ["chain", spec]
        if idea_dir := args.get("idea_dir"):
            argv.extend(["--idea-dir", idea_dir])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_bootstrap":
        idea_file = args.get("idea_file")
        if not idea_file:
            raise ValueError("cloud_bootstrap requires idea_file")
        argv = ["bootstrap", idea_file]
        if plan_name := args.get("plan_name"):
            argv.extend(["--plan-name", plan_name])
        if robustness := args.get("robustness"):
            argv.extend(["--robustness", robustness])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_resume":
        argv = ["resume"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_logs":
        argv = ["logs"]
        if args.get("no_follow") == "true":
            argv.append("--no-follow")
    else:
        raise ValueError(f"unsupported cloud operation: {request.operation}")
    if cloud_yaml:
        argv.extend(["--cloud-yaml", cloud_yaml])
    return argv


def _append_repo_args(argv: list[str], args: dict[str, str]) -> None:
    if repo_url := args.get("repo_url"):
        argv.extend(["--repo-url", repo_url])
    if repo_branch := args.get("repo_branch"):
        argv.extend(["--repo-branch", repo_branch])
    if repo_workspace := args.get("repo_workspace"):
        argv.extend(["--repo-workspace", repo_workspace])


def _summary_for_payload(
    operation: CloudOperation,
    classification: CloudClassification,
    payload: object,
    *,
    ok: bool,
) -> str:
    if not ok:
        return f"{operation} failed"
    if isinstance(payload, dict):
        next_step = payload.get("next_step")
        if isinstance(next_step, str) and next_step:
            return f"{operation}: next step {next_step}"
        summary = payload.get("summary")
        if isinstance(summary, dict):
            current = summary.get("current")
            if current:
                return f"{operation}: {current}"
    return f"{operation}: {classification}"


def _json_payload(text: str) -> object | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _walk_values(value: object) -> list[object]:
    if isinstance(value, dict):
        values: list[object] = []
        for key, item in value.items():
            values.append(key)
            values.extend(_walk_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_walk_values(item))
        return values
    return [value]
