from __future__ import annotations

import json

from agent_kit.ports import BlobRef, FileUpload, OpenAIImageResult, OpenAISecondOpinionResult
from agent_kit.tool_kit import ToolContext, registry
from tests.helpers import create_store, insert_epic
import agent_kit.tools.editorial  # noqa: F401
import agent_kit.tools.images  # noqa: F401
import agent_kit.tools.second_opinion  # noqa: F401


class FakeBlob:
    def __init__(self) -> None:
        self.puts = []
        self.content_by_key = {}

    def get(self, ref: BlobRef) -> bytes:
        return self.content_by_key.get(ref.key, b"")

    def put(self, epic_id: str, content: bytes, mime_type: str, *, idempotency_key=None) -> BlobRef:
        self.puts.append(
            {
                "epic_id": epic_id,
                "content": content,
                "mime_type": mime_type,
                "idempotency_key": idempotency_key,
            }
        )
        ref = BlobRef(
            epic_id=epic_id,
            key=f"images/{epic_id}/{idempotency_key}.png",
            mime_type=mime_type,
            size_bytes=len(content),
        )
        self.content_by_key[ref.key] = content
        return ref

    def exists(self, ref: BlobRef) -> bool:
        return False


class FakeOpenAIOps:
    def __init__(self, second_opinion_raw: str | None = None) -> None:
        self.image_calls = []
        self.second_opinion_calls = []
        self.second_opinion_raw = second_opinion_raw or "{}"

    def generate_image(self, *, prompt: str, quality: str, size: str, idempotency_key: str):
        self.image_calls.append(
            {
                "prompt": prompt,
                "quality": quality,
                "size": size,
                "idempotency_key": idempotency_key,
            }
        )
        return OpenAIImageResult(
            content=b"generated image bytes",
            mime_type="image/png",
            provider_request_id="openai_image_1",
            response_summary={"kind": "image"},
        )

    def request_second_opinion(self, *, payload, idempotency_key: str):
        self.second_opinion_calls.append(
            {"payload": payload, "idempotency_key": idempotency_key}
        )
        return OpenAISecondOpinionResult(
            raw_response=self.second_opinion_raw,
            provider_request_id="openai_second_1",
            response_summary={"kind": "second_opinion"},
        )


class FakePushTransport:
    def __init__(self) -> None:
        self.posts = []

    def post_message(self, channel_id, content, *, files=None):
        self.posts.append({"channel_id": channel_id, "content": content, "files": files})
        return {"id": "discord_image_1"}


def test_full_mocked_image_generation_render_and_send_audit_flow(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    conn.execute(
        "UPDATE epics SET body = ? WHERE id = ?",
        ("# Title\n\n![flow](image:img_data_flow)", "epic_1"),
    )
    conn.commit()
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    blob = FakeBlob()
    openai_ops = FakeOpenAIOps()
    transport = FakePushTransport()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        blob=blob,
        openai_ops=openai_ops,
        transport=transport,
        metadata={"channel_id": "channel_1"},
    )

    generated = registry.invoke(
        "generate_image",
        context,
        {
            "epic_id": "epic_1",
            "prompt": "draw the data flow",
            "reference_key": "img_data_flow",
            "caption": "Data flow",
        },
    ).result
    sent = registry.invoke(
        "send_image",
        context,
        {"image_id": generated["image_id"], "caption": "Data flow"},
    ).result
    rendered = registry.invoke(
        "render_epic",
        context,
        {"epic_id": "epic_1"},
    ).result

    image = store.load_image(generated["image_id"])
    assert image["source"] == "agent_generated"
    assert image["active"] == 1
    assert image["reference_key"] == "img_data_flow"
    assert blob.puts[0]["content"] == b"generated image bytes"
    assert openai_ops.image_calls[0]["quality"] == "medium"
    assert sent["message_row_id"]
    assert transport.posts == [
        {
            "channel_id": "channel_1",
            "content": "Data flow",
            "files": [
                FileUpload(
                    filename=image["storage_url"].rsplit("/", 1)[-1],
                    content=b"generated image bytes",
                    mime_type="image/png",
                    metadata={
                        "image_id": generated["image_id"],
                        "storage_url": image["storage_url"],
                        "media_type": "image/png",
                        "reference_key": "img_data_flow",
                        "filename": image["storage_url"].rsplit("/", 1)[-1],
                    },
                )
            ],
        }
    ]
    assert "![flow](" + image["storage_url"] + ")" in rendered["body"]
    assert rendered["raw_body"] == "# Title\n\n![flow](image:img_data_flow)"
    assert rendered["missing_image_references"] == []
    assert [row["tool_name"] for row in conn.execute("SELECT tool_name FROM tool_calls ORDER BY rowid")] == [
        "generate_image",
        "send_image",
        "render_epic",
    ]
    external = conn.execute(
        "SELECT provider, endpoint, status, provider_request_id FROM external_requests ORDER BY rowid"
    ).fetchall()
    assert [(row["provider"], row["status"]) for row in external] == [
        ("openai", "confirmed"),
        ("supabase_storage", "confirmed"),
        ("discord", "confirmed"),
    ]
    assert external[0]["provider_request_id"] == "openai_image_1"
    assert external[2]["provider_request_id"] == "discord_image_1"


def test_full_mocked_second_opinion_flow_with_checklist_confirmation(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    store.seed_checklist("epic_1", ["Define target users"])
    raw = json.dumps(
        {
            "score": 6,
            "summary": "Promising, but three handoff holes remain.",
            "verdict": "needs work",
            "strengths": ["Clear direction"],
            "holes": [
                {
                    "gap": "No rollout",
                    "why_it_matters": "PM cannot phase delivery",
                    "suggested_fix": "Add rollout milestones",
                    "severity": "high",
                },
                {
                    "gap": "No metrics",
                    "why_it_matters": "Success is ambiguous",
                    "suggested_fix": "Define success metrics",
                    "severity": "medium",
                },
                {
                    "gap": "No risk register",
                    "why_it_matters": "Reviewers cannot judge tradeoffs",
                    "suggested_fix": "Add risk mitigations",
                    "severity": "medium",
                },
            ],
        }
    )
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        openai_ops=FakeOpenAIOps(second_opinion_raw=raw),
    )

    opinion = registry.invoke(
        "request_second_opinion",
        context,
        {"epic_id": "epic_1", "focus_areas": ["PM handoff"]},
    ).result
    edit = registry.invoke(
        "edit_epic",
        context,
        {
            "epic_id": "epic_1",
            "change_summary": "Accept second-opinion checklist proposals",
            "changes": {
                "checklist": {
                    "add": opinion["proposed_checklist_items"],
                }
            },
        },
    ).result

    assert opinion["score"] == 6
    assert [item["content"] for item in opinion["proposed_checklist_items"]] == [
        "Add rollout milestones",
        "Define success metrics",
        "Add risk mitigations",
    ]
    assert len(edit["created_checklist_item_ids"]) == 3
    linked = store.list_second_opinions("epic_1")[0]
    assert linked["id"] == opinion["second_opinion_id"]
    assert linked["resulting_checklist_item_ids"] == edit["created_checklist_item_ids"]
    checklist_contents = [
        item["content"] for item in store.list_checklist_items("epic_1")
    ]
    assert checklist_contents[-3:] == [
        "Add rollout milestones",
        "Define success metrics",
        "Add risk mitigations",
    ]
    assert [row["tool_name"] for row in conn.execute("SELECT tool_name FROM tool_calls ORDER BY rowid")] == [
        "request_second_opinion",
        "edit_epic",
    ]
    external = conn.execute(
        "SELECT provider, endpoint, status, provider_request_id FROM external_requests ORDER BY rowid"
    ).fetchall()
    assert [(row["provider"], row["status"], row["provider_request_id"]) for row in external] == [
        ("openai", "confirmed", "openai_second_1")
    ]
