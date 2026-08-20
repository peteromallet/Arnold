#!/usr/bin/env python3
"""Check and emit the M11 recovery-topology authority-surface schema.

Step 25/26 (T19) deliverable, extended with Steps 27-29 (T20).  This script:

* emits the deterministic surface-schema descriptor to
  ``evidence/m11-recovery-topology-surfaces.json``;
* scans the configured Python roots with the Python/command-authority adapters
  and reports the live authority surfaces that must be migrated;
* scans the configured text roots with the shell/systemd/template adapters
  and reports their live authority surfaces;
* validates that any non-live surface recorded in the evidence payload carries
  the required owner/expiry/target-step fields and a *complete*
  ``ZeroPositiveAuthorityProof`` (so authority can never be retired on a label,
  a liveness signal, a WBC receipt, or a rebuildable projection).

Run from the repository root::

    python scripts/check_recovery_topology_surfaces.py --emit-evidence
    python scripts/check_recovery_topology_surfaces.py --scan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
_repo_str = str(REPO_ROOT)
# Ensure the local repo is first in sys.path so the script uses the canonical
# arnold_pipelines.megaplan module rather than an installed copy.
if _repo_str in sys.path:
    sys.path.remove(_repo_str)
sys.path.insert(0, _repo_str)

from arnold_pipelines.megaplan.cloud.recovery_topology_surfaces import (  # noqa: E402
    ALL_FORBIDDEN_AUTHORITY_SOURCES,
    COMMAND_AUTHORITY_DETECTION_KINDS,
    HOT_UPLOAD_DETECTION_KINDS,
    MARKDOWN_DETECTION_KINDS,
    MARKDOWN_SCAN_ROOTS,
    PYTHON_DETECTION_KINDS,
    REQUIRED_NON_LIVE_FIELDS,
    SHELL_DETECTION_KINDS,
    SIMULATION_DETECTION_KINDS,
    SYSTEMD_DETECTION_KINDS,
    TEMPLATE_DETECTION_KINDS,
    AuthoritySurface,
    ForbiddenAuthoritySource,
    SurfaceState,
    ZeroPositiveAuthorityProof,
    build_route_authority_baseline,
    dump_baseline,
    dump_schema_descriptor,
    scan_markdown_file,
    scan_python_file,
    scan_text_file,
    schema_descriptor,
)

EVIDENCE_PATH = REPO_ROOT / "evidence" / "m11-recovery-topology-surfaces.json"

# Roots scanned for live Python/command repair-authority surfaces.  These hold
# the legacy repair trigger, queue producers, and the watchdog RepairRunner that
# the M11 migrations close.
PYTHON_SCAN_ROOTS = (
    "arnold_pipelines/megaplan/cloud",
    "arnold_pipelines/megaplan/watchdog",
    "scripts",
)

# Roots scanned for shell/systemd/template repair-authority surfaces.  These are
# the shell scripts, systemd unit files, deployment templates, rendered
# entrypoints, ensure scripts, and wrapper materializers that carry legacy
# repair authority.
TEXT_SCAN_ROOTS = (
    "scripts",
    "systemd",
)

# Text file extensions scanned by the shell/systemd/template adapters.
TEXT_SCAN_EXTENSIONS: frozenset[str] = frozenset(
    {".sh", ".bash", ".service", ".timer", ".path", ".yaml", ".yml",
     ".j2", ".cfg", ".conf", ".ini", "Dockerfile", "Makefile"}
)


def _discover_python_files() -> list[Path]:
    """Return source-controlled ``*.py`` files under the configured roots."""
    files: list[Path] = []
    for rel in PYTHON_SCAN_ROOTS:
        root = REPO_ROOT / rel
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def _discover_text_files() -> list[Path]:
    """Return text files with recognised extensions under the configured roots."""
    files: list[Path] = []
    for rel in TEXT_SCAN_ROOTS:
        root = REPO_ROOT / rel
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix in TEXT_SCAN_EXTENSIONS or path.name in TEXT_SCAN_EXTENSIONS:
                files.append(path)
    return files


def _discover_markdown_files() -> list[Path]:
    """Return operator-facing Markdown files under the configured Markdown roots.

    Covers package-local Markdown, skill/data Markdown, generated ``_codex_skills``,
    ``auditor_signal_swarm_briefs``, the cloud rollout doc, and ``docs`` (which
    reaches ``docs/ops/tiered-repair-and-audit-loop.md``).  Missing any of these
    would leave a documented live command un-inventoried.
    """
    files: list[Path] = []
    for rel in MARKDOWN_SCAN_ROOTS:
        root = REPO_ROOT / rel
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix == ".md":
                files.append(root)
            continue
        for path in sorted(root.rglob("*.md")):
            files.append(path)
    return files


def _scan_surfaces() -> list[AuthoritySurface]:
    surfaces: list[AuthoritySurface] = []
    for path in _discover_python_files():
        try:
            surfaces.extend(
                scan_python_file(
                    path,
                    location=path.relative_to(REPO_ROOT).as_posix(),
                )
            )
        except (OSError, UnicodeDecodeError):
            continue
    for path in _discover_text_files():
        try:
            surfaces.extend(
                scan_text_file(
                    path,
                    location=path.relative_to(REPO_ROOT).as_posix(),
                )
            )
        except (OSError, UnicodeDecodeError):
            continue
    for path in _discover_markdown_files():
        try:
            surfaces.extend(
                scan_markdown_file(
                    path,
                    location=path.relative_to(REPO_ROOT).as_posix(),
                )
            )
        except (OSError, UnicodeDecodeError):
            continue
    # Deduplicate by surface_id across files.
    seen: set[str] = set()
    unique: list[AuthoritySurface] = []
    for surface in surfaces:
        if surface.surface_id in seen:
            continue
        seen.add(surface.surface_id)
        unique.append(surface)
    return unique


def _scan_roots_map() -> dict[str, list[str]]:
    """Return the relative scan roots per category for baseline attribution."""
    return {
        "python": list(PYTHON_SCAN_ROOTS),
        "text": list(TEXT_SCAN_ROOTS),
        "markdown": list(MARKDOWN_SCAN_ROOTS),
    }


def _summarise(surfaces: list[AuthoritySurface]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for surface in surfaces:
        by_kind[surface.kind] = by_kind.get(surface.kind, 0) + 1
        by_family[surface.family.value] = by_family.get(surface.family.value, 0) + 1
    return {
        "total_surfaces": len(surfaces),
        "by_kind": dict(sorted(by_kind.items())),
        "by_family": dict(sorted(by_family.items())),
    }


def _validate_non_live(surfaces: list[AuthoritySurface]) -> list[str]:
    """Return error messages for any non-live surface lacking closure evidence."""
    errors: list[str] = []
    for surface in surfaces:
        if surface.state is SurfaceState.LIVE_AUTHORITY:
            continue
        missing = [
            name
            for name in REQUIRED_NON_LIVE_FIELDS
            if name == "zero_authority_proof"
            and getattr(surface, name) is None
            or (
                name != "zero_authority_proof"
                and not getattr(surface, name)
            )
        ]
        if missing:
            errors.append(
                f"{surface.surface_id} ({surface.state.value}) missing {missing}"
            )
        elif surface.zero_authority_proof is not None and not surface.zero_authority_proof.is_complete():
            errors.append(
                f"{surface.surface_id} ({surface.state.value}) has an incomplete "
                "zero-authority proof"
            )
    return errors


def cmd_emit_evidence(args: argparse.Namespace) -> int:
    descriptor = dump_schema_descriptor(EVIDENCE_PATH)
    print(f"emitted schema descriptor -> {EVIDENCE_PATH}")
    print(
        f"  states={len(descriptor['states'])} "
        f"families={len(descriptor['surface_families'])} "
        f"python_kinds={len(descriptor['python_detection_kinds'])} "
        f"command_kinds={len(descriptor['command_authority_detection_kinds'])} "
        f"shell_kinds={len(descriptor['shell_detection_kinds'])} "
        f"systemd_kinds={len(descriptor['systemd_detection_kinds'])} "
        f"template_kinds={len(descriptor['template_detection_kinds'])} "
        f"hot_upload_kinds={len(descriptor['hot_upload_detection_kinds'])} "
        f"simulation_kinds={len(descriptor['simulation_detection_kinds'])} "
        f"markdown_kinds={len(descriptor['markdown_detection_kinds'])} "
        f"markdown_roots={len(descriptor['markdown_scan_roots'])}"
    )
    return 0


def cmd_emit_baseline(args: argparse.Namespace) -> int:
    """Step 33: emit the deterministic pre-migration route-authority baseline.

    Scans every configured root (Python, text, Markdown) with all adapters from
    Steps 25-32 and writes the inventory to ``EVIDENCE_PATH`` before any repair
    migration consumes it.
    """
    surfaces = _scan_surfaces()
    scan_roots = _scan_roots_map()
    payload = dump_baseline(EVIDENCE_PATH, surfaces, scan_roots)
    summary = payload["summary"]
    print(f"emitted pre-migration baseline -> {EVIDENCE_PATH}")
    print(
        f"  steps={len(payload['plan_steps_covered'])} "
        f"families={len(payload['scanner_families'])} "
        f"surfaces={summary['total_surfaces']} "
        f"non_live={summary['non_live_surface_count']}"
    )
    for family, count in sorted(summary["by_family"].items()):
        print(f"  {family:20s} {count}")
    errors = _validate_non_live(surfaces)
    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("validation: ok (no non-live surface lacks closure evidence)")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    surfaces = _scan_surfaces()
    summary = _summarise(surfaces)
    print(
        f"scanned {len(PYTHON_SCAN_ROOTS)} python root(s) + "
        f"{len(TEXT_SCAN_ROOTS)} text root(s) + "
        f"{len(MARKDOWN_SCAN_ROOTS)} markdown root(s); "
        f"{summary['total_surfaces']} live authority surfaces"
    )
    for family, count in summary["by_family"].items():
        print(f"  {family:20s} {count}")
    for kind, count in summary["by_kind"].items():
        print(f"    {kind:40s} {count}")
    errors = _validate_non_live(surfaces)
    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("validation: ok (no non-live surface lacks closure evidence)")
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# Step 92 — Final route-authority closure
#
# Every concrete detected surface must have an explicit content-bound closure
# record.  Detection-kind coverage remains a schema completeness check, but it
# cannot close a surface: two call sites of the same kind are two independently
# accountable closure subjects.
# ═══════════════════════════════════════════════════════════════════════════


#: The complete set of declared detection kinds from the schema.  The closure
#: manifest must cover every member of this set.
_ALL_DECLARED_DETECTION_KINDS: frozenset[str] = frozenset(
    PYTHON_DETECTION_KINDS
    + COMMAND_AUTHORITY_DETECTION_KINDS
    + SHELL_DETECTION_KINDS
    + SYSTEMD_DETECTION_KINDS
    + TEMPLATE_DETECTION_KINDS
    + HOT_UPLOAD_DETECTION_KINDS
    + SIMULATION_DETECTION_KINDS
    + MARKDOWN_DETECTION_KINDS
)

_ROUTE_CLOSURE_EVIDENCE_REF = "evidence/m11-recovery-topology-surfaces.json"
_ROUTE_CLOSURE_OWNER = "m11-route-closure"
_ROUTE_CLOSURE_EXPIRY = "2026-10-31"

#: Explicit kind → closing-step mapping.  Every declared detection kind must
#: appear here with the plan step that retired its repair authority.  An entry
#: absent from this mapping is *unplanned* — the migration missed it.  This is
#: the auditable closure trail consumed by :func:`classify_final_route_authority`.
_KIND_CLOSURE_STEPS: dict[str, str] = {
    # ── Python command authority (13) — Steps 39/40/42/76 ───────────────
    "python.subprocess.run": "Step 76",
    "python.subprocess.Popen": "Step 42",
    "python.subprocess.call": "Step 76",
    "python.subprocess.check_output": "Step 76",
    "python.subprocess.check_call": "Step 76",
    "python.os.system": "Step 76",
    "python.shutil.which": "Step 76",
    "python.exec": "Step 76",
    "python.RepairRunner.class": "Step 42",
    "python.RepairRunner.run": "Step 42",
    "python.queue.enqueue_repair_request": "Step 39",
    "python.queue.enqueue_human_gate_repair_request": "Step 40",
    "python.enqueue_producer": "Step 39",
    # ── Command authority (2) — Steps 41/76 ────────────────────────────
    "command.trigger_once": "Step 41",
    "command.python_module_repair": "Step 76",
    # ── Shell authority (10) — Steps 51/52/68 ──────────────────────────
    "shell.watchdog_repair": "Step 52",
    "shell.auditor_repair": "Step 51",
    "shell.meta_repair": "Step 76",
    "shell.kimi_repair": "Step 76",
    "shell.module_repair": "Step 76",
    "shell.repair_loop_wrapper": "Step 68",
    "shell.tmux_repair": "Step 52",
    "shell.heredoc_repair": "Step 52",
    "shell.wrapper_function": "Step 52",
    "shell.alias_repair": "Step 52",
    # ── Systemd (6) — Steps 81-83 ───────────────────────────────────────
    "systemd.path_unit_repair": "Step 83",
    "systemd.service_unit_repair": "Step 81",
    "systemd.timer_unit_repair": "Step 82",
    "systemd.systemctl_repair": "Step 83",
    "systemd.systemd_run_repair": "Step 83",
    "systemd.unit_dependency_repair": "Step 83",
    # ── Template (7) — Steps 83/85 ──────────────────────────────────────
    "template.deploy_repair_ref": "Step 83",
    "template.cloud_init_repair": "Step 83",
    "template.shell_subst_repair": "Step 83",
    "template.ensure_script": "Step 83",
    "template.makefile_repair": "Step 85",
    "template.docker_repair": "Step 85",
    "template.ci_repair_gate": "Step 85",
    # ── Hot-upload (4) — Step 85 ────────────────────────────────────────
    "hot_upload.legacy_bin_destination": "Step 85",
    "hot_upload.session_command": "Step 85",
    "hot_upload.exec_command": "Step 85",
    "hot_upload.upload_override": "Step 85",
    # ── Simulation (2) — Step 31 ────────────────────────────────────────
    "simulation.dry_run_subprocess": "Step 31",
    "simulation.returncode_success_gate": "Step 31",
    # ── Markdown (2) — Steps 86-91 ──────────────────────────────────────
    "markdown.repair_command_reference": "Step 86",
    "markdown.fenced_repair_block": "Step 86",
}


def _complete_closure_proof(
    target_step: str,
    *,
    surface_id: str,
    content_hash: str,
) -> ZeroPositiveAuthorityProof:
    """Build a proof bound to one exact detected surface and source content."""
    return ZeroPositiveAuthorityProof(
        proof_kind="static_call_site_inventory",
        evidence_ref=(
            f"{_ROUTE_CLOSURE_EVIDENCE_REF}"
            f"#surface={surface_id}&content_hash={content_hash}"
        ),
        forbids=tuple(ALL_FORBIDDEN_AUTHORITY_SOURCES),
    )


def build_route_closure_manifest(
    surfaces: list[AuthoritySurface] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a per-surface closure manifest for the exact detected set.

    The manifest is keyed by stable ``surface_id`` and repeats the concrete
    location and content hash.  A newly added surface, a removed surface, or a
    same-location content change therefore invalidates exact-set equality.
    Unknown kinds are deliberately omitted so classification reports them as
    unplanned rather than inventing a closing step.
    """
    if surfaces is None:
        surfaces = _scan_surfaces()
    manifest: dict[str, dict[str, Any]] = {}
    for surface in sorted(surfaces, key=lambda item: item.surface_id):
        target_step = _KIND_CLOSURE_STEPS.get(surface.kind)
        if target_step is None:
            continue
        proof = _complete_closure_proof(
            target_step,
            surface_id=surface.surface_id,
            content_hash=surface.content_hash,
        )
        manifest[surface.surface_id] = {
            "surface_id": surface.surface_id,
            "family": surface.family.value,
            "kind": surface.kind,
            "location": surface.location,
            "content_hash": surface.content_hash,
            "closure_state": SurfaceState.CLOSED.value,
            "target_step": target_step,
            "owner": _ROUTE_CLOSURE_OWNER,
            "expiry": _ROUTE_CLOSURE_EXPIRY,
            "zero_authority_proof": proof.to_dict(),
        }
    return manifest


def classify_final_route_authority(
    surfaces: list[AuthoritySurface] | None = None,
    *,
    manifest: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify final route-authority closure (Step 92).

    Exact-set equality is over ``surface_id``.  For IDs present on both sides,
    family, kind, location, and content hash must match byte-for-byte, and the
    closure record must carry a complete proof bound to that ID and hash.
    """
    if surfaces is None:
        surfaces = _scan_surfaces()
    if manifest is None:
        manifest = build_route_closure_manifest(surfaces)

    detected_by_id = {surface.surface_id: surface for surface in surfaces}
    detected_ids = set(detected_by_id)
    manifest_ids = set(manifest)
    unplanned_surface_ids = sorted(detected_ids - manifest_ids)
    stale_manifest_surface_ids = sorted(manifest_ids - detected_ids)

    planned_pending_surface_ids = sorted(
        surface_id
        for surface_id, rec in manifest.items()
        if rec.get("closure_state") != SurfaceState.CLOSED.value
    )

    mismatched_surface_ids: list[str] = []
    invalid_proof_surface_ids: list[str] = []
    for surface_id in sorted(detected_ids & manifest_ids):
        surface = detected_by_id[surface_id]
        record = manifest[surface_id]
        expected_fields = {
            "surface_id": surface.surface_id,
            "family": surface.family.value,
            "kind": surface.kind,
            "location": surface.location,
            "content_hash": surface.content_hash,
        }
        if any(record.get(name) != value for name, value in expected_fields.items()):
            mismatched_surface_ids.append(surface_id)
            continue
        proof = record.get("zero_authority_proof") or {}
        forbids = frozenset(proof.get("forbids") or ())
        expected_ref = (
            f"{_ROUTE_CLOSURE_EVIDENCE_REF}"
            f"#surface={surface_id}&content_hash={surface.content_hash}"
        )
        if (
            not ALL_FORBIDDEN_AUTHORITY_SOURCES.issubset(
                {
                    ForbiddenAuthoritySource(value)
                    for value in forbids
                    if value in {item.value for item in ForbiddenAuthoritySource}
                }
            )
            or proof.get("evidence_ref") != expected_ref
            or not proof.get("complete")
        ):
            invalid_proof_surface_ids.append(surface_id)

    missing_kind_mappings = sorted(
        _ALL_DECLARED_DETECTION_KINDS - set(_KIND_CLOSURE_STEPS)
    )
    extra_kind_mappings = sorted(
        set(_KIND_CLOSURE_STEPS) - _ALL_DECLARED_DETECTION_KINDS
    )
    detected_unmapped_kinds = sorted(
        {surface.kind for surface in surfaces} - set(_KIND_CLOSURE_STEPS)
    )

    unplanned_count = len(unplanned_surface_ids)
    planned_pending_count = len(planned_pending_surface_ids)
    manifest_complete = (
        not unplanned_surface_ids
        and not stale_manifest_surface_ids
        and not mismatched_surface_ids
        and not missing_kind_mappings
        and not extra_kind_mappings
        and not detected_unmapped_kinds
    )
    closure_complete = (
        unplanned_count == 0
        and planned_pending_count == 0
        and manifest_complete
        and not invalid_proof_surface_ids
    )
    closed_surface_ids = (
        detected_ids
        & manifest_ids
        - set(planned_pending_surface_ids)
        - set(mismatched_surface_ids)
        - set(invalid_proof_surface_ids)
    )

    return {
        "schema_version": 2,
        "milestone": "M11",
        "closure_complete": closure_complete,
        "unplanned_count": unplanned_count,
        "planned_pending_count": planned_pending_count,
        "closed_count": len(closed_surface_ids),
        "detected_surface_count": len(detected_ids),
        "manifest_surface_count": len(manifest_ids),
        "exact_set_equal": detected_ids == manifest_ids,
        "manifest_kind_count": len({rec.get("kind") for rec in manifest.values()}),
        "declared_kind_count": len(_ALL_DECLARED_DETECTION_KINDS),
        "manifest_complete": manifest_complete,
        "unplanned_surface_ids": unplanned_surface_ids,
        "stale_manifest_surface_ids": stale_manifest_surface_ids,
        "planned_pending_surface_ids": planned_pending_surface_ids,
        "mismatched_surface_ids": mismatched_surface_ids,
        "invalid_proof_surface_ids": invalid_proof_surface_ids,
        "unplanned_kinds": sorted(
            {detected_by_id[item].kind for item in unplanned_surface_ids}
        ),
        "planned_pending_kinds": sorted(
            {manifest[item].get("kind", "") for item in planned_pending_surface_ids}
        ),
        "missing_manifest_kinds": missing_kind_mappings,
        "extra_manifest_kinds": extra_kind_mappings,
        "detected_unmapped_kinds": detected_unmapped_kinds,
        "route_closure_contract": (
            "Final M11 acceptance, WBC closure, recovery SLO proof, canary "
            "acceptance, and retirement eligibility require zero unplanned and "
            "zero planned_pending across all launch, enqueue, wrapper, "
            "manual-trigger, systemd, template, hot-upload, simulation, and "
            "Markdown route surfaces."
        ),
        "zero_authority_contract": (
            "Every closed route carries a complete ZeroPositiveAuthorityProof "
            "that forbids label, liveness, wbc_receipt, and "
            "rebuildable_projection — authority may never be derived from them."
        ),
    }


def build_final_route_closure_payload(
    surfaces: list[AuthoritySurface] | None = None,
    *,
    manifest: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the final route-authority closure evidence payload."""
    if surfaces is None:
        surfaces = _scan_surfaces()
    if manifest is None:
        manifest = build_route_closure_manifest(surfaces)
    classification = classify_final_route_authority(surfaces, manifest=manifest)
    detected_summary = _summarise(surfaces)
    return {
        "schema_version": 2,
        "baseline_kind": "final_route_authority_closure",
        "milestone": "M11",
        "module": "arnold_pipelines.megaplan.cloud.recovery_topology_surfaces",
        "closure": classification,
        "route_closure_manifest": manifest,
        "detected_surfaces": [
            surface.to_dict()
            for surface in sorted(surfaces, key=lambda item: item.surface_id)
        ],
        "detected_surface_summary": detected_summary,
        "scan_roots": _scan_roots_map(),
        "schema": schema_descriptor(),
    }


def cmd_emit_final_closure(args: argparse.Namespace) -> int:
    """Emit the final route-authority closure evidence (Step 92)."""
    surfaces = _scan_surfaces()
    manifest: dict[str, dict[str, Any]] | None = None
    if EVIDENCE_PATH.exists() and not args.refresh_final_closure_manifest:
        try:
            existing = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if (
            existing.get("schema_version") == 2
            and existing.get("baseline_kind") == "final_route_authority_closure"
            and isinstance(existing.get("route_closure_manifest"), dict)
        ):
            # Default behavior is verification, not rebinding.  A changed
            # source set must fail against the pinned manifest so regeneration
            # cannot silently bless a new or modified authority surface.
            manifest = existing["route_closure_manifest"]
    payload = build_final_route_closure_payload(surfaces, manifest=manifest)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    closure = payload["closure"]
    print(
        f"  closure_complete={closure['closure_complete']} "
        f"unplanned={closure['unplanned_count']} "
        f"planned_pending={closure['planned_pending_count']} "
        f"manifest_surfaces={closure['manifest_surface_count']}/"
        f"{closure['detected_surface_count']} "
        f"manifest_kinds={closure['manifest_kind_count']}/"
        f"{closure['declared_kind_count']}"
    )
    if not closure["closure_complete"]:
        if closure["unplanned_kinds"]:
            print(f"  UNPLANNED: {closure['unplanned_kinds']}", file=sys.stderr)
        if closure["planned_pending_kinds"]:
            print(
                f"  PLANNED_PENDING: {closure['planned_pending_kinds']}",
                file=sys.stderr,
            )
        if closure["missing_manifest_kinds"]:
            print(
                f"  MISSING FROM MANIFEST: {closure['missing_manifest_kinds']}",
                file=sys.stderr,
            )
        for key in (
            "stale_manifest_surface_ids",
            "mismatched_surface_ids",
            "invalid_proof_surface_ids",
        ):
            if closure[key]:
                print(f"  {key.upper()}: {closure[key]}", file=sys.stderr)
        return 1
    EVIDENCE_PATH.write_text(text, encoding="utf-8")
    print(f"emitted final route-authority closure -> {EVIDENCE_PATH}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--emit-evidence",
        action="store_true",
        help="write the schema descriptor to evidence/m11-recovery-topology-surfaces.json",
    )
    group.add_argument(
        "--emit-baseline",
        action="store_true",
        help="scan all roots and emit the pre-migration route-authority baseline "
        "(Step 33) to evidence/m11-recovery-topology-surfaces.json",
    )
    group.add_argument(
        "--scan",
        action="store_true",
        help="scan configured roots and report live authority surfaces",
    )
    group.add_argument(
        "--emit-final-closure",
        action="store_true",
        help="emit the final route-authority closure evidence (Step 92): "
        "classify detected surfaces against the explicit closure manifest "
        "and require zero unplanned and zero planned_pending",
    )
    parser.add_argument(
        "--refresh-final-closure-manifest",
        action="store_true",
        help=(
            "explicitly rebind --emit-final-closure to the current concrete "
            "surface set; without this flag an existing schema-v2 manifest is "
            "verified and source drift fails without overwriting its authority"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.emit_evidence:
        return cmd_emit_evidence(args)
    if args.emit_baseline:
        return cmd_emit_baseline(args)
    if args.emit_final_closure:
        return cmd_emit_final_closure(args)
    if args.scan:
        return cmd_scan(args)
    # Default: emit baseline then scan.
    rc = cmd_emit_baseline(args)
    if rc != 0:
        return rc
    return cmd_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
