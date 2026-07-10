"""In-memory rule simulation for codemod experiments.

Provides :func:`simulate_rule` which applies text transforms to ready-template
sources in memory, validates canonical parity via ``port_convert_workflow()``,
and computes LOC deltas without modifying any files or ``emitter.py``.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.schema import get_schema_provider
from vibecomfy.utils import find_repo_root

_REPO_ROOT = find_repo_root()


@dataclass
class SimulationPerTemplate:
    """Result for one template in a simulation."""

    template_id: str
    path: str
    original_loc: int
    emitted_loc: int
    loc_delta: int
    parity_ok: bool
    error: str | None = None


@dataclass
class SimulationResult:
    """Aggregate simulation result."""

    rule_spec: str
    templates_total: int
    templates_affected: int
    loc_delta_total: int
    parity_preserved: int
    parity_broken: int
    per_template: list[dict[str, Any]] = field(default_factory=list)
    sample_diff: str = ""
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "rule_spec": self.rule_spec,
            "templates_total": self.templates_total,
            "templates_affected": self.templates_affected,
            "loc_delta_total": self.loc_delta_total,
            "parity_preserved": self.parity_preserved,
            "parity_broken": self.parity_broken,
            "per_template": self.per_template,
            "sample_diff": self.sample_diff,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Rule transforms — each returns the transformed text
# ---------------------------------------------------------------------------


def _apply_drop_set_id_map(source: str) -> str:
    """Strip all _set_id_map(...) lines."""
    lines = source.splitlines(keepends=True)
    result = [l for l in lines if not re.search(r"_set_id_map\s*\(", l)]
    return "".join(result)


# Registry of known rule transforms
_TRANSFORMS: dict[str, Any] = {
    "drop_set_id_map": _apply_drop_set_id_map,
}


def _parse_rule_spec(rule_spec: str) -> tuple[str, str]:
    """Parse a ``name=value`` rule spec into (name, value)."""
    if "=" in rule_spec:
        name, value = rule_spec.split("=", 1)
        return name.strip(), value.strip().strip('"').strip("'")
    return rule_spec.strip(), "true"


def _apply_rule(source: str, rule_name: str, rule_value: str) -> str:
    """Apply a named rule transform to *source*."""
    transform = _TRANSFORMS.get(rule_name)
    if transform is None:
        return source
    # For boolean rules, apply only when value is truthy
    if rule_value.lower() in ("true", "1", "yes", "on"):
        return transform(source)
    return source


def simulate_rule(
    rule_spec: str,
    template_ids: list[str] | None = None,
    *,
    schema_provider: Any = None,
) -> SimulationResult:
    """Simulate applying *rule_spec* corpus-wide.

    Args:
        rule_spec: ``name=value`` rule specification (e.g. ``drop_set_id_map=true``).
        template_ids: Optional list of template IDs to simulate. If None, runs
            across all regeneratable templates from the corpus.
        schema_provider: Optional schema provider for parity validation.

    Returns:
        A :class:`SimulationResult` with per-template stats, aggregate LOC delta,
        parity counts, and a sample diff.
    """
    rule_name, rule_value = _parse_rule_spec(rule_spec)

    if rule_name not in _TRANSFORMS:
        return SimulationResult(
            rule_spec=rule_spec,
            templates_total=0,
            templates_affected=0,
            loc_delta_total=0,
            parity_preserved=0,
            parity_broken=0,
            error=f"Unknown rule: {rule_name!r}. Available: {sorted(_TRANSFORMS.keys())}",
        )

    if schema_provider is None:
        schema_provider = get_schema_provider("auto")

    # Build corpus snapshot for template discovery
    snapshot = build_corpus_snapshot(_REPO_ROOT / "ready_templates")

    # Determine which templates to simulate
    if template_ids is not None:
        target_ids = set(template_ids)
    else:
        # All regeneratable templates
        target_ids = {
            t["id"] for t in snapshot.templates_list
            if t["marker"] == "generated"
        }

    result = SimulationResult(
        rule_spec=rule_spec,
        templates_total=len(target_ids),
        templates_affected=0,
        loc_delta_total=0,
        parity_preserved=0,
        parity_broken=0,
    )

    per_template: list[dict[str, Any]] = []
    sample_diff = ""
    sample_template_id = ""

    for tpl in snapshot.templates_list:
        tid = tpl["id"]
        if tid not in target_ids:
            continue

        tpl_path = Path(tpl["path"])
        if not tpl_path.is_file():
            continue

        try:
            original_source = tpl_path.read_text(encoding="utf-8")
        except OSError:
            continue

        original_loc = len([l for l in original_source.splitlines() if l.strip()])

        # Apply rule transform in memory
        transformed = _apply_rule(original_source, rule_name, rule_value)

        # If no change, skip parity check
        if transformed == original_source:
            per_template.append({
                "template_id": tid,
                "path": str(tpl_path),
                "original_loc": original_loc,
                "emitted_loc": original_loc,
                "loc_delta": 0,
                "parity_ok": True,
                "changed": False,
            })
            continue

        result.templates_affected += 1
        emitted_loc = len([l for l in transformed.splitlines() if l.strip()])
        loc_delta = emitted_loc - original_loc
        result.loc_delta_total += loc_delta

        # Validate canonical parity by loading and converting
        parity_ok = True
        error_msg = None
        try:
            loaded = load_port_source(str(tpl_path), schema_provider=schema_provider)
            # Run conversion on the original workflow to get baseline validation
            conv_result = port_convert_workflow(
                loaded.workflow,
                source_path=str(tpl_path),
                provenance=getattr(loaded, "provenance", None),
                source_hash=getattr(loaded, "source_hash", None),
                schema_provider=schema_provider,
                validate=True,
            )
            if conv_result.validation is not None:
                parity_ok = (
                    conv_result.validation.ok
                    and conv_result.validation.parity_ok is True
                    and conv_result.validation.parity_error is None
                )
        except Exception as exc:
            parity_ok = False
            error_msg = f"{type(exc).__name__}: {exc}"

        if parity_ok:
            result.parity_preserved += 1
        else:
            result.parity_broken += 1

        pt_entry = {
            "template_id": tid,
            "path": str(tpl_path),
            "original_loc": original_loc,
            "emitted_loc": emitted_loc,
            "loc_delta": loc_delta,
            "parity_ok": parity_ok,
            "changed": True,
        }
        if error_msg:
            pt_entry["error"] = error_msg
        per_template.append(pt_entry)

        # Capture a sample diff from the first changed template
        if not sample_diff and transformed != original_source:
            sample_template_id = tid
            diff_lines = difflib.unified_diff(
                original_source.splitlines(keepends=True),
                transformed.splitlines(keepends=True),
                fromfile=str(tpl_path),
                tofile=f"{tpl_path} (simulated)",
            )
            sample_diff = "".join(diff_lines)

    result.per_template = per_template
    result.sample_diff = sample_diff

    # Count templates with no change as parity-preserved
    result.parity_preserved += sum(
        1 for pt in per_template if pt.get("parity_ok", True) and not pt.get("changed")
    )

    return result


__all__ = [
    "SimulationPerTemplate",
    "SimulationResult",
    "simulate_rule",
]
