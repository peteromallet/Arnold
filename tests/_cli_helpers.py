"""Shared helpers for the split test_cli_*.py files.

Pytest does not collect underscore-prefixed modules, so this lives alongside
the test files and is imported explicitly. Pure helper utilities only — no
fixtures here (the helpers don't need monkeypatching).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _top_level_commands(parser: argparse.ArgumentParser) -> list[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    raise AssertionError("parser has no subparsers")


def _write_fetch_scratchpad(tmp_path: Path) -> Path:
    scratchpad = tmp_path / "fetch_scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow(id="fetch-test", source=WorkflowSource(id="fetch-test"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple")
    workflow.metadata["model_assets"] = [
        {
            "name": "present.safetensors",
            "url": "https://example.test/present.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "missing.safetensors",
            "url": "https://example.test/missing.safetensors",
            "subdir": "checkpoints",
        },
    ]
    return workflow
""",
        encoding="utf-8",
    )
    return scratchpad


def _write_port_node_index(tmp_path: Path) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "LoadImage",
                    "pack": "core",
                    "inputs": {"image": {"type": "STRING", "required": True}},
                    "outputs": [{"type": "IMAGE", "name": "image"}],
                },
                {
                    "class_type": "SaveImage",
                    "pack": "core",
                    "inputs": {
                        "images": {"type": "IMAGE", "required": True},
                        "filename_prefix": {"type": "STRING", "required": True},
                    },
                    "outputs": [],
                },
                {
                    "class_type": "PromptNode",
                    "pack": "core",
                    "inputs": {
                        "clip": {"type": "CLIP", "required": True},
                        "text": {"type": "STRING", "required": True},
                        "mode": {"type": "STRING", "required": False},
                    },
                    "outputs": [],
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_port_workflow(tmp_path: Path) -> Path:
    workflow_path = tmp_path / "port_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
                "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "out/port"}},
            }
        ),
        encoding="utf-8",
    )
    return workflow_path


def _load_emitted_provenance(path: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(f"test_emitted_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build().source.provenance
