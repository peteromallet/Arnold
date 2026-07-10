#!/usr/bin/env python3
"""Generate object_info stubs for node classes found in Hotshot workflows.

The headless test environment does not have ComfyUI-AnimateDiff-Evolved,
ComfyUI-IPAdapter-Plus, etc. installed. This script derives minimal
object_info signatures from the saved Hotshot workflow JSONs so the agentic
harness can instantiate those nodes during agent edits.
"""
from __future__ import annotations

import json
from pathlib import Path


def _widget_type(value: object) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    return "STRING"


def _build_stubs() -> dict[str, dict[str, object]]:
    repo_root = Path(__file__).resolve().parents[1]
    stub_dir = repo_root / "vibecomfy" / "porting" / "cache" / "object_info"
    index = json.loads((stub_dir / "index.json").read_text(encoding="utf-8"))

    schemas: dict[str, dict[str, object]] = {}

    for path in sorted((repo_root / "external_workflows" / ".shadow" / "source").glob("*hotshot*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("nodes")
        if isinstance(nodes, dict):
            node_iter = nodes.values()
        elif isinstance(nodes, list):
            node_iter = nodes
        else:
            continue
        for node in node_iter:
            if not isinstance(node, dict):
                continue
            class_type = node.get("type")
            if not isinstance(class_type, str) or not class_type.strip():
                continue
            if class_type in index:
                continue
            if class_type in schemas:
                continue

            inputs = node.get("inputs")
            if not isinstance(inputs, list):
                inputs = []
            widgets = list(node.get("widgets_values") or [])

            required: dict[str, list[object]] = {}
            optional: dict[str, list[object]] = {}
            widget_index = 0
            for inp in inputs:
                if not isinstance(inp, dict):
                    continue
                name = inp.get("name")
                if not isinstance(name, str) or not name:
                    continue
                socket_type = inp.get("type") or "*"
                link = inp.get("link")
                if link is not None and link != "":
                    required[name] = [socket_type, {}]
                else:
                    if widget_index < len(widgets):
                        wtype = _widget_type(widgets[widget_index])
                        widget_index += 1
                    else:
                        wtype = socket_type
                    optional[name] = [wtype, {}]

            outputs_raw = node.get("outputs")
            outputs: list[dict[str, object]] = []
            if isinstance(outputs_raw, list):
                for out in outputs_raw:
                    if isinstance(out, dict):
                        outputs.append({"name": out.get("name") or out.get("type"), "type": out.get("type")})

            info: dict[str, object] = {
                "category": "hotshot/stub",
                "description": f"Stub schema for {class_type} derived from Hotshot workflow JSON.",
                "display_name": class_type,
                "evidence_identity": "hotshot-workflow-stub",
                "function": class_type,
                "input_order": {"required": list(required.keys()), "optional": list(optional.keys())},
                "input_order_all": list(required.keys()) + list(optional.keys()),
                "inputs": {"required": required, "optional": optional},
                "name": class_type,
                "object_info_widget_order": list(required.keys()) + list(optional.keys()),
                "outputs": outputs,
                "pack": "ComfyUI-Hotshot",
                "pack_slug": "ComfyUI-Hotshot",
                "pack_version": "stub",
                "python_module": "custom_nodes.hotshot_stub",
                "source_kind": "workflow_json_stub",
            }
            schemas[class_type] = info

    return schemas


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    stub_dir = repo_root / "vibecomfy" / "porting" / "cache" / "object_info"
    index_path = stub_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    stubs = _build_stubs()
    if not stubs:
        print("No new stub classes to add.")
        return 0

    stub_file = stub_dir / "ComfyUI-Hotshot@stub.json"
    existing = {}
    if stub_file.exists():
        existing = json.loads(stub_file.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}

    # Merge, preferring freshly inferred signatures.
    merged = {**existing, **stubs}
    stub_file.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")

    for class_type in merged:
        index[class_type] = "ComfyUI-Hotshot@stub.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {len(merged)} stub class(es) to {stub_file}")
    print(f"Updated {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
