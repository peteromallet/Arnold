from __future__ import annotations

from pathlib import Path

from vibecomfy import runpod_setup
from vibecomfy.registry.models_loader import canonical_filename, load_registry


def test_baseline_registry_includes_sd15_fp16() -> None:
    entries = load_registry()

    assert canonical_filename("sd15_v1_5_pruned_emaonly_fp16", registry=entries) == "v1-5-pruned-emaonly-fp16.safetensors"


def test_configure_workspace_cache_defaults_to_models_parent(tmp_path: Path, monkeypatch) -> None:
    for name in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)

    cache_root = runpod_setup.configure_workspace_cache(models_root=tmp_path / "vibecomfy" / "models")

    assert cache_root == (tmp_path / "vibecomfy" / "cache").resolve()
    assert Path(runpod_setup.os.environ["HF_HOME"]) == cache_root / "huggingface"
    assert Path(runpod_setup.os.environ["HUGGINGFACE_HUB_CACHE"]) == cache_root / "huggingface" / "hub"
    assert Path(runpod_setup.os.environ["XDG_CACHE_HOME"]) == cache_root / "xdg"


def test_park_node_packs_moves_resadapter_out_of_custom_nodes(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    disabled = tmp_path / "disabled_custom_nodes"
    pack = custom_nodes / "ComfyUI-ResAdapter"
    pack.mkdir(parents=True)
    (pack / "__init__.py").write_text("", encoding="utf-8")

    result = runpod_setup.park_node_packs(custom_nodes=custom_nodes, disabled_custom_nodes=disabled)

    assert result[0].changed is True
    assert not pack.exists()
    assert (disabled / "ComfyUI-ResAdapter" / "__init__.py").exists()


def test_park_node_packs_dry_run_leaves_tree_in_place(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    disabled = tmp_path / "disabled_custom_nodes"
    pack = custom_nodes / "ComfyUI-ResAdapter"
    pack.mkdir(parents=True)

    result = runpod_setup.park_node_packs(custom_nodes=custom_nodes, disabled_custom_nodes=disabled, dry_run=True)

    assert result[0].changed is True
    assert pack.exists()


def test_unpark_node_packs_moves_resadapter_back_to_custom_nodes(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    disabled = tmp_path / "disabled_custom_nodes"
    pack = disabled / "ComfyUI-ResAdapter"
    pack.mkdir(parents=True)
    (pack / "__init__.py").write_text("", encoding="utf-8")

    result = runpod_setup.unpark_node_packs(custom_nodes=custom_nodes, disabled_custom_nodes=disabled)

    assert result[0].changed is True
    assert not pack.exists()
    assert (custom_nodes / "ComfyUI-ResAdapter" / "__init__.py").exists()
