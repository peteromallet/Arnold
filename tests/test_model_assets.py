from __future__ import annotations

from pathlib import Path

from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.model_assets import entries_from_scratchpad_path, extract_from_raw_workflow


def test_extract_from_raw_workflow_normalises_model_metadata() -> None:
    raw = {
        "nodes": [
            {
                "id": 30,
                "type": "UNETLoader",
                "properties": {
                    "models": [
                        {
                            "name": "fallback.safetensors",
                            "url": "https://example.test/models/fallback.safetensors?download=true",
                        }
                    ]
                },
            },
            {
                "id": 10,
                "type": "UnknownLoader",
                "properties": {
                    "models": [
                        {
                            "name": "explicit.safetensors",
                            "url": "https://example.test/models/explicit.safetensors?download=true&x=1",
                            "directory": "custom_dir",
                        },
                        {
                            "name": "skip-missing-url.safetensors",
                        },
                    ]
                },
            },
            {
                "id": 20,
                "type": "NoDirectoryLoader",
                "properties": {
                    "models": [
                        {
                            "name": "split.safetensors",
                            "url": "https://huggingface.co/org/repo/resolve/main/split_files/vae/split.safetensors?download=true",
                        },
                        {
                            "name": "explicit.safetensors",
                            "url": "https://example.test/models/explicit.safetensors?download=true",
                            "directory": "custom_dir",
                        },
                    ]
                },
            },
        ]
    }

    assert extract_from_raw_workflow(raw) == [
        {
            "name": "explicit.safetensors",
            "url": "https://example.test/models/explicit.safetensors?x=1",
            "subdir": "custom_dir",
        },
        {
            "name": "split.safetensors",
            "url": "https://huggingface.co/org/repo/resolve/main/split_files/vae/split.safetensors",
            "subdir": "vae",
        },
        {
            "name": "fallback.safetensors",
            "url": "https://example.test/models/fallback.safetensors",
            "subdir": "diffusion_models",
        },
    ]


def test_extract_from_raw_workflow_recurses_nested_subgraphs() -> None:
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "nodes": [
                        {
                            "id": "2",
                            "type": "CLIPLoader",
                            "properties": {
                                "models": [
                                    {
                                        "name": "outer.safetensors",
                                        "url": "https://example.test/outer.safetensors",
                                    }
                                ]
                            },
                        }
                    ],
                    "definitions": {
                        "subgraphs": [
                            {
                                "nodes": [
                                    {
                                        "id": "1",
                                        "type": "VAELoader",
                                        "properties": {
                                            "models": [
                                                {
                                                    "name": "inner.safetensors",
                                                    "url": "https://example.test/inner.safetensors",
                                                }
                                            ]
                                        },
                                    }
                                ]
                            }
                        ]
                    },
                }
            ]
        }
    }

    assert extract_from_raw_workflow(raw) == [
        {"name": "outer.safetensors", "url": "https://example.test/outer.safetensors", "subdir": "text_encoders"},
        {"name": "inner.safetensors", "url": "https://example.test/inner.safetensors", "subdir": "vae"},
    ]


def test_extract_from_raw_workflow_returns_empty_for_api_shaped_workflow() -> None:
    assert extract_from_raw_workflow({"1": {"class_type": "VAELoader", "inputs": {}}}) == []


def test_entries_from_scratchpad_path_reads_materialized_requirements(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "READY_REQUIREMENTS = {'models': ["
        "{'name': 'model.safetensors', 'url': 'https://example.test/model.safetensors?download=true', 'subdir': 'checkpoints'},"
        "'legacy.safetensors',"
        "{'name': 'model.safetensors', 'url': 'https://example.test/duplicate.safetensors', 'subdir': 'checkpoints'}"
        "], 'custom_nodes': []}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors", "subdir": "checkpoints"}
    ]


def test_entries_from_scratchpad_path_resolves_literal_module_constants(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "MODEL_ASSETS = ["
        "{'name': 'from_constant.safetensors', 'url': 'https://example.test/from_constant.safetensors', 'subdir': 'vae'}"
        "]\n"
        "READY_REQUIREMENTS = {'models': MODEL_ASSETS, 'custom_nodes': []}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {
            "name": "from_constant.safetensors",
            "url": "https://example.test/from_constant.safetensors",
            "subdir": "vae",
        }
    ]


def test_entries_from_scratchpad_path_respects_explicit_subdir_for_non_split_asset(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "READY_REQUIREMENTS = {'models': ["
        "{'name': 'flux-2-klein-4b-fp8.safetensors', "
        "'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors', "
        "'subdir': 'diffusion_models'}"
        "], 'custom_nodes': []}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {
            "name": "flux-2-klein-4b-fp8.safetensors",
            "url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors",
            "subdir": "diffusion_models",
        }
    ]


def test_real_wan_t2v_extracts_three_assets() -> None:
    entries = extract_from_raw_workflow(load_workflow_json("workflow_corpus/official/video/wan_t2v.json"))

    assert [(entry["name"], entry["subdir"]) for entry in entries] == [
        ("wan2.1_t2v_1.3B_fp16.safetensors", "diffusion_models"),
        ("umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders"),
        ("wan_2.1_vae.safetensors", "vae"),
    ]
    assert all("?download=true" not in entry["url"] for entry in entries)


def test_real_flux2_subgraph_extracts_pre_policy_assets() -> None:
    entries = extract_from_raw_workflow(load_workflow_json("workflow_corpus/official/image/flux2_klein_9b_t2i.json"))

    assert [(entry["name"], entry["subdir"]) for entry in entries] == [
        ("flux-2-klein-base-9b-fp8.safetensors", "diffusion_models"),
        ("qwen_3_8b_fp8mixed.safetensors", "text_encoders"),
        ("full_encoder_small_decoder.safetensors", "vae"),
    ]
