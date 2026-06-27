"""Live agentic harness runner for VibeComfy headless scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapter import run_headless_scenario
from .guard import guard_output_dir


def _scenario_paths(scenarios_dir: Path) -> list[Path]:
    if not scenarios_dir.is_dir():
        return []
    return sorted(p for p in scenarios_dir.iterdir() if p.suffix in {".yaml", ".yml", ".json"})


def _load_scenario(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_tag(
    tag: str,
    *,
    scenarios_dir: Path | None = None,
    output_base: Path | str | None = None,
) -> dict[str, Any]:
    """Run every scenario under *scenarios_dir* for a given tag.

    Each scenario is dispatched through the headless service and the artifact
    directory is guarded.  The result is a JSON summary safe for CI or human
    review.
    """
    if scenarios_dir is None:
        scenarios_dir = Path(__file__).with_name("scenarios")

    summaries: list[dict[str, Any]] = []
    for scenario_path in _scenario_paths(scenarios_dir):
        scenario = _load_scenario(scenario_path)
        if not isinstance(scenario, dict):
            continue
        scenario.setdefault("id", scenario_path.stem)
        summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
        summary["guard"] = guard_output_dir(summary["output_dir"])
        summaries.append(summary)

    overall_success = all(s["guard"]["live_agentic_success"] for s in summaries)
    return {
        "tag": tag,
        "scenario_count": len(summaries),
        "overall_success": overall_success,
        "scenarios": summaries,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests.agentic_harness.runner")
    parser.add_argument("--tag", required=True, help="Run tag (used in evidence path).")
    parser.add_argument(
        "--scenarios-dir",
        default=None,
        help="Directory containing scenario YAML/JSON files.",
    )
    parser.add_argument(
        "--output-base",
        default=None,
        help="Base evidence directory (default: out/agentic).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary instead of a short report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else None
    output_base = Path(args.output_base) if args.output_base else None

    summary = run_tag(args.tag, scenarios_dir=scenarios_dir, output_base=output_base)

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"tag: {summary['tag']}")
        print(f"scenarios: {summary['scenario_count']}")
        print(f"overall_success: {summary['overall_success']}")
        for s in summary["scenarios"]:
            print(f"  {s['scenario_id']}: {s['status']} (live_agentic_success={s['guard']['live_agentic_success']})")

    return 0 if summary["overall_success"] or summary["scenario_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
