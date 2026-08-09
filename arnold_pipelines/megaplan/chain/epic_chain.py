from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan epic-chain requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from arnold.runtime.durable_ops import OperationState

from arnold_pipelines.megaplan._core import atomic_write_json
from arnold_pipelines.megaplan.chain.spec import AnchorSpec
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    effective_chain_policy,
    load_chain_state,
    load_runtime_policy,
    load_spec,
)
from arnold_pipelines.megaplan.chain.wbc import (
    ChainWbcRule,
    EPIC_PROGRESS_SURFACE,
    EPIC_PROGRESS_WRITER_ID,
    record_chain_wbc_evidence,
    validate_chain_wbc_transition,
)
from arnold_pipelines.megaplan.chain.status import classify_chain_status
from arnold_pipelines.megaplan.planning.state import (
    STATE_ABORTED,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_AWAITING_PR_MERGE,
    STATE_BLOCKED,
    STATE_CANCELLED,
    STATE_DONE,
    STATE_FAILED,
    STATE_FINALIZED,
    STATE_PAUSED,
)
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_env
from arnold_pipelines.megaplan.types import CliError

log = logging.getLogger("megaplan")

VALID_EPIC_FAILURE_ACTIONS = ("stop_epic_chain", "skip_epic", "retry_epic")
WAITING_CHILD_STATUSES = frozenset(
    {
        "running",
        "awaiting_pr_merge",
        "awaiting_human_verify",
        "human_prerequisite",
        "quality_gate",
    }
)
STOPPED_CHILD_STATUSES = frozenset(
    {
        "blocked",
        "failed",
        "cancelled",
        "paused",
        "stale_bookkeeping",
        "validation_failed_before_running",
        "not_started",
    }
)


@dataclass(frozen=True)
class EpicFailurePolicy:
    abort: str = "stop_epic_chain"

    @classmethod
    def from_yaml(cls, value: Any, section: str) -> "EpicFailurePolicy":
        if value is None:
            return cls()
        if isinstance(value, str):
            if value not in VALID_EPIC_FAILURE_ACTIONS:
                raise CliError(
                    "invalid_spec",
                    f"{section} must be one of {VALID_EPIC_FAILURE_ACTIONS}; got {value!r}",
                )
            return cls(abort=value)
        if not isinstance(value, dict):
            raise CliError(
                "invalid_spec",
                f"`{section}` must be a string or a mapping with `abort`",
            )
        abort = value.get("abort", "stop_epic_chain")
        if abort not in VALID_EPIC_FAILURE_ACTIONS:
            raise CliError(
                "invalid_spec",
                f"{section}.abort must be one of {VALID_EPIC_FAILURE_ACTIONS}; got {abort!r}",
            )
        unknown = sorted(set(value) - {"abort"})
        if unknown:
            raise CliError(
                "invalid_spec",
                f"`{section}` only supports `abort`; unknown key `{unknown[0]}`",
            )
        return cls(abort=abort)


@dataclass(frozen=True)
class HandoffArtifactSpec:
    path: str
    check: str | dict[str, Any] = "exists"

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "HandoffArtifactSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", f"artifacts[{index}] must be a mapping")
        path = raw.get("path")
        check = raw.get("check", "exists")
        if not isinstance(path, str) or not path.strip():
            raise CliError("invalid_spec", f"artifacts[{index}].path is required")
        if not isinstance(check, (str, dict)):
            raise CliError(
                "invalid_spec",
                f"artifacts[{index}].check must be a string or mapping",
            )
        return cls(path=path.strip(), check=check)


@dataclass(frozen=True)
class HandoffSpec:
    require_merged_base: bool = False
    artifacts: list[HandoffArtifactSpec] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, value: Any, section: str) -> "HandoffSpec":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise CliError("invalid_spec", f"`{section}` must be a mapping")
        require_merged_base = bool(value.get("require_merged_base", False))
        artifacts_raw = value.get("artifacts") or []
        if not isinstance(artifacts_raw, list):
            raise CliError("invalid_spec", f"`{section}.artifacts` must be a list")
        return cls(
            require_merged_base=require_merged_base,
            artifacts=[
                HandoffArtifactSpec.from_dict(raw, index)
                for index, raw in enumerate(artifacts_raw)
            ],
        )


@dataclass(frozen=True)
class EpicSpec:
    id: str
    spec: str
    observe_spec: str | None = None
    handoff_from_previous: HandoffSpec = field(default_factory=HandoffSpec)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "EpicSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", f"epics[{index}] must be a mapping")
        epic_id = raw.get("id")
        spec = raw.get("spec")
        observe_spec = raw.get("observe_spec")
        if not isinstance(epic_id, str) or not epic_id.strip():
            raise CliError("invalid_spec", f"epics[{index}].id is required")
        if not isinstance(spec, str) or not spec.strip():
            raise CliError("invalid_spec", f"epics[{index}].spec is required")
        if observe_spec is not None and (
            not isinstance(observe_spec, str) or not observe_spec.strip()
        ):
            raise CliError(
                "invalid_spec",
                f"epics[{index}].observe_spec must be a non-empty string",
            )
        unknown = sorted(
            set(raw) - {"id", "spec", "observe_spec", "handoff_from_previous"}
        )
        if unknown:
            raise CliError(
                "invalid_spec",
                f"epics[{index}] has unknown key `{unknown[0]}`",
            )
        return cls(
            id=epic_id.strip(),
            spec=spec.strip(),
            observe_spec=observe_spec.strip() if observe_spec else None,
            handoff_from_previous=HandoffSpec.from_yaml(
                raw.get("handoff_from_previous"),
                f"epics[{index}].handoff_from_previous",
            ),
        )


@dataclass(frozen=True)
class EpicChainSpec:
    epics: list[EpicSpec]
    anchors: AnchorSpec = field(default_factory=AnchorSpec)
    base_branch: str = "main"
    on_failure_policy: EpicFailurePolicy = field(default_factory=EpicFailurePolicy)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EpicChainSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", "epic-chain spec must be a YAML mapping")
        allowed_keys = {"anchors", "base_branch", "epics", "on_failure"}
        unknown = sorted(set(raw) - allowed_keys)
        if unknown:
            raise CliError("invalid_spec", f"Unknown epic-chain spec key `{unknown[0]}`")
        base_branch = raw.get("base_branch", "main")
        if not isinstance(base_branch, str) or not base_branch.strip():
            raise CliError("invalid_spec", "`base_branch` must be a non-empty string")
        anchors = AnchorSpec.from_yaml(raw.get("anchors"), "anchors")
        epics_raw = raw.get("epics") or []
        if not isinstance(epics_raw, list):
            raise CliError("invalid_spec", "`epics` must be a list")
        epics = [EpicSpec.from_dict(raw_epic, idx) for idx, raw_epic in enumerate(epics_raw)]
        if not epics:
            raise CliError("invalid_spec", "`epics` must declare at least one child epic")
        seen_ids: set[str] = set()
        for epic in epics:
            if epic.id in seen_ids:
                raise CliError("invalid_spec", f"duplicate epic id {epic.id!r}")
            seen_ids.add(epic.id)
        return cls(
            epics=epics,
            anchors=anchors,
            base_branch=base_branch.strip(),
            on_failure_policy=EpicFailurePolicy.from_yaml(
                raw.get("on_failure"), "on_failure"
            ),
        )


@dataclass
class EpicChainState:
    current_epic_index: int = -1
    current_epic_id: str | None = None
    current_spec_path: str | None = None
    last_state: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)
    chain_session: str | None = None
    resolved_workspace: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_epic_index": self.current_epic_index,
            "current_epic_id": self.current_epic_id,
            "current_spec_path": self.current_spec_path,
            "last_state": self.last_state,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
            "completed": list(self.completed),
            "chain_session": self.chain_session,
            "resolved_workspace": self.resolved_workspace,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EpicChainState":
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
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
        return cls(
            current_epic_index=int(raw.get("current_epic_index", -1)),
            current_epic_id=raw.get("current_epic_id"),
            current_spec_path=raw.get("current_spec_path"),
            last_state=raw.get("last_state"),
            pr_number=int(raw["pr_number"]) if raw.get("pr_number") is not None else None,
            pr_state=raw.get("pr_state"),
            completed=list(raw.get("completed") or []),
            chain_session=chain_session,
            resolved_workspace=resolved_workspace,
            metadata=dict(metadata),
            schema_version=int(raw.get("schema_version", 1)),
        )


@dataclass(frozen=True)
class ObservedChildEpic:
    effective_status: str
    reason: str
    spec_path: Path
    observed_spec_path: Path
    state_path: Path
    project_root: Path | None
    chain_spec: ChainSpec
    chain_state: ChainState
    plan_status: dict[str, Any]
    classification: dict[str, Any]
    authority_drift: dict[str, Any] | None = None


def _state_path_for(spec_path: Path) -> Path:
    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return (
        spec_resolved.parent
        / ".megaplan"
        / "plans"
        / ".epic_chains"
        / f"{spec_resolved.stem}-{digest}.json"
    )


def load_epic_chain_spec(spec_path: Path) -> EpicChainSpec:
    if not spec_path.exists():
        raise CliError("invalid_spec", f"spec file not found: {spec_path}")
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CliError("invalid_spec", f"YAML parse error: {exc}") from exc
    return EpicChainSpec.from_dict(raw or {})


def load_epic_chain_state(spec_path: Path) -> EpicChainState:
    state_path = _state_path_for(spec_path)
    if not state_path.exists():
        return EpicChainState()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("invalid_chain_state", f"epic-chain state is invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CliError("invalid_chain_state", "epic-chain state must be an object")
    return EpicChainState.from_dict(raw)


def save_epic_chain_state(spec_path: Path, state: EpicChainState) -> None:
    state_path = _state_path_for(spec_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(state_path, state.to_dict())


def _resolve_child_spec_path(spec_path: Path, child_spec: str) -> Path:
    candidate = Path(child_spec).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (spec_path.parent / candidate).resolve()


def _find_project_root_from_spec_path(spec_path: Path) -> Path | None:
    resolved = spec_path.resolve()
    for parent in resolved.parents:
        if parent.name == ".megaplan":
            return parent.parent
    return None


def _child_project_root(observed_spec_path: Path, chain_state: ChainState) -> Path | None:
    execution_environment = chain_state.metadata.get("execution_environment")
    if isinstance(execution_environment, dict):
        project_root = execution_environment.get("project_root")
        if isinstance(project_root, str) and project_root:
            return Path(project_root).expanduser().resolve()
    return _find_project_root_from_spec_path(observed_spec_path)


def _read_child_plan_status(
    project_root: Path | None,
    chain_state: ChainState,
) -> dict[str, Any]:
    plan_name = chain_state.current_plan_name
    if not plan_name:
        return {"status": "missing", "reason": "no current plan"}
    if project_root is None:
        return {"status": "unavailable", "reason": "unknown project root", "plan": plan_name}
    state_path = project_root / ".megaplan" / "plans" / plan_name / "state.json"
    if not state_path.exists():
        return {
            "status": "missing",
            "reason": f"plan state missing: {state_path}",
            "plan": plan_name,
        }
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "unavailable", "reason": "unreadable plan state", "plan": plan_name}
    if not isinstance(raw, dict):
        return {"status": "unavailable", "reason": "invalid plan state", "plan": plan_name}
    status = raw.get("current_state")
    if not isinstance(status, str) or not status:
        status = "unknown"
    return {"status": status, "plan": plan_name, "plan_dir": str(state_path.parent)}


def _completed_prefix_index(spec: ChainSpec, completed_labels: set[str]) -> int:
    idx = 0
    while idx < len(spec.milestones) and spec.milestones[idx].label in completed_labels:
        idx += 1
    return idx


def _observe_child_epic(epic: EpicSpec, *, parent_spec_path: Path) -> ObservedChildEpic:
    spec_path = _resolve_child_spec_path(parent_spec_path, epic.spec)
    observed_spec_path = _resolve_child_spec_path(
        parent_spec_path, epic.observe_spec or epic.spec
    )
    chain_spec = load_spec(spec_path)
    chain_state = load_chain_state(observed_spec_path)
    project_root = _child_project_root(observed_spec_path, chain_state)
    plan_status = _read_child_plan_status(project_root, chain_state)
    policy = effective_chain_policy(chain_spec, load_runtime_policy(observed_spec_path))
    classification = classify_chain_status(
        operation_state=OperationState.RUNNING,
        launch_state=None,
        spec=chain_spec,
        chain_state=chain_state,
        plan_status=plan_status,
        human_verification={"status": "unavailable"},
        runner={"status": "unknown"},
        policy=policy,
        sync={"sync_state": chain_state.sync_state},
    )
    completed_labels = {
        record.get("label")
        for record in chain_state.completed
        if isinstance(record, dict) and isinstance(record.get("label"), str)
    }
    completed_prefix = _completed_prefix_index(chain_spec, completed_labels)
    current_index = chain_state.current_milestone_index
    active_unfinished = 0 <= current_index < len(chain_spec.milestones)
    if completed_prefix >= len(chain_spec.milestones):
        effective_status = "complete"
        reason = "all_child_milestones_completed"
    elif chain_state.pr_number is not None and chain_state.pr_state == "open":
        effective_status = "awaiting_pr_merge"
        reason = "active_child_pr_open"
    elif classification.effective_status in WAITING_CHILD_STATUSES:
        effective_status = classification.effective_status
        reason = classification.reason
    elif plan_status.get("status") in {STATE_FAILED, STATE_BLOCKED}:
        effective_status = "blocked"
        reason = f"child_plan_{plan_status.get('status')}"
    elif plan_status.get("status") in {STATE_ABORTED, STATE_CANCELLED, STATE_PAUSED}:
        effective_status = "stopped"
        reason = f"child_plan_{plan_status.get('status')}"
    elif chain_state.last_state in {
        STATE_BLOCKED,
        STATE_FAILED,
        STATE_ABORTED,
        STATE_CANCELLED,
        STATE_PAUSED,
        "authority_divergence",
        "pr_closed",
    }:
        effective_status = "blocked"
        reason = f"child_chain_{chain_state.last_state}"
    elif active_unfinished and chain_state.current_plan_name:
        # Current chain status classification still reports
        # ``stale_bookkeeping`` for an active child whose PR is open and whose
        # cursor has not advanced yet. The parent must treat that as "still
        # active" rather than complete or failed.
        effective_status = "running"
        reason = "active_child_cursor_unfinished"
    elif current_index < 0 and not chain_state.completed:
        effective_status = "not_started"
        reason = "child_chain_state_missing"
    elif active_unfinished:
        effective_status = "not_started"
        reason = "active_child_has_no_plan"
    else:
        effective_status = classification.effective_status
        reason = classification.reason

    # ── authority-view drift check ──────────────────────────────────────
    # When the legacy classification says "complete" and the child has a
    # project root and a current plan, cross-check against the authority-view
    # backed completion check (_plan_terminal_completion_is_authoritative).
    # If the views disagree, capture the drift as a diagnostic — the legacy
    # effective_status is preserved (fail-safe), but the drift is observable.
    authority_drift: dict[str, Any] | None = None
    if effective_status == "complete" and project_root is not None and chain_state.current_plan_name:
        try:
            from arnold_pipelines.megaplan.chain import (
                _plan_terminal_completion_is_authoritative,
            )

            authoritative, auth_reason = _plan_terminal_completion_is_authoritative(
                project_root, chain_state.current_plan_name
            )
            if not authoritative:
                authority_drift = {
                    "kind": "legacy_complete_authority_disagrees",
                    "legacy_effective_status": effective_status,
                    "legacy_reason": reason,
                    "authority_verdict": authoritative,
                    "authority_reason": auth_reason,
                    "child_plan": chain_state.current_plan_name,
                    "child_project_root": str(project_root),
                }
        except Exception:
            # Authority check is best-effort — never block the parent
            # observation on a cross-check failure.
            pass

    classification_dict = classification.to_dict()
    if authority_drift is not None:
        classification_dict.setdefault("metadata", {})
        if isinstance(classification_dict.get("metadata"), dict):
            classification_dict["metadata"]["epic_chain_authority_drift"] = authority_drift
    return ObservedChildEpic(
        effective_status=effective_status,
        reason=reason,
        spec_path=spec_path,
        observed_spec_path=observed_spec_path,
        state_path=_chain_state_path_for(observed_spec_path),
        project_root=project_root,
        chain_spec=chain_spec,
        chain_state=chain_state,
        plan_status=plan_status,
        classification=classification_dict,
        authority_drift=authority_drift,
    )


def _chain_state_path_for(spec_path: Path) -> Path:
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    return (
        spec_path.resolve().parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{spec_path.resolve().stem}-{digest}.json"
    )


def _resolve_artifact_path(
    artifact_path: str,
    *,
    project_root: Path | None,
    parent_spec_path: Path,
) -> Path:
    candidate = Path(artifact_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if project_root is not None:
        return (project_root / artifact_path).resolve()
    return (parent_spec_path.parent / artifact_path).resolve()


def _verify_handoff(
    spec: EpicChainSpec,
    completed_index: int,
    child: ObservedChildEpic,
    *,
    parent_spec_path: Path,
) -> dict[str, Any]:
    if completed_index + 1 >= len(spec.epics):
        return {"status": "none"}
    handoff = spec.epics[completed_index + 1].handoff_from_previous
    verified: dict[str, Any] = {"status": "verified", "artifacts": []}
    if handoff.require_merged_base and child.chain_state.pr_number is not None:
        if child.chain_state.pr_state != "merged":
            raise CliError(
                "handoff_unverified",
                (
                    f"epic {spec.epics[completed_index].id!r} is not ready to hand off: "
                    f"PR #{child.chain_state.pr_number} state={child.chain_state.pr_state!r}"
                ),
            )
        verified["merged_pr"] = child.chain_state.pr_number
    for artifact in handoff.artifacts:
        target = _resolve_artifact_path(
            artifact.path,
            project_root=child.project_root,
            parent_spec_path=parent_spec_path,
        )
        check = artifact.check
        if isinstance(check, str):
            if check != "exists":
                raise CliError(
                    "invalid_spec",
                    f"unsupported handoff artifact check {check!r}",
                )
            if not target.exists():
                raise CliError(
                    "handoff_unverified",
                    f"required handoff artifact missing: {target}",
                )
            verified["artifacts"].append({"path": str(target), "check": "exists"})
            continue
        kind = check.get("kind")
        if kind == "contains_text":
            text = check.get("text")
            if not isinstance(text, str) or not text:
                raise CliError(
                    "invalid_spec",
                    "contains_text handoff check requires non-empty `text`",
                )
            if not target.exists():
                raise CliError(
                    "handoff_unverified",
                    f"required handoff artifact missing: {target}",
                )
            contents = target.read_text(encoding="utf-8")
            if text not in contents:
                raise CliError(
                    "handoff_unverified",
                    f"handoff artifact {target} does not contain required text",
                )
            verified["artifacts"].append(
                {"path": str(target), "check": {"kind": "contains_text", "text": text}}
            )
            continue
        raise CliError(
            "invalid_spec",
            f"unsupported handoff artifact check kind {kind!r}",
        )
    return verified


def _completed_epic_ids(state: EpicChainState) -> set[str]:
    return {
        record.get("id")
        for record in state.completed
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }


def _completed_prefix_epic_index(spec: EpicChainSpec, state: EpicChainState) -> int:
    completed_ids = _completed_epic_ids(state)
    idx = 0
    while idx < len(spec.epics) and spec.epics[idx].id in completed_ids:
        idx += 1
    return idx


def _display_current_epic_index(spec: EpicChainSpec, state: EpicChainState) -> int:
    prefix = _completed_prefix_epic_index(spec, state)
    if state.current_epic_index >= prefix:
        return state.current_epic_index
    return prefix


def _handle_child_failure(policy: EpicFailurePolicy) -> str:
    if policy.abort == "skip_epic":
        return "skip"
    if policy.abort == "retry_epic":
        return "retry"
    return "stop"


def _default_start_child_chain(
    child: EpicSpec,
    *,
    parent_spec_path: Path,
) -> subprocess.CompletedProcess[str]:
    child_spec_path = _resolve_child_spec_path(parent_spec_path, child.spec)
    child_chain_state = load_chain_state(
        _resolve_child_spec_path(parent_spec_path, child.observe_spec or child.spec)
    )
    child_project_root = _child_project_root(
        _resolve_child_spec_path(parent_spec_path, child.observe_spec or child.spec),
        child_chain_state,
    ) or _find_project_root_from_spec_path(child_spec_path) or Path.cwd()
    cmd = [
        sys.executable,
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
        "--spec",
        str(child_spec_path),
        "--project-dir",
        str(child_project_root),
    ]
    return subprocess.run(
        cmd,
        cwd=str(child_project_root),
        capture_output=True,
        text=True,
        check=False,
        env=megaplan_engine_env(),
    )


def _launch_output_indicates_already_running(proc: subprocess.CompletedProcess[str]) -> bool:
    output = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
    return "already running" in output


def run_epic_chain(
    root: Path,
    spec_path: Path,
    *,
    writer: Callable[[str], None],
    one: bool = False,
    start_child: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    spec = load_epic_chain_spec(spec_path)
    state = load_epic_chain_state(spec_path)
    prefix = _completed_prefix_epic_index(spec, state)
    if state.current_epic_index < prefix:
        state.current_epic_index = prefix
    if state.current_epic_index < 0:
        state.current_epic_index = 0
    if state.current_epic_index >= len(spec.epics):
        state.current_epic_id = None
        state.current_spec_path = None
        state.last_state = "done"
        state.pr_number = None
        state.pr_state = None
        save_epic_chain_state(spec_path, state)
        return _result("done", state, spec=spec, reason="all child epics complete")

    start_child = start_child or _default_start_child_chain
    idx = state.current_epic_index
    while idx < len(spec.epics):
        epic = spec.epics[idx]
        state.current_epic_index = idx
        state.current_epic_id = epic.id
        state.current_spec_path = str(_resolve_child_spec_path(spec_path, epic.spec))
        save_epic_chain_state(spec_path, state)
        child = _observe_child_epic(epic, parent_spec_path=spec_path)
        state.last_state = child.effective_status
        state.pr_number = child.chain_state.pr_number
        state.pr_state = child.chain_state.pr_state
        save_epic_chain_state(spec_path, state)
        if child.effective_status in WAITING_CHILD_STATUSES:
            writer(
                f"[epic-chain] child epic {epic.id} is {child.effective_status}; waiting\n"
            )
            return _result(
                child.effective_status,
                state,
                spec=spec,
                reason=f"child epic {epic.id} is {child.effective_status}",
                active_child=child,
            )
        if child.effective_status == "complete":
            handoff_verified = _verify_handoff(
                spec, idx, child, parent_spec_path=spec_path
            )
            completion_evidence = validate_chain_wbc_transition(
                writer_id=EPIC_PROGRESS_WRITER_ID,
                surface_name=EPIC_PROGRESS_SURFACE,
                transition_name="epic_child_complete",
                subject=epic.id,
                source_path=spec_path,
                project_dir=root,
                rules=(
                    ChainWbcRule(
                        "child_status",
                        "complete",
                        child.effective_status,
                        child.effective_status == "complete",
                    ),
                    ChainWbcRule(
                        "observed_spec_exists",
                        True,
                        child.observed_spec_path.exists(),
                        child.observed_spec_path.exists(),
                    ),
                ),
                extra={
                    "child_spec_path": str(child.spec_path),
                    "observed_spec_path": str(child.observed_spec_path),
                    "child_state_path": str(child.state_path),
                    "handoff_verified": handoff_verified,
                },
            )
            record_chain_wbc_evidence(
                state.metadata,
                entry_key=f"epic_complete:{epic.id}:{idx}",
                evidence=completion_evidence,
            )
            if epic.id not in _completed_epic_ids(state):
                state.completed.append(
                    {
                        "id": epic.id,
                        "spec": str(child.spec_path),
                        "observed_spec": str(child.observed_spec_path),
                        "status": "done",
                        "base_branch": child.chain_spec.base_branch,
                        "pr_number": child.chain_state.pr_number,
                        "pr_state": child.chain_state.pr_state,
                        "child_state_path": str(child.state_path),
                        "handoff_verified": handoff_verified,
                    }
                )
            idx += 1
            state.current_epic_index = idx
            state.current_epic_id = None
            state.current_spec_path = None
            state.last_state = "done"
            state.pr_number = None
            state.pr_state = None
            save_epic_chain_state(spec_path, state)
            if one:
                writer(f"[epic-chain] paused after epic {epic.id}\n")
                return _result(
                    "paused",
                    state,
                    spec=spec,
                    reason=f"completed one child epic: {epic.id}",
                )
            continue
        if child.effective_status == "not_started":
            launch_evidence = validate_chain_wbc_transition(
                writer_id=EPIC_PROGRESS_WRITER_ID,
                surface_name=EPIC_PROGRESS_SURFACE,
                transition_name="epic_child_launch",
                subject=epic.id,
                source_path=spec_path,
                project_dir=root,
                rules=(
                    ChainWbcRule(
                        "child_status",
                        "not_started",
                        child.effective_status,
                        child.effective_status == "not_started",
                    ),
                    ChainWbcRule(
                        "child_spec_exists",
                        True,
                        child.spec_path.exists(),
                        child.spec_path.exists(),
                    ),
                ),
                extra={
                    "child_spec_path": str(child.spec_path),
                    "observed_spec_path": str(child.observed_spec_path),
                },
            )
            record_chain_wbc_evidence(
                state.metadata,
                entry_key=f"epic_launch:{epic.id}:{idx}",
                evidence=launch_evidence,
            )
            writer(f"[epic-chain] launching child epic {epic.id}\n")
            proc = start_child(epic, parent_spec_path=spec_path)
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise CliError(
                    "epic_chain_child_launch_failed",
                    (
                        f"child epic {epic.id!r} failed to launch with rc={proc.returncode}: "
                        f"{detail or 'no output'}"
                    ),
                )
            child = _observe_child_epic(epic, parent_spec_path=spec_path)
            state.last_state = child.effective_status
            state.pr_number = child.chain_state.pr_number
            state.pr_state = child.chain_state.pr_state
            save_epic_chain_state(spec_path, state)
            if child.effective_status in WAITING_CHILD_STATUSES:
                return _result(
                    child.effective_status,
                    state,
                    spec=spec,
                    reason=f"child epic {epic.id} is {child.effective_status}",
                    active_child=child,
                )
            if child.effective_status == "complete":
                continue
            if _launch_output_indicates_already_running(proc):
                writer(
                    f"[epic-chain] child epic {epic.id} reports an existing live session; preserving running state\n"
                )
                state.last_state = "running"
                save_epic_chain_state(spec_path, state)
                return _result(
                    "running",
                    state,
                    spec=spec,
                    reason=f"child epic {epic.id} already running",
                    active_child=child,
                )
        decision = _handle_child_failure(spec.on_failure_policy)
        if decision == "retry":
            writer(f"[epic-chain] retrying child epic {epic.id}\n")
            continue
        if decision == "skip":
            writer(f"[epic-chain] skipping child epic {epic.id}\n")
            state.completed.append(
                {
                    "id": epic.id,
                    "spec": str(child.spec_path),
                    "observed_spec": str(child.observed_spec_path),
                    "status": "skipped",
                    "reason": child.reason,
                    "child_state_path": str(child.state_path),
                }
            )
            idx += 1
            state.current_epic_index = idx
            state.current_epic_id = None
            state.current_spec_path = None
            state.last_state = "skipped"
            state.pr_number = None
            state.pr_state = None
            save_epic_chain_state(spec_path, state)
            if one:
                return _result(
                    "paused",
                    state,
                    spec=spec,
                    reason=f"skipped one child epic: {epic.id}",
                )
            continue
        writer(
            f"[epic-chain] child epic {epic.id} halted in {child.effective_status}: {child.reason}\n"
        )
        return _result(
            "stopped",
            state,
            spec=spec,
            reason=f"child epic {epic.id} halted: {child.effective_status}",
            active_child=child,
        )

    state.current_epic_id = None
    state.current_spec_path = None
    state.last_state = "done"
    state.pr_number = None
    state.pr_state = None
    save_epic_chain_state(spec_path, state)
    return _result("done", state, spec=spec, reason="all child epics complete")


def format_epic_chain_status(spec: EpicChainSpec, state: EpicChainState) -> dict[str, Any]:
    idx = _display_current_epic_index(spec, state)
    current_epic: dict[str, Any] | None = None
    if 0 <= idx < len(spec.epics):
        epic = spec.epics[idx]
        current_epic = {"id": epic.id, "index": idx, "spec": epic.spec}
    completed_ids = _completed_epic_ids(state)
    completed = [
        {"id": epic.id, "index": index}
        for index, epic in enumerate(spec.epics)
        if epic.id in completed_ids
    ]
    remaining = [
        {"id": epic.id, "index": index}
        for index, epic in enumerate(spec.epics)
        if epic.id not in completed_ids and (current_epic is None or index >= idx)
    ]
    return {
        "current_epic": current_epic,
        "completed": completed,
        "remaining": remaining,
        "base_branch": spec.base_branch,
        "last_state": state.last_state,
        "current_spec_path": state.current_spec_path,
        "pr_number": state.pr_number,
        "pr_state": state.pr_state,
    }


def _write_epic_chain_status_pretty(
    summary: dict[str, Any],
    *,
    writer: Callable[[str], None],
) -> None:
    current = summary.get("current_epic")
    if current is None:
        writer("Current epic: none\n")
    else:
        writer(f"Current epic: {current['id']} (index {current['index']})\n")
        writer(f"Current child spec: {current['spec']}\n")
    completed = summary.get("completed") or []
    remaining = summary.get("remaining") or []
    writer(
        "Completed: "
        + (", ".join(item["id"] for item in completed) if completed else "(none)")
        + "\n"
    )
    writer(
        "Remaining: "
        + (", ".join(item["id"] for item in remaining) if remaining else "(none)")
        + "\n"
    )
    writer(f"Base branch: {summary.get('base_branch')}\n")
    writer(f"Last state: {summary.get('last_state')}\n")
    if summary.get("pr_number") is not None:
        writer(f"Current PR: #{summary['pr_number']} ({summary.get('pr_state')})\n")


def _result(
    status: str,
    state: EpicChainState,
    *,
    spec: EpicChainSpec,
    reason: str,
    active_child: ObservedChildEpic | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "epic_chain_state": state.to_dict(),
        "base_branch": spec.base_branch,
        "summary": format_epic_chain_status(spec, state),
    }
    if active_child is not None:
        payload["active_child"] = {
            "effective_status": active_child.effective_status,
            "reason": active_child.reason,
            "spec_path": str(active_child.spec_path),
            "observed_spec_path": str(active_child.observed_spec_path),
            "state_path": str(active_child.state_path),
            "project_root": str(active_child.project_root)
            if active_child.project_root is not None
            else None,
            "plan_status": dict(active_child.plan_status),
            "classification": dict(active_child.classification),
            "chain_state": active_child.chain_state.to_dict(),
        }
    return payload


def build_epic_chain_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "epic-chain",
        help="Drive an ordered chain of child megaplan epics",
    )
    parser.add_argument(
        "--spec",
        required=False,
        help="Path to the epic-chain spec YAML (required at top-level or on subcommands)",
    )
    parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the epic-chain against this project directory instead of discovering from CWD.",
    )
    parser.add_argument(
        "--one",
        action="store_true",
        help="Advance at most one completed child epic, persist progress, then stop cleanly.",
    )
    epic_sub = parser.add_subparsers(dest="epic_chain_action")

    start_parser = epic_sub.add_parser("start", help="Drive an epic-chain spec")
    start_parser.add_argument("--spec", required=True, help="Path to the epic-chain spec YAML")
    start_parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the epic-chain against this project directory instead of discovering from CWD.",
    )
    start_parser.add_argument(
        "--one",
        action="store_true",
        help="Advance at most one completed child epic, persist progress, then stop cleanly.",
    )

    status_parser = epic_sub.add_parser(
        "status", help="Show persisted epic-chain progress without driving"
    )
    status_parser.add_argument("--spec", required=True, help="Path to the epic-chain spec YAML")
    status_parser.add_argument(
        "--project-dir",
        required=False,
        help="Read epic-chain state from this project directory instead of discovering from CWD.",
    )


def run_epic_chain_cli(
    root: Path,
    args: argparse.Namespace,
    *,
    writer: Callable[[str], None] = sys.stderr.write,
) -> int:
    action = getattr(args, "epic_chain_action", None)
    spec_arg = getattr(args, "spec", None)
    if not spec_arg:
        sys.stderr.write("megaplan epic-chain: --spec is required\n")
        return 64
    spec_path = Path(spec_arg).expanduser().resolve()
    if action == "status":
        try:
            spec = load_epic_chain_spec(spec_path)
            state = load_epic_chain_state(spec_path)
            summary = format_epic_chain_status(spec, state)
            if summary.get("current_epic") is not None:
                current = spec.epics[_display_current_epic_index(spec, state)]
                active_child = _observe_child_epic(current, parent_spec_path=spec_path)
            else:
                active_child = None
        except CliError as exc:
            sys.stdout.write(
                json.dumps(
                    {"success": False, "error": exc.code, "message": exc.message},
                    indent=2,
                )
                + "\n"
            )
            return exc.exit_code
        _write_epic_chain_status_pretty(summary, writer=writer)
        payload = {
            "success": True,
            "spec": str(spec_path),
            "epic_count": len(spec.epics),
            "base_branch": spec.base_branch,
            "epic_chain_state": state.to_dict(),
            "summary": summary,
        }
        if active_child is not None:
            payload["active_child"] = _result(
                "status",
                state,
                spec=spec,
                reason="status",
                active_child=active_child,
            )["active_child"]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0
    try:
        payload = run_epic_chain(
            root,
            spec_path,
            writer=writer,
            one=bool(getattr(args, "one", False)),
        )
    except CliError as exc:
        sys.stdout.write(
            json.dumps(
                {"success": False, "error": exc.code, "message": exc.message},
                indent=2,
            )
            + "\n"
        )
        return exc.exit_code
    sys.stdout.write(json.dumps({"success": True, **payload}, indent=2) + "\n")
    return 0
