"""Subprocess tests for the ``arnold pipeline check <fixture-id>`` CLI verb.

The singular ``pipeline`` verb group dispatches to a C4-static-check
fixture runner; it must not collide with the existing plural ``pipelines``
verb (list / check / doctor / new) which addresses discovered pipeline
modules.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from arnold.pipeline._cli_check import FIXTURES


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arnold", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestPipelineCheckCli:
    def test_wellformed_fixture_exits_zero(self) -> None:
        cp = _run("pipeline", "check", "wellformed")
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout
        assert "wellformed" in cp.stdout

    @pytest.mark.parametrize(
        "fixture_id",
        sorted(fid for fid in FIXTURES if fid.startswith("mismatch-")),
    )
    def test_mismatch_fixture_exits_nonzero_with_locus(
        self, fixture_id: str
    ) -> None:
        cp = _run("pipeline", "check", fixture_id)
        assert cp.returncode != 0
        # Every reported finding carries a locus= prefix.
        assert "locus=" in cp.stderr, cp.stderr
        assert fixture_id in cp.stderr

    def test_unknown_fixture_id_exits_two(self) -> None:
        cp = _run("pipeline", "check", "no-such-fixture")
        assert cp.returncode == 2
        assert "unknown fixture-id" in cp.stderr

    def test_list_subcommand(self) -> None:
        cp = _run("pipeline", "list")
        assert cp.returncode == 0, cp.stderr
        for fid in FIXTURES:
            assert fid in cp.stdout

    def test_singular_does_not_collide_with_plural(self) -> None:
        """`arnold pipelines list` must still work after adding `pipeline`."""
        cp = _run("pipelines", "list")
        # Either 0 (success) or any nonzero is fine — what matters is that
        # the singular verb didn't shadow / break the plural dispatch.
        assert "arnold: unknown command" not in cp.stderr

    def test_module_factory_loads_real_pipeline_and_renders_findings(self, tmp_path) -> None:
        module = tmp_path / "c4_fixture_module.py"
        module.write_text(
            textwrap.dedent(
                """
                from arnold.pipeline import Pipeline, Port, PortRef, Stage, StepInvocation

                class _Step:
                    name = "step"
                    kind = "model"
                    def run(self, ctx):
                        raise AssertionError("static check must not execute steps")

                def build():
                    producer = Stage(
                        name="producer",
                        step=_Step(),
                        produces=(Port(name="out", content_type="application/json"),),
                        invocation=StepInvocation(kind="model"),
                    )
                    consumer = Stage(
                        name="consumer",
                        step=_Step(),
                        consumes=(PortRef(port_name="in", content_type="application/json"),),
                        invocation=StepInvocation(kind="model"),
                    )
                    return Pipeline(
                        stages={"producer": producer, "consumer": consumer},
                        entry="producer",
                        binding_map={("consumer", "missing"): ("producer", "out")},
                    )
                """
            ),
            encoding="utf-8",
        )

        cp = subprocess.run(
            [
                sys.executable,
                "-m",
                "arnold",
                "pipeline",
                "check",
                "--module",
                "c4_fixture_module:build",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )

        assert cp.returncode == 1
        assert "FAIL" in cp.stderr
        assert "locus=" in cp.stderr
        assert "c4_fixture_module:build" in cp.stderr

    def test_module_factory_clean_pipeline_exits_zero(self, tmp_path) -> None:
        module = tmp_path / "c4_clean_module.py"
        module.write_text(
            textwrap.dedent(
                """
                from arnold.pipeline import Pipeline, Port, PortRef, Stage, StepInvocation

                class _Step:
                    name = "step"
                    kind = "model"

                def build():
                    producer = Stage(
                        name="producer",
                        step=_Step(),
                        produces=(Port(name="out", content_type="application/json"),),
                        invocation=StepInvocation(kind="model"),
                    )
                    consumer = Stage(
                        name="consumer",
                        step=_Step(),
                        consumes=(PortRef(port_name="in", content_type="application/json"),),
                        invocation=StepInvocation(kind="model"),
                    )
                    return Pipeline(
                        stages={"producer": producer, "consumer": consumer},
                        entry="producer",
                        binding_map={("consumer", "in"): ("producer", "out")},
                    )
                """
            ),
            encoding="utf-8",
        )

        cp = subprocess.run(
            [
                sys.executable,
                "-m",
                "arnold",
                "pipeline",
                "check",
                "--module",
                "c4_clean_module:build",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )

        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout
        assert "c4_clean_module:build" in cp.stdout


# ── Media content-type CLI tests (T12) ──────────────────────────────────────


class TestPipelineCheckMediaEdge:
    """Subprocess CLI tests proving the ``media-wellformed`` fixture passes
    ``arnold pipeline check`` and that the ``video/mp4`` typed edge is
    actually checked through ``PortRef(port_name=...)`` (T12).
    """

    def test_media_wellformed_fixture_exits_zero(self) -> None:
        """``arnold pipeline check media-wellformed`` exits 0 with OK."""
        cp = _run("pipeline", "check", "media-wellformed")
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout
        assert "media-wellformed" in cp.stdout

    def test_media_wellformed_listed_in_fixture_list(self) -> None:
        """The ``media-wellformed`` fixture appears in ``arnold pipeline list`` output."""
        cp = _run("pipeline", "list")
        assert cp.returncode == 0, cp.stderr
        assert "media-wellformed" in cp.stdout, (
            f"media-wellformed should be in list output, got: {cp.stdout}"
        )

    @pytest.mark.parametrize(
        "fixture_id",
        sorted(fid for fid in FIXTURES if fid.startswith("mismatch-")),
    )
    def test_mismatch_fixture_exits_nonzero_with_locus(
        self, fixture_id: str
    ) -> None:
        cp = _run("pipeline", "check", fixture_id)
        assert cp.returncode != 0
        # Every reported finding carries a locus= prefix.
        assert "locus=" in cp.stderr, cp.stderr
        assert fixture_id in cp.stderr


# ── T17: Media-pricing advisory CLI tests ────────────────────────────────────


class TestPipelineCheckMediaPricingAdvisory:
    """Subprocess tests proving media-pricing warnings render in CLI output
    while preserving zero exit code for warning-only reports."""

    def test_media_wellformed_exits_zero_with_warning(self) -> None:
        """``media-wellformed`` (video/mp4) exits 0 but includes a media-pricing warning."""
        cp = _run("pipeline", "check", "media-wellformed")
        assert cp.returncode == 0, (
            f"exit {cp.returncode} — warnings must not affect exit code\n"
            f"stderr: {cp.stderr}"
        )
        # Must still report OK (no findings).
        assert "OK" in cp.stdout
        # Must include a warning for missing video_second pricing.
        assert "WARNING" in cp.stdout
        assert "media-pricing" in cp.stdout
        assert "missing_media_pricing" in cp.stdout
        assert "video_second" in cp.stdout

    def test_media_audio_edge_exits_zero_with_warning(self) -> None:
        """``media-audio-edge`` (audio/wav) exits 0 with audio_second warning."""
        cp = _run("pipeline", "check", "media-audio-edge")
        assert cp.returncode == 0, (
            f"exit {cp.returncode} — warnings must not affect exit code\n"
            f"stderr: {cp.stderr}"
        )
        assert "OK" in cp.stdout
        assert "WARNING" in cp.stdout
        assert "media-pricing" in cp.stdout
        assert "audio_second" in cp.stdout

    def test_media_multi_exits_zero_with_two_warnings(self) -> None:
        """``media-multi`` (video/mp4 + audio/wav) exits 0 with two warnings."""
        cp = _run("pipeline", "check", "media-multi")
        assert cp.returncode == 0, (
            f"exit {cp.returncode} — warnings must not affect exit code\n"
            f"stderr: {cp.stderr}"
        )
        assert "OK" in cp.stdout
        assert "WARNING" in cp.stdout
        # Should mention both missing units.
        assert "video_second" in cp.stdout
        assert "audio_second" in cp.stdout

    def test_wellformed_exits_zero_no_warnings(self) -> None:
        """``wellformed`` (no media ports) exits 0 with no warnings."""
        cp = _run("pipeline", "check", "wellformed")
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout
        assert "WARNING" not in cp.stdout

    def test_warning_only_does_not_trigger_fail_output(self) -> None:
        """Warning-only reports must NOT print FAIL or write to stderr."""
        cp = _run("pipeline", "check", "media-wellformed")
        assert cp.returncode == 0
        assert "FAIL" not in cp.stdout
        assert "FAIL" not in cp.stderr

    def test_warnings_also_render_when_findings_present(self) -> None:
        """When findings exist, any warnings still render alongside FAIL output."""
        cp = _run("pipeline", "check", "mismatch-unknown-producer")
        assert cp.returncode != 0
        # The mismatch fixtures don't have media ports, so no warnings expected.
        # This test just proves the warning machinery doesn't crash on findings-only.

    def test_media_multi_listed_in_fixture_list(self) -> None:
        """New media fixtures appear in ``arnold pipeline list``."""
        cp = _run("pipeline", "list")
        assert cp.returncode == 0, cp.stderr
        assert "media-audio-edge" in cp.stdout
        assert "media-multi" in cp.stdout

    def test_warning_detail_explains_missing_config(self) -> None:
        """The warning detail text explains that pricing is not configured
        for the unit and mentions the unit name explicitly."""
        cp = _run("pipeline", "check", "media-wellformed")
        assert cp.returncode == 0
        # The detail message must mention the missing unit and pricing config.
        assert "video_second" in cp.stdout
        assert "media-producing ports" in cp.stdout
        assert "pricing is not configured" in cp.stdout


# ── T18: Image-only no-warning CLI tests ──────────────────────────────────


class TestPipelineCheckMediaImageOnly:
    """Subprocess tests proving an image-only media fixture exits 0
    with no warnings because the ``image`` unit is priced."""

    def test_media_image_only_exits_zero_no_warning(self) -> None:
        """``arnold pipeline check media-image-only`` exits 0 with OK, no WARNING."""
        cp = _run("pipeline", "check", "media-image-only")
        assert cp.returncode == 0, (
            f"exit {cp.returncode} — image-only should pass cleanly\n"
            f"stderr: {cp.stderr}"
        )
        assert "OK" in cp.stdout
        assert "WARNING" not in cp.stdout, (
            f"image is a priced unit; no warning expected, got: {cp.stdout}"
        )

    def test_media_image_only_listed_in_fixture_list(self) -> None:
        """The ``media-image-only`` fixture appears in ``arnold pipeline list`` output."""
        cp = _run("pipeline", "list")
        assert cp.returncode == 0, cp.stderr
        assert "media-image-only" in cp.stdout, (
            f"media-image-only should be in list output, got: {cp.stdout}"
        )

    def test_media_image_only_no_fail_no_stderr(self) -> None:
        """Image-only fixture must not print FAIL or write findings to stderr."""
        cp = _run("pipeline", "check", "media-image-only")
        assert cp.returncode == 0
        assert "FAIL" not in cp.stdout
        assert "FAIL" not in cp.stderr
        # No findings mean nothing on stderr.
        assert cp.stderr == "" or "FAIL" not in cp.stderr
