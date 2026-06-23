from __future__ import annotations

import json
from typing import Any

from scripts import upload_ready_templates_to_hivemind as upload


def test_envelope_includes_optional_description_in_body_metadata_and_payload() -> None:
    row = {
        "id": "video/example",
        "path": "ready_templates/video/example.py",
        "media": "video",
        "description": "  Turns a single portrait into a short motion clip.  ",
    }

    envelope = upload._envelope(row, "def build():\n    pass\n")

    data = envelope["data"]
    assert "Description: Turns a single portrait into a short motion clip." in data["body"]
    assert data["metadata"]["description"] == "Turns a single portrait into a short motion clip."
    assert data["payload"]["description"] == "Turns a single portrait into a short motion clip."


def test_description_map_can_enrich_by_template_id_path_or_filename(tmp_path) -> None:
    description_map = tmp_path / "descriptions.json"
    description_map.write_text(
        json.dumps(
            {
                "image/by-id": "Matched by id.",
                "ready_templates/video/by-path.py": "Matched by path.",
                "by-filename.py": "Matched by filename.",
            }
        ),
        encoding="utf-8",
    )
    args = upload.build_parser().parse_args(
        [
            "--dry-run",
            "--description-map",
            str(description_map),
        ]
    )

    descriptions = upload._read_description_args(args, root=tmp_path)

    assert upload._apply_description(
        {"id": "image/by-id", "path": "ready_templates/image/by-id.py"},
        descriptions,
    )["description"] == "Matched by id."
    assert upload._apply_description(
        {"id": "video/other", "path": "ready_templates/video/by-path.py"},
        descriptions,
    )["description"] == "Matched by path."
    assert upload._apply_description(
        {"id": "audio/other", "path": "ready_templates/audio/by-filename.py"},
        descriptions,
    )["description"] == "Matched by filename."


def test_inline_description_applies_as_batch_default() -> None:
    args = upload.build_parser().parse_args(
        [
            "--dry-run",
            "--description",
            "  Useful because it combines depth conditioning with a stylized LoRA. ",
        ]
    )

    descriptions = upload._read_description_args(args, root=upload._repo_root())
    row = upload._apply_description(
        {"id": "image/depth-style", "path": "ready_templates/image/depth_style.py"},
        descriptions,
    )

    assert row["description"] == "Useful because it combines depth conditioning with a stylized LoRA."


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_verify_recorded_checks_description_body_metadata_and_payload(monkeypatch) -> None:
    row = {
        "id": "video/example",
        "path": "ready_templates/video/example.py",
        "media": "video",
        "description": "Special because it combines camera control with image-to-video.",
    }
    envelope = upload._envelope(row, "def build():\n    pass\n")

    def fake_urlopen(request: object, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(
            [
                {
                    "id": 123,
                    "kind": "workflow",
                    "source": "vibecomfy",
                    "external_id": "vibecomfy:ready_template:video/example",
                    "title": "video/example",
                    "body": envelope["data"]["body"],
                    "metadata": envelope["data"]["metadata"],
                    "payload": envelope["data"]["payload"],
                }
            ]
        )

    monkeypatch.setattr(upload.urllib.request, "urlopen", fake_urlopen)

    result = upload._verify_recorded(
        envelope,
        api_url="https://example.test/rest/v1",
        anon_key="anon",
    )

    assert result["ok"] is True
    assert result["checks"] == {
        "kind": True,
        "source": True,
        "external_id": True,
        "title": True,
        "metadata_description": True,
        "payload_description": True,
        "body_description": True,
    }
