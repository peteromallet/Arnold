from __future__ import annotations

import asyncio
import base64
import logging
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI

from arnold_pipelines.megaplan.resident.agent_loop import AgentResponse
from arnold_pipelines.megaplan.resident.auth import ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.discord import (
    VOICE_FAILURE_ENDPOINT,
    VOICE_FAILURE_TOO_LARGE,
    VOICE_FAILURE_UNSUPPORTED,
    ResidentDiscordService,
)
from arnold_pipelines.megaplan.resident.runtime import ResidentRuntime
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistry
from arnold_pipelines.megaplan.resident.transcription import (
    AudioTranscriptionError,
    GROQ_TRANSCRIPTION_BASE_URL,
    OpenAICompatibleAudioTranscriber,
    resolve_audio_provider,
)
from arnold_pipelines.megaplan.store import FileStore


def test_voice_transcript_is_the_exact_user_message_and_provenance_is_persisted(tmp_path) -> None:
    async def run_case() -> None:
        config = ResidentConfig(
            allowed_user_ids=("user-1",),
            burst_idle_delay_s=0,
            burst_max_delay_s=1,
        )
        store = FileStore(tmp_path / "store")
        authorizer = ResidentAuthorizer(config)
        runner = CapturingRunner()
        runtime = ResidentRuntime(
            config=config,
            authorizer=authorizer,
            store=store,
            profile=StubProfile(),
            runner=runner,
            outbound=CapturingOutbound(),
        )
        transcriber = FakeTranscriber("please inspect the current chain")
        downloader = FakeDownloader(b"fake-mp3-data")
        service = ResidentDiscordService(
            runtime=runtime,
            token="test-token",
            transcriber=transcriber,
            attachment_downloader=downloader,
        )
        message = make_message(
            content="attachment metadata must not become the prompt",
            attachment=FakeAttachment(
                attachment_id="attachment-9",
                filename="private-note.mp3",
                content_type="audio/mpeg",
                size=13,
            ),
        )

        await service.handle_message(message)
        await runtime.coalescer.flush_all()

        assert len(runner.requests) == 1
        assert runner.requests[0].messages[-1] == {
            "role": "user",
            "content": "please inspect the current chain",
        }
        assert "private-note.mp3" not in runner.requests[0].messages[-1]["content"]
        assert transcriber.calls[0]["data"] == b"fake-mp3-data"
        conversations = store.list_resident_conversations(transport="discord", limit=10)
        messages = store.list_conversation_messages(conversations[0].id, limit=10)
        inbound = next(row for row in messages if row.direction == "inbound")
        assert inbound.content == "please inspect the current chain"
        assert inbound.discord_message_id == "1001"
        assert inbound.was_voice_message is True
        assert inbound.audio_storage_url is None
        assert inbound.transcription_metadata == {
            "source": "discord_audio_attachment",
            "status": "completed",
            "discord_message_id": "1001",
            "discord_attachment_id": "attachment-9",
            "filename": "private-note.mp3",
            "content_type": "audio/mpeg",
            "declared_size_bytes": 13,
            "downloaded_size_bytes": 13,
            "model": "whisper-large-v3-turbo",
            "provider": "groq",
            "normalization": "none",
        }

    asyncio.run(run_case())


@pytest.mark.parametrize(
    ("attachment_kwargs", "expected_message"),
    [
        (
            {
                "attachment_id": "unsupported",
                "filename": "recording.flac",
                "content_type": "audio/flac",
                "size": 1024,
            },
            VOICE_FAILURE_UNSUPPORTED,
        ),
        (
            {
                "attachment_id": "oversized",
                "filename": "recording.mp3",
                "content_type": "audio/mpeg",
                "size": 21 * 1024 * 1024,
            },
            VOICE_FAILURE_TOO_LARGE,
        ),
    ],
)
def test_unsupported_and_oversized_audio_are_rejected_visibly(
    attachment_kwargs: dict[str, Any],
    expected_message: str,
) -> None:
    async def run_case() -> None:
        runtime = RuntimeStub(ResidentConfig())
        downloader = FakeDownloader(b"must-not-download")
        message = make_message(attachment=FakeAttachment(**attachment_kwargs))
        service = ResidentDiscordService(
            runtime=runtime,
            token="test-token",
            transcriber=FakeTranscriber("must not run"),
            attachment_downloader=downloader,
        )

        await service.handle_message(message)

        assert runtime.received == []
        assert downloader.calls == []
        assert message.channel.sent == [(expected_message, {"reference": "partial:1001", "mention_author": False})]

    asyncio.run(run_case())


def test_transcription_endpoint_failure_is_user_visible_and_not_sent_to_runtime() -> None:
    async def run_case() -> None:
        runtime = RuntimeStub(ResidentConfig())
        message = make_message(
            attachment=FakeAttachment(
                attachment_id="voice-1",
                filename="voice-message.ogg",
                content_type="audio/ogg; codecs=opus",
                size=180,
                voice=True,
            )
        )
        service = ResidentDiscordService(
            runtime=runtime,
            token="test-token",
            transcriber=FailingTranscriber(),
            attachment_downloader=FakeDownloader(b"ogg-data"),
        )

        await service.handle_message(message)

        assert runtime.received == []
        assert message.channel.sent == [
            (VOICE_FAILURE_ENDPOINT, {"reference": "partial:1001", "mention_author": False})
        ]

    asyncio.run(run_case())


def test_missing_audio_api_credential_is_classified_without_losing_reply_target(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def run_case() -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        config = ResidentConfig(model_provider="codex")
        runtime = RuntimeStub(config)
        message = make_message(
            attachment=FakeAttachment(
                attachment_id="voice-no-key",
                filename="voice-message.mp3",
                content_type="audio/mpeg",
                size=14,
                voice=True,
            )
        )
        service = ResidentDiscordService(
            runtime=runtime,
            token="test-token",
            attachment_downloader=FakeDownloader(b"synthetic-mp3"),
        )

        with caplog.at_level(logging.WARNING):
            await service.handle_message(message)

        assert runtime.received == []
        assert message.channel.sent == [
            (VOICE_FAILURE_ENDPOINT, {"reference": "partial:1001", "mention_author": False})
        ]
        diagnostic = next(
            record.message for record in caplog.records if "voice input rejected" in record.message
        )
        assert "message_id=1001" in diagnostic
        assert "attachment_id=voice-no-key" in diagnostic
        assert "code=transcription_credential_missing" in diagnostic
        assert "provider=groq" in diagnostic
        assert "model=whisper-large-v3-turbo" in diagnostic
        assert "endpoint_host=api.groq.com" in diagnostic
        assert "credential_env=GROQ_API_KEY" in diagnostic
        assert "credential_present=False" in diagnostic

    asyncio.run(run_case())


def test_transcriber_reports_missing_credential_after_ogg_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_case() -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        ogg = base64.b64decode(
            "T2dnUwACAAAAAAAAAACtrXrdAAAAAKIv7Y8BE09wdXNIZWFkAQE4AYC7AAAAAABPZ2dT"
            "AAAAAAAAAAAAAK2tet0BAAAA5dx3mAE2T3B1c1RhZ3MNAAAATGF2ZjYyLjEyLjEwMgEA"
            "AAAVAAAAZW5jb2Rlcj1MYXZ"
            "mNjIuMTIuMTAyT2dnUwAEMBUAAAAAAACtrXrdAgAAAO1XfYoGAwMDAwMD+P/++P/++P/++P/++P/++P/+"
        )
        transcriber = OpenAICompatibleAudioTranscriber(ResidentConfig(model_provider="codex"))

        with pytest.raises(AudioTranscriptionError) as exc_info:
            await transcriber.transcribe(
                data=ogg,
                filename="voice-message.ogg",
                content_type="audio/ogg",
            )

        assert exc_info.value.code == "credential_missing"
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert transcriber.safe_configuration() == {
            "provider": "groq",
            "model": "whisper-large-v3-turbo",
            "endpoint_host": "api.groq.com",
            "credential_env": "GROQ_API_KEY",
            "credential_present": False,
        }

    asyncio.run(run_case())


def test_normal_text_message_bypasses_download_and_transcription() -> None:
    async def run_case() -> None:
        runtime = RuntimeStub(ResidentConfig())
        downloader = FakeDownloader(b"unused")
        transcriber = FakeTranscriber("unused")
        service = ResidentDiscordService(
            runtime=runtime,
            token="test-token",
            transcriber=transcriber,
            attachment_downloader=downloader,
        )

        await service.handle_message(make_message(content="ordinary text"))

        assert len(runtime.received) == 1
        assert runtime.received[0].content == "ordinary text"
        assert runtime.received[0].raw["was_voice_message"] is False
        assert downloader.calls == []
        assert transcriber.calls == []

    asyncio.run(run_case())


def test_transcriber_uses_configured_model_and_remuxes_discord_ogg_to_webm() -> None:
    async def run_case() -> None:
        client = FakeOpenAIClient("transcribed voice")
        config = ResidentConfig(
            voice_transcription_model="whisper-large-v3",
            voice_max_attachment_bytes=1024 * 1024,
        )
        transcriber = OpenAICompatibleAudioTranscriber(config, client_override=client)
        ogg = base64.b64decode(
            "T2dnUwACAAAAAAAAAACtrXrdAAAAAKIv7Y8BE09wdXNIZWFkAQE4AYC7AAAAAABPZ2dT"
            "AAAAAAAAAAAAAK2tet0BAAAA5dx3mAE2T3B1c1RhZ3MNAAAATGF2ZjYyLjEyLjEwMgEA"
            "AAAVAAAAZW5jb2Rlcj1MYXZ"
            "mNjIuMTIuMTAyT2dnUwAEMBUAAAAAAACtrXrdAgAAAO1XfYoGAwMDAwMD+P/++P/++P/++P/++P/++P/+"
        )

        result = await transcriber.transcribe(
            data=ogg,
            filename="voice-message.ogg",
            content_type="audio/ogg",
        )

        assert result == "transcribed voice"
        call = client.audio.transcriptions.calls[0]
        assert call["model"] == "whisper-large-v3"
        assert call["file"][0] == "voice-message.webm"
        assert call["file"][1].startswith(b"\x1aE\xdf\xa3")
        assert call["file"][2] == "audio/webm"
        assert call["response_format"] == "json"
        assert call["timeout"] == 90.0

    asyncio.run(run_case())


def test_voice_configuration_environment_overrides() -> None:
    config = ResidentConfig.from_env(
        {
            "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_ENABLED": "false",
            "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_PROVIDER": "openai",
            "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_MODEL": "whisper-1",
            "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_API_KEY_ENV": "VOICE_KEY",
            "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_BASE_URL": "https://voice.example/v1",
            "MEGAPLAN_RESIDENT_VOICE_MAX_BYTES": "12345",
            "MEGAPLAN_RESIDENT_VOICE_DOWNLOAD_TIMEOUT_S": "4.5",
            "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_TIMEOUT_S": "30",
        }
    )

    assert config.voice_transcription_enabled is False
    assert config.voice_transcription_provider == "openai"
    assert config.voice_transcription_model == "whisper-1"
    assert config.voice_transcription_api_key_env == "VOICE_KEY"
    assert config.voice_transcription_base_url == "https://voice.example/v1"
    assert config.voice_max_attachment_bytes == 12345
    assert config.voice_download_timeout_s == 4.5
    assert config.voice_transcription_timeout_s == 30.0


def test_default_voice_provider_is_groq_and_is_decoupled_from_resident_chat() -> None:
    config = ResidentConfig(
        model_provider="codex",
        model_name="gpt-5.6-sol",
        model_api_key_env="CHAT_ONLY_KEY",
        model_base_url="https://chat.example/v1",
    )

    settings = resolve_audio_provider(config)

    assert settings.provider == "groq"
    assert settings.model == "whisper-large-v3-turbo"
    assert settings.credential_env == "GROQ_API_KEY"
    assert settings.base_url == GROQ_TRANSCRIPTION_BASE_URL


def test_transcriber_sends_multipart_audio_to_openai_compatible_endpoint() -> None:
    async def run_case() -> None:
        captured: dict[str, Any] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["content_type"] = request.headers["content-type"]
            captured["body"] = await request.aread()
            return httpx.Response(200, json={"text": "multipart transcript"})

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = AsyncOpenAI(
            api_key="unit-test-only",
            base_url=GROQ_TRANSCRIPTION_BASE_URL,
            http_client=http_client,
            max_retries=0,
        )
        try:
            result = await OpenAICompatibleAudioTranscriber(
                ResidentConfig(),
                client_override=client,
            ).transcribe(
                data=b"small-audio-payload",
                filename="note.mp3",
                content_type="audio/mpeg",
            )
        finally:
            await http_client.aclose()

        assert result == "multipart transcript"
        assert captured["content_type"].startswith("multipart/form-data; boundary=")
        body = captured["body"]
        assert b'name="file"; filename="note.mp3"' in body
        assert b"Content-Type: audio/mpeg" in body
        assert b"small-audio-payload" in body
        assert b'name="model"' in body
        assert b"whisper-large-v3-turbo" in body

    asyncio.run(run_case())


def test_transcription_timeout_is_stable_and_provider_details_are_redacted() -> None:
    async def run_case() -> None:
        timeout_client = SimpleNamespace(
            audio=SimpleNamespace(transcriptions=HangingTranscriptions())
        )
        with pytest.raises(AudioTranscriptionError) as timeout_info:
            await OpenAICompatibleAudioTranscriber(
                ResidentConfig(voice_transcription_timeout_s=0.01),
                client_override=timeout_client,
            ).transcribe(data=b"audio", filename="note.mp3", content_type="audio/mpeg")
        assert timeout_info.value.code == "request_timeout"

        failing_client = SimpleNamespace(
            audio=SimpleNamespace(transcriptions=LeakyProviderFailureTranscriptions())
        )
        with pytest.raises(AudioTranscriptionError) as failure_info:
            await OpenAICompatibleAudioTranscriber(
                ResidentConfig(),
                client_override=failing_client,
            ).transcribe(data=b"audio", filename="note.mp3", content_type="audio/mpeg")
        error = failure_info.value
        assert error.code == "request_failed"
        assert str(error) == "audio transcription request failed"
        assert error.__cause__ is None
        assert error.__context__ is None

    asyncio.run(run_case())


class FakeAttachment:
    def __init__(
        self,
        *,
        attachment_id: str,
        filename: str,
        content_type: str,
        size: int,
        voice: bool = False,
    ) -> None:
        self.id = attachment_id
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.url = f"https://cdn.discordapp.com/attachments/channel/message/{filename}"
        self._voice = voice

    def is_voice_message(self) -> bool:
        return self._voice


class FakeChannel:
    def __init__(self) -> None:
        self.id = "user-1"
        self.parent = None
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def get_partial_message(self, message_id: int) -> str:
        return f"partial:{message_id}"

    async def send(self, content: str, **kwargs: Any) -> SimpleNamespace:
        self.sent.append((content, kwargs))
        return SimpleNamespace(id=f"sent-{len(self.sent)}")


def make_message(*, content: str = "", attachment: FakeAttachment | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="1001",
        content=content,
        guild=None,
        channel=FakeChannel(),
        author=SimpleNamespace(id="user-1", bot=False),
        reference=None,
        flags=SimpleNamespace(voice=bool(attachment and attachment.is_voice_message())),
        attachments=[attachment] if attachment else [],
    )


class RuntimeStub:
    def __init__(self, config: ResidentConfig) -> None:
        self.config = config
        self.received: list[Any] = []

    async def receive(self, event: Any) -> None:
        self.received.append(event)


class FakeDownloader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.calls: list[dict[str, Any]] = []

    async def download(self, attachment: Any, *, max_bytes: int, timeout_s: float) -> bytes:
        self.calls.append({"attachment": attachment, "max_bytes": max_bytes, "timeout_s": timeout_s})
        return self.data


class FakeTranscriber:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.calls: list[dict[str, Any]] = []

    async def transcribe(self, *, data: bytes, filename: str, content_type: str) -> str:
        self.calls.append({"data": data, "filename": filename, "content_type": content_type})
        return self.transcript


class FailingTranscriber:
    async def transcribe(self, *, data: bytes, filename: str, content_type: str) -> str:
        raise RuntimeError("endpoint unavailable")


class CapturingRunner:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def run(self, request: Any, tools: Any) -> AgentResponse:
        self.requests.append(request)
        return AgentResponse(final_text="")


class CapturingOutbound:
    async def send(self, message: Any) -> None:
        raise AssertionError("an empty agent response must not emit outbound text")


class StubProfile:
    def __init__(self) -> None:
        self._tools = ToolRegistry()

    def system_prompt(self) -> str:
        return "test resident"

    async def load_hot_context(self, conversation_id: str) -> dict[str, Any]:
        return {}

    def tools(self) -> ToolRegistry:
        return self._tools


class FakeTranscriptions:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


class HangingTranscriptions:
    async def create(self, **_kwargs: Any) -> None:
        await asyncio.sleep(60)


class LeakyProviderFailureTranscriptions:
    async def create(self, **_kwargs: Any) -> None:
        raise RuntimeError(
            "Authorization: Bearer should-never-escape; provider body: private diagnostics"
        )


class FakeOpenAIClient:
    def __init__(self, text: str) -> None:
        self.audio = SimpleNamespace(transcriptions=FakeTranscriptions(text))
