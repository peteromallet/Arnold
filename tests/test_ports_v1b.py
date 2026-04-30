from __future__ import annotations

from agent_kit.ports import Blob, PushTransport, Store, Transport


def test_store_protocol_has_sprint_1b_methods() -> None:
    for name in [
        "find_abandoned_turns",
        "find_pending_external_requests",
        "mark_orphaned",
        "find_unprocessed_messages",
        "load_messages",
        "update_message",
        "create_image",
        "load_image",
        "list_images",
        "update_image",
    ]:
        assert hasattr(Store, name)


def test_blob_and_push_transport_protocols_are_extended_separately() -> None:
    assert hasattr(Blob, "exists")
    for name in [
        "start",
        "stop",
        "post_message",
        "edit_message",
        "download_attachment",
        "fetch_recent_messages",
    ]:
        assert hasattr(PushTransport, name)

    assert {"receive", "send", "stream_event"} <= set(dir(Transport))
    assert not hasattr(Transport, "post_message")
