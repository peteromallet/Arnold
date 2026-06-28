"""Live agentic harness runner for VibeComfy headless scenarios.

Scenarios run CONCURRENTLY — each in its own subprocess (process isolation +
kill-on-timeout via ``subprocess.run``), bounded by ``--max-workers``. Modeled
on the subagent-launcher fanout: one process per task, a bounded pool, a
per-task timeout. ``--single`` is the per-scenario subprocess entry point.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from vibecomfy.agent.deepseek_usage import (
    add_deepseek_usage,
    coerce_deepseek_usage,
    combine_deepseek_cost_bases,
)

from .adapter import run_headless_scenario
from .guard import guard_output_dir

DEFAULT_MAX_WORKERS = 12
DEFAULT_PER_SCENARIO_TIMEOUT = 600  # seconds; kills a wedged/over-slow scenario
REPO = Path(__file__).resolve().parents[2]


def _scenario_paths(scenarios_dir: Path) -> list[Path]:
    if not scenarios_dir.is_dir():
        return []
    return sorted(p for p in scenarios_dir.iterdir() if p.suffix in {".yaml", ".yml", ".json"})


def _load_scenario(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _output_dir_for(output_base: Any, tag: str, scenario_id: str) -> Path:
    base = Path(output_base) if output_base else Path("out/agentic")
    return Path(base) / tag / scenario_id


def _trim(s: str) -> str:
    return s if len(s) <= 400 else s[-400:]


def _synthetic_guard(detail: str) -> dict[str, Any]:
    """A failing guard for scenarios that errored/timed out in the runner itself."""
    return {
        "live_agentic_success": False,
        "metadata_success": False,
        "assessment": {
            "passed": False,
            "expect_graph_changed": True,
            "issue_count": 1,
            "error_count": 1,
            "issues": [{"check": "runner", "severity": "error", "detail": detail}],
        },
    }


def _failure_summary(scenario_id: str, output_base: Any, tag: str, detail: str) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "status": "error",
        "ok": False,
        "error": detail,
        "output_dir": str(_output_dir_for(output_base, tag, scenario_id)),
        "guard": _synthetic_guard(detail),
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
    }


def run_single(scenario_path: str, tag: str, output_base: Any, out_file: Path | None) -> dict[str, Any]:
    """Run ONE scenario in-process; write its summary JSON to *out_file* if given.

    This is the entry point invoked by the per-scenario subprocess in parallel mode.
    """
    path = Path(scenario_path)
    scenario = _load_scenario(path)
    scenario.setdefault("id", path.stem)
    summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
    summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
    if out_file is not None:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(summary, default=str), encoding="utf-8")
    return summary


def run_tag(
    tag: str,
    *,
    scenarios_dir: Path | None = None,
    output_base: Path | str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    per_scenario_timeout: int = DEFAULT_PER_SCENARIO_TIMEOUT,
) -> dict[str, Any]:
    """Run every scenario under *scenarios_dir* CONCURRENTLY — each in its own
    subprocess (process-isolated + kill-on-timeout), bounded by *max_workers*."""
    if scenarios_dir is None:
        scenarios_dir = Path(__file__).with_name("scenarios")
    paths = _scenario_paths(scenarios_dir)
    results: list[dict[str, Any] | None] = [None] * len(paths)
    sem = threading.Semaphore(max(1, max_workers))
    tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
    try:
        def worker(idx: int, path: Path) -> None:
            sid = path.stem
            out_file = tmpdir / f"{idx:03d}.json"
            cmd = [
                sys.executable, "-m", "tests.live_agentic_harness.runner",
                "--single", str(path), "--tag", tag, "--single-out", str(out_file),
            ]
            if output_base is not None:
                cmd += ["--output-base", str(output_base)]
            with sem:
                try:
                    proc = subprocess.run(
                        cmd, cwd=str(REPO), capture_output=True, text=True,
                        timeout=per_scenario_timeout,
                    )
                    if out_file.exists():
                        results[idx] = json.loads(out_file.read_text(encoding="utf-8"))
                        results[idx].setdefault("scenario_id", sid)
                    else:
                        tail = _trim((proc.stderr or ""))
                        results[idx] = _failure_summary(
                            sid, output_base, tag,
                            f"runner produced no summary (rc={proc.returncode}); {tail}",
                        )
                except subprocess.TimeoutExpired:
                    results[idx] = _failure_summary(
                        sid, output_base, tag,
                        f"scenario exceeded {per_scenario_timeout}s and was killed",
                    )
                except Exception as exc:  # noqa: BLE001 — isolate one failure
                    results[idx] = _failure_summary(sid, output_base, tag, _trim(str(exc)))

        threads = [
            threading.Thread(target=worker, args=(i, p), daemon=True)
            for i, p in enumerate(paths)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        for f in tmpdir.glob("*.json"):
            try:
                f.unlink()
            except Exception:  # noqa: BLE001
                pass
        try:
            tmpdir.rmdir()
        except Exception:  # noqa: BLE001
            pass

    summaries = [r for r in results if r]
    overall_success = all(s["guard"]["live_agentic_success"] for s in summaries)
    deepseek_usage = add_deepseek_usage(
        *[coerce_deepseek_usage(summary.get("deepseek_usage")) for summary in summaries]
    )
    deepseek_est_cost_usd = float(
        sum(float(summary.get("deepseek_est_cost_usd") or 0.0) for summary in summaries)
    )
    deepseek_cost_basis = combine_deepseek_cost_bases(
        [summary.get("deepseek_cost_basis") for summary in summaries]
    )
    return {
        "tag": tag,
        "scenario_count": len(summaries),
        "overall_success": overall_success,
        "deepseek_usage": deepseek_usage,
        "deepseek_est_cost_usd": deepseek_est_cost_usd,
        "deepseek_cost_basis": deepseek_cost_basis,
        "scenarios": summaries,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
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
    parser.add_argument(
        "--single",
        default=None,
        help="Run a SINGLE scenario file (subprocess entry point for parallel mode).",
    )
    parser.add_argument(
        "--single-out",
        default=None,
        help="Path to write the single-scenario summary JSON (used with --single).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"max concurrent scenarios (default {DEFAULT_MAX_WORKERS}).",
    )
    parser.add_argument(
        "--per-scenario-timeout",
        type=int,
        default=DEFAULT_PER_SCENARIO_TIMEOUT,
        help=f"per-scenario seconds before kill (default {DEFAULT_PER_SCENARIO_TIMEOUT}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.single:
        out_file = Path(args.single_out) if args.single_out else None
        ob = Path(args.output_base) if args.output_base else None
        summary = run_single(args.single, args.tag, ob, out_file)
        # Compact one-line stdout for liveness; the real payload is in --single-out.
        print(json.dumps({"scenario_id": summary.get("scenario_id"),
                          "ok": summary["guard"]["live_agentic_success"]}))
        return 0 if summary["guard"]["live_agentic_success"] else 1

    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else None
    output_base = Path(args.output_base) if args.output_base else None
    summary = run_tag(
        args.tag,
        scenarios_dir=scenarios_dir,
        output_base=output_base,
        max_workers=args.max_workers,
        per_scenario_timeout=args.per_scenario_timeout,
    )

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"tag: {summary['tag']}")
        print(f"scenarios: {summary['scenario_count']}")
        print(f"overall_success: {summary['overall_success']}")
        for s in summary["scenarios"]:
            assessment = s["guard"].get("assessment", {})
            errors = assessment.get("error_count", 0)
            print(
                f"  {s['scenario_id']}: {s['status']} "
                f"(live_agentic_success={s['guard']['live_agentic_success']}, "
                f"assessment_errors={errors})"
            )

    return 0 if summary["overall_success"] or summary["scenario_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
