from __future__ import annotations

import pytest

from vibecomfy.porting.report import (
    AssetCandidate,
    AssetCheckResult,
    NodePackSuggestion,
    PortArtifact,
    PortIssue,
    PortReport,
)


def test_port_report_serializes_stable_analysis_shape() -> None:
    report = PortReport(
        source="ready_templates/sources/official/image/example.json",
        provenance={"source_type": "raw_json", "original_path": "example.json"},
        source_hash="sha256:abc123",
        workflow_id="image/example",
        workflow_shape={"nodes": 2, "edges": 1, "outputs": 1},
        node_counts={"SaveImage": 1, "KSampler": 1},
        output_mode="scratchpad",
        diagnostics=[
            PortIssue(
                code="missing_required_input",
                message="KSampler is missing seed.",
                severity="error",
                node_id="4",
                class_type="KSampler",
                detail={"input": "seed"},
                recommendation="Set a seed before running validation.",
            ),
            PortIssue(
                code="filename_only_asset",
                message="Model candidate has no source URL.",
                severity="warning",
            ),
            PortIssue(
                code="helper_node_stripped",
                message="MarkdownNote is UI-only.",
                severity="info",
            ),
        ],
        artifacts=[
            PortArtifact(
                kind="scratchpad",
                path="out/scratchpads/example.py",
                description="Converted Python scratchpad.",
            )
        ],
        node_pack_suggestions=[
            NodePackSuggestion(
                pack_name="ComfyUI-Example",
                repo="https://github.com/example/ComfyUI-Example.git",
                matched_classes=["ExampleNode"],
                pip_packages=["example-extra"],
            )
        ],
        asset_candidates=[
            AssetCandidate(
                name="model.safetensors",
                source="api_prompt",
                subdir="checkpoints",
                node_id="1",
                class_type="CheckpointLoaderSimple",
            )
        ],
        asset_checks=[
            AssetCheckResult(
                url="https://example.com/model.safetensors",
                ok=False,
                status_code=404,
                error="not_found",
            )
        ],
        recommendations=["Run `python -m vibecomfy.cli validate out/scratchpads/example.py`."],
    )

    payload = report.to_json()

    assert payload["ok"] is False
    assert payload["source"] == "ready_templates/sources/official/image/example.json"
    assert payload["provenance"]["source_type"] == "raw_json"
    assert payload["source_hash"] == "sha256:abc123"
    assert payload["workflow_shape"] == {"nodes": 2, "edges": 1, "outputs": 1}
    assert payload["node_counts"]["KSampler"] == 1
    assert payload["output_mode"] == "scratchpad"
    assert [issue["severity"] for issue in payload["diagnostics"]] == ["error", "warning", "info"]
    assert payload["artifacts"][0]["kind"] == "scratchpad"
    assert payload["node_pack_suggestions"][0]["matched_classes"] == ["ExampleNode"]
    assert payload["asset_candidates"][0]["source"] == "api_prompt"
    assert payload["asset_checks"][0]["status_code"] == 404
    assert "recommendations" in payload


def test_port_issue_rejects_unknown_severity() -> None:
    with pytest.raises(ValueError, match="severity must be one of"):
        PortIssue(code="bad", message="Bad severity.", severity="fatal")  # type: ignore[arg-type]
