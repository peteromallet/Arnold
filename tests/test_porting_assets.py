from __future__ import annotations

from pathlib import Path

from vibecomfy.model_assets import extract_from_raw_workflow
from vibecomfy.porting.assets import analyze_model_assets


def test_porting_asset_analysis_merges_sources_and_warns_on_filename_only_candidates(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "READY_METADATA = {'model_assets': ["
        "{'name': 'from_metadata.safetensors', 'url': 'https://example.test/from_metadata.safetensors?download=true', 'subdir': 'checkpoints'}"
        "]}\n"
        "READY_REQUIREMENTS = {'models': ["
        "'filename_only.safetensors',"
        "{'name': 'shared.safetensors', 'url': 'https://example.test/shared.safetensors', 'subdir': 'vae'}"
        "]}\n",
        encoding="utf-8",
    )
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "UNETLoader",
                "properties": {
                    "models": [
                        {
                            "name": "shared.safetensors",
                            "url": "https://example.test/shared.safetensors?download=true",
                            "subdir": "vae",
                        },
                        {"name": "raw_filename_only.safetensors"},
                    ]
                },
            }
        ]
    }
    api_prompt = {
        "10": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "api_only.safetensors", "unrelated": "notes.txt"},
        }
    }

    analysis = analyze_model_assets(
        raw_workflow=raw,
        api_prompt=api_prompt,
        scratchpad_path=scratchpad,
        ready_metadata={
            "model_assets": [
                {
                    "name": "ready_meta.safetensors",
                    "url": "https://example.test/ready_meta.safetensors",
                    "subdir": "diffusion_models",
                }
            ]
        },
        ready_requirements={"models": [{"name": "ready_req.safetensors", "subdir": "loras"}]},
    )
    payload = analysis.to_json()

    assert [(candidate["name"], candidate["url"], candidate["subdir"]) for candidate in payload["candidates"]] == [
        ("api_only.safetensors", None, "checkpoints"),
        ("filename_only.safetensors", None, "checkpoints"),
        ("from_metadata.safetensors", "https://example.test/from_metadata.safetensors", "checkpoints"),
        ("raw_filename_only.safetensors", None, "diffusion_models"),
        ("ready_meta.safetensors", "https://example.test/ready_meta.safetensors", "diffusion_models"),
        ("ready_req.safetensors", None, "loras"),
        ("shared.safetensors", "https://example.test/shared.safetensors", "vae"),
    ]
    assert [issue["code"] for issue in payload["diagnostics"]] == [
        "filename_only_asset_candidate",
        "filename_only_asset_candidate",
        "filename_only_asset_candidate",
        "filename_only_asset_candidate",
    ]
    shared = next(candidate for candidate in payload["candidates"] if candidate["name"] == "shared.safetensors")
    assert shared["metadata"]["sources"] == ["ui_properties", "scratchpad_ready_requirements"]


def test_python_metadata_extractor_resolves_literal_module_constants(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "MODEL_ASSETS = ["
        "{'name': 'from_constant.safetensors', 'url': 'https://example.test/from_constant.safetensors', 'subdir': 'vae'}"
        "]\n"
        "READY_METADATA = {'model_assets': MODEL_ASSETS}\n"
        "READY_REQUIREMENTS = {'models': MODEL_ASSETS, 'custom_nodes': ['ComfyUI-Test']}\n",
        encoding="utf-8",
    )

    analysis = analyze_model_assets(scratchpad_path=scratchpad)
    payload = analysis.to_json()

    assert [(candidate["name"], candidate["subdir"], candidate["source"]) for candidate in payload["candidates"]] == [
        ("from_constant.safetensors", "vae", "scratchpad_metadata")
    ]


def test_legacy_raw_workflow_extractor_still_returns_only_url_bearing_assets() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "UNETLoader",
                "properties": {
                    "models": [
                        {"name": "filename_only.safetensors"},
                        {
                            "name": "url_asset.safetensors",
                            "url": "https://example.test/url_asset.safetensors?download=true",
                        },
                    ]
                },
            }
        ]
    }

    assert extract_from_raw_workflow(raw) == [
        {
            "name": "url_asset.safetensors",
            "url": "https://example.test/url_asset.safetensors",
            "subdir": "diffusion_models",
        }
    ]
    assert [
        (candidate.name, candidate.url)
        for candidate in analyze_model_assets(raw_workflow=raw).candidates
    ] == [
        ("filename_only.safetensors", None),
        ("url_asset.safetensors", "https://example.test/url_asset.safetensors"),
    ]


def test_head_checks_are_opt_in_injectable_and_dedupe_duplicate_urls() -> None:
    calls: list[tuple[str, float]] = []

    def head_client(url: str, timeout: float) -> dict[str, object]:
        calls.append((url, timeout))
        if url.endswith("missing.safetensors"):
            return {"status_code": 404, "url": url}
        return {"status_code": 302, "url": "https://cdn.example.test/model.safetensors"}

    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "UNETLoader",
                "properties": {
                    "models": [
                        {"name": "model.safetensors", "url": "https://example.test/model.safetensors"},
                        {"name": "duplicate.safetensors", "url": "https://example.test/model.safetensors"},
                        {"name": "missing.safetensors", "url": "https://example.test/missing.safetensors"},
                    ]
                },
            }
        ]
    }

    assert analyze_model_assets(raw_workflow=raw, head_client=head_client).checks == []

    analysis = analyze_model_assets(
        raw_workflow=raw,
        head_check=True,
        head_client=head_client,
        head_timeout_seconds=1.25,
    )
    payload = analysis.to_json()

    assert calls == [
        ("https://example.test/missing.safetensors", 1.25),
        ("https://example.test/model.safetensors", 1.25),
    ]
    assert [(check["url"], check["ok"], check["status_code"], check["error"]) for check in payload["checks"]] == [
        ("https://example.test/missing.safetensors", False, 404, "not_found"),
        ("https://example.test/model.safetensors", True, 302, None),
    ]
    assert payload["checks"][1]["detail"]["duplicate_count"] == 2
    assert [issue["code"] for issue in payload["diagnostics"]] == ["model_asset_head_check_failed"]
