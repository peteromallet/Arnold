"""Tests for the DriverSpec.babysitter status-trigger policy field."""

from __future__ import annotations

import pathlib

import pytest

from arnold_pipelines.megaplan.cloud.spec import (
    BabysitterSpec,
    DriverSpec,
    babysitter_effective_mode,
    load_spec,
)
from arnold_pipelines.megaplan.types import CliError


def _write_cloud_yaml(tmp_path: pathlib.Path, extra: str = "") -> pathlib.Path:
    path = tmp_path / "cloud.yaml"
    path.write_text(
        "provider: ssh\n"
        "mode: chain\n"
        "repo:\n"
        "  url: https://github.com/o/r.git\n"
        "  workspace: /workspace/app\n"
        "agents: {default: codex}\n"
        "ssh:\n"
        "  host: box\n"
        "chain:\n"
        "  spec: /workspace/app/.megaplan/initiatives/demo/chain.yaml\n"
        + extra,
        encoding="utf-8",
    )
    return path


class TestBabysitterSpecDefaults:
    """Absent driver.babysitter defaults to the superfixer mode."""

    def test_no_driver_block_defaults_to_superfixer(self, tmp_path: pathlib.Path) -> None:
        spec = load_spec(_write_cloud_yaml(tmp_path))
        assert spec.driver is None
        assert babysitter_effective_mode(spec.driver) == "superfixer"

    def test_driver_block_without_babysitter_defaults_to_superfixer(
        self, tmp_path: pathlib.Path
    ) -> None:
        spec = load_spec(
            _write_cloud_yaml(tmp_path, "driver:\n  max_stall_iterations: 3\n")
        )
        assert spec.driver is not None
        assert spec.driver.max_stall_iterations == 3
        assert spec.driver.babysitter is None
        assert babysitter_effective_mode(spec.driver) == "superfixer"

    def test_empty_babysitter_mapping_defaults_mode(self, tmp_path: pathlib.Path) -> None:
        spec = load_spec(
            _write_cloud_yaml(tmp_path, "driver:\n  babysitter: {}\n")
        )
        assert spec.driver is not None
        assert spec.driver.babysitter == BabysitterSpec()
        assert spec.driver.babysitter.mode == "superfixer"
        assert spec.driver.babysitter.after is None
        assert babysitter_effective_mode(spec.driver) == "superfixer"


class TestBabysitterSpecParse:
    def test_mode_off(self, tmp_path: pathlib.Path) -> None:
        # PyYAML parses `mode: off` as boolean False; the loader must coerce it
        # to the documented "off" string.
        spec = load_spec(
            _write_cloud_yaml(tmp_path, "driver:\n  babysitter:\n    mode: off\n")
        )
        assert spec.driver is not None
        assert spec.driver.babysitter == BabysitterSpec(mode="off")
        assert babysitter_effective_mode(spec.driver) == "off"

    def test_mode_layered_rejected(self, tmp_path: pathlib.Path) -> None:
        # The layered repair stack was removed; the single-flash babysitter
        # (superfixer) is the ONLY repair flow.
        path = _write_cloud_yaml(
            tmp_path,
            "driver:\n  babysitter:\n    mode: layered\n    after: PT2H\n",
        )
        with pytest.raises(CliError, match="driver.babysitter.mode must be one of"):
            load_spec(path)

    def test_mode_superfixer_explicit(self, tmp_path: pathlib.Path) -> None:
        spec = load_spec(
            _write_cloud_yaml(
                tmp_path,
                "driver:\n  babysitter:\n    mode: superfixer\n    after: PT1H\n",
            )
        )
        assert spec.driver is not None
        assert spec.driver.babysitter == BabysitterSpec(mode="superfixer", after="PT1H")


class TestBabysitterSpecValidation:
    def test_invalid_mode_rejected(self, tmp_path: pathlib.Path) -> None:
        path = _write_cloud_yaml(
            tmp_path, "driver:\n  babysitter:\n    mode: bogus\n"
        )
        with pytest.raises(CliError, match="driver.babysitter.mode must be one of"):
            load_spec(path)

    def test_invalid_after_rejected(self, tmp_path: pathlib.Path) -> None:
        path = _write_cloud_yaml(
            tmp_path, "driver:\n  babysitter:\n    after: not-a-duration\n"
        )
        with pytest.raises(CliError, match="positive ISO-8601 duration"):
            load_spec(path)

    def test_zero_duration_rejected(self, tmp_path: pathlib.Path) -> None:
        path = _write_cloud_yaml(
            tmp_path, "driver:\n  babysitter:\n    after: PT0S\n"
        )
        with pytest.raises(CliError, match="positive ISO-8601 duration"):
            load_spec(path)

    def test_frozen_dataclass(self) -> None:
        with pytest.raises(Exception):
            BabysitterSpec(mode="off").mode = "superfixer"  # type: ignore[misc]
