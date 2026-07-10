from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.commands import nodes as nodes_command
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


def test_nodes_spec_falls_back_to_latest_object_info_cache(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    Path("node_index.json").write_text("[]", encoding="utf-8")
    cache_dir = Path("out/cache")
    cache_dir.mkdir(parents=True)
    older = cache_dir / "object_info.old.json"
    older.write_text(json.dumps({"SomeNode": {"input": {"required": {}}, "output": []}}), encoding="utf-8")
    newer = cache_dir / "object_info.runpod.json"
    newer.write_text(
        json.dumps(
            {
                "LTXVImgToVideoInplaceKJ": {
                    "input": {"required": {"latent": ["LATENT"], "num_images": ["INT"], "vae": ["VAE"]}},
                    "output": ["LATENT"],
                    "output_name": ["latent"],
                }
            }
        ),
        encoding="utf-8",
    )
    older.touch()
    newer.touch()

    class Args:
        class_type = "LTXVImgToVideoInplaceKJ"
        object_info_cache = None

    assert nodes_command._cmd_nodes_spec(Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["class_type"] == "LTXVImgToVideoInplaceKJ"
    assert sorted(payload["inputs"]) == ["latent", "num_images", "vae"]
    assert payload["outputs"] == [{"name": "latent", "type": "LATENT"}]
