#!/usr/bin/env python3
"""Generate 77 STAGED live-agentic scenarios from the external_workflows corpus.

These live OUTSIDE the vibecomfy repo working tree (in this sibling dir) so the
running live_agentic_watchdog's git-tree safety gate cannot sweep them, and so
they do NOT auto-run. The runner only globs ``tests/live_agentic_harness/scenarios/``
by default; to activate a scenario, copy its .json into that folder.

Each scenario's ``query`` is authored from the workflow's REAL manifest metadata
(title / task_type / tags / flags / family) according to its assigned
``query_type`` and ``complexity``, so every query is specific to its workflow
rather than boilerplate. ``_tags`` embeds the categorization so the catalog is
self-describing and operators can filter (e.g. by modality, query_type,
complexity, requires_custom_nodes). ``workflow_path`` is repo-relative and
resolves at run time when the harness is invoked from the repo root.

Inputs:  /tmp/agentic_selected.json  (77 selected workflows + assigned qt/cx)
Output:  ./<id>.json  (77 scenario files)

Re-run freely; it overwrites the staged files deterministically.
"""
from __future__ import annotations

import json
import os
import random
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECTED = Path("/tmp/agentic_selected.json")

# ── model families, used to make "swap backbone" queries concrete ────────────
FAMILIES_BY_MEDIA = {
    "image": ["Flux", "SDXL", "SD 1.5", "Pony", "Illustrious"],
    "video": ["Wan2.2", "Hunyuan Video", "LTX-Video", "SVD", "AnimateDiff", "Mochi", "CogVideoX"],
    "3d": ["Rodin", "TripoSR", "InstantMesh", "Hunyuan3D"],
    "audio": ["AceStep", "IndexTTS", "CosyVoice", "Chatterbox", "F5-TTS", "Bark"],
    "multi": ["Flux", "Wan2.2", "Hunyuan Video", "LTX-Video", "Qwen-Image"],
}
FAMILY_RE = re.compile(
    r"\b(flux|sdxl|sd ?1\.5|sd15|pony|illustrious|wan2?\.?2?|hunyuan|ltx|ltxv|svd|"
    r"animatediff|mochi|cogvideo|rodin|triposr|instantmesh|ace.?step|indextts|"
    r"cosyvoice|chatterbox|f5|qwen)\b",
    re.I,
)

# All symptoms are PREDICATES (no leading subject) so "The {noun} {sym}" reads
# correctly for edit/fix and "The {noun} this produces {sym}" for diagnose.
SYMPTOMS = {
    "image": [
        "comes out plasticky and over-smoothed",
        "has a muddy color cast in the midtones",
        "loses all its fine detail in the shadows",
        "looks slightly soft, like it's been through a jpeg cycle",
        "gets cropped too tight at the edges",
        "drifts green in the skin tones on anything backlit",
    ],
    "video": [
        "flickers and shimmers between frames",
        "barely moves — the motion is almost dead",
        "jitters in a way that reads as glitchy, not cinematic",
        "drops to mush about halfway through",
        "comes out at the wrong aspect ratio and gets squashed",
        "has a boiling, flickering texture in flat regions",
    ],
    "audio": [
        "has a constant low hiss riding under everything",
        "comes out flat and robotic in the voice",
        "clips into distortion on the louder phrases",
        "drowns the narration under the music bed",
        "pops and clicks at every phrase boundary",
    ],
    "3d": [
        "is full of floating bits and stray geometry",
        "stretches and smears across the UV seams",
        "comes out blocky and low-poly",
        "has inverted normals on one whole side",
        "has holes where the back faces never closed",
    ],
    "multi": [
        "doesn't line up between stages — the second pass fights the first",
        "drifts out of sync with the audio by the end",
        "loses the character's identity across the frames",
        "drops the conditioning from stage one in stage two",
        "regenerates from scratch instead of building on the prior pass",
    ],
}

OUTPUT_NOUN = {
    "image": "image",
    "video": "clip",
    "audio": "audio",
    "3d": "mesh",
    "multi": "output",
}

# Per-modality rotating symptom pool so diagnose + high-edit queries don't
# repeat the same symptom back-to-back. Populated lazily, refills when empty.
_SYMPTOM_QUEUES: dict[str, deque] = {}


def next_symptom(media: str) -> str:
    q = _SYMPTOM_QUEUES.get(media)
    if not q:
        items = list(SYMPTOMS[media])
        random.shuffle(items)
        q = deque(items)
        _SYMPTOM_QUEUES[media] = q
    item = q.popleft()
    if not q:  # exhausted -> refill for subsequent draws
        items = list(SYMPTOMS[media])
        random.shuffle(items)
        _SYMPTOM_QUEUES[media] = deque(items)
    return item


def slugify(text: str, limit: int = 46) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].strip("-")


def detect_family(cand: dict, media: str) -> str | None:
    """Detect the workflow's model family, but only if it belongs to *media*.

    Avoids cross-modal mismatches (e.g. a manifest-mislabeled video workflow
    tagged ``media=image`` yielding "swap Wan2.2 -> SDXL").
    """
    media_fams = set(FAMILIES_BY_MEDIA.get(media, []))
    norm = {
        "flux": "Flux", "sdxl": "SDXL", "sd15": "SD 1.5", "sd 1.5": "SD 1.5",
        "pony": "Pony", "illustrious": "Illustrious", "wan2": "Wan2.2", "wan2.2": "Wan2.2",
        "hunyuan": "Hunyuan Video", "ltx": "LTX-Video", "ltxv": "LTX-Video", "svd": "SVD",
        "animatediff": "AnimateDiff", "mochi": "Mochi", "cogvideo": "CogVideoX",
        "rodin": "Rodin", "triposr": "TripoSR", "instantmesh": "InstantMesh",
        "ace-step": "AceStep", "ace step": "AceStep", "indextts": "IndexTTS",
        "cosyvoice": "CosyVoice", "chatterbox": "Chatterbox", "f5": "F5-TTS",
        "qwen": "Qwen-Image",
    }
    hay = " ".join([cand.get("title", ""), " ".join(cand.get("tags", []))]).lower()
    for m in FAMILY_RE.finditer(hay):
        fam = norm.get(m.group(1).lower())
        if fam and fam in media_fams:
            return fam
    return None


def alt_family(cand: dict, media: str) -> str:
    cur = detect_family(cand, media)
    opts = [f for f in FAMILIES_BY_MEDIA.get(media, []) if f != cur]
    return random.choice(opts) if opts else (cur or "a newer model")


# Rotating generic edit-tweak pools, used when a workflow has no lora/controlnet/
# ipadapter flags and a task_type with no specific branch (e.g. task="other").
# Per-media so 3d/audio edits read sensibly instead of all repeating one line.
_GENERIC_EDIT_QUEUES: dict[str, deque] = {}
_GENERIC_EDITS = {
    "image": [
        "Lower the denoise on the final pass to 0.35 so it keeps more of the original detail.",
        "Bump the CFG scale up to 7.5 for a sharper, more committed result.",
        "Drop the sampling steps to 25 — it's running hotter than it needs to.",
        "Raise the guidance to 8 so the prompt reads through more strongly.",
        "Switch the scheduler to 'karras' at 30 steps for a smoother convergence.",
        "Set the seed to 42 so the result is reproducible across runs.",
    ],
    "video": [
        "Lower the denoise on the final pass to 0.35 so it keeps more of the original detail.",
        "Drop the sampling steps to 25 — the render is taking longer than it needs to.",
        "Set the output to 24 fps and cap the frame count at 48 to keep it snappy.",
        "Raise the CFG to 7.5 for a sharper, more committed look.",
        "Switch the scheduler to 'karras' at 30 steps for smoother temporal convergence.",
    ],
    "3d": [
        "Raise the mesh subdivision target so the export isn't so coarse.",
        "Lower the diffusion guidance so the geometry stays closer to the input silhouette.",
        "Increase the texture resolution to 2K before export.",
        "Set the output to GLB with normals and UVs included.",
        "Drop the sampling steps to 25 — it's running hotter than it needs to.",
    ],
    "audio": [
        "Lower the noise-gate threshold so it stops cutting off the quiet tails.",
        "Set the sample rate to 44.1 kHz and normalize the output to -1 dB.",
        "Reduce the reverb mix to 20% — it's washing out the dry signal.",
        "Raise the guidance/temperature slightly so the generation is less monotone.",
    ],
    "multi": [
        "Lower the denoise on the final pass to 0.35 so it keeps more of the original detail.",
        "Drop the sampling steps to 25 — it's running hotter than it needs to.",
        "Raise the CFG to 7.5 for a sharper, more committed result across both stages.",
        "Set the output to 24 fps and cap the frame count at 48 to keep it snappy.",
    ],
}


def next_generic_edit(media: str) -> str:
    q = _GENERIC_EDIT_QUEUES.get(media)
    if not q:
        items = list(_GENERIC_EDITS[media])
        random.shuffle(items)
        q = deque(items)
        _GENERIC_EDIT_QUEUES[media] = q
    item = q.popleft()
    if not q:
        items = list(_GENERIC_EDITS[media])
        random.shuffle(items)
        _GENERIC_EDIT_QUEUES[media] = deque(items)
    return item


def pick_task_phrase(cand: dict, media: str) -> str:
    """Concrete param tweak grounded in the workflow's flags/task."""
    f = cand.get("flags", {})
    task = cand.get("task") or "other"
    if f.get("has_lora"):
        return "Drop the LoRA strength to 0.55 — it's overpowering the base model."
    if f.get("has_ipadapter"):
        return "Raise the IP-Adapter weight to 0.85 so the reference actually reads through."
    if f.get("has_controlnet"):
        return "Pull the ControlNet conditioning weight back to 0.5 so it guides without taking over."
    if task == "upscaling":
        return "Switch the upscaler to 4x-UltraSharp and set the upscale ratio to 2x."
    if task == "text_to_image":
        return "Set the sampler to dpmpp_2m, 28 steps, CFG 5 — the current settings are overcooking it."
    if task == "image_to_video" or f.get("has_video_output"):
        return "Set the output to 24 fps and cap the frame count at 48 to keep the render snappy."
    if task == "inpainting":
        return "Set the inpaint denoise to 0.62 so the edit blends cleanly into the surrounding area."
    if task == "outpainting":
        return "Extend the canvas by 1.25x on every side with feathering set to 20px."
    if task == "compositing":
        return "Change the overlay blend mode to 'screen' at 70% opacity."
    if task == "animation":
        return "Bump the motion bucket to 5 and raise the context frames to 16."
    if task == "image_to_image":
        return "Set the img2img denoise to 0.45 so it keeps the structure but re-renders the surface."
    if task == "lora_training":
        return "Raise the training steps to 1500 and set the learning rate to 1e-4."
    return next_generic_edit(media)


def author_query(cand: dict) -> tuple[str, str]:
    """Return (query, abstraction) for the assigned query_type + complexity."""
    media = cand["media"]
    qt = cand["qt"]
    cx = cand["cx_bucket"]
    noun = OUTPUT_NOUN.get(media, "output")
    family = detect_family(cand, media)
    task = cand.get("task") or "this"
    tags = cand.get("tags", [])
    tag_phrase = tags[0].replace("-", " ") if tags else "this pipeline"
    sym = next_symptom(media)

    if qt == "edit":
        # low/med complexity -> specific param edit; high -> symptom fix
        if cx in ("low", "med"):
            return pick_task_phrase(cand, media), "low"
        return (f"The {noun} {sym} — can you fix it without changing the overall composition?"), "high"

    if qt == "big_adjustment":
        kind = random.choice(["replace", "add_stage", "split", "reroute"])
        if kind == "replace":
            alt = alt_family(cand, media)
            if family:
                q = (f"Replace the {family} backbone with {alt} and rewire the sampler and "
                     f"conditioning to match the new model.")
            else:
                q = (f"Swap out the current backbone for {alt} and rewire the sampler and "
                     f"conditioning to match the new model.")
        elif kind == "add_stage":
            q = (f"Insert a final refinement/upscale pass after the main generation so the "
                 f"{noun} comes out cleaner and higher-resolution.")
        elif kind == "split":
            q = (f"Split this into two stages — a coarse first pass, then a detail-refinement "
                 f"pass driven by the first — instead of generating in one shot.")
        else:  # reroute
            q = (f"Reroute the {tag_phrase} output into a conditioning loop so the result feeds "
                 f"back and self-improves over two iterations.")
        return q, "high"

    if qt == "research":
        angles = [
            f"This {media} workflow is too slow and heavy. Is there a distilled or faster way to "
            f"run it without changing the creative intent? Summarize the realistic options before editing.",
            f"What's the current state of the art for {task.replace('_', ' ')}? I want to know whether "
            f"there's a better technique than what's wired here — don't change anything yet.",
            f"How does {alt_family(cand, media)} compare to the {family or 'current'} model this graph "
            f"uses, and would it be a drop-in upgrade? Research first, then advise.",
            f"I'm hitting {media} quality ceilings with this setup. What are the highest-leverage "
            f"changes I could make — models, samplers, conditioning? Give me a ranked shortlist, no edits.",
        ]
        return random.choice(angles), "high"

    if qt == "diagnose":
        return (f"The {noun} this produces {sym}. Walk the graph, find the misconfigured node or wrong "
                f"setting, and tell me the root cause before you change anything."), "high"

    if qt == "explain":
        q = random.choice([
            (f"Walk me through this graph stage by stage — what each major node does and how data "
             f"flows through it — and call out anything that looks redundant, fragile, or over-engineered. "
             f"Don't modify it."),
            (f"I inherited this workflow and need to understand it fast. Summarize what it produces, the "
             f"key techniques it relies on, and any stage that looks risky or over-engineered. Don't change "
             f"anything."),
            (f"Explain this graph end to end: which nodes are load-bearing versus optional, and where the "
             f"fragile parts are. Ask one clarifying question if anything is ambiguous rather than guessing."),
        ])
        return q, "med"

    return "Inspect this workflow and improve the output quality.", "med"


def desired_for(cand: dict) -> dict | None:
    qt = cand["qt"]
    media = cand["media"]
    noun = OUTPUT_NOUN.get(media, "output")
    if qt == "edit":
        return {
            "outcome": "the requested change is applied correctly and the output clearly reflects it.",
            "quality": ("the edit is scoped to the intended stage only; no orphaned nodes, no broken or "
                        "dangling wiring, and the rest of the pipeline still produces its outputs."),
            "alternatives_ok": True,
        }
    if qt == "big_adjustment":
        return {
            "outcome": "the restructured pipeline runs end-to-end and produces the intended improvement.",
            "quality": ("every new or changed stage is fully wired with no dangling inputs; the original "
                        "pipeline's function is preserved or improved; nothing is left half-connected."),
            "alternatives_ok": True,
        }
    return None  # research / diagnose / explain don't go through the edit judge


def timeout_for(cand: dict) -> int:
    media = cand["media"]
    qt = cand["qt"]
    base = {"image": 200, "video": 320, "3d": 360, "audio": 320, "multi": 360}[media]
    if qt == "big_adjustment":
        base += 60
    if cand["cx_bucket"] == "low":
        base -= 40
    return base


def main() -> None:
    selected = json.loads(SELECTED.read_text())
    random.seed(7777)
    seen_ids = set()
    written = []

    for cand in selected:
        query, abstraction = author_query(cand)
        qt = cand["qt"]
        is_change = qt in ("edit", "big_adjustment")

        scenario = {
            "id": None,
            "query": query,
            "workflow_path": cand["path"],
            "network": True,
            "timeout": timeout_for(cand),
        }
        if is_change:
            scenario["apply"] = True
            scenario["assessment"] = {"expect_graph_changed": True}
            d = desired_for(cand)
            if d:
                scenario["desired"] = d
        else:
            scenario["apply"] = False
            scenario["assessment"] = {"expect_graph_changed": False}

        sid = f"{cand['media']}-{slugify(cand.get('title') or cand['id'])}-{cand['id'][:6]}"
        scenario["id"] = sid
        scenario["_tags"] = {
            "modality": cand["media"],
            "query_type": qt,
            "abstraction": abstraction,
            "complexity": cand["cx_bucket"],
            "manifest_complexity": cand.get("complexity"),
            "task_type": cand.get("task"),
            "requires_custom_nodes": cand.get("rcn"),
            "techniques": cand.get("tags", []),
            "source_workflow_id": cand["id"],
            "source": "external_workflows/corpus",
            "staged": True,
        }
        assert sid not in seen_ids, sid
        seen_ids.add(sid)
        (HERE / f"{sid}.json").write_text(json.dumps(scenario, indent=2) + "\n")
        written.append(scenario)

    print(f"wrote {len(written)} staged scenarios to {HERE}")
    print("query_type:", dict(Counter(w["_tags"]["query_type"] for w in written)))
    print("modality:", dict(Counter(w["_tags"]["modality"] for w in written)))
    print("complexity:", dict(Counter(w["_tags"]["complexity"] for w in written)))
    print("apply=True (change) :", sum(1 for w in written if w.get("apply")))
    print("apply=False (no-change):", sum(1 for w in written if w.get("apply") is False))


if __name__ == "__main__":
    main()
