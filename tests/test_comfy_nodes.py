from __future__ import annotations

from vibecomfy.comfy_nodes import VibeComfyStripConditioningKeys


def test_strip_conditioning_keys_removes_metadata_without_touching_embeddings() -> None:
    node = VibeComfyStripConditioningKeys()
    positive = [["embedding", {"guide_attention_entries": ["mask"], "keyframe_idxs": "keep"}]]
    negative = [["negative", {"guide_attention_entries": ["mask"], "other": 1}]]

    stripped_positive, stripped_negative = node.strip(positive, negative, "guide_attention_entries")

    assert stripped_positive == [["embedding", {"keyframe_idxs": "keep"}]]
    assert stripped_negative == [["negative", {"other": 1}]]
    assert positive[0][1]["guide_attention_entries"] == ["mask"]
