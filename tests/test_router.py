from __future__ import annotations

import pytest

from vibecomfy import router
from vibecomfy.patches.types import Patch


@pytest.mark.parametrize(
    ("verb_kind", "verb_name", "inputs", "template_id", "patch_names"),
    [
        ("image", "t2i", {}, "image/z_image", []),
        ("image", "t2i", {"model": "flux2_klein_4b"}, "image/flux2_klein_4b_t2i", []),
        ("video", "t2v", {}, "video/wan_t2v", []),
        ("video", "t2v", {"model": "ltx"}, "video/ltx2_3_t2v", ["ltx_lowvram", "resolution:384x256x9"]),
        ("video", "i2v", {}, "video/wan_i2v", []),
        ("video", "i2v", {"model": "ltx"}, "video/ltx2_3_i2v", ["ltx_lowvram", "resolution:384x256x9"]),
    ],
)
def test_router_positive_rules(
    verb_kind: str,
    verb_name: str,
    inputs: dict[str, object],
    template_id: str,
    patch_names: list[str],
) -> None:
    result = router.pick(verb_kind, verb_name, **inputs)

    assert result.template_id == template_id
    assert [patch.name for patch in result.explicit_patches] == patch_names
    assert isinstance(result.applicable_patches, list)
    assert all(isinstance(patch, Patch) for patch in result.applicable_patches)
    if inputs.get("model") == "ltx":
        assert result.applicable_patches == []


@pytest.mark.parametrize(
    ("verb_kind", "verb_name", "inputs"),
    [
        ("whatever", "unknown", {}),
        ("image", "t2i", {"model": "flux2_klein_9b_gguf"}),
        ("image", "edit", {"model": "qwen"}),
        ("image", "edit", {"model": "flux2_klein_4b"}),
    ],
)
def test_router_rejects_unknown_and_deferred_routes(
    verb_kind: str,
    verb_name: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(KeyError):
        router.pick(verb_kind, verb_name, **inputs)
