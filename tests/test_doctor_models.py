from __future__ import annotations

import argparse
from pathlib import Path

from vibecomfy.commands.doctor import _cmd_doctor


MODEL_ENTRY = {
    "name": "missing.safetensors",
    "url": "https://example.test/models/missing.safetensors",
    "subdir": "checkpoints",
}


def _write_scratchpad(path: Path) -> Path:
    path.write_text(
        f"""
from vibecomfy.registry.ready_template import build_api_ready_workflow

API_WORKFLOW = {{
    "1": {{"class_type": "SaveImage", "inputs": {{}}}},
}}

READY_METADATA = {{"ready_template": "test/model-missing"}}
READY_REQUIREMENTS = {{
    "models": [{MODEL_ENTRY!r}],
    "custom_nodes": [],
}}

def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        READY_METADATA,
        source_path=__file__,
        workflow_id="test/model-missing",
        requirements=READY_REQUIREMENTS,
    )
""",
        encoding="utf-8",
    )
    return path


def test_doctor_reports_missing_model_with_url_and_expected_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    scratchpad = _write_scratchpad(tmp_path / "scratch.py")
    models_root = tmp_path / "models"
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(models_root))

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 1

    captured = capsys.readouterr()
    expected_path = models_root / MODEL_ENTRY["subdir"] / MODEL_ENTRY["name"]
    assert "Missing models:" in captured.out
    assert f"missing model {MODEL_ENTRY['name']}" in captured.out
    assert str(expected_path) in captured.out
    assert MODEL_ENTRY["url"] in captured.out


def test_doctor_passes_when_model_exists(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    scratchpad = _write_scratchpad(tmp_path / "scratch.py")
    models_root = tmp_path / "models"
    model_path = models_root / MODEL_ENTRY["subdir"] / MODEL_ENTRY["name"]
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"model")
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(models_root))

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 0

    captured = capsys.readouterr()
    assert "Missing models:" not in captured.out
    assert "missing model" not in captured.out
