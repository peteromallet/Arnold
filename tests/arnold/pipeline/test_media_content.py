"""Tests for ``arnold.pipeline.media_content`` validators.

Covers valid references, malformed references, wrong ``content_type``,
negative and non-integer ``size_bytes``, optional fields, and a sentinel
proving that validators never read referenced blob bytes.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.content_validation import ContentValidatorRegistry
from arnold.pipeline.media_content import (
    register_media_content_validators,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_video_mp4(**overrides) -> dict:
    ref = {
        "content_type": "video/mp4",
        "uri": "file:///tmp/test.mp4",
        "digest": "abc123",
        "size_bytes": 1024,
        "name": "test-clip",
    }
    ref.update(overrides)
    return ref


def _valid_audio_wav(**overrides) -> dict:
    ref = {
        "content_type": "audio/wav",
        "uri": "file:///tmp/test.wav",
        "digest": "def456",
        "size_bytes": 2048,
        "name": "test-audio",
    }
    ref.update(overrides)
    return ref


def _valid_astrid_timeline(**overrides) -> dict:
    ref = {
        "content_type": "application/x-astrid-timeline",
        "uri": "file:///tmp/test.timeline",
        "digest": "ghi789",
        "size_bytes": 4096,
        "name": "test-timeline",
    }
    ref.update(overrides)
    return ref


@pytest.fixture
def registry() -> ContentValidatorRegistry:
    reg = ContentValidatorRegistry()
    register_media_content_validators(reg)
    return reg


# ---------------------------------------------------------------------------
# Valid references
# ---------------------------------------------------------------------------


class TestValidReferences:
    def test_valid_video_mp4_passes(self, registry: ContentValidatorRegistry) -> None:
        result = registry.validate("video/mp4", _valid_video_mp4())
        assert result.ok

    def test_valid_audio_wav_passes(self, registry: ContentValidatorRegistry) -> None:
        result = registry.validate("audio/wav", _valid_audio_wav())
        assert result.ok

    def test_valid_astrid_timeline_passes(self, registry: ContentValidatorRegistry) -> None:
        result = registry.validate(
            "application/x-astrid-timeline", _valid_astrid_timeline()
        )
        assert result.ok

    def test_minimal_valid_video_mp4_passes(self, registry: ContentValidatorRegistry) -> None:
        """Only content_type and uri are required — all others optional."""
        result = registry.validate(
            "video/mp4",
            {"content_type": "video/mp4", "uri": "file:///tmp/minimal.mp4"},
        )
        assert result.ok

    def test_minimal_valid_audio_wav_passes(self, registry: ContentValidatorRegistry) -> None:
        result = registry.validate(
            "audio/wav",
            {"content_type": "audio/wav", "uri": "file:///tmp/minimal.wav"},
        )
        assert result.ok

    def test_minimal_valid_astrid_timeline_passes(self, registry: ContentValidatorRegistry) -> None:
        result = registry.validate(
            "application/x-astrid-timeline",
            {"content_type": "application/x-astrid-timeline", "uri": "file:///tmp/minimal.timeline"},
        )
        assert result.ok


# ---------------------------------------------------------------------------
# Wrong content_type
# ---------------------------------------------------------------------------


class TestWrongContentType:
    @pytest.mark.parametrize(
        "expected_ct,actual_ct",
        [
            ("video/mp4", "audio/wav"),
            ("video/mp4", "text/markdown"),
            ("video/mp4", "application/x-astrid-timeline"),
            ("audio/wav", "video/mp4"),
            ("audio/wav", "text/markdown"),
            ("application/x-astrid-timeline", "video/mp4"),
            ("application/x-astrid-timeline", "audio/wav"),
        ],
    )
    def test_wrong_content_type_fails(
        self,
        registry: ContentValidatorRegistry,
        expected_ct: str,
        actual_ct: str,
    ) -> None:
        ref = {"content_type": actual_ct, "uri": "file:///tmp/test"}
        result = registry.validate(expected_ct, ref)
        assert not result.ok
        assert any(d.code == "invalid_content_type" for d in result.diagnostics)

    def test_missing_content_type_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = {"uri": "file:///tmp/test.mp4"}
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "invalid_content_type" for d in result.diagnostics)

    def test_missing_content_type_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = {"uri": "file:///tmp/test.wav"}
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "invalid_content_type" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Malformed references
# ---------------------------------------------------------------------------


class TestMalformedReferences:
    def test_missing_uri_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "video/mp4"}
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_missing_uri_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "audio/wav"}
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_missing_uri_fails_astrid(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "application/x-astrid-timeline"}
        result = registry.validate("application/x-astrid-timeline", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_empty_uri_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "video/mp4", "uri": ""}
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_empty_uri_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "audio/wav", "uri": ""}
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_non_string_uri_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "video/mp4", "uri": 42}
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_non_string_uri_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "audio/wav", "uri": None}
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "missing_uri" for d in result.diagnostics)

    def test_non_string_digest_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(digest=123)
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "invalid_digest" for d in result.diagnostics)

    def test_non_string_digest_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(digest=True)
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "invalid_digest" for d in result.diagnostics)

    def test_invalid_name_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(name=99)
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "invalid_name" for d in result.diagnostics)

    def test_invalid_name_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(name=[])
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "invalid_name" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Negative and non-integer size_bytes
# ---------------------------------------------------------------------------


class TestSizeBytes:
    def test_negative_size_bytes_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(size_bytes=-1)
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(
            d.code == "invalid_size_bytes" and "non-negative" in d.message
            for d in result.diagnostics
        )

    def test_negative_size_bytes_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(size_bytes=-100)
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(
            d.code == "invalid_size_bytes" and "non-negative" in d.message
            for d in result.diagnostics
        )

    def test_float_size_bytes_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(size_bytes=3.14)
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(
            d.code == "invalid_size_bytes" and "integer" in d.message
            for d in result.diagnostics
        )

    def test_float_size_bytes_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(size_bytes=2.5)
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(
            d.code == "invalid_size_bytes" and "integer" in d.message
            for d in result.diagnostics
        )

    def test_bool_size_bytes_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(size_bytes=True)
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "invalid_size_bytes" for d in result.diagnostics)

    def test_bool_size_bytes_fails_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(size_bytes=False)
        result = registry.validate("audio/wav", ref)
        assert not result.ok
        assert any(d.code == "invalid_size_bytes" for d in result.diagnostics)

    def test_string_size_bytes_fails_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(size_bytes="1024")
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "invalid_size_bytes" for d in result.diagnostics)

    def test_zero_size_bytes_passes_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(size_bytes=0)
        result = registry.validate("video/mp4", ref)
        assert result.ok

    def test_zero_size_bytes_passes_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(size_bytes=0)
        result = registry.validate("audio/wav", ref)
        assert result.ok

    def test_size_bytes_none_passes(self, registry: ContentValidatorRegistry) -> None:
        """size_bytes is optional — None should pass."""
        ref = _valid_video_mp4(size_bytes=None)
        result = registry.validate("video/mp4", ref)
        assert result.ok


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


class TestOptionalFields:
    def test_digest_none_passes_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(digest=None)
        result = registry.validate("video/mp4", ref)
        assert result.ok

    def test_digest_none_passes_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(digest=None)
        result = registry.validate("audio/wav", ref)
        assert result.ok

    def test_name_none_passes_video(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_video_mp4(name=None)
        result = registry.validate("video/mp4", ref)
        assert result.ok

    def test_name_none_passes_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = _valid_audio_wav(name=None)
        result = registry.validate("audio/wav", ref)
        assert result.ok

    def test_all_optionals_absent_passes_video(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "video/mp4", "uri": "file:///tmp/lean.mp4"}
        result = registry.validate("video/mp4", ref)
        assert result.ok

    def test_all_optionals_absent_passes_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = {"content_type": "audio/wav", "uri": "file:///tmp/lean.wav"}
        result = registry.validate("audio/wav", ref)
        assert result.ok

    def test_extra_unknown_field_passes_video(self, registry: ContentValidatorRegistry) -> None:
        """Extra fields are not rejected — validators only inspect known fields."""
        ref = {**_valid_video_mp4(), "extra_thing": "anything"}
        result = registry.validate("video/mp4", ref)
        assert result.ok

    def test_extra_unknown_field_passes_audio(self, registry: ContentValidatorRegistry) -> None:
        ref = {**_valid_audio_wav(), "extra_thing": "anything"}
        result = registry.validate("audio/wav", ref)
        assert result.ok


# ---------------------------------------------------------------------------
# Astrid timeline permissive behaviour
# ---------------------------------------------------------------------------


class TestAstridTimelinePermissive:
    def test_astrid_accepts_non_string_digest(self, registry: ContentValidatorRegistry) -> None:
        """Astrid timeline is permissive — non-string digest is fine."""
        ref = _valid_astrid_timeline(digest=42)
        result = registry.validate("application/x-astrid-timeline", ref)
        assert result.ok

    def test_astrid_accepts_negative_size_bytes(self, registry: ContentValidatorRegistry) -> None:
        """Astrid timeline is permissive — negative size_bytes is fine."""
        ref = _valid_astrid_timeline(size_bytes=-1)
        result = registry.validate("application/x-astrid-timeline", ref)
        assert result.ok

    def test_astrid_accepts_float_size_bytes(self, registry: ContentValidatorRegistry) -> None:
        """Astrid timeline is permissive — float size_bytes is fine."""
        ref = _valid_astrid_timeline(size_bytes=1.5)
        result = registry.validate("application/x-astrid-timeline", ref)
        assert result.ok

    def test_astrid_accepts_non_string_name(self, registry: ContentValidatorRegistry) -> None:
        """Astrid timeline is permissive — non-string name is fine."""
        ref = _valid_astrid_timeline(name=42)
        result = registry.validate("application/x-astrid-timeline", ref)
        assert result.ok

    def test_astrid_accepts_arbitrary_extra_fields(self, registry: ContentValidatorRegistry) -> None:
        """Astrid timeline is permissive — unknown fields are fine."""
        ref = {
            "content_type": "application/x-astrid-timeline",
            "uri": "file:///tmp/test.timeline",
            "custom_thing": object(),
            "another": ["list"],
        }
        result = registry.validate("application/x-astrid-timeline", ref)
        assert result.ok


# ---------------------------------------------------------------------------
# Sentinel: prove validators never read referenced blob bytes
# ---------------------------------------------------------------------------

SENTINEL_URI = "sentinel://should-never-be-opened-or-read/trap.mp4"


class TestNoBlobDereference:
    """Prove that media content validators never open, fetch, or read blob bytes.

    Every validator function is called with a URI that would fail if
    dereferenced — a non-existent scheme and path.  Because validators
    only inspect metadata shape (string type, non-empty), all of these
    must pass without attempting any I/O.
    """

    def test_video_validator_never_opens_sentinel_uri(
        self, registry: ContentValidatorRegistry
    ) -> None:
        ref = {
            "content_type": "video/mp4",
            "uri": SENTINEL_URI,
            "digest": "abc123",
            "size_bytes": 1024,
            "name": "sentinel-clip",
        }
        # Must pass — the URI is a non-empty string; no I/O is attempted.
        result = registry.validate("video/mp4", ref)
        assert result.ok

    def test_audio_validator_never_opens_sentinel_uri(
        self, registry: ContentValidatorRegistry
    ) -> None:
        ref = {
            "content_type": "audio/wav",
            "uri": SENTINEL_URI,
            "digest": "abc123",
            "size_bytes": 2048,
            "name": "sentinel-audio",
        }
        result = registry.validate("audio/wav", ref)
        assert result.ok

    def test_astrid_validator_never_opens_sentinel_uri(
        self, registry: ContentValidatorRegistry
    ) -> None:
        ref = {
            "content_type": "application/x-astrid-timeline",
            "uri": SENTINEL_URI,
        }
        result = registry.validate("application/x-astrid-timeline", ref)
        assert result.ok

    def test_sentinel_uri_with_bad_content_type_fails_but_no_io(
        self, registry: ContentValidatorRegistry
    ) -> None:
        """Even when content_type is wrong, no I/O is attempted."""
        ref = {
            "content_type": "image/png",  # wrong content_type
            "uri": SENTINEL_URI,
        }
        result = registry.validate("video/mp4", ref)
        assert not result.ok
        assert any(d.code == "invalid_content_type" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_registry_contains_all_three_builtins(
        self, registry: ContentValidatorRegistry
    ) -> None:
        assert "video/mp4" in registry
        assert "audio/wav" in registry
        assert "application/x-astrid-timeline" in registry

    def test_registry_names_includes_all_three(self, registry: ContentValidatorRegistry) -> None:
        names = set(registry.names())
        assert "video/mp4" in names
        assert "audio/wav" in names
        assert "application/x-astrid-timeline" in names

    def test_unregistered_content_type_uses_default(
        self, registry: ContentValidatorRegistry
    ) -> None:
        """Content types not registered pass via no-op default."""
        result = registry.validate("image/png", {"uri": "whatever"})
        assert result.ok
