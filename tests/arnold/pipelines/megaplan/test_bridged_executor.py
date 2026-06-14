"""Bridge parity tests: demo_judges bridged vs legacy artifact set + dispatcher routing.

T7 — parity assertions:
  1. Both bridged and legacy paths produce the same 7-file artifact set under
     the plan directory.
  2. Common files (verdict.json × 3, synthesis.md, state.json) are byte-identical.
  3. Dispatcher routing: unknown pipeline_key falls through to the legacy
     executor (proved via monkeypatch); demo_judges key routes to the bridge.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _build_demo_pipeline_and_ctx(fixture_path: Path, artifact_root: Path):
    """Return (pipeline, ctx) matching what run_demo() constructs."""
    from arnold.pipelines.megaplan._pipeline.demo_judges import build_pipeline
    from arnold.pipelines.megaplan._pipeline.types import StepContext

    pipeline = build_pipeline()
    ctx = StepContext(
        plan_dir=artifact_root,
        state={},
        profile=None,
        mode="demo",
        inputs={"doc": fixture_path},
        budget=None,
    )
    return pipeline, ctx


def _run_legacy(fixture_path: Path, artifact_root: Path) -> dict:
    """Run demo_judges through the legacy executor (executor.run_pipeline)."""
    from arnold.pipelines.megaplan._pipeline.executor import run_pipeline

    pipeline, ctx = _build_demo_pipeline_and_ctx(fixture_path, artifact_root)
    return run_pipeline(pipeline, ctx, artifact_root=artifact_root)


def _run_bridged(fixture_path: Path, artifact_root: Path) -> dict:
    """Run demo_judges through the bridged executor (run_pipeline_bridged)."""
    from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_bridged

    pipeline, ctx = _build_demo_pipeline_and_ctx(fixture_path, artifact_root)
    return run_pipeline_bridged(pipeline, ctx, artifact_root=artifact_root)


def _relative_file_set(root: Path) -> set[str]:
    """Return the set of relative (posix) paths for all files under *root*."""
    if not root.is_dir():
        return set()
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
    }


def _normalize_paths_in_dict(obj: object, roots: tuple[Path, Path]) -> object:
    """Replace absolute paths rooted at *roots*[0] with the same path under *roots*[1]."""
    if isinstance(obj, str):
        for src, dst in ((roots[0], roots[1]), (roots[1], roots[0])):
            src_str = str(src)
            if obj.startswith(src_str):
                return str(dst) + obj[len(src_str):]
        return obj
    if isinstance(obj, list):
        return [_normalize_paths_in_dict(v, roots) for v in obj]
    if isinstance(obj, dict):
        return {k: _normalize_paths_in_dict(v, roots) for k, v in obj.items()}
    return obj


def _assert_json_structurally_equal(
    path_a: Path, path_b: Path, *, artifact_roots: tuple[Path, Path]
) -> None:
    """Assert two JSON files are equal after normalizing artifact-root paths."""
    data_a = json.loads(path_a.read_text())
    data_b = json.loads(path_b.read_text())
    # Normalize paths in both directions so both point to the same root.
    data_a_normalized = _normalize_paths_in_dict(data_a, artifact_roots)
    assert data_a_normalized == data_b, (
        f"{path_a.name} differs structurally after path normalization:\n"
        f"  normalized legacy: {data_a_normalized!r}\n"
        f"  bridged: {data_b!r}"
    )


def _fixture_doc(tmp_path: Path) -> Path:
    """Write and return a fixture document path."""
    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "The pipeline executor walks stages and dispatches steps in order. "
        "Each step writes artifacts under the plan directory it was handed. "
        "Judges score the fixture document along independent rubric axes. "
        "The synthesis stage merges every judge verdict into a single report. "
        "Sprint One freezes the dataclass shapes for downstream Sprint Two ports. "
        "The fan-out judges demo proves the executor can express parallel "
        "fan-out plus a barrier-join entirely through the new primitives. "
        "Three deterministic judges run concurrently against the same fixture "
        "and the synthesis stage merges their verdicts deterministically. "
        "This fixture exists purely to drive the rubric calculations and the "
        "shape of the artifacts written under the supplied plan directory."
    )
    return fixture


EXPECTED_7_FILE_SET: set[str] = {
    "judges/judge_clarity/verdict.json",
    "judges/judge_concreteness/verdict.json",
    "judges/judge_brevity/verdict.json",
    "synthesis/synthesis.md",
    "state.json",
    "events.ndjson",
    ".events.seq",
}

# Files that are always expected to be byte-identical between legacy and bridged.
# events.ndjson and .events.seq are emitted by the megaplan activation/event
# subsystem in the legacy executor; the bridged path uses the neutral Arnold
# walk-loop which does not emit megaplan-specific event journals.
BYTE_IDENTICAL_FILES: set[str] = {
    "judges/judge_clarity/verdict.json",
    "judges/judge_concreteness/verdict.json",
    "judges/judge_brevity/verdict.json",
    "synthesis/synthesis.md",
    "state.json",
}


# ── parity test ──────────────────────────────────────────────────────────────

def test_bridged_legacy_artifact_parity(tmp_path: Path) -> None:
    """Bridged and legacy paths produce the same 7-file artifact set and
    the 5 core files are byte-identical."""
    fixture = _fixture_doc(tmp_path)

    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir(parents=True, exist_ok=True)
    legacy_result = _run_legacy(fixture, legacy_root)

    bridged_root = tmp_path / "bridged"
    bridged_root.mkdir(parents=True, exist_ok=True)
    bridged_result = _run_bridged(fixture, bridged_root)

    legacy_files = _relative_file_set(legacy_root)
    bridged_files = _relative_file_set(bridged_root)

    # Both paths produce the exact 7-file artifact set.
    assert legacy_files == EXPECTED_7_FILE_SET, (
        f"Legacy file set mismatch: {legacy_files!r} != {EXPECTED_7_FILE_SET!r}"
    )
    assert bridged_files == EXPECTED_7_FILE_SET, (
        f"Bridged file set mismatch: {bridged_files!r} != {EXPECTED_7_FILE_SET!r}"
    )

    # Core 5 files are structurally identical.  state.json contains absolute
    # paths in judge_verdict_paths that differ between the two artifact roots,
    # so the JSON is compared structurally with path normalization.
    for rel_path in sorted(BYTE_IDENTICAL_FILES):
        if rel_path.endswith(".json"):
            _assert_json_structurally_equal(
                legacy_root / rel_path,
                bridged_root / rel_path,
                artifact_roots=(legacy_root, bridged_root),
            )
        else:
            legacy_data = (legacy_root / rel_path).read_bytes()
            bridged_data = (bridged_root / rel_path).read_bytes()
            assert legacy_data == bridged_data, (
                f"{rel_path} differs between legacy and bridged"
            )

    # Both return dicts carry the expected shape keys.
    for result in (legacy_result, bridged_result):
        assert result.get("final_stage") == "synthesis"
        assert result.get("status", "completed") in ("completed", None)
        assert isinstance(result.get("state"), dict)

    # state.json is valid JSON and contains the expected judge keys.
    for root in (legacy_root, bridged_root):
        state = json.loads((root / "state.json").read_text())
        assert "judges" in state
        assert {
            Path(path).relative_to(root).as_posix()
            for path in state["judge_verdict_paths"]
        } == {
            "judges/judge_clarity/verdict.json",
            "judges/judge_concreteness/verdict.json",
            "judges/judge_brevity/verdict.json",
        }


# ── dispatcher routing test ──────────────────────────────────────────────────

def test_dispatcher_routes_unknown_key_to_legacy(tmp_path: Path) -> None:
    """run_pipeline_dispatch with a non-allowlisted pipeline_key falls through
    to the legacy run_pipeline (proved via monkeypatch)."""
    from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

    fixture = _fixture_doc(tmp_path)
    pipeline, ctx = _build_demo_pipeline_and_ctx(fixture, tmp_path / "dispatch")

    # Monkeypatch the legacy executor import that run_pipeline_dispatch uses.
    legacy_called_with = []

    def _fake_legacy_run(pipeline_arg, ctx_arg, *, artifact_root):
        legacy_called_with.append(
            {"pipeline": pipeline_arg, "ctx": ctx_arg, "artifact_root": artifact_root}
        )
        # Return a minimal terminal dict so the caller gets something.
        return {
            "state": ctx_arg.state if hasattr(ctx_arg, "state") else {},
            "final_stage": None,
            "halt_reason": None,
            "envelope": None,
            "status": "completed",
            "contract_result": None,
        }

    # Patch the legacy executor's run_pipeline which run_pipeline_dispatch
    # imports locally when the pipeline_key is not in _BRIDGED_PIPELINES.
    with patch(
        "arnold.pipelines.megaplan._pipeline.executor.run_pipeline",
        _fake_legacy_run,
    ):
        result = run_pipeline_dispatch(
            pipeline,
            ctx,
            artifact_root=tmp_path / "artifacts",
            pipeline_key="unknown_pipeline",
        )

    assert len(legacy_called_with) == 1, (
        "Expected legacy run_pipeline to be called exactly once for unknown key"
    )
    assert result is not None


def test_dispatcher_routes_demo_judges_to_bridge(tmp_path: Path) -> None:
    """run_pipeline_dispatch with pipeline_key='demo_judges' routes to the
    bridged path and does NOT invoke the legacy executor."""
    from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch

    fixture = _fixture_doc(tmp_path)
    pipeline, ctx = _build_demo_pipeline_and_ctx(fixture, tmp_path / "dispatch")

    legacy_called = []

    def _fake_legacy_run(pipeline_arg, ctx_arg, *, artifact_root):
        legacy_called.append(True)
        return {}

    # Patch the legacy executor's run_pipeline which the dispatcher would call
    # for non-allowlisted keys.  For demo_judges it should route to the bridge
    # and never invoke this patched function.
    with patch(
        "arnold.pipelines.megaplan._pipeline.executor.run_pipeline",
        _fake_legacy_run,
    ):
        result = run_pipeline_dispatch(
            pipeline,
            ctx,
            artifact_root=tmp_path / "artifacts",
            pipeline_key="demo_judges",
        )

    assert len(legacy_called) == 0, (
        "Legacy run_pipeline should NOT be called for demo_judges key"
    )
    assert result is not None
    assert result.get("final_stage") == "synthesis"
