from __future__ import annotations

from agent_kit.loop import run_turn
from agent_kit.model import FakeModel, tool_request
from agent_kit.tool_kit import ToolContext, register_tool
from tests.helpers import create_store, insert_epic


@register_tool(
    "return_image_for_loop_test",
    schema={"type": "object"},
    operation_kind="read",
)
def return_image_for_loop_test(context: ToolContext) -> dict:
    return {
        "media_type": "image/png",
        "image_bytes_b64": "cG5n",
        "description": "small png",
    }


def test_tool_result_with_image_bytes_emits_vision_content_blocks(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    model = FakeModel(
        script=[
            {
                "tool_requests": [
                    tool_request("return_image_for_loop_test", {})
                ]
            },
            {"final_text": "done"},
        ]
    )

    envelope = run_turn(
        epic_id="epic_1",
        input="show image",
        store=store,
        model=model,
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    tool_result_message = model.calls[1]["messages"][-1]
    content = tool_result_message["content"]
    assert isinstance(content, list)
    assert content[0] == {
        "type": "text",
        "text": "Tool result from return_image_for_loop_test:",
    }
    assert content[1] == {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "cG5n",
        },
    }
    assert "image_bytes_b64" not in content[2]["text"]
    assert "small png" in content[2]["text"]
