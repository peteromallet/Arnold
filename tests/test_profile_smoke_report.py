from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.profile_smoke_report import (
    build_profile_smoke_report,
    load_json_file,
    main,
    validate_profile_smoke_report,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "profile_smokes"


@pytest.mark.parametrize("profile", [1, 3])
def test_committed_profile_smoke_fixtures_match_schema(profile: int) -> None:
    data = load_json_file(FIXTURE_DIR / f"profile-{profile}.json")

    validate_profile_smoke_report(data)

    assert data["profile"] == profile


@pytest.mark.parametrize(
    ("profile", "label"),
    [
        (1, "Low RAM"),
        (3, "Low VRAM"),
    ],
)
def test_build_profile_smoke_report_from_run_artifacts(
    tmp_path: Path,
    profile: int,
    label: str,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": f"profile-{profile}-run",
                "workflow_id": "video/wan_t2v",
                "runtime": "embedded",
                "memory_profile": profile,
                "memory_profile_label": label,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "watchdog.json").write_text(
        "WATCHDOG diagnosis=completed prompt_id=abc\n"
        + json.dumps(
            {
                "diagnosis": "completed",
                "diagnosis_reason": "prompt finished cleanly",
                "elapsed_seconds": 42.25,
                "vram_samples": [
                    {
                        "timestamp": 1.0,
                        "vram_free_bytes": 8 * 1024**3,
                        "vram_total_bytes": 24 * 1024**3,
                    },
                    {
                        "timestamp": 2.0,
                        "vram_free_bytes": 7 * 1024**3,
                        "vram_total_bytes": 24 * 1024**3,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / f"profile-{profile}.json"
    report = build_profile_smoke_report(
        profile=profile,
        run_dir=run_dir,
        output=output,
        command=f"vibecomfy run video/wan_t2v --ready --runtime embedded --memory-profile {profile}",
        template_id="video/wan_t2v",
        gpu_label="test-gpu",
        generated_at="2026-05-06T00:00:00Z",
    )

    assert output.exists()
    validate_profile_smoke_report(load_json_file(output))
    assert report["profile"] == profile
    assert report["profile_label"] == label
    assert report["wall_clock_seconds"] == 42.25
    assert report["vram"] == {
        "samples": 2,
        "min_free_bytes": 7 * 1024**3,
        "total_bytes": 24 * 1024**3,
        "source": "watchdog.json",
    }


def test_build_profile_smoke_report_rejects_profile_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": "profile-1-run",
                "workflow_id": "video/wan_t2v",
                "runtime": "embedded",
                "memory_profile": 3,
                "memory_profile_label": "Low VRAM",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "watchdog.json").write_text(
        json.dumps(
            {
                "diagnosis": "completed",
                "diagnosis_reason": "prompt finished cleanly",
                "elapsed_seconds": 42.25,
                "vram_samples": [
                    {
                        "timestamp": 1.0,
                        "vram_free_bytes": 8 * 1024**3,
                        "vram_total_bytes": 24 * 1024**3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="memory_profile must be 1"):
        build_profile_smoke_report(profile=1, run_dir=run_dir)


def test_profile_smoke_report_cli_writes_schema_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": "profile-1-run",
                "workflow_id": "video/wan_t2v",
                "runtime": "embedded",
                "memory_profile": 1,
                "memory_profile_label": "Low RAM",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "watchdog.json").write_text(
        json.dumps(
            {
                "diagnosis": "completed",
                "diagnosis_reason": "prompt finished cleanly",
                "elapsed_seconds": 10.0,
                "vram_samples": [
                    {
                        "timestamp": 1.0,
                        "vram_free_bytes": 8 * 1024**3,
                        "vram_total_bytes": 24 * 1024**3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "profile-1.json"

    rc = main(
        [
            "--profile",
            "1",
            "--run-dir",
            str(run_dir),
            "--output",
            str(output),
            "--template-id",
            "video/wan_t2v",
            "--command",
            "vibecomfy run video/wan_t2v --ready --runtime embedded --memory-profile 1",
            "--gpu-label",
            "test-gpu",
        ]
    )

    assert rc == 0
    validate_profile_smoke_report(load_json_file(output))


def test_profile_smoke_report_requires_numeric_vram_sample() -> None:
    data = load_json_file(FIXTURE_DIR / "profile-1.json")
    data["vram"] = {
        "samples": 0,
        "min_free_bytes": 0,
        "total_bytes": 24 * 1024**3,
        "source": "watchdog.json",
    }

    with pytest.raises(ValueError, match="vram.samples"):
        validate_profile_smoke_report(data)
