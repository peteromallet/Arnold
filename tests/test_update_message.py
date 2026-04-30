from __future__ import annotations

from tests.helpers import create_store, insert_epic


def test_update_message_partial_update_json_and_scalar_fields(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    message = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="",
        discord_message_id="discord_1",
        was_voice_message=True,
    )

    updated = store.update_message(
        message["id"],
        content="transcribed",
        audio_storage_url="audio/epic_1/a.ogg",
        transcription_metadata={"model": "whisper-large-v3", "duration": 1.2},
        has_image_attachment=True,
    )

    assert updated["content"] == "transcribed"
    assert updated["audio_storage_url"] == "audio/epic_1/a.ogg"
    assert updated["transcription_metadata"] == {
        "model": "whisper-large-v3",
        "duration": 1.2,
    }
    assert updated["has_image_attachment"] == 1
    assert store.load_message(message["id"]) == updated
