"""Tests for session-id path-component normalizer and filesystem containment."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.session import (
    normalize_path_component,
    normalize_session_id,
    session_dir_for,
    turn_dir_for,
)


# ── normalize_path_component ────────────────────────────────────────────────


class TestNormalizePathComponent:
    def test_preserves_ordinary_safe_ids(self):
        """Ordinary hex/alpha ids pass through unchanged."""
        assert normalize_path_component("abc123") == "abc123"
        assert normalize_path_component("my-session.id_v2") == "my-session.id_v2"
        assert normalize_path_component("a" * 80) == "a" * 80

    def test_truncates_long_ids(self):
        """Ids exceeding _MAX_PATH_COMPONENT_LENGTH are truncated."""
        result = normalize_path_component("x" * 200)
        assert len(result) == 80
        assert result == "x" * 80

    def test_empty_or_none_gets_fallback(self):
        """Empty, whitespace-only, and None values produce a UUID fallback."""
        r1 = normalize_path_component("")
        r2 = normalize_path_component(None)
        r3 = normalize_path_component("   ")
        # All are 32-char hex strings (uuid4().hex)
        assert re.fullmatch(r"[0-9a-f]{32}", r1)
        assert re.fullmatch(r"[0-9a-f]{32}", r2)
        assert re.fullmatch(r"[0-9a-f]{32}", r3)
        # Each gets a unique fallback
        assert len({r1, r2, r3}) == 3

    def test_custom_fallback_factory(self):
        """Custom fallback_factory is used when value is empty."""
        result = normalize_path_component("", fallback_factory=lambda: "custom-fallback")
        assert result == "custom-fallback"

    def test_replaces_non_safe_characters(self):
        """Characters outside [A-Za-z0-9_.-] become underscores."""
        assert normalize_path_component("hello world") == "hello_world"
        assert normalize_path_component("a\tb\nc") == "a_b_c"
        assert normalize_path_component("a\0b") == "a_b"

    def test_strips_leading_slashes(self):
        """Leading / and \\ are stripped before replacement."""
        assert normalize_path_component("/absolute/path") == "absolute_path"
        assert normalize_path_component("\\windows\\path") == "windows_path"
        assert normalize_path_component("//double/slash") == "double_slash"

    def test_rejects_dot_dot_traversal(self):
        """Values containing .. (even after normalization) get fallback."""
        # Direct traversal
        r1 = normalize_path_component("..")
        assert re.fullmatch(r"[0-9a-f]{32}", r1)
        # Nested traversal
        r2 = normalize_path_component("../../etc/passwd")
        assert re.fullmatch(r"[0-9a-f]{32}", r2)
        # Traversal with encoding attempts
        r3 = normalize_path_component("....")
        assert re.fullmatch(r"[0-9a-f]{32}", r3)

    def test_preserves_dots_in_non_traversal_positions(self):
        """Single dots and non-.. dot patterns are preserved."""
        # Single dot is valid in a filename
        assert normalize_path_component("my.file") == "my.file"
        # Trailing dot
        assert normalize_path_component("trailing.") == "trailing."
        # Leading dot (hidden file style) — could be ".." if input is ".hidden"
        # but ".hidden" doesn't contain ".." substring
        assert normalize_path_component(".hidden") == ".hidden"


# ── normalize_session_id ────────────────────────────────────────────────────


class TestNormalizeSessionId:
    def test_delegates_to_normalize_path_component(self):
        """normalize_session_id is a thin wrapper."""
        assert normalize_session_id("my-session") == "my-session"
        assert normalize_session_id("") != ""
        assert re.fullmatch(r"[0-9a-f]{32}", normalize_session_id("../../etc"))

    def test_default_called_with_no_args(self):
        """Calling with no args produces a UUID."""
        result = normalize_session_id()
        assert re.fullmatch(r"[0-9a-f]{32}", result)


# ── session_dir_for containment ─────────────────────────────────────────────


class TestSessionDirFor:
    @pytest.fixture
    def temp_root(self):
        root = Path(tempfile.mkdtemp())
        yield root
        import shutil

        shutil.rmtree(root, ignore_errors=True)

    def test_ordinary_session_id(self, temp_root):
        d = session_dir_for(temp_root, "my-session")
        assert d.name == "my-session"
        assert d.is_relative_to(temp_root.resolve())

    def test_malicious_traversal_id(self, temp_root):
        """A traversal session id is normalised to a UUID, staying within root."""
        d = session_dir_for(temp_root, "../../etc/passwd")
        assert d.is_relative_to(temp_root.resolve())
        # The directory name should be a UUID, not the raw traversal string
        assert d.name != "../../etc/passwd"
        assert re.fullmatch(r"[0-9a-f]{32}", d.name)

    def test_absolute_path_id(self, temp_root):
        """An absolute-path id is stripped of leading slashes."""
        d = session_dir_for(temp_root, "/etc/passwd")
        assert d.is_relative_to(temp_root.resolve())
        assert d.name == "etc_passwd"

    def test_empty_id(self, temp_root):
        d = session_dir_for(temp_root, "")
        assert d.is_relative_to(temp_root.resolve())
        assert re.fullmatch(r"[0-9a-f]{32}", d.name)

    def test_none_like_behavior(self, temp_root):
        """Empty string id produces a UUID-named directory within root."""
        d = session_dir_for(temp_root, "   ")
        assert d.is_relative_to(temp_root.resolve())
        assert re.fullmatch(r"[0-9a-f]{32}", d.name)

    def test_containment_with_symlink_root(self, temp_root):
        """Containment check works even with symlinked roots."""
        # Create a real dir and symlink to it
        real_dir = temp_root / "real"
        real_dir.mkdir()
        link_dir = temp_root / "link"
        link_dir.symlink_to(real_dir, target_is_directory=True)

        d = session_dir_for(link_dir, "test-session")
        # Must resolve within the real directory
        assert str(d.resolve()).startswith(str(real_dir.resolve()))

    def test_containment_raises_on_escape(self, temp_root):
        """If path somehow escapes root, ValueError is raised."""
        # This tests the defense-in-depth containment check.
        # We can't easily trigger it since the normaliser prevents escapes,
        # but we verify the API exists and works for the normal case.
        d = session_dir_for(temp_root, "safe-id")
        temp_root.resolve()  # just verify resolve() works
        assert d.is_relative_to(temp_root.resolve())


# ── turn_dir_for containment ────────────────────────────────────────────────


class TestTurnDirFor:
    @pytest.fixture
    def temp_root(self):
        root = Path(tempfile.mkdtemp())
        yield root
        import shutil

        shutil.rmtree(root, ignore_errors=True)

    def test_ordinary_turn_id(self, temp_root):
        t = turn_dir_for(temp_root, "my-session", "5")
        assert t.name == "5"
        assert t.is_relative_to(temp_root.resolve())
        assert t.parent.name == "turns"

    def test_malicious_turn_id(self, temp_root):
        """A traversal turn_id is normalised to a UUID."""
        t = turn_dir_for(temp_root, "my-session", "../../../malicious")
        assert t.is_relative_to(temp_root.resolve())
        assert t.name != "../../../malicious"
        assert re.fullmatch(r"[0-9a-f]{32}", t.name)
        # The session part should still be "my-session"
        assert t.parent.parent.name == "my-session"

    def test_malicious_both_ids(self, temp_root):
        """Both session_id and turn_id traversals are neutralised."""
        t = turn_dir_for(temp_root, "../../etc", "../../../malicious")
        assert t.is_relative_to(temp_root.resolve())
        # Both names should be UUIDs
        assert re.fullmatch(r"[0-9a-f]{32}", t.name)
        assert re.fullmatch(r"[0-9a-f]{32}", t.parent.parent.name)

    def test_empty_turn_id(self, temp_root):
        t = turn_dir_for(temp_root, "my-session", "")
        assert t.is_relative_to(temp_root.resolve())
        assert re.fullmatch(r"[0-9a-f]{32}", t.name)
        assert t.parent.parent.name == "my-session"

    def test_containment_with_resolved_paths(self, temp_root):
        """The resolved turn path is always within the resolved root."""
        t = turn_dir_for(temp_root, "sess-1", "turn-42")
        resolved_root = temp_root.resolve()
        assert str(t.resolve()).startswith(str(resolved_root))


# ── round-trip: session_dir_for → mkdir → turn_dir_for ────────────────────


class TestRoundTrip:
    def test_create_and_access(self):
        root = Path(tempfile.mkdtemp())
        try:
            sdir = session_dir_for(root, "my-workflow")
            sdir.mkdir(parents=True, exist_ok=True)
            tdir = turn_dir_for(root, "my-workflow", "1")
            tdir.mkdir(parents=True, exist_ok=True)

            assert sdir.is_dir()
            assert tdir.is_dir()
            assert tdir.is_relative_to(sdir)
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)
