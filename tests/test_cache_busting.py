"""Focused tests for the cache-busting build helper and WEB_DIRECTORY resolver.

Proves:
- The build helper creates a physical web_dist/<hash>/ copy with extracted modules.
- The dist matching current web/ content is selected by WEB_DIRECTORY.
- Fallback to './web' works when no valid dist exists.
- Arbitrary older dists are never selected.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "vibecomfy" / "comfy_nodes" / "web"
WEB_DIST = ROOT / "vibecomfy" / "comfy_nodes" / "web_dist"
BUILD_SCRIPT = ROOT / "scripts" / "build_web_cache_bust.sh"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _src_module_names() -> set[str]:
    """Return the set of distributable source file names (no .bak, ~, .orig, .tmp)."""
    names: set[str] = set()
    for f in WEB_SRC.iterdir():
        if not f.is_file():
            continue
        if f.name.endswith((".bak", "~", ".orig", ".tmp")):
            continue
        names.add(f.name)
    return names


def _source_hash() -> str:
    digest = hashlib.sha256()
    for f in sorted(p for p in WEB_SRC.iterdir() if p.is_file()):
        if f.name.endswith((".bak", "~", ".orig", ".tmp")):
            continue
        digest.update(f.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _run_python_expr(expr: str, *, env: dict[str, str] | None = None) -> str:
    """Run a Python expression in a subprocess and return stdout (stripped)."""
    cmd = [sys.executable, "-c", expr]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**os.environ, **(env or {})},
    )
    assert result.returncode == 0, (
        f"Python expr failed (rc={result.returncode}):\n"
        f"  stderr: {result.stderr}\n"
        f"  stdout: {result.stdout}"
    )
    return result.stdout.strip()


def _get_web_directory(*, env: dict[str, str] | None = None) -> str:
    """Import vibecomfy.comfy_nodes in a subprocess and return WEB_DIRECTORY."""
    return _run_python_expr(
        "import vibecomfy.comfy_nodes as m; print(m.WEB_DIRECTORY)",
        env=env,
    )


# ---------------------------------------------------------------------------
# cache-busting helper tests
# ---------------------------------------------------------------------------


class TestBuildHelper:
    """Tests for scripts/build_web_cache_bust.sh."""

    def test_creates_dist_copy(self):
        """The helper creates web_dist/<tag>/ with all ESM modules."""
        tag = "test-cb-creates-copy"
        dest = WEB_DIST / tag
        if dest.exists():
            shutil.rmtree(dest)

        try:
            result = subprocess.run(
                ["bash", str(BUILD_SCRIPT), "--dir", tag],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            assert result.returncode == 0, (
                f"Build script failed (rc={result.returncode}):\n{result.stderr}"
            )
            assert dest.is_dir(), f"Expected {dest} to be a directory"

            expected = _src_module_names()
            actual = {f.name for f in dest.iterdir() if f.is_file()}

            missing = expected - actual
            extra = actual - expected
            assert not missing, f"Missing files in dist: {missing}"
            assert not extra, f"Extra files in dist: {extra}"

            # Spot-check key extracted modules
            for name in (
                "agent_status_poller.js",
                "diagnostics_reporting.js",
                "vibecomfy_roundtrip.js",
                "agent_turn_feed.js",
                "executor_progress.js",
            ):
                assert (dest / name).is_file(), f"{name} missing from dist copy"

        finally:
            if dest.exists():
                shutil.rmtree(dest)

    def test_refuses_overwrite(self):
        """The helper exits non-zero when the destination already exists."""
        tag = "test-cb-refuse-overwrite"
        dest = WEB_DIST / tag
        if dest.exists():
            shutil.rmtree(dest)

        try:
            # First build — should succeed
            r1 = subprocess.run(
                ["bash", str(BUILD_SCRIPT), "--dir", tag],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            assert r1.returncode == 0, f"First build failed: {r1.stderr}"
            assert dest.is_dir()

            # Second build — should refuse
            r2 = subprocess.run(
                ["bash", str(BUILD_SCRIPT), "--dir", tag],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            assert r2.returncode != 0, (
                "Second build should refuse to overwrite, "
                f"but exited {r2.returncode}"
            )
        finally:
            if dest.exists():
                shutil.rmtree(dest)

    def test_force_overwrites_destination(self):
        """The helper can deliberately replace an existing destination."""
        tag = "test-cb-force-overwrite"
        dest = WEB_DIST / tag
        if dest.exists():
            shutil.rmtree(dest)

        try:
            r1 = subprocess.run(
                ["bash", str(BUILD_SCRIPT), "--dir", tag],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            assert r1.returncode == 0, f"First build failed: {r1.stderr}"
            stale = dest / "stale.js"
            stale.write_text("// stale")

            r2 = subprocess.run(
                ["bash", str(BUILD_SCRIPT), "--dir", tag, "--force"],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            assert r2.returncode == 0, f"Force build failed: {r2.stderr}"
            assert not stale.exists(), "--force should replace the destination"
        finally:
            if dest.exists():
                shutil.rmtree(dest)

    def test_excludes_backup_files(self):
        """The helper excludes .bak files from the dist copy."""
        tag = "test-cb-excludes-bak"
        dest = WEB_DIST / tag
        if dest.exists():
            shutil.rmtree(dest)

        try:
            result = subprocess.run(
                ["bash", str(BUILD_SCRIPT), "--dir", tag],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            assert result.returncode == 0, f"Build failed: {result.stderr}"

            # No .bak files should appear
            bak_files = list(dest.glob("*.bak"))
            assert len(bak_files) == 0, f".bak files leaked into dist: {bak_files}"
        finally:
            if dest.exists():
                shutil.rmtree(dest)

    def test_content_hash_repeatable(self):
        """The --hash mode produces the same tag across runs (deterministic)."""
        tag_dest_pairs: list[tuple[str, Path]] = []
        try:
            for i in range(2):
                result = subprocess.run(
                    ["bash", str(BUILD_SCRIPT), "--hash", "--force"],
                    capture_output=True,
                    text=True,
                    cwd=str(ROOT),
                )
                assert result.returncode == 0, (
                    f"--hash build failed (run {i}): {result.stderr}"
                )
                tag_line = [
                    ln for ln in result.stdout.splitlines() if "Tag:" in ln
                ][0]
                tag = tag_line.split("Tag:")[1].strip()
                assert tag == _source_hash()
                assert len(tag) == 12, f"Expected 12-char hash tag, got {tag!r}"
                assert all(c in "0123456789abcdef" for c in tag), (
                    f"Tag is not hex: {tag!r}"
                )
                dest = WEB_DIST / tag
                assert dest.is_dir()
                tag_dest_pairs.append((tag, dest))

            # Both runs should produce the same tag
            assert tag_dest_pairs[0][0] == tag_dest_pairs[1][0], (
                "--hash should be deterministic across runs"
            )
        finally:
            current_hash = _source_hash()
            for _, d in tag_dest_pairs:
                if d.exists() and d.name != current_hash:
                    shutil.rmtree(d)

    def test_git_sha_produces_full_sha_tag(self):
        """The --sha mode produces a full 40-char Git SHA tag."""
        # Clean up the real sha dist so the build doesn't bail
        sha_result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        )
        if sha_result.returncode == 0:
            existing = WEB_DIST / sha_result.stdout.strip()
            if existing.exists():
                shutil.rmtree(existing)

        result = subprocess.run(
            ["bash", str(BUILD_SCRIPT), "--sha"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, f"--sha build failed: {result.stderr}"

        tag_line = [
            ln for ln in result.stdout.splitlines() if "Tag:" in ln
        ][0]
        tag = tag_line.split("Tag:")[1].strip()
        assert len(tag) == 40, f"Expected 40-char SHA, got {tag!r} (len={len(tag)})"
        assert all(c in "0123456789abcdef" for c in tag), (
            f"SHA tag is not hex: {tag!r}"
        )
        dest = WEB_DIST / tag
        try:
            assert dest.is_dir()
            # Rebuild the real dist after ourselves
        finally:
            pass  # leave it; other tests may need it


# ---------------------------------------------------------------------------
# WEB_DIRECTORY resolver tests
# ---------------------------------------------------------------------------


class TestWebDirectoryResolver:
    """Tests for the WEB_DIRECTORY dynamic resolution in __init__.py.

    Strategy: each test that needs an isolated web_dist temporarily renames the
    real one aside, runs its scenario in a clean subprocess, then restores.
    Tests that need the real dist in place just run without manipulation.
    """

    _SAVED_NAME = "web_dist_cb_saved"

    @staticmethod
    def _saved_path() -> Path:
        return WEB_DIST.with_name(TestWebDirectoryResolver._SAVED_NAME)

    @classmethod
    def _save_web_dist(cls):
        """Rename real web_dist aside so we control what's there."""
        saved = cls._saved_path()
        if saved.exists():
            shutil.rmtree(saved)
        if WEB_DIST.exists():
            shutil.move(str(WEB_DIST), str(saved))

    @classmethod
    def _restore_web_dist(cls):
        """Put the real web_dist back."""
        saved = cls._saved_path()
        if WEB_DIST.exists():
            shutil.rmtree(WEB_DIST)
        if saved.exists():
            shutil.move(str(saved), str(WEB_DIST))

    # ------------------------------------------------------------------

    def test_fallback_when_no_web_dist(self):
        """WEB_DIRECTORY falls back to './web' when web_dist/ is absent."""
        self._save_web_dist()
        try:
            val = _get_web_directory()
            assert val == "./web", (
                f"Expected './web' fallback when web_dist/ absent, got {val!r}"
            )
        finally:
            self._restore_web_dist()

    def test_fallback_when_web_dist_empty(self):
        """WEB_DIRECTORY falls back when web_dist/ has no valid subdirectories."""
        self._save_web_dist()
        try:
            WEB_DIST.mkdir(exist_ok=True)
            # Create a subdir with no files (invalid — skipped by resolver)
            empty_sub = WEB_DIST / "empty-sub"
            empty_sub.mkdir(exist_ok=True)

            val = _get_web_directory()
            assert val == "./web", (
                f"Expected './web' fallback for empty web_dist/, got {val!r}"
            )
        finally:
            if empty_sub.exists():
                shutil.rmtree(empty_sub)
            if WEB_DIST.exists():
                shutil.rmtree(WEB_DIST)
            self._restore_web_dist()

    def test_selects_matching_source_hash_before_newest_dist(self):
        """WEB_DIRECTORY prefers the dist matching the current source hash."""
        self._save_web_dist()
        WEB_DIST.mkdir(exist_ok=True)

        matching = WEB_DIST / _source_hash()
        newer = WEB_DIST / "test-newer-bbb"
        for d in (matching, newer):
            if d.exists():
                shutil.rmtree(d)

        try:
            matching.mkdir(parents=True, exist_ok=True)
            (matching / "placeholder.js").write_text("// matching")
            newer.mkdir(parents=True, exist_ok=True)
            (newer / "placeholder.js").write_text("// newer")

            os.utime(str(matching), (1000.0, 1000.0))
            os.utime(str(newer), (2000.0, 2000.0))

            val = _get_web_directory()
            assert val == f"./web_dist/{matching.name}", (
                f"Expected './web_dist/{matching.name}' (matching source hash), got {val!r}"
            )
        finally:
            for d in (matching, newer):
                if d.exists():
                    shutil.rmtree(d)
            if WEB_DIST.exists():
                shutil.rmtree(WEB_DIST)
            self._restore_web_dist()

    def test_falls_back_to_web_when_matching_source_hash_missing(self):
        """Older valid dists are ignored when none match the current source hash."""
        self._save_web_dist()
        WEB_DIST.mkdir(exist_ok=True)

        tags = ["test-a-first", "test-b-second", "test-c-third"]
        dirs: list[Path] = []
        for tag in tags:
            d = WEB_DIST / tag
            if d.exists():
                shutil.rmtree(d)
            dirs.append(d)

        try:
            for i, d in enumerate(dirs):
                d.mkdir(parents=True, exist_ok=True)
                (d / "stub.js").write_text(f"// tag {i}")
                os.utime(str(d), (1000.0 + i * 100, 1000.0 + i * 100))

            val = _get_web_directory()
            assert val == "./web", (
                f"Expected './web' when current source hash is missing, got {val!r}"
            )
        finally:
            for d in dirs:
                if d.exists():
                    shutil.rmtree(d)
            if WEB_DIST.exists():
                shutil.rmtree(WEB_DIST)
            self._restore_web_dist()

    def test_uses_real_matching_dist_when_present(self):
        """WEB_DIRECTORY resolves to the real dist matching current web/ content."""
        # The real web_dist should exist from the build script output.
        assert WEB_DIST.exists(), "Real web_dist/ must exist for this test"
        matching = WEB_DIST / _source_hash()
        assert matching.is_dir(), "web_dist/ must contain the current source hash"

        val = _get_web_directory()
        assert val == f"./web_dist/{matching.name}"
        # Verify the resolved path actually exists on disk
        resolved = WEB_DIST.parent / val.lstrip("./")
        assert resolved.is_dir(), (
            f"WEB_DIRECTORY {val!r} does not resolve to an existing directory"
        )
        for name in _src_module_names():
            assert (resolved / name).is_file(), f"{name} missing from resolved dist"
            assert (resolved / name).read_bytes() == (WEB_SRC / name).read_bytes(), (
                f"{name} differs between source and resolved dist"
            )
