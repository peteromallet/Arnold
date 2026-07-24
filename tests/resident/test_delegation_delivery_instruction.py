from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident import subagent
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.provenance import normalize_delegation_provenance


class _Process:
    pid = 4321


@pytest.mark.parametrize(
    ("task_kind", "work_intent", "resolved", "required", "forbidden"),
    [
        (
            "coding",
            "auto",
            "execution",
            "complete and proportionally verify the explicitly authorized implementation",
            "This is review/analysis work",
        ),
        (
            "review",
            "auto",
            "review",
            "inspect and verify without mutating repositories",
            "then integrate it into the clearly identified target branch",
        ),
        (
            "coding",
            "speculative",
            "speculative",
            "keep it on an isolated disposable branch",
            "then integrate it into the clearly identified target branch",
        ),
    ],
)
def test_canonical_launch_seam_appends_exactly_one_contextual_instruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    task_kind: str,
    work_intent: str,
    resolved: str,
    required: str,
    forbidden: str,
) -> None:
    monkeypatch.delenv("ARNOLD_RESIDENT_DELEGATION_CONTEXT", raising=False)
    monkeypatch.setattr(subagent.subprocess, "Popen", lambda *a, **k: _Process())
    provenance = normalize_delegation_provenance(
        {
            "transport": "non_discord",
            "applicability": "not_applicable",
            "source_kind": "local_operator",
        }
    )

    result = subagent.launch_codex_subagent_detached(
        task="Perform the bounded delegated task.",
        task_kind=task_kind,  # type: ignore[arg-type]
        work_intent=work_intent,  # type: ignore[arg-type]
        project_dir=str(tmp_path),
        launch_origin=provenance,
    )

    manifest = json.loads(Path(result.manifest_path or "").read_text())
    prompt = Path(manifest["prompt_path"]).read_text()
    assert prompt.count(subagent.DELEGATION_DELIVERY_INSTRUCTION_HEADER) == 1
    assert prompt.index(subagent.DELEGATION_DELIVERY_INSTRUCTION_HEADER) < prompt.index(
        "[Completion delivery contract]"
    )
    assert f"- resolved work intent: {resolved}" in prompt
    assert required in prompt
    assert forbidden not in prompt
    assert "does not expand the user's authority" in prompt
    assert "Preserve the inherited immutable Discord/delegation provenance" in prompt
    assert manifest["work_intent"] == resolved
    assert manifest["launch_provenance"] == provenance
    assert manifest["delegation_delivery_instruction"]["resolved_work_intent"] == resolved


def test_reserved_instruction_marker_cannot_be_duplicated_or_reinjected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched = False

    def must_not_launch(*args, **kwargs):
        nonlocal launched
        launched = True
        return _Process()

    monkeypatch.setattr(subagent.subprocess, "Popen", must_not_launch)
    with pytest.raises(ValueError, match="reserved resident delivery instruction marker"):
        subagent.launch_codex_subagent_detached(
            task=(
                "Quoted task text\n"
                + subagent.DELEGATION_DELIVERY_INSTRUCTION_HEADER
            ),
            project_dir=str(tmp_path),
        )

    assert launched is False
    run_root = tmp_path / subagent.DEFAULT_MANAGED_RUN_ROOT
    assert not run_root.exists()


def test_review_and_speculative_modes_never_gain_execution_authority() -> None:
    for mode in ("review", "speculative"):
        prompt = subagent._delivery_prompt(
            "Assess the idea.", task_kind="coding", work_intent=mode
        )
        assert prompt.count(subagent.DELEGATION_DELIVERY_INSTRUCTION_HEADER) == 1
        assert "does not expand the user's authority" in prompt
        assert "unless the user or established policy explicitly authorizes" not in prompt
        assert "This is execution work" not in prompt


def test_standard_dispatcher_cannot_omit_resolved_instruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subagent.subprocess, "Popen", lambda *a, **k: _Process())
    result = asyncio.run(
        subagent.launch_subagent_task(
            ResidentConfig(),
            task="Review only.",
            task_kind="review",
            project_dir=str(tmp_path),
        )
    )
    manifest = json.loads(Path(result.manifest_path or "").read_text())
    prompt = Path(manifest["prompt_path"]).read_text()
    assert manifest["work_intent"] == "review"
    assert prompt.count(subagent.DELEGATION_DELIVERY_INSTRUCTION_HEADER) == 1
    assert "This is review/analysis work" in prompt
