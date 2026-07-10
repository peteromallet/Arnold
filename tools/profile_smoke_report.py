from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecomfy.memory_profile import MemoryProfile


SCHEMA_VERSION = 1
ARTIFACT_KIND = "vibecomfy_profile_smoke"
REQUIRED_SMOKE_PROFILES = {1, 3}


def load_json_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        payload = stripped
    else:
        first_json = text.find("{")
        if first_json < 0:
            raise ValueError(f"{path} does not contain a JSON object")
        payload = text[first_json:]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_profile_smoke_report(
    *,
    profile: int,
    run_dir: Path,
    output: Path | None = None,
    command: str | None = None,
    template_id: str | None = None,
    gpu_label: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    parsed = _parse_required_smoke_profile(profile)
    metadata_path = run_dir / "metadata.json"
    watchdog_path = run_dir / "watchdog.json"
    metadata = load_json_file(metadata_path)
    watchdog = load_json_file(watchdog_path)

    metadata_profile = metadata.get("memory_profile")
    if metadata_profile != int(parsed):
        raise ValueError(
            f"{metadata_path} memory_profile must be {int(parsed)}, got {metadata_profile!r}"
        )

    wall_clock_seconds = _require_non_negative_number(
        watchdog.get("elapsed_seconds"), "watchdog.elapsed_seconds"
    )
    vram = _summarize_vram_samples(watchdog.get("vram_samples"))

    report = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "profile": int(parsed),
        "profile_label": parsed.label,
        "generated_at": generated_at or _utc_now(),
        "run_id": _require_string(metadata.get("run_id"), "metadata.run_id"),
        "run_dir": str(run_dir),
        "runtime": _require_string(metadata.get("runtime"), "metadata.runtime"),
        "workflow_id": _require_string(metadata.get("workflow_id"), "metadata.workflow_id"),
        "template_id": template_id,
        "command": command,
        "gpu_label": gpu_label,
        "wall_clock_seconds": wall_clock_seconds,
        "vram": vram,
        "watchdog": {
            "diagnosis": _require_string(watchdog.get("diagnosis"), "watchdog.diagnosis"),
            "diagnosis_reason": _require_string(
                watchdog.get("diagnosis_reason"), "watchdog.diagnosis_reason"
            ),
        },
    }
    validate_profile_smoke_report(report)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def validate_profile_smoke_report(data: dict[str, Any]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("artifact_kind") != ARTIFACT_KIND:
        raise ValueError(f"artifact_kind must be {ARTIFACT_KIND!r}")

    profile = _parse_required_smoke_profile(data.get("profile"))
    if data.get("profile_label") != profile.label:
        raise ValueError(f"profile_label must be {profile.label!r}")

    for key in ("generated_at", "run_id", "run_dir", "runtime", "workflow_id"):
        _require_string(data.get(key), key)

    _require_non_negative_number(data.get("wall_clock_seconds"), "wall_clock_seconds")

    vram = data.get("vram")
    if not isinstance(vram, dict):
        raise ValueError("vram must be an object")
    samples = _require_positive_int(vram.get("samples"), "vram.samples")
    min_free = _require_non_negative_int(vram.get("min_free_bytes"), "vram.min_free_bytes")
    total = _require_positive_int(vram.get("total_bytes"), "vram.total_bytes")
    if min_free > total:
        raise ValueError("vram.min_free_bytes must be <= vram.total_bytes")
    if samples < 1:
        raise ValueError("vram.samples must be positive")
    _require_string(vram.get("source"), "vram.source")

    watchdog = data.get("watchdog")
    if not isinstance(watchdog, dict):
        raise ValueError("watchdog must be an object")
    _require_string(watchdog.get("diagnosis"), "watchdog.diagnosis")
    _require_string(watchdog.get("diagnosis_reason"), "watchdog.diagnosis_reason")


def _parse_required_smoke_profile(value: object) -> MemoryProfile:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("profile smoke artifacts require integer profile 1 or 3")
    profile = MemoryProfile.parse(value)
    if int(profile) not in REQUIRED_SMOKE_PROFILES:
        raise ValueError("profile smoke artifacts are required for profiles 1 and 3")
    return profile


def _summarize_vram_samples(value: object) -> dict[str, Any]:
    if not isinstance(value, list):
        raise ValueError("watchdog.vram_samples must be a list")
    usable: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        free = item.get("vram_free_bytes")
        total = item.get("vram_total_bytes")
        if (
            isinstance(free, int)
            and not isinstance(free, bool)
            and free >= 0
            and isinstance(total, int)
            and not isinstance(total, bool)
            and total > 0
        ):
            usable.append((free, total))
    if not usable:
        raise ValueError("watchdog.vram_samples must include at least one numeric VRAM sample")
    return {
        "samples": len(usable),
        "min_free_bytes": min(free for free, _ in usable),
        "total_bytes": max(total for _, total in usable),
        "source": "watchdog.json",
    }


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_non_negative_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{label} must be a non-negative number")
    return float(value)


def _require_non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _require_positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a profile 1 or profile 3 VRAM/wall-clock smoke artifact."
    )
    parser.add_argument(
        "--profile",
        type=int,
        choices=sorted(REQUIRED_SMOKE_PROFILES),
        required=True,
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--command")
    parser.add_argument("--template-id")
    parser.add_argument("--gpu-label")
    args = parser.parse_args(argv)

    build_profile_smoke_report(
        profile=args.profile,
        run_dir=args.run_dir,
        output=args.output,
        command=args.command,
        template_id=args.template_id,
        gpu_label=args.gpu_label,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
