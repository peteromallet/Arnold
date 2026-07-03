from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

from tests.structural_harness.actors import _write_actions
from vibecomfy.porting.reorganise.orchestrate import (
    apply_layout_candidate_patch_to_ui,
    assess_reorganise_workflow,
    preview_reorganise_workflow,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LARGE_LTX_REQUEST = REPO_ROOT / "tests" / "fixtures" / "editor_sessions" / "327b0e1235c353a9" / "request.json"
LARGE_MESSY_UI_REQUESTS = (
    ("ltx-large-a", LARGE_LTX_REQUEST),
    ("ltx-large-b", REPO_ROOT / "tests" / "fixtures" / "editor_sessions" / "e0b4f2df7b4da808" / "request.json"),
    ("ltx-medium-a", REPO_ROOT / "tests" / "fixtures" / "editor_sessions" / "be790a2a958a7975" / "request.json"),
    ("ltx-medium-b", REPO_ROOT / "tests" / "fixtures" / "editor_sessions" / "66e9a889a48d5f60" / "request.json"),
)


def build_reorganise_large_messy_ltx_workflow_evidence(report_dir: Path) -> dict[str, Any]:
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    summary = _build_single_reorganise_case(root, "reorganise-large-messy-ltx-workflow", LARGE_LTX_REQUEST)
    return {
        "scenario": "reorganise-large-messy-ltx-workflow",
        "layout_observation_path": str(root / "layout_observation.json"),
        "before_png_path": str(root / "layout_before.png"),
        "after_png_path": str(root / "layout_after.png"),
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
        "summary": summary,
    }


def build_reorganise_large_messy_batch_evidence(report_dir: Path) -> dict[str, Any]:
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    case_summaries = []
    before_paths = []
    after_paths = []
    for slug, request_path in LARGE_MESSY_UI_REQUESTS:
        case_root = root / slug
        summary = _build_single_reorganise_case(case_root, slug, request_path)
        case_summaries.append(summary)
        before_paths.append(case_root / "layout_before.png")
        after_paths.append(case_root / "layout_after.png")

    batch_summary = {
        "scenario": "reorganise-large-messy-batch",
        "case_count": len(case_summaries),
        "cases": case_summaries,
        "all_structural_noop": all(case["structural_noop"] for case in case_summaries),
        "all_overlap_free": all(case["after_metrics"]["overlap_count"] == 0 for case in case_summaries),
        "all_grouped": all(case["after_metrics"]["group_signal_strength"] >= 1.0 for case in case_summaries),
        "all_wall_aspect": all(case["after_wall_aspect_ratio"] >= 1.6 for case in case_summaries),
    }
    assert batch_summary["case_count"] == 4
    assert batch_summary["all_structural_noop"] is True
    assert batch_summary["all_overlap_free"] is True
    assert batch_summary["all_grouped"] is True
    assert batch_summary["all_wall_aspect"] is True

    _write_json(root / "layout_observation.json", batch_summary)
    _write_contact_sheet(before_paths, root / "layout_before_contact.png")
    _write_contact_sheet(after_paths, root / "layout_after_contact.png")
    (root / "vision_prompt.txt").write_text(
        "Review these four Comfy workflow reorganisations as a batch. The first "
        "contact sheet shows before layouts; the second shows after layouts. "
        "Judge whether each after layout is both beautiful and logical: clear "
        "left-to-right flow, resources/input/settings on the left, prompt and "
        "conditioning together, latent/prep before first sampler, first sampler "
        "left of second/upscale sampler, then decode/output, with helpers visually "
        "subordinate rather than dominant. Identify any remaining visual or logical "
        "quirks by case.\n",
        encoding="utf-8",
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "reorganise.batch_preview",
                "case_count": len(case_summaries),
                "status": "ok",
            },
            {
                "op": "reorganise.batch_observe_layout",
                "visual_artifacts": ["layout_before_contact.png", "layout_after_contact.png"],
                "status": "completed",
            },
        ],
    )
    (root / "report.md").write_text(
        "Reorganised four large messy UI workflow fixtures. All candidates preserved "
        "structural hashes, removed overlaps, and produced contact-sheet visual "
        "evidence for image-understanding review.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "reorganise-large-messy-batch",
        "layout_observation_path": str(root / "layout_observation.json"),
        "before_contact_path": str(root / "layout_before_contact.png"),
        "after_contact_path": str(root / "layout_after_contact.png"),
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def _build_single_reorganise_case(root: Path, scenario: str, request_path: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    before_ui = request["graph"]
    before = assess_reorganise_workflow(before_ui)
    preview = preview_reorganise_workflow(before_ui)
    if not preview.ok or preview.candidate_patch is None:
        raise AssertionError(f"large workflow reorganisation preview failed: {preview.to_json()}")

    applied = apply_layout_candidate_patch_to_ui(before_ui, preview.candidate_patch)
    after = assess_reorganise_workflow(applied.ui_json)

    before_metrics = _metrics(before.assessment)
    after_metrics = _metrics(after.assessment)
    before_bounds = _layout_bounds(before_ui)
    after_bounds = _layout_bounds(applied.ui_json)
    after_group_stats = _group_stats(applied.ui_json)
    summary = {
        "scenario": scenario,
        "source_fixture": str(request_path.relative_to(REPO_ROOT)),
        "node_count": len(before_ui.get("nodes", [])),
        "link_count": len(before_ui.get("links", [])),
        "structural_noop": applied.layout_only_structural_noop,
        "structural_hash_before": applied.structural_hash_before,
        "structural_hash_after": applied.structural_hash_after,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "before_bounds": before_bounds,
        "after_bounds": after_bounds,
        "after_group_stats": after_group_stats,
        "after_wall_aspect_ratio": round(after_bounds["width"] / max(1.0, after_bounds["height"]), 4),
        "compile_warnings": [
            diagnostic.to_json()
            for diagnostic in (preview.compile_result.report.diagnostics if preview.compile_result else ())
            if getattr(diagnostic, "severity", "") == "warning"
        ],
        "visual_verdict": _deterministic_visual_verdict(before_metrics, after_metrics),
    }

    _write_json(root / "before_ui.json", before_ui)
    _write_json(root / "after_ui.json", applied.ui_json)
    _write_json(root / "preview_result.json", preview.to_json())
    _write_json(root / "layout_observation.json", summary)
    _write_layout_png(before_ui, root / "layout_before.png")
    _write_layout_png(applied.ui_json, root / "layout_after.png")
    (root / "vision_prompt.txt").write_text(
        "Use the first abstract workflow image as the reference style: a tidy "
        "high-level Comfy workflow wall with small-to-medium stage groups, close "
        "columns, and left-to-right flow. Judge whether the second image is "
        "acceptably close: sensible stage groups, no oversized top-left slab, "
        "reasonable gaps, and flow from inputs/resources to conditioning, prep, "
        "sampling, decode, and output. Mention remaining visual concerns.\n",
        encoding="utf-8",
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "reorganise.preview",
                "source_fixture": str(request_path.relative_to(REPO_ROOT)),
                "node_count": summary["node_count"],
                "link_count": summary["link_count"],
                "status": "ok",
            },
            {
                "op": "reorganise.apply_layout_candidate",
                "layout_only_structural_noop": applied.layout_only_structural_noop,
                "status": "completed",
            },
            {
                "op": "reorganise.observe_layout",
                "visual_artifacts": ["layout_before.png", "layout_after.png"],
                "verdict": summary["visual_verdict"],
            },
        ],
    )
    (root / "report.md").write_text(
        f"Reorganised {summary['node_count']}-node messy workflow fixture. The candidate preserved "
        "the structural hash, reduced overlap_count from "
        f"{before_metrics['overlap_count']} to {after_metrics['overlap_count']}, "
        "and produced colored group sections for visual review.\n",
        encoding="utf-8",
    )
    _assert_layout_cleanup(summary)
    return summary


def _metrics(report: Any) -> dict[str, int | float | bool]:
    return {metric.name: metric.value for metric in report.metrics}


def _assert_layout_cleanup(summary: Mapping[str, Any]) -> None:
    before = summary["before_metrics"]
    after = summary["after_metrics"]
    assert summary["structural_noop"] is True
    assert before["overlap_count"] > 0
    assert after["overlap_count"] == 0
    assert after["spacing_density"] < before["spacing_density"]
    assert after["group_signal_strength"] >= 1.0
    assert after["group_coherence"] >= 0.65
    assert summary["after_wall_aspect_ratio"] >= 1.6
    assert summary["after_group_stats"]["max_primary_node_count"] <= 12
    assert summary["after_group_stats"]["setget_group_count"] <= 1
    assert summary["after_group_stats"]["standalone_label_group_count"] == 0
    assert summary["after_group_stats"]["max_primary_width_ratio"] <= 0.28
    assert summary["after_group_stats"]["max_primary_area_ratio"] <= 0.15


def _deterministic_visual_verdict(
    before: Mapping[str, int | float | bool],
    after: Mapping[str, int | float | bool],
) -> str:
    if (
        after["overlap_count"] == 0
        and after["spacing_density"] < before["spacing_density"]
        and after["group_signal_strength"] > before["group_signal_strength"]
        and after["group_coherence"] >= 0.65
    ):
        return "cleaner_layout"
    return "needs_review"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _layout_bounds(ui_json: Mapping[str, Any]) -> dict[str, float]:
    rects = []
    for node in ui_json.get("nodes", []):
        if isinstance(node, Mapping):
            rect = _node_rect(node)
            if rect is not None:
                rects.append(rect)
    for group in ui_json.get("groups", []):
        if isinstance(group, Mapping):
            rect = _group_rect(group)
            if rect is not None:
                rects.append(rect)
    if not rects:
        return {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0, "width": 0.0, "height": 0.0}
    left = min(rect[0] for rect in rects)
    top = min(rect[1] for rect in rects)
    right = max(rect[0] + rect[2] for rect in rects)
    bottom = max(rect[1] + rect[3] for rect in rects)
    return {
        "left": round(left, 2),
        "top": round(top, 2),
        "right": round(right, 2),
        "bottom": round(bottom, 2),
        "width": round(right - left, 2),
        "height": round(bottom - top, 2),
    }


def _group_stats(ui_json: Mapping[str, Any]) -> dict[str, float | int]:
    bounds = _layout_bounds(ui_json)
    width = max(1.0, bounds["width"])
    height = max(1.0, bounds["height"])
    group_rects = [
        (group, rect)
        for group in ui_json.get("groups", [])
        if isinstance(group, Mapping)
        for rect in [_group_rect(group)]
        if rect is not None
    ]
    if not group_rects:
        return {
            "count": 0,
            "max_node_count": 0,
            "max_primary_node_count": 0,
            "max_width": 0.0,
            "max_height": 0.0,
            "max_width_ratio": 0.0,
            "max_height_ratio": 0.0,
            "max_primary_width_ratio": 0.0,
            "max_primary_area_ratio": 0.0,
            "setget_group_count": 0,
            "standalone_label_group_count": 0,
        }
    primary_group_rects = [
        (group, rect)
        for group, rect in group_rects
        if "set / get" not in str(group.get("title") or "").lower()
    ]
    max_width = max(rect[2] for _group, rect in group_rects)
    max_height = max(rect[3] for _group, rect in group_rects)
    max_area = max(rect[2] * rect[3] for _group, rect in group_rects)
    max_primary_width = max((rect[2] for _group, rect in primary_group_rects), default=0.0)
    max_primary_area = max((rect[2] * rect[3] for _group, rect in primary_group_rects), default=0.0)
    return {
        "count": len(group_rects),
        "max_node_count": max(len(group.get("nodes") or []) for group, _rect in group_rects),
        "max_primary_node_count": max((len(group.get("nodes") or []) for group, _rect in primary_group_rects), default=0),
        "max_width": round(max_width, 2),
        "max_height": round(max_height, 2),
        "max_width_ratio": round(max_width / width, 4),
        "max_height_ratio": round(max_height / height, 4),
        "max_area_ratio": round(max_area / (width * height), 4),
        "max_primary_width_ratio": round(max_primary_width / width, 4),
        "max_primary_area_ratio": round(max_primary_area / (width * height), 4),
        "setget_group_count": sum(
            1 for group, _rect in group_rects if "set / get" in str(group.get("title") or "").lower()
        ),
        "standalone_label_group_count": sum(
            1
            for group, _rect in group_rects
            if "label" in str(group.get("title") or "").lower() or "note" in str(group.get("title") or "").lower()
        ),
    }


def _write_layout_png(ui_json: Mapping[str, Any], path: Path) -> None:
    nodes = [node for node in ui_json.get("nodes", []) if isinstance(node, Mapping)]
    groups = [group for group in ui_json.get("groups", []) if isinstance(group, Mapping)]
    rects = [_node_rect(node) for node in nodes]
    rects.extend(_group_rect(group) for group in groups if _group_rect(group) is not None)
    rects = [rect for rect in rects if rect is not None]
    if not rects:
        Image.new("RGB", (1200, 800), "white").save(path)
        return

    min_x = min(rect[0] for rect in rects)
    min_y = min(rect[1] for rect in rects)
    max_x = max(rect[0] + rect[2] for rect in rects)
    max_y = max(rect[1] + rect[3] for rect in rects)
    canvas_w, canvas_h = 1600, 1000
    margin = 48
    scale = min(
        (canvas_w - margin * 2) / max(1.0, max_x - min_x),
        (canvas_h - margin * 2) / max(1.0, max_y - min_y),
    )

    def tx(x: float) -> int:
        return round((x - min_x) * scale + margin)

    def ty(y: float) -> int:
        return round((y - min_y) * scale + margin)

    image = Image.new("RGB", (canvas_w, canvas_h), "#f7f7f4")
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()

    for group in groups:
        rect = _group_rect(group)
        if rect is None:
            continue
        x, y, w, h = rect
        color = _group_color(group)
        is_support = _is_support_group(group)
        draw.rounded_rectangle(
            [tx(x), ty(y), tx(x + w), ty(y + h)],
            radius=8 if is_support else 10,
            fill=(*color, 6 if is_support else 48),
            outline=(*color, 38 if is_support else 220),
            width=1 if is_support else 3,
        )
        draw.text(
            (tx(x) + 8, ty(y) + 7),
            str(group.get("title") or "Group")[:30],
            fill=(*color, 70 if is_support else 255),
            font=font,
        )

    for node in nodes:
        rect = _node_rect(node)
        if rect is None:
            continue
        x, y, w, h = rect
        class_type = str(node.get("type") or node.get("class_type") or "Node")
        color = _node_color(class_type)
        is_support = _is_support_node(class_type)
        draw.rectangle(
            [tx(x), ty(y), tx(x + w), ty(y + h)],
            fill=(*color, 36 if is_support else 190),
            outline=(45, 45, 45, 32 if is_support else 170),
            width=1,
        )

    image.save(path)


def _write_contact_sheet(paths: list[Path], path: Path) -> None:
    images = [Image.open(item).convert("RGB") for item in paths]
    if not images:
        Image.new("RGB", (1200, 800), "white").save(path)
        return
    thumb_w, thumb_h = 800, 500
    label_h = 24
    columns = 2
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + label_h)), "#f7f7f4")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (image, source_path) in enumerate(zip(images, paths, strict=True)):
        image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_w
        y = (index // columns) * (thumb_h + label_h)
        sheet.paste(image, (x + (thumb_w - image.width) // 2, y + label_h + (thumb_h - image.height) // 2))
        draw.text((x + 8, y + 6), source_path.parent.name, fill=(55, 65, 75), font=font)
    sheet.save(path)


def _node_rect(node: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    pos = node.get("pos")
    size = node.get("size")
    if not (isinstance(pos, list) and len(pos) >= 2):
        return None
    width, height = 260.0, 100.0
    if isinstance(size, list) and len(size) >= 2:
        width = _number(size[0], width)
        height = _number(size[1], height)
    return (_number(pos[0], 0.0), _number(pos[1], 0.0), width, height)


def _group_rect(group: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    bounding = group.get("bounding")
    if not (isinstance(bounding, list) and len(bounding) >= 4):
        return None
    return (
        _number(bounding[0], 0.0),
        _number(bounding[1], 0.0),
        _number(bounding[2], 0.0),
        _number(bounding[3], 0.0),
    )


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _group_color(group: Mapping[str, Any]) -> tuple[int, int, int]:
    explicit = group.get("color")
    if isinstance(explicit, str):
        parsed = _hex_color(explicit)
        if parsed is not None:
            return parsed
    title = str(group.get("title") or "Group")
    lowered = title.lower()
    if _is_support_group(group):
        return (168, 173, 180)
    palette = {
        "Loaders": (63, 111, 143),
        "Conditioning": (123, 94, 167),
        "Latent": (107, 143, 90),
        "Sampling": (154, 106, 58),
        "Decode": (79, 127, 114),
        "Output": (138, 95, 104),
        "Postprocess": (122, 117, 96),
        "Utility": (104, 111, 120),
        "Custom": (100, 100, 100),
    }
    return palette.get(title, (80, 120, 150))


def _is_support_group(group: Mapping[str, Any]) -> bool:
    title = str(group.get("title") or "Group").lower()
    return "set / get" in title or "helper" in title or "label" in title or "note" in title


def _hex_color(value: str) -> tuple[int, int, int] | None:
    raw = value.strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6:
        return None
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return None


def _node_color(class_type: str) -> tuple[int, int, int]:
    lowered = class_type.lower()
    if any(token in lowered for token in ("loader", "clip", "vae", "unet", "model", "lora")):
        return (80, 125, 165)
    if any(token in lowered for token in ("sampler", "scheduler", "noise", "sigma")):
        return (180, 120, 70)
    if any(token in lowered for token in ("decode", "save", "combine", "output", "preview")):
        return (100, 145, 120)
    if any(token in lowered for token in ("note", "markdown", "setnode", "getnode")):
        return (130, 130, 138)
    return (150, 120, 165)


def _is_support_node(class_type: str) -> bool:
    lowered = class_type.lower()
    return any(token in lowered for token in ("setnode", "getnode", "reroute"))


_REORGANISE_BUILDERS = {
    "reorganise-large-messy-batch": build_reorganise_large_messy_batch_evidence,
    "reorganise-large-messy-ltx-workflow": build_reorganise_large_messy_ltx_workflow_evidence,
}

__all__ = [
    "_REORGANISE_BUILDERS",
    "build_reorganise_large_messy_batch_evidence",
    "build_reorganise_large_messy_ltx_workflow_evidence",
]
