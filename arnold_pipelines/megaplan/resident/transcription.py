"""OpenAI-compatible audio transcription for resident inbound messages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import io
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent_loop import (
    ResidentCredentialError,
    api_base_url,
    api_credential_env,
    openai_client_for_endpoint,
)
from .config import ResidentConfig

GROQ_TRANSCRIPTION_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_TRANSCRIPTION_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class AudioProviderSettings:
    provider: str
    model: str
    credential_env: str
    base_url: str | None


def resolve_audio_provider(config: ResidentConfig) -> AudioProviderSettings:
    """Resolve voice-only credentials and endpoint independently from resident chat."""

    provider = config.voice_transcription_provider
    if provider == "groq":
        credential_env = config.voice_transcription_api_key_env or "GROQ_API_KEY"
        base_url = config.voice_transcription_base_url or GROQ_TRANSCRIPTION_BASE_URL
    elif provider == "openai":
        credential_env = config.voice_transcription_api_key_env or "OPENAI_API_KEY"
        base_url = config.voice_transcription_base_url or OPENAI_TRANSCRIPTION_BASE_URL
    else:
        credential_env = config.voice_transcription_api_key_env or api_credential_env(config)
        base_url = config.voice_transcription_base_url or api_base_url(config)
    return AudioProviderSettings(
        provider=provider,
        model=config.voice_transcription_model,
        credential_env=credential_env,
        base_url=base_url,
    )


class AudioTranscriptionError(RuntimeError):
    """Raised when an accepted audio file cannot produce a usable transcript."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OpenAICompatibleAudioTranscriber:
    """Transcribe via a voice-specific OpenAI-compatible provider."""

    def __init__(self, config: ResidentConfig, *, client_override: Any | None = None) -> None:
        self.config = config
        self._client_override = client_override

    def safe_configuration(self) -> dict[str, Any]:
        """Return non-secret endpoint/credential diagnostics for operational logs."""

        settings = resolve_audio_provider(self.config)
        endpoint_host = urlparse(settings.base_url).hostname if settings.base_url else "api.openai.com"
        return {
            "provider": settings.provider,
            "model": settings.model,
            "endpoint_host": endpoint_host or "invalid",
            "credential_env": settings.credential_env,
            "credential_present": self._client_override is not None
            or bool(os.getenv(settings.credential_env)),
        }

    async def transcribe(self, *, data: bytes, filename: str, content_type: str) -> str:
        failure: AudioTranscriptionError | None = None
        try:
            upload_data, upload_filename, upload_content_type = await _normalize_discord_audio(
                data=data,
                filename=filename,
                content_type=content_type,
                max_bytes=self.config.voice_max_attachment_bytes,
                timeout_s=self.config.voice_transcription_timeout_s,
            )
            settings = resolve_audio_provider(self.config)
            client = self._client_override or openai_client_for_endpoint(
                credential_env=settings.credential_env,
                base_url=settings.base_url,
                timeout_s=self.config.voice_transcription_timeout_s,
            )
        except asyncio.CancelledError:
            raise
        except ResidentCredentialError as exc:
            failure = AudioTranscriptionError(
                "credential_missing",
                f"audio transcription credential is missing ({exc.env_name})",
            )
        except AudioTranscriptionError:
            raise
        except asyncio.TimeoutError:
            failure = AudioTranscriptionError(
                "normalization_timeout",
                "audio normalization timed out",
            )
        except Exception:
            failure = AudioTranscriptionError(
                "normalization_failed",
                "audio normalization failed",
            )
        if failure is not None:
            # Raise outside the provider exception handler so response bodies,
            # headers, and credential-bearing exception context cannot escape.
            raise failure

        failure = None
        try:
            response = await asyncio.wait_for(
                client.audio.transcriptions.create(
                    model=settings.model,
                    file=(upload_filename, upload_data, upload_content_type),
                    response_format="json",
                    timeout=self.config.voice_transcription_timeout_s,
                ),
                timeout=self.config.voice_transcription_timeout_s,
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            failure = AudioTranscriptionError(
                "request_timeout",
                "audio transcription request timed out",
            )
        except Exception:
            failure = AudioTranscriptionError(
                "request_failed",
                "audio transcription request failed",
            )
        if failure is not None:
            raise failure

        text = response if isinstance(response, str) else getattr(response, "text", None)
        transcript = str(text or "").strip()
        if not transcript:
            raise AudioTranscriptionError(
                "empty_transcript",
                "audio transcription returned no text",
            )
        return transcript


async def _normalize_discord_audio(
    *,
    data: bytes,
    filename: str,
    content_type: str,
    max_bytes: int,
    timeout_s: float,
) -> tuple[bytes, str, str]:
    """Remux Discord's Ogg/Opus voice container to API-supported WebM/Opus."""

    extension = Path(filename).suffix.lower()
    media_type = content_type.partition(";")[0].strip().lower()
    if extension not in {".ogg", ".opus"} and media_type not in {
        "audio/ogg",
        "application/ogg",
        "audio/opus",
    }:
        return data, filename, content_type
    remuxed = await asyncio.wait_for(
        asyncio.to_thread(_remux_ogg_opus_to_webm, data),
        timeout=timeout_s,
    )
    if not remuxed or len(remuxed) > max_bytes:
        raise AudioTranscriptionError(
            "normalized_audio_too_large",
            "normalized audio exceeds the configured size limit",
        )
    return remuxed, f"{Path(filename).stem or 'voice-message'}.webm", "audio/webm"


def _remux_ogg_opus_to_webm(data: bytes) -> bytes:
    try:
        import av
    except ImportError as exc:  # pragma: no cover - faster-whisper installs PyAV in production
        raise AudioTranscriptionError(
            "normalization_dependency_missing",
            "PyAV is required for Discord Ogg voice messages",
        ) from exc

    source_buffer = io.BytesIO(data)
    output_buffer = io.BytesIO()
    source = av.open(source_buffer, mode="r")
    destination = None
    try:
        audio_streams = tuple(source.streams.audio)
        if len(audio_streams) != 1 or audio_streams[0].codec_context.name != "opus":
            raise AudioTranscriptionError(
                "invalid_ogg_opus",
                "Discord Ogg attachment is not single-stream Opus audio",
            )
        source_stream = audio_streams[0]
        destination = av.open(output_buffer, mode="w", format="webm")
        destination_stream = destination.add_stream_from_template(source_stream)
        for packet in source.demux(source_stream):
            if packet.dts is None:
                continue
            packet.stream = destination_stream
            destination.mux(packet)
    except AudioTranscriptionError:
        raise
    except Exception as exc:
        raise AudioTranscriptionError(
            "normalization_failed",
            "could not normalize Discord Ogg audio",
        ) from exc
    finally:
        if destination is not None:
            destination.close()
        source.close()
    return output_buffer.getvalue()
