from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.porting.emitter import emit_ready_template_python
from vibecomfy.commands.validate import _subgraph_freshness_diagnostics


def test_materialized_subgraph_contract_includes_call_site_and_source_hash() -> None:
    path = "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json"
    text = _emit_ready_from_ui_json(path, "edit/flux2_klein_9b_image_edit_base")

    assert "def image_edit_flux2_klein_9b(" in text
    assert "edited = image_edit_flux2_klein_9b(" in text
    assert "raw_call('7b34ab90" not in text
    assert "# vibecomfy source hash: sha256:" in text


def test_subgraph_freshness_detects_hash_drift(tmp_path: Path) -> None:
    path = "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json"
    text = _emit_ready_from_ui_json(path, "edit/flux2_klein_9b_image_edit_base")
    template = tmp_path / "template.py"
    template.write_text(text.replace("# vibecomfy source hash: sha256:", "# vibecomfy source hash: sha256:" + "0" * 64 + "X", 1), encoding="utf-8")

    diagnostics = _subgraph_freshness_diagnostics(template)

    assert diagnostics
    assert "source hash changed" in diagnostics[0]


def _emit_ready_from_ui_json(path: str, template_id: str) -> str:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = convert_to_vibe_format(api, source_path=path, workflow_id=Path(path).stem)
    return emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": template_id,
            "capability": "image_edit",
            "provenance": {"source_workflow": path},
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id=template_id,
        raw_workflow=raw,
    )
