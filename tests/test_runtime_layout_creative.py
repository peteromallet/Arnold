from __future__ import annotations

import json

from arnold.pipelines.megaplan._core import ensure_runtime_layout
from arnold.pipelines.megaplan.schemas import get_execution_schema_key


def _schema(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_layout_writes_creative_schemas(tmp_path):
    ensure_runtime_layout(tmp_path)
    schemas_root = tmp_path / ".megaplan" / "schemas"

    execution_doc = _schema(schemas_root / "execution_doc.json")
    task_update_props = execution_doc["properties"]["task_updates"]["items"]["properties"]
    assert "stance" in task_update_props
    assert "stop_signal" in task_update_props

    finalize = _schema(schemas_root / "finalize.json")
    task_props = finalize["properties"]["tasks"]["items"]["properties"]
    assert "stance" in task_props
    assert "stop_signal" in task_props

    assert (schemas_root / "directors_notes.json").exists()
    assert get_execution_schema_key("creative", "poem") == "execution_doc.json"
