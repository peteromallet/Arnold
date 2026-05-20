from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibecomfy.porting.parity import _is_schema_default_input, compile_equivalent
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.testing.canonical import canonical_form


BASELINE_DIR = Path("out/v26_baseline")


def _snapshot_to_api(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Adapt stored canonical snapshots to the API shape used by parity checks.

    The v2.6 emitter intentionally elides schema defaults. Those defaults
    participate in the old canonical snapshot labels, so direct JSON equality
    is too strict. Rehydrating the snapshot into a graph-shaped dict lets the
    shared `compile_equivalent()` comparator ignore exactly the same defaults
    for both sides while still checking class types, literals, and topology.
    """

    nodes = list(snapshot.get("nodes") or [])
    label_to_id: dict[str, str] = {}
    for index, node in enumerate(nodes):
        label_to_id.setdefault(str(node.get("label")), str(index))

    api: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        class_type = str(node.get("class_type") or "")
        inputs: dict[str, Any] = {}
        for key, value in dict(node.get("inputs") or {}).items():
            if _is_schema_default_input(class_type, str(key), value):
                continue
            if isinstance(value, list) and len(value) == 2:
                source_label = str(value[0])
                inputs[str(key)] = [label_to_id.get(source_label, source_label), value[1]]
            else:
                inputs[str(key)] = value
        api[str(index)] = {"class_type": class_type, "inputs": inputs}
    return api


def test_v26_templates_are_semantically_equivalent_to_baseline_snapshots() -> None:
    records = json.loads((BASELINE_DIR / "compiled_templates.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    for record in records:
        template_id = str(record["template_id"])
        baseline = json.loads(Path(record["snapshot"]).read_text(encoding="utf-8"))
        current = canonical_form(workflow_from_ready(template_id).compile("api"))

        ok, diffs = compile_equivalent(_snapshot_to_api(baseline), _snapshot_to_api(current))
        if not ok:
            failures.append(f"{template_id}: {'; '.join(diffs[:5])}")

    assert failures == []
