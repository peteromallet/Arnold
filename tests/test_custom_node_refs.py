from __future__ import annotations

from vibecomfy.custom_node_refs import check_pack_pin_compatibility, normalize_custom_node_requirements
from vibecomfy.node_packs import LockEntry
from vibecomfy.workflow import VibeWorkflow, WorkflowRequirements, WorkflowSource


def test_structured_custom_nodes_normalize_to_string_nodes_and_refs() -> None:
    requirements, warnings = normalize_custom_node_requirements(
        {
            "custom_nodes": [
                {"slug": "comfyui-kjnodes", "source": "git", "url": "https://example.test/kj.git", "commit": "abc"},
                "ComfyUI-VideoHelperSuite",
            ],
            "custom_node_refs": [
                {"slug": "comfyui-controlnet-aux", "source": "comfy-registry", "version": "1.0.5"},
            ],
        }
    )

    assert requirements["custom_nodes"] == ["ComfyUI-VideoHelperSuite", "comfyui-kjnodes"]
    assert requirements["custom_node_refs"] == [
        {"slug": "comfyui-controlnet-aux", "source": "comfy-registry", "version": "1.0.5"},
        {"slug": "comfyui-kjnodes", "source": "git", "url": "https://example.test/kj.git", "commit": "abc"},
    ]
    assert warnings


def test_pack_pin_compatibility_reports_commit_conflict() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["comfyui-kjnodes"]),
        metadata={
            "requirements": {
                "custom_nodes": ["comfyui-kjnodes"],
                "custom_node_refs": [
                    {"slug": "comfyui-kjnodes", "source": "git", "commit": "expected"},
                ],
            }
        },
    )

    issues = check_pack_pin_compatibility(
        workflow,
        [
            LockEntry(
                name="ComfyUI-KJNodes",
                slug="comfyui-kjnodes",
                source="git",
                commit="actual",
                url="https://example.test/kj.git",
            )
        ],
    )

    assert [(issue.code, issue.severity) for issue in issues] == [("custom_node_ref_pin_conflict", "error")]
    assert "expected" in issues[0].message
    assert "actual" in issues[0].message


def test_pack_pin_compatibility_warns_for_legacy_unpinned_custom_nodes() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["ComfyUI-KJNodes"]),
        metadata={"requirements": {"custom_nodes": ["ComfyUI-KJNodes"]}},
    )

    issues = check_pack_pin_compatibility(workflow, [])

    assert [(issue.code, issue.severity) for issue in issues] == [("legacy_custom_nodes_unpinned", "warning")]


def test_pack_pin_compatibility_warns_for_unpinned_structured_ref_missing_from_lock() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["ComfyUI-GGUF"]),
        metadata={
            "requirements": {
                "custom_nodes": ["ComfyUI-GGUF"],
                "custom_node_refs": [
                    {"slug": "ComfyUI-GGUF", "source": "git", "url": "https://example.test/gguf.git"},
                ],
            }
        },
    )

    issues = check_pack_pin_compatibility(workflow, [])

    assert [(issue.code, issue.severity) for issue in issues] == [("custom_node_ref_missing_from_lock", "warning")]


def test_pack_pin_compatibility_errors_for_pinned_structured_ref_missing_from_lock() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["ComfyUI-GGUF"]),
        metadata={
            "requirements": {
                "custom_nodes": ["ComfyUI-GGUF"],
                "custom_node_refs": [
                    {"slug": "ComfyUI-GGUF", "source": "git", "commit": "abc123"},
                ],
            }
        },
    )

    issues = check_pack_pin_compatibility(workflow, [])

    assert [(issue.code, issue.severity) for issue in issues] == [("custom_node_ref_missing_from_lock", "error")]
