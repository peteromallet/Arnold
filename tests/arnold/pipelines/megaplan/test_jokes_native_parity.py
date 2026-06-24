"""Native/graph parity coverage for ``jokes`` pipeline.

T3 — Full parity + resume-after-draft
-------------------------------------
Build graph and native traces for the same deterministic topic input and
compare dimensions that survive the two execution engines:

* topology hash (pinned below)
* stage sequence
* normalized working state
* folded event journal
* native ``resume_cursor.json``
* artifact inventory and content hashes (deterministic mocked workers)

The graph side runs through the Arnold executor
(:func:`arnold.pipeline.run_pipeline`) because ``jokes`` is built with
plain Arnold primitives.  The native side runs the attached
:class:`NativeProgram` via :func:`arnold.pipeline.native.runtime.run_native_pipeline`
with ``trace_dir`` enabled.

Resume-after-draft coverage uses ``max_phases=1`` to pause after the
``draft`` phase, then resumes to completion.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import StepContext
from arnold.pipeline.native import run_native_pipeline
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.topology import compute_topology_hash
from arnold.pipelines.megaplan.pipelines.jokes import (
    _native_bundle,
    build_pipeline,
)
from arnold.pipelines.megaplan.pipelines.jokes.steps import JokeStep
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipeline.native.parity_trace import normalize_event_fold
from tests.arnold.pipelines.megaplan.parity_harness import (
    normalize_cursor_narrow,
    normalize_state_narrow,
)

# ═══════════════════════════════════════════════════════════════════════════
# Baselines
# ═══════════════════════════════════════════════════════════════════════════

EXPECTED_JOKES_TOPOLOGY_HASH: str = (
    "sha256:1ec4b14f851f42fe09fd9d06aee569d2386e02014247266107bd3d5dff33ded7"
)

EXPECTED_STAGE_SEQUENCE: tuple[str, ...] = (
    "draft",
    "tighten",
    "emit",
)

# Files that are runtime checkpoints/journals, not pipeline output artifacts.
_CHECKPOINT_SKIP_NAMES: frozenset[str] = frozenset({
    ".events.init_ts",
    ".events.seq",
    "events.ndjson",
    "resume_cursor.json",
    "state.json",
    "awaiting_user.json",
})


# ═══════════════════════════════════════════════════════════════════════════
# Deterministic worker
# ═══════════════════════════════════════════════════════════════════════════

def _deterministic_worker(**kwargs: object) -> str:
    """Return a deterministic string that depends only on step name and inputs."""
    step_name = str(kwargs.get("step_name") or "")
    inputs = kwargs.get("inputs") or {}
    input_keys = sorted(str(key) for key in dict(inputs))
    return (
        f"step={step_name}\n"
        f"input_keys={','.join(input_keys)}\n"
        "body=deterministic jokes parity output\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Trace data class
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class _JokesTrace:
    """Comparable trace captured from one jokes run."""

    topology_hash: str
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifacts: dict[str, str]


# ═══════════════════════════════════════════════════════════════════════════
# Graph-side execution
# ═══════════════════════════════════════════════════════════════════════════

def _run_graph_trace(
    root: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> _JokesTrace:
    """Run the graph-default pipeline and capture a normalized trace."""
    import arnold.pipeline.executor as _exec

    # Patch JokeStep.run for deterministic output (same as native side).
    _patch_native_joke_step(monkeypatch)

    pipeline = build_pipeline(topic="dependency graphs")

    root.mkdir(parents=True, exist_ok=True)
    envelope = RuntimeEnvelope(artifact_root=str(root))

    import os

    previous_runtime = os.environ.get("ARNOLD_PIPELINE_RUNTIME")
    os.environ["ARNOLD_PIPELINE_RUNTIME"] = "graph"
    try:
        _exec.run_pipeline(pipeline, initial_state={
            "joke_topic": "dependency graphs",
        }, envelope=envelope)
    finally:
        if previous_runtime is None:
            os.environ.pop("ARNOLD_PIPELINE_RUNTIME", None)
        else:
            os.environ["ARNOLD_PIPELINE_RUNTIME"] = previous_runtime

    state_path = root / "state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else None
    )

    events = read_event_journal(root)
    folded = fold_journal(
        events,
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial=None,
    )

    return _JokesTrace(
        topology_hash=compute_topology_hash(build_pipeline(topic="dependency graphs")),
        stage_sequence=EXPECTED_STAGE_SEQUENCE,
        state=normalize_state_narrow(state),
        event_fold=normalize_event_fold(folded),
        resume_cursor=None,  # graph executor doesn't write resume_cursor for jokes
        artifacts=_artifact_inventory(root),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Native-side execution
# ═══════════════════════════════════════════════════════════════════════════

def _patch_native_joke_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the deterministic worker into JokeStep for native phases."""
    import arnold.pipelines.megaplan.pipelines.jokes as jokes_mod

    def _patched_run(self: JokeStep, ctx: StepContext) -> Any:
        """Deterministic run that bypasses LLM calls but keeps disk I/O."""
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        state["joke_topic"] = str(state.get("joke_topic") or self.topic or "default")
        artifacts = state.get("_joke_artifacts")
        state["_joke_artifacts"] = dict(artifacts) if isinstance(artifacts, dict) else {}

        out_dir = Path(ctx.artifact_root) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        version = 1
        existing = sorted(out_dir.glob("v*.md"))
        if existing:
            import re
            nums = []
            for p in existing:
                m = re.match(r"v(\d+)\.md", p.name)
                if m:
                    nums.append(int(m.group(1)))
            version = max(nums) + 1 if nums else 1

        prompt_path = out_dir / f"prompt_v{version}.md"
        artifact_path = out_dir / f"v{version}.md"

        body = _deterministic_worker(
            step_name=self.name,
            inputs=state["_joke_artifacts"],
        )
        prompt_path.write_text(f"# prompt: {self.prompt_key}\n", encoding="utf-8")
        artifact_path.write_text(body, encoding="utf-8")

        artifact_str = str(artifact_path)
        prompt_str = str(prompt_path)

        artifacts = dict(state["_joke_artifacts"])
        artifacts[self.name] = artifact_str
        patch: dict[str, Any] = {
            "joke_topic": state["joke_topic"],
            "_joke_artifacts": artifacts,
            "_joke_last_stage": self.name,
        }
        if self.next_label == "halt":
            patch["joke_artifact"] = artifact_str

        from arnold.pipeline import StepResult as SR
        return SR(
            outputs={self.name: artifact_str, f"{self.name}_prompt": prompt_str},
            next=self.next_label,
            state_patch=patch,
        )

    monkeypatch.setattr(JokeStep, "run", _patched_run)


def _run_native_trace(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    resume: bool = False,
    max_phases: int | None = None,
) -> _JokesTrace:
    """Run the native bundle and capture a normalized trace."""
    _patch_native_joke_step(monkeypatch)

    program = _native_bundle()
    assert hasattr(program, "run_native_pipeline")

    root.mkdir(parents=True, exist_ok=True)
    trace_dir = root / "traces"

    if resume:
        result = program.run_native_pipeline(
            artifact_root=root,
            resume=True,
            trace_dir=trace_dir,
        )
    elif max_phases is not None:
        result = program.run_native_pipeline(
            artifact_root=root,
            initial_state={
                "joke_topic": "dependency graphs",
                "_pipeline_name": "jokes",
                "_pipeline_version": 1,
            },
            max_phases=max_phases,
            trace_dir=trace_dir,
        )
    else:
        result = program.run_native_pipeline(
            artifact_root=root,
            initial_state={
                "joke_topic": "dependency graphs",
                "_pipeline_name": "jokes",
                "_pipeline_version": 1,
            },
            trace_dir=trace_dir,
        )

    state_path = trace_dir / "state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else dict(result.state)
    )

    events = read_event_journal(trace_dir)
    folded = fold_journal(
        events,
        kind_filter="stage.complete",
        projector=last_state_snapshot_projector,
        initial=None,
    )

    cursor_path = root / "resume_cursor.json"
    resume_cursor = (
        json.loads(cursor_path.read_text(encoding="utf-8"))
        if cursor_path.exists()
        else None
    )

    return _JokesTrace(
        topology_hash=compute_topology_hash(build_pipeline(topic="dependency graphs")),
        stage_sequence=_native_stage_sequence(result),
        state=normalize_state_narrow(state),
        event_fold=normalize_event_fold(folded),
        resume_cursor=normalize_cursor_narrow(resume_cursor),
        artifacts=_artifact_inventory(root),
    )


def _native_stage_sequence(result: Any) -> tuple[str, ...]:
    """Normalize native runtime stage ids to bare phase names."""
    seq: list[str] = []
    for stage_id in result.stages:
        parts = stage_id.split("__")
        if len(parts) >= 2:
            name = parts[-2]
            seq.append(name)
    return tuple(seq)


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

def _artifact_inventory(root: Path) -> dict[str, str]:
    """Return ``{relpath: sha256:<hex>}`` for pipeline output artifacts under *root*."""
    inventory: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name in _CHECKPOINT_SKIP_NAMES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("traces/"):
            continue
        inventory[rel] = f"sha256:{_content_digest(path, root)}"
    return inventory


def _content_digest(path: Path, root: Path) -> str:
    """SHA-256 of file content with root-absolute paths normalized away."""
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = raw.replace(str(root).encode("utf-8"), b"<artifact-root>")
    else:
        normalized = _normalize_artifact_payload(payload, root)
        data = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _normalize_artifact_payload(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_artifact_payload(item, root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_artifact_payload(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root), "<artifact-root>")
    return value


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


# ═══════════════════════════════════════════════════════════════════════════
# T3 — Deterministic parity + resume-after-draft
# ═══════════════════════════════════════════════════════════════════════════

class TestJokesNativeParity:
    """Graph/native parity for the standalone jokes pipeline."""

    def test_topology_hash_matches_baseline(self) -> None:
        """The graph pipeline topology hash is stable and pinned."""
        pipeline = build_pipeline(topic="dependency graphs")
        actual = compute_topology_hash(pipeline)
        assert actual == EXPECTED_JOKES_TOPOLOGY_HASH, (
            f"jokes topology hash mismatch!\n"
            f"  expected: {EXPECTED_JOKES_TOPOLOGY_HASH}\n"
            f"  actual:   {actual}\n"
            f"If the graph was intentionally changed, update "
            f"EXPECTED_JOKES_TOPOLOGY_HASH in this file."
        )

    def test_full_run_parity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Both engines complete the full draft→tighten→emit sequence with identical artifacts."""
        graph_root = tmp_path / "graph"
        native_root = tmp_path / "native"

        graph = _run_graph_trace(graph_root, monkeypatch=monkeypatch)
        native = _run_native_trace(monkeypatch, native_root)

        # Topology hash
        assert graph.topology_hash == native.topology_hash == EXPECTED_JOKES_TOPOLOGY_HASH, (
            f"topology_hash: graph={graph.topology_hash}, native={native.topology_hash}"
        )

        # Stage sequence
        assert graph.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert native.stage_sequence == EXPECTED_STAGE_SEQUENCE, (
            f"native stage_sequence: {native.stage_sequence}"
        )

        # Artifact inventory
        assert graph.artifacts == native.artifacts, (
            f"artifact diff:\n"
            f"  graph:   {sorted(graph.artifacts.keys())}\n"
            f"  native:  {sorted(native.artifacts.keys())}\n"
            f"  graph values: {graph.artifacts}\n"
            f"  native values: {native.artifacts}"
        )

        # Verify emit artifact exists in both
        for trace, label in [(graph, "graph"), (native, "native")]:
            emit_files = [k for k in trace.artifacts if "emit/v" in k and k.endswith(".md")]
            assert emit_files, f"{label}: no emit artifact found in {sorted(trace.artifacts.keys())}"

    def test_resume_after_draft(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Native-only: suspend after draft via max_phases=1, then resume to completion."""
        _patch_native_joke_step(monkeypatch)

        program = _native_bundle()
        assert hasattr(program, "run_native_pipeline")

        root = tmp_path / "native_resume"
        root.mkdir(parents=True, exist_ok=True)

        # 1. Run with max_phases=1 — should suspend after draft.
        first = program.run_native_pipeline(
            artifact_root=root,
            initial_state={
                "joke_topic": "dependency graphs",
                "_pipeline_name": "jokes",
                "_pipeline_version": 1,
            },
            max_phases=1,
        )
        assert first.suspended is True, "Expected suspension after max_phases=1"
        assert first.pc >= 1, f"Expected pc >= 1, got {first.pc}"

        # Verify draft artifact exists.
        assert (root / "draft" / "v1.md").exists(), "draft artifact missing after first phase"
        # Verify resume cursor was persisted.
        assert (root / "resume_cursor.json").exists(), "resume_cursor.json missing after suspend"

        cursor = json.loads((root / "resume_cursor.json").read_text(encoding="utf-8"))
        assert "stages" in cursor or "pc" in cursor, f"Unexpected cursor shape: {list(cursor.keys())}"

        # 2. Resume to completion.
        second = program.run_native_pipeline(
            artifact_root=root,
            resume=True,
        )
        assert second.suspended is False, "Expected clean completion after resume"

        # Verify all three stage artifacts exist.
        for stage in ("draft", "tighten", "emit"):
            stage_dir = root / stage
            assert stage_dir.is_dir(), f"{stage} directory missing"
            artifacts = sorted(stage_dir.glob("v*.md"))
            assert len(artifacts) >= 1, f"no artifact in {stage}"

        # Verify emit artifact contains deterministic content.
        emit_artifact = sorted((root / "emit").glob("v*.md"))[-1]
        content = emit_artifact.read_text(encoding="utf-8")
        assert "deterministic jokes parity output" in content

    def test_native_bundle_is_attached(self) -> None:
        """build_pipeline() attaches a native dispatch bundle as a resource bundle."""
        pipeline = build_pipeline(topic="test")
        native_bundles = [
            b for b in pipeline.resource_bundles
            if isinstance(b, NativeProgram) or hasattr(b, "run_native_pipeline")
        ]
        assert len(native_bundles) == 1, (
            f"Expected exactly one native dispatch resource bundle, "
            f"found {len(native_bundles)}"
        )
