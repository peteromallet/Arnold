"""Audit trail helpers for eval runs."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils import atomic_json_write


TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "prompt_tokens",
    "completion_tokens",
)

PHASE_ARTIFACT_NAMES = {
    "plan": "plan.json",
    "finalize": "finalize.json",
    "execute": "execution.json",
    "review": "review.json",
}


@dataclass(slots=True)
class PhaseRecord:
    phase: str
    model: str
    duration_ms: int = 0
    cost_usd: float = 0.0
    session_id: str | None = None
    message_offset: int = 0
    iteration: int = 1
    artifact_name: str | None = None
    artifact_payload: dict[str, Any] | list[Any] | None = None
    raw_output: str | None = None
    trace_messages: list[dict[str, Any]] = field(default_factory=list)
    token_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trace_message_count"] = len(self.trace_messages)
        return payload


@dataclass(slots=True)
class EvalAudit:
    eval_name: str
    run_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    results_root: Path = field(default_factory=lambda: Path("results"))
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    initial_commit_sha: str | None = None
    prompt: str | None = None
    build_result: dict[str, Any] | None = None
    eval_result: dict[str, Any] | None = None
    test_result: dict[str, Any] | None = None
    results_json: dict[str, Any] | None = None
    git_diff: str | None = None
    notes: list[str] = field(default_factory=list)
    phase_records: list[PhaseRecord] = field(default_factory=list)

    def add_phase_result(
        self,
        *,
        phase: str,
        model: str,
        duration_ms: int = 0,
        cost_usd: float = 0.0,
        session_id: str | None = None,
        message_offset: int = 0,
        iteration: int = 1,
        artifact_payload: dict[str, Any] | list[Any] | None = None,
        artifact_name: str | None = None,
        raw_output: str | None = None,
        trace_messages: list[dict[str, Any]] | None = None,
        token_counts: dict[str, Any] | None = None,
    ) -> PhaseRecord:
        normalized_tokens = {
            field_name: int((token_counts or {}).get(field_name, 0) or 0)
            for field_name in TOKEN_FIELDS
        }
        record = PhaseRecord(
            phase=phase,
            model=model,
            duration_ms=int(duration_ms or 0),
            cost_usd=float(cost_usd or 0.0),
            session_id=session_id,
            message_offset=int(message_offset or 0),
            iteration=int(iteration or 1),
            artifact_name=artifact_name or default_artifact_name(phase, int(iteration or 1)),
            artifact_payload=artifact_payload,
            raw_output=raw_output,
            trace_messages=list(trace_messages or []),
            token_counts=normalized_tokens,
        )
        self.phase_records.append(record)
        return record

    @property
    def output_dir(self) -> Path:
        return Path(self.results_root) / self.eval_name / self.run_timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_name": self.eval_name,
            "run_timestamp": self.run_timestamp,
            "results_root": str(self.results_root),
            "initial_commit_sha": self.initial_commit_sha,
            "prompt": self.prompt,
            "config_snapshot": self.config_snapshot,
            "environment": self.environment,
            "build_result": self.build_result,
            "eval_result": self.eval_result,
            "test_result": self.test_result,
            "results_json": self.results_json,
            "git_diff_path": "git/diff.patch" if self.git_diff is not None else None,
            "notes": self.notes,
            "phases": [record.to_dict() for record in self.phase_records],
        }

    def save_audit(self) -> Path:
        out_dir = self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        atomic_json_write(out_dir / "summary.json", self.to_dict(), default=str)
        if self.config_snapshot:
            atomic_json_write(out_dir / "run-config.json", self.config_snapshot, default=str)
        if self.environment:
            atomic_json_write(out_dir / "environment.json", self.environment, default=str)
        if self.results_json is not None:
            atomic_json_write(out_dir / "scoring" / "results.json", self.results_json, default=str)
        if self.build_result is not None:
            atomic_json_write(out_dir / "scoring" / "build.json", self.build_result, default=str)
        if self.eval_result is not None:
            atomic_json_write(out_dir / "scoring" / "eval.json", self.eval_result, default=str)
        if self.test_result is not None:
            atomic_json_write(out_dir / "scoring" / "test.json", self.test_result, default=str)
        if self.git_diff is not None:
            git_dir = out_dir / "git"
            git_dir.mkdir(parents=True, exist_ok=True)
            (git_dir / "diff.patch").write_text(self.git_diff, encoding="utf-8")

        megaplan_dir = out_dir / "megaplan"
        traces_dir = out_dir / "traces"
        phases_dir = out_dir / "phases"
        for record in self.phase_records:
            atomic_json_write(
                phases_dir / f"{record.phase}_v{record.iteration}.json",
                record.to_dict(),
                default=str,
            )
            if record.artifact_payload is not None and record.artifact_name:
                atomic_json_write(
                    megaplan_dir / record.artifact_name,
                    record.artifact_payload,
                    default=str,
                )
            if record.trace_messages:
                atomic_json_write(
                    traces_dir / f"{record.phase}_v{record.iteration}.json",
                    record.trace_messages,
                    default=str,
                )
            if record.raw_output is not None:
                raw_dir = out_dir / "raw"
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / f"{record.phase}_v{record.iteration}.txt").write_text(
                    record.raw_output,
                    encoding="utf-8",
                )

        (out_dir / "README.md").write_text(generate_run_readme(self), encoding="utf-8")
        return out_dir


def default_artifact_name(phase: str, iteration: int = 1) -> str:
    if phase in {"critique", "revise", "gate"}:
        return f"{phase}_v{iteration}.json"
    return PHASE_ARTIFACT_NAMES.get(phase, f"{phase}.json")


def collect_phase_trace(
    session_id: str | None,
    message_offset: int,
    *,
    hermes_home: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not session_id:
        return []
    payload = _read_session_log(session_id, hermes_home=hermes_home)
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return []
    start = max(int(message_offset or 0), 0)
    return messages[start:]


def get_session_message_count(
    session_id: str | None,
    *,
    hermes_home: str | Path | None = None,
) -> int:
    if not session_id:
        return 0
    payload = _read_session_log(session_id, hermes_home=hermes_home)
    messages = payload.get("messages", [])
    if isinstance(messages, list):
        return len(messages)
    message_count = payload.get("message_count", 0)
    try:
        return int(message_count or 0)
    except (TypeError, ValueError):
        return 0


def generate_run_readme(audit: EvalAudit) -> str:
    scoring_artifacts: list[str] = []
    if audit.results_json is not None:
        scoring_artifacts.append("`results.json`")
    if audit.build_result is not None:
        scoring_artifacts.append("`build.json`")
    if audit.eval_result is not None:
        scoring_artifacts.append("`eval.json`")
    if audit.test_result is not None:
        scoring_artifacts.append("`test.json`")

    lines = [
        f"# Eval Audit: {audit.eval_name}",
        "",
        f"- Run timestamp: `{audit.run_timestamp}`",
        f"- Initial commit SHA: `{audit.initial_commit_sha or 'unknown'}`",
        f"- Phase count: `{len(audit.phase_records)}`",
        "",
        "## Reproduction",
        "",
        "Artifacts in this directory were generated by the Hermes eval harness.",
        "Replay the experiment with the recorded `run-config.json` once the orchestrator is wired up:",
        "",
        "```bash",
        "python -m evals.run_evals --config results/<eval>/<timestamp>/run-config.json",
        "```",
        "",
        "## Audit Scope",
        "",
        "- Raw provider HTTP payloads are not captured.",
        "- Traces come from normalized Hermes session logs in `~/.hermes/sessions/`.",
        "- Cost and token counters come from `run_conversation()` aggregate fields.",
        "",
        "## Saved Artifacts",
        "",
        "- `summary.json`: top-level run summary",
        "- `run-config.json`: experiment configuration snapshot",
        "- `environment.json`: git SHAs and runtime versions",
        "- `megaplan/`: copied phase artifacts",
        "- `traces/`: phase-isolated Hermes message slices",
        "- `logs/subprocess.log`: full stderr from all megaplan/Hermes subprocess calls",
        "- `raw/`: raw megaplan JSON output per phase",
    ]
    if scoring_artifacts:
        lines.insert(
            -2,
            f"- `scoring/`: generated {', '.join(scoring_artifacts)}",
        )
    if audit.git_diff is not None:
        lines.append("- `git/diff.patch`: workspace diff captured after execution")
    return "\n".join(lines) + "\n"


def _read_session_log(session_id: str, *, hermes_home: str | Path | None = None) -> dict[str, Any]:
    base = Path(hermes_home or os.getenv("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    path = base / "sessions" / f"session_{session_id}.json"
    if not path.exists():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
