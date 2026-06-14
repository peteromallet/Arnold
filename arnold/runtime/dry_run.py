"""Dry-run proof harness for the Arnold runtime settings resolver.

``python -m arnold.runtime.dry_run --spec fixture.json`` reads a JSON
spec, resolves settings through the five-layer precedence chain, and
prints a deterministic report.

The report lists **every supported setting** with its ``key``, ``value``,
and ``source``.  When a setting has no resolved value it is shown as
``---``.  Validation errors (if any) are rendered in a distinct
``ERRORS:`` block.

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from arnold.runtime.settings import SettingSource
from arnold.runtime.settings_resolver import ResolvedSettings, resolve_settings

__all__ = ["dry_run_report", "main"]

# ---------------------------------------------------------------------------
# Every key the resolver knows about — ordered for deterministic output.
# ---------------------------------------------------------------------------

_SUPPORTED_KEYS: tuple[str, ...] = (
    # InheritableSettings
    "wall_timeout_s",
    "idle_timeout_s",
    "heartbeat_interval_s",
    "poll_cadence_s",
    "deadline_epoch_s",
    "retry_budget",
    "cost_cap_usd",
    # GloballyAggregatedSettings
    "max_workers",
    "cancellation",
    # IsolationSettings
    "isolation_mode",
)

# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _fmt_value(value: Any) -> str:
    """Render a single value for the table column."""
    if value is None:
        return "---"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        # repr gives us enough precision without trailing noise
        return repr(value)
    if isinstance(value, Mapping):
        # Collapse small dicts; show key count for larger ones
        if len(value) <= 3:
            inner = ", ".join(f"{k}={_fmt_value(v)}" for k, v in value.items())
            return f"{{{inner}}}"
        return f"{{...{len(value)} keys...}}"
    return str(value)


def dry_run_report(resolved: ResolvedSettings) -> str:
    """Render a deterministic text report from resolved settings.

    Parameters
    ----------
    resolved:
        The output of :func:`~arnold.runtime.settings_resolver.resolve_settings`.

    Returns
    -------
    str
        A deterministic multi-line report listing every supported setting
        with ``key``, ``value``, and ``source``, followed by any validation
        errors in an ``ERRORS:`` block.
    """
    lines: list[str] = []

    # Header
    lines.append(f"{'key':<24s}  {'value':<20s}  {'source':<20s}")
    lines.append(f"{'---':<24s}  {'---':<20s}  {'---':<20s}")

    effective = resolved.effective

    # Keys that are declared but unsupported in M3d (SD4).
    _UNSUPPORTED_KEYS: frozenset[str] = frozenset({"idle_timeout_s", "heartbeat_interval_s"})

    for key in _SUPPORTED_KEYS:
        es = effective.get(key)
        if es is not None:
            val_str = _fmt_value(es.value)
            src_str = es.source.value
        else:
            val_str = "---"
            src_str = "---"
        if key in _UNSUPPORTED_KEYS:
            val_str = f"{val_str} (unsupported)"
        lines.append(f"{key:<24s}  {val_str:<20s}  {src_str:<20s}")

    # Stage-effective block (if any)
    if resolved.stage_effective:
        lines.append("")
        lines.append("STAGE EFFECTIVE SETTINGS")
        lines.append("=" * 70)
        for stage_id in sorted(resolved.stage_effective):
            stage = resolved.stage_effective[stage_id]
            lines.append(f"  [{stage_id}]")
            for key in _SUPPORTED_KEYS:
                es = stage.get(key)
                if es is not None:
                    val_str = _fmt_value(es.value)
                    src_str = es.source.value
                else:
                    val_str = "---"
                    src_str = "---"
                if key in _UNSUPPORTED_KEYS:
                    val_str = f"{val_str} (unsupported)"
                lines.append(f"    {key:<22s}  {val_str:<18s}  {src_str:<20s}")
            lines.append("")

    # Child-scope-effective block (if any)
    if resolved.child_scope_effective:
        lines.append("CHILD SCOPE EFFECTIVE SETTINGS")
        lines.append("=" * 70)
        for scope_name in sorted(resolved.child_scope_effective):
            scope = resolved.child_scope_effective[scope_name]
            lines.append(f"  [{scope_name}]")
            for key in _SUPPORTED_KEYS:
                es = scope.get(key)
                if es is not None:
                    val_str = _fmt_value(es.value)
                    src_str = es.source.value
                else:
                    val_str = "---"
                    src_str = "---"
                if key in _UNSUPPORTED_KEYS:
                    val_str = f"{val_str} (unsupported)"
                lines.append(f"    {key:<22s}  {val_str:<18s}  {src_str:<20s}")
            lines.append("")

    # Errors block
    if resolved.errors:
        lines.append("ERRORS:")
        for err in resolved.errors:
            lines.append(f"  [{err.code}] {err.message}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# __main__ entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``python -m arnold.runtime.dry_run``.

    Reads a JSON spec file and prints the dry-run report to stdout.
    """
    parser = argparse.ArgumentParser(
        prog="python -m arnold.runtime.dry_run",
        description="Dry-run Arnold runtime settings resolution.",
    )
    parser.add_argument(
        "--spec",
        required=True,
        type=Path,
        help="Path to a JSON spec file with resolve_settings inputs.",
    )
    args = parser.parse_args(argv)

    spec_path: Path = args.spec
    try:
        raw = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read spec file {spec_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        spec: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {spec_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    # Translate optional pipeline_stages list → frozenset
    pipeline_stages: frozenset[str] | None = None
    if "pipeline_stages" in spec:
        raw_stages = spec["pipeline_stages"]
        if isinstance(raw_stages, list):
            pipeline_stages = frozenset(str(s) for s in raw_stages)

    result = resolve_settings(
        arnold_defaults=spec.get("arnold_defaults"),
        plugin_defaults=spec.get("plugin_defaults"),
        profile=spec.get("profile"),
        run_overrides=spec.get("run_overrides"),
        env_overrides=spec.get("env_overrides"),
        pipeline_stages=pipeline_stages,
        stage_local=spec.get("stage_local"),
        child_scope_overrides=spec.get("child_scope_overrides"),
    )

    print(dry_run_report(result))


if __name__ == "__main__":
    main()
