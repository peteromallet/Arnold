from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.nodes import index as node_index


def test_index_runtime_nodes_uses_module_command_when_comfy_script_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(node_index, "has_comfyui_runtime", lambda: True)
    monkeypatch.setattr(node_index, "comfyui_command", lambda: (str(python), "-m", "comfy.cmd.main"))
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs

        class Result:
            returncode = 0
            stdout = json.dumps([{"class_type": "WanVideoSampler"}])

        return Result()

    monkeypatch.setattr(node_index.subprocess, "run", fake_run)

    assert node_index.index_runtime_nodes() == [{"class_type": "WanVideoSampler"}]
    assert seen["argv"] == [str(python), "-m", "comfy.cmd.main", "nodes", "ls", "--format", "json"]
    assert seen["kwargs"]["text"] is True
    assert seen["kwargs"]["capture_output"] is True
