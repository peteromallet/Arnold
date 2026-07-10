from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tools import backfill_custom_node_refs as backfill


def test_backfill_selects_generated_and_strict_ready_protected(monkeypatch):
    entries = [
        SimpleNamespace(ready_id="image/generated", path="ready_templates/image/generated.py", marker="generated"),
        SimpleNamespace(ready_id="image/app", path="ready_templates/image/app.py", marker="manual"),
        SimpleNamespace(ready_id="image/required", path="ready_templates/image/required.py", marker="unknown"),
        SimpleNamespace(ready_id="image/supplemental", path="ready_templates/image/supplemental.py", marker="manual"),
    ]
    monkeypatch.setattr(backfill, "build_readability_inventory", lambda: SimpleNamespace(entries=entries))
    monkeypatch.setattr(
        backfill,
        "_load_template_index",
        lambda: {
            "image/generated": {"coverage_tier": "supplemental", "app_active": False},
            "image/app": {"coverage_tier": "supplemental", "app_active": True},
            "image/required": {"coverage_tier": "required", "app_active": False},
            "image/supplemental": {"coverage_tier": "supplemental", "app_active": False},
        },
    )

    targets = backfill._select_targets()

    assert [target.ready_id for target in targets] == ["image/app", "image/generated", "image/required"]
    assert {target.ready_id for target in targets if target.strict_ready_protected} == {"image/app", "image/required"}


def test_backfill_maps_node_classes_and_existing_pack_names_to_refs():
    ref = {"slug": "ComfyUI-Example", "source": "git", "url": "https://example.test/pack.git"}
    lookup = backfill.PackLookup(
        refs_by_name={"ComfyUI-Example": ref},
        refs_by_class={"ExampleNode": ref},
        pack_name_by_class={"ExampleNode": "ComfyUI-Example"},
    )
    source = """
def build():
    wf.node("ExampleNode")
    _node(wf, "ExampleNode", "1")
"""

    refs, unresolved = backfill._refs_for_template(
        source,
        {"models": [], "custom_nodes": ["ComfyUI-Example"]},
        lookup,
    )

    assert refs == [ref]
    assert unresolved == []


def test_backfill_uses_static_pack_ref_when_lock_entry_missing():
    lookup = backfill._pack_lookup([])

    refs, unresolved = backfill._refs_for_template(
        "",
        {"models": [], "custom_nodes": ["ComfyUI-GGUF"]},
        lookup,
    )

    assert refs == [
        {
            "slug": "ComfyUI-GGUF",
            "source": "git",
            "url": "https://github.com/city96/ComfyUI-GGUF.git",
        }
    ]
    assert unresolved == []


def test_backfill_replaces_ready_requirements_only():
    source = 'READY_METADATA = {"ready_template": "x"}\n\nREADY_REQUIREMENTS = {"models": [], "custom_nodes": []}\n\n\ndef build():\n    return None\n'
    updated = backfill._replace_ready_requirements(
        source,
        {
            "models": [],
            "custom_nodes": ["ComfyUI-Example"],
            "custom_node_refs": [{"slug": "ComfyUI-Example", "source": "git"}],
        },
    )

    assert 'READY_METADATA = {"ready_template": "x"}' in updated
    assert "'custom_nodes': ['ComfyUI-Example']" in updated
    assert "'custom_node_refs': [{'slug': 'ComfyUI-Example', 'source': 'git'}]" in updated
    assert "def build()" in updated


def test_backfill_report_buckets_unknown_and_manual(monkeypatch, tmp_path: Path):
    unknown = tmp_path / "unknown.py"
    manual = tmp_path / "manual.py"
    unknown.write_text('READY_REQUIREMENTS = {"models": [], "custom_nodes": []}\n', encoding="utf-8")
    manual.write_text(
        'READY_REQUIREMENTS = {"models": [], "custom_nodes": ["ComfyUI-Example"]}\n'
        'def build():\n    _node(None, "ExampleNode", "1")\n',
        encoding="utf-8",
    )
    ref = {"slug": "ComfyUI-Example", "source": "git"}
    monkeypatch.setattr(
        backfill,
        "_select_targets",
        lambda: [
            backfill.BackfillTarget("image/unknown", unknown, "unknown", True),
            backfill.BackfillTarget("image/manual", manual, "manual", True),
        ],
    )
    monkeypatch.setattr(
        backfill,
        "_pack_lookup",
        lambda entries: backfill.PackLookup({"ComfyUI-Example": ref}, {"ExampleNode": ref}, {"ExampleNode": "ComfyUI-Example"}),
    )
    monkeypatch.setattr(backfill, "read_lockfile", lambda: [])

    report = backfill.backfill_custom_node_refs(write=False, template_index=tmp_path / "template_index.json")

    assert report["buckets"]["unknown_marker_strict_ready_protected"] == ["image/unknown"]
    assert report["buckets"]["manual_or_authored"] == ["image/manual"]
    assert report["summary"]["target_count"] == 2
