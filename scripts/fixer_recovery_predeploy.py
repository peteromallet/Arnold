#!/usr/bin/env python3
"""Emit the T-0601 predeploy verdict against a captured baseline envelope.

The predeploy gate takes the baseline envelope produced by
``fixer_recovery_baseline.py``, the G13-approved source SHA, and the current
initiative inputs, and re-verifies the live state fail-closed:

* **pinned target** — the envelope must prove EXACTLY the G13 session / plan
  / chain record (``--session`` ``--plan`` ``--chain-record``; defaults are
  ``megaplan-maintenance`` / ``m1-containment-and-truthful-20260811-0640`` /
  ``chain-c511d8baf7d7.json``), and its captured session/chain/ledger lineage
  must be internally consistent with that pin;
* **stale session** — the pinned session must be classified ``current`` by
  its captured liveness (a stopped/dead marker, or activity older than the
  threshold, fails);
* **source SHA binding** — ``--source-sha`` must resolve to a real commit in
  the repo (``rev-parse``) and the working tree's tracked files must match
  it (``git diff``), so a PASS cannot be issued for an un-published SHA;
* **missing proof** — any captured source file absent, unreadable, or
  content-drifting from its recorded SHA (including reconcile refs that
  moved or disappeared);
* **incoherent capture** — a torn or overlapping half-open window in the
  envelope (the baseline was not an atomic read);
* **non-canonical actions** — the repair queue carries anything outside the
  canonical request/join/reclaim vocabulary or breaks the request/decision/
  claim/attempt reference chain;
* **mixed versions** — more than one distinct engine/lineage SHA across the
  runtime manifest, session markers, chain records, and the approved source
  SHA (the approved SHA must BE the deployed lineage);
* **selectors** — a retired ``MEGAPLAN_*_SRC`` / ``SYNC_BRANCH`` token in any
  launch-path file or in the process environment;
* **editable installs** — ``<runtime>/.venv`` present, ``venv_path`` inside
  the runtime root, missing/incomplete T-0301 dependency-generation proof,
  a missing generation interpreter, non-empty ``base.editable_install_path``,
  or ``pip install -e`` residue in a launch-path file;
* **ledger bypass** — any captured plan ``state.json`` without canonical
  writer provenance (TransitionWriter marker or a CAS reference inside the
  captured queue);
* **unsnapshotted initiative inputs** — chain.yaml, NORTHSTAR.md, or any
  chain-referenced brief changed since the baseline (or went missing).

The verdict is ``PASS`` only when every check passes.  The only effect this
script performs is the verdict receipt write to the evidence directory
(``<evidence-dir>/predeploy-verdict.json``); ``--no-write`` runs in pure
collector mode with zero effects.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in (None, ""):  # pragma: no cover - direct script invocation
    # ``python3 scripts/fixer_recovery_predeploy.py`` runs with ``scripts/`` on
    # sys.path; make the repository root importable so the shared baseline
    # constants/helpers resolve the same way pytest (pythonpath=["."]) loads them.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fixer_recovery_baseline import (
    BASELINE_SCHEMA,
    DEFAULT_CHAIN_RECORD,
    DEFAULT_PLAN,
    DEFAULT_SESSION,
    RETIRED_SELECTOR_TOKENS,
    RUNTIME_VENV_DIR_NAME,
    _FULL_SHA256_RE,
    _FULL_SHA_RE,
    _digest,
    _sha256_file,
)

PREDEPLOY_SCHEMA = "arnold.megaplan.fixer_recovery_predeploy.v1"
VERDICT_RECEIPT_NAME = "predeploy-verdict.json"

# Fail reason codes (the predeploy vocabulary).
FAIL_MISSING_PROOF = "missing_proof"
FAIL_INVALID_BASELINE = "invalid_baseline"
FAIL_INCOHERENT_CAPTURE = "incoherent_capture"
FAIL_NON_CANONICAL_ACTION = "non_canonical_action"
FAIL_MIXED_VERSIONS = "mixed_versions"
FAIL_SELECTORS = "selectors"
FAIL_EDITABLE_INSTALL = "editable_install"
FAIL_LEDGER_BYPASS = "ledger_bypass"
FAIL_UNSNAPSHOTTED_INPUTS = "unsnapshotted_inputs"
FAIL_NOT_PINNED = "not_pinned"
FAIL_STALE_SESSION = "stale_session"
FAIL_SOURCE_SHA = "source_sha_unbound"

_ISO_CREATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")

# The pinned source SHA must actually CONTAIN the gate's own tooling.
# ``git diff --quiet`` alone cannot see untracked files, so a pin whose
# scripts were never committed (or were added after the pin) would pass the
# worktree check while the gate that produced the verdict is absent from the
# SHA.  Each repo-relative path must resolve inside the pinned commit.
SOURCE_SHA_GATE_FILES = (
    "scripts/fixer_recovery_baseline.py",
    "scripts/fixer_recovery_predeploy.py",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class PredeployError(ValueError):
    """The verdict cannot be computed from the given inputs."""


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PredeployError(f"{label}: unreadable JSON {path}: {exc}") from exc


def _iter_captured_files(baseline: Mapping[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """Yield ``(source_kind, file_record)`` for every captured file."""
    sources = baseline.get("sources") if isinstance(baseline.get("sources"), dict) else {}
    for kind, source in sources.items():
        if not isinstance(source, dict):
            continue
        for record in source.get("files", []):
            if isinstance(record, dict):
                yield kind, record
    ledger = baseline.get("ledger")
    if isinstance(ledger, dict):
        for record in ledger.get("files", []):
            if isinstance(record, dict):
                yield "ledger", record
    initiative = baseline.get("initiative")
    if isinstance(initiative, dict):
        for record in initiative.get("files", []):
            if isinstance(record, dict):
                yield "initiative", record


# ── individual checks ───────────────────────────────────────────────────────


def check_baseline_proof(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Load + validate the envelope and its content address.  Fail-closed."""
    detail: dict[str, Any] = {"path": str(path), "valid": False}
    try:
        baseline = _load_json(path, "baseline")
    except PredeployError as exc:
        detail["error"] = str(exc)
        return detail, None
    if not isinstance(baseline, dict):
        detail["error"] = "baseline is not a JSON object"
        return detail, None
    if baseline.get("schema") != BASELINE_SCHEMA:
        detail["error"] = f"baseline schema mismatch: {baseline.get('schema')!r}"
        return detail, None
    recomputed = _recompute_baseline_digest(baseline)
    recorded = ""
    root = baseline.get("root")
    if isinstance(root, dict):
        recorded = str(root.get("content_sha256") or "")
    if not recorded or recorded != recomputed:
        detail["error"] = (
            f"baseline content address mismatch: recorded {recorded!r} != "
            f"recomputed {recomputed!r}"
        )
        return detail, None
    baseline_id = str(baseline.get("baseline_id") or "")
    if baseline_id != recomputed:
        detail["error"] = (
            f"baseline_id mismatch: recorded {baseline_id!r} != content address {recomputed!r}"
        )
        return detail, None
    detail["valid"] = True
    detail["content_sha256"] = recomputed
    return detail, baseline


def _recompute_baseline_digest(baseline: Mapping[str, Any]) -> str:
    clone = json.loads(json.dumps(baseline, sort_keys=True))
    clone.pop("baseline_id", None)
    clone.pop("captured_at", None)
    root = clone.get("root")
    if isinstance(root, dict):
        root.pop("content_sha256", None)
    return _digest(clone)


def check_source_proof(baseline: Mapping[str, Any]) -> dict[str, Any]:
    """Every captured file must still exist with its recorded content SHA."""
    missing: list[str] = []
    mismatched: list[str] = []
    for kind, record in _iter_captured_files(baseline):
        path = Path(record["path"])
        if not path.is_file():
            missing.append(f"{kind}:{record['path']}")
            continue
        try:
            observed = _sha256_file(path)
        except OSError as exc:
            missing.append(f"{kind}:{record['path']} ({exc})")
            continue
        if observed != record.get("content_sha256"):
            mismatched.append(f"{kind}:{record['path']}")

    ref_drift: list[str] = []
    reconcile = baseline.get("sources", {}).get("reconcile")
    if isinstance(reconcile, dict):
        git_root = Path(str(reconcile.get("git_root") or "")).expanduser()
        if not git_root.is_dir():
            ref_drift.append(f"reconcile:git_root_missing:{git_root}")
        else:
            resolved = _resolve_refs(git_root, tuple(reconcile.get("reconcile_refs") or ()))
            for recorded_ref in reconcile.get("refs", []):
                if not isinstance(recorded_ref, dict):
                    continue
                refname = str(recorded_ref.get("refname") or "")
                recorded_present = bool(recorded_ref.get("objectname"))
                live = [ref for ref in resolved if ref["refname"] == refname]
                if recorded_present and not live:
                    ref_drift.append(f"reconcile:ref_gone:{refname}")
                elif recorded_present and live[0]["objectname"] != recorded_ref["objectname"]:
                    ref_drift.append(f"reconcile:ref_moved:{refname}")
                elif not recorded_present and live:
                    ref_drift.append(f"reconcile:ref_appeared:{refname}")

    return {
        "passed": not missing and not mismatched and not ref_drift,
        "missing": missing,
        "mismatched": mismatched,
        "reconcile_ref_drift": ref_drift,
    }


def _resolve_refs(git_root: Path, patterns: Sequence[str]) -> list[dict[str, Any]]:
    command = [
        "git",
        "-C",
        str(git_root),
        "for-each-ref",
        "--format=%(refname)%00%(objectname)",
    ] + list(patterns)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    refs: list[dict[str, Any]] = []
    if result.returncode != 0:
        return refs
    for line in result.stdout.splitlines():
        if not line:
            continue
        refname, sep, objectname = line.partition("\x00")
        if sep:
            refs.append({"refname": refname, "objectname": objectname.strip()})
    return refs


def check_window_integrity(baseline: Mapping[str, Any]) -> dict[str, Any]:
    """The envelope must be free of torn and overlapping half-open windows."""
    torn: list[str] = []
    unordered: list[str] = []
    windows = baseline.get("windows")
    if not isinstance(windows, dict):
        return {"passed": False, "torn": ["<missing windows index>"], "unordered": []}
    for source, window in windows.items():
        if not isinstance(window, dict):
            torn.append(source)
            continue
        if window.get("torn"):
            torn.append(source)
        if not window.get("ordered"):
            unordered.append(source)
    overlaps = baseline.get("overlaps")
    if not isinstance(overlaps, list):
        overlaps = []
    return {
        "passed": not torn and not unordered and not overlaps,
        "torn": torn,
        "unordered": unordered,
        "overlaps": [item.get("path") for item in overlaps if isinstance(item, dict)],
    }


def check_canonical_router(baseline: Mapping[str, Any]) -> dict[str, Any]:
    router = baseline.get("router")
    if not isinstance(router, dict):
        return {"passed": False, "violations": ["<missing router>"]}
    violations = router.get("violations")
    if not isinstance(violations, list):
        return {"passed": False, "violations": ["<malformed router>"]}
    return {"passed": not violations and router.get("canonical_only") is True, "violations": violations}


def check_mixed_versions(baseline: Mapping[str, Any], source_sha: str) -> dict[str, Any]:
    """The engine lineage must be exactly the approved source SHA."""
    if not _FULL_SHA_RE.match(source_sha):
        return {
            "passed": False,
            "lineage": [],
            "observed": [f"<invalid source_sha {source_sha!r}>"],
        }
    root = baseline.get("root")
    lineage: list[str] = []
    if isinstance(root, dict):
        lineage_root = root.get("lineage")
        if isinstance(lineage_root, dict):
            engine = lineage_root.get("engine")
            if isinstance(engine, list):
                lineage = [str(item) for item in engine if isinstance(item, str)]

    runtime = baseline.get("sources", {}).get("runtime")
    manifest_head = ""
    if isinstance(runtime, dict):
        parsed = runtime.get("parsed")
        if isinstance(parsed, dict):
            manifest_head = str(parsed.get("epic", {}).get("expected_head") or "")

    observed = sorted(set([*lineage, source_sha]))
    return {
        "passed": (
            observed == [source_sha]
            and bool(manifest_head)
            and manifest_head == source_sha
        ),
        "lineage": sorted(set(lineage)),
        "observed": observed,
        "manifest_expected_head": manifest_head,
        "source_sha": source_sha,
    }


def _launch_path_files(baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    sources = baseline.get("sources")
    if isinstance(sources, dict):
        for kind in ("runtime", "schedule"):
            source = sources.get(kind)
            if isinstance(source, dict):
                files.extend(
                    record for record in source.get("files", []) if isinstance(record, dict)
                )
    return files


def check_selectors(baseline: Mapping[str, Any]) -> dict[str, Any]:
    """Retired selectors must be absent from launch-path files and the env."""
    hits: list[dict[str, str]] = []
    for record in _launch_path_files(baseline):
        try:
            data = Path(record["path"]).read_bytes()
        except OSError:
            continue
        for token in RETIRED_SELECTOR_TOKENS:
            if token.encode("utf-8") in data:
                hits.append({"path": record["path"], "token": token})
    env_hits = [
        {"env": name}
        for name in RETIRED_SELECTOR_TOKENS
        if os.environ.get(name)
    ]
    return {"passed": not hits and not env_hits, "file_hits": hits, "env_hits": env_hits}


def check_editable_install(baseline: Mapping[str, Any]) -> dict[str, Any]:
    """The T-0301 dependency generation must be the only venv in the launch path."""
    findings: list[str] = []
    runtime = baseline.get("sources", {}).get("runtime")
    if not isinstance(runtime, dict):
        return {"passed": False, "findings": ["<missing runtime source>"]}
    parsed = runtime.get("parsed")
    if not isinstance(parsed, dict):
        return {"passed": False, "findings": ["<missing runtime parsed>"]}

    epic = parsed.get("epic")
    if not isinstance(epic, dict):
        return {"passed": False, "findings": ["<missing runtime epic>"]}

    generation = epic.get("dependency_generation")
    if not isinstance(generation, dict):
        findings.append("dependency_generation proof missing")
    else:
        generation_id = str(generation.get("id") or "")
        frozen_spec = str(generation.get("frozen_spec_sha256") or "")
        interpreter = str(generation.get("interpreter_path") or "")
        venv_digest = str(generation.get("venv_digest") or "")
        created = str(generation.get("created") or "")
        if not _FULL_SHA256_RE.match(generation_id):
            findings.append("dependency_generation.id not a 64-hex sha256")
        if generation_id != frozen_spec:
            findings.append("dependency_generation.id != frozen_spec_sha256")
        if not _FULL_SHA256_RE.match(venv_digest):
            findings.append("dependency_generation.venv_digest not a 64-hex sha256")
        if not interpreter or not Path(interpreter).expanduser().is_absolute():
            findings.append("dependency_generation.interpreter_path not an absolute path")
        if not created or not _ISO_CREATED_RE.match(created):
            findings.append("dependency_generation.created not a UTC ISO timestamp")
        if interpreter and not Path(interpreter).expanduser().is_file():
            findings.append(f"generation interpreter missing: {interpreter}")

    runtime_root = Path(str(epic.get("runtime_root") or "")).expanduser().resolve(strict=False)
    venv_path = str(epic.get("venv_path") or "").strip()
    if not runtime_root.is_dir():
        findings.append(f"runtime_root missing: {runtime_root}")
    else:
        if (runtime_root / RUNTIME_VENV_DIR_NAME).is_dir():
            findings.append(f"<runtime>/.venv present under {runtime_root}")
        if venv_path:
            venv_resolved = Path(venv_path).expanduser().resolve(strict=False)
            if venv_resolved.is_relative_to(runtime_root):
                findings.append(f"venv_path inside runtime_root (per-epic venv): {venv_path}")
        else:
            findings.append("epic.venv_path empty")

    base = parsed.get("base")
    if isinstance(base, dict) and str(base.get("editable_install_path") or "").strip():
        findings.append(
            f"base.editable_install_path non-empty: {base.get('editable_install_path')}"
        )

    wrapper = runtime.get("wrapper")
    if not isinstance(wrapper, dict) or not wrapper.get("present"):
        findings.append("runtime repair_bin wrapper missing")

    residue = baseline.get("editable_residue")
    residue_hits = residue.get("hits") if isinstance(residue, dict) else []
    if isinstance(residue_hits, list) and residue_hits:
        findings.append(f"pip install -e residue in launch path: {len(residue_hits)} hit(s)")

    return {"passed": not findings, "findings": findings}


def check_ledger_bypass(baseline: Mapping[str, Any]) -> dict[str, Any]:
    ledger = baseline.get("ledger")
    if not isinstance(ledger, dict):
        return {"passed": False, "violations": ["<missing ledger source>"]}
    violations = ledger.get("violations")
    if not isinstance(violations, list):
        return {"passed": False, "violations": ["<malformed ledger>"]}
    return {"passed": not violations, "violations": violations}


def check_initiative_snapshot(
    baseline: Mapping[str, Any],
    initiative_dir: Path,
    git_root: Path | None = None,
) -> dict[str, Any]:
    """Chain.yaml, NORTHSTAR.md, and chain briefs must be unchanged since capture.

    Files are re-resolved exactly like capture: chain.yaml / NORTHSTAR.md
    live under the recorded initiative dir, while chain-referenced briefs may
    be REPO-RELATIVE (the live ``chain.yaml`` shape: ``git_root / idea``).
    A repo-relative brief is re-resolved against the recorded git root (or
    the ``git_root`` override), so the live repo-relative shape passes here
    instead of being flagged as outside the initiative dir.
    """
    initiative = baseline.get("initiative")
    if not isinstance(initiative, dict):
        return {"passed": False, "drifted": ["<missing initiative source>"], "missing": []}
    recorded_dir = Path(str(initiative.get("initiative_dir") or "")).expanduser().resolve(strict=False)
    live_dir = initiative_dir.expanduser().resolve(strict=False) if initiative_dir else recorded_dir

    reconcile = baseline.get("sources", {}).get("reconcile")
    recorded_git_root = (
        Path(str(reconcile.get("git_root") or "")).expanduser().resolve(strict=False)
        if isinstance(reconcile, dict)
        else None
    )
    live_git_root = (
        git_root.expanduser().resolve(strict=False) if git_root else recorded_git_root
    )

    drifted: list[str] = []
    missing: list[str] = []
    for record in initiative.get("files", []):
        if not isinstance(record, dict):
            continue
        recorded_path = Path(record["path"]).expanduser().resolve(strict=False)
        live_path: Path | None = None
        try:
            relative = recorded_path.relative_to(recorded_dir)
            live_path = live_dir / relative
        except ValueError:
            if recorded_git_root is not None:
                try:
                    relative = recorded_path.relative_to(recorded_git_root)
                    live_path = live_git_root / relative
                except ValueError:
                    live_path = None
        if live_path is None:
            drifted.append(
                f"{recorded_path}: outside recorded initiative dir and git root"
            )
            continue
        live_path = live_path.expanduser().resolve(strict=False)
        if not live_path.is_file():
            missing.append(str(live_path))
            continue
        try:
            observed = _sha256_file(live_path)
        except OSError as exc:
            missing.append(f"{live_path} ({exc})")
            continue
        if observed != record.get("content_sha256"):
            drifted.append(str(relative))
    return {"passed": not drifted and not missing, "drifted": drifted, "missing": missing}


def check_pinned_target(
    baseline: Mapping[str, Any],
    session: str,
    plan: str,
    chain_record: str,
) -> dict[str, Any]:
    """The envelope must pin EXACTLY the expected session/plan/chain record."""
    problems: list[str] = []
    pinned = baseline.get("pinned")
    if not isinstance(pinned, dict):
        return {"passed": False, "problems": ["<envelope carries no pinned target>"]}
    if str(pinned.get("session") or "") != session:
        problems.append(
            f"session mismatch: envelope {pinned.get('session')!r} != expected {session!r}"
        )
    if str(pinned.get("plan") or "") != plan:
        problems.append(
            f"plan mismatch: envelope {pinned.get('plan')!r} != expected {plan!r}"
        )
    if str(pinned.get("chain_record") or "") != chain_record:
        problems.append(
            f"chain_record mismatch: envelope {pinned.get('chain_record')!r} "
            f"!= expected {chain_record!r}"
        )

    session_source = baseline.get("sources", {}).get("session")
    if isinstance(session_source, dict):
        captured_sessions = session_source.get("sessions")
        if captured_sessions != [session]:
            problems.append(
                f"session lineage mismatch: captured {captured_sessions!r} != [{session!r}]"
            )
    else:
        problems.append("<missing session source>")

    chain_source = baseline.get("sources", {}).get("chain")
    if isinstance(chain_source, dict):
        if str(chain_source.get("chain_record") or "") != chain_record:
            problems.append(
                f"chain lineage mismatch: captured {chain_source.get('chain_record')!r} "
                f"!= [{chain_record!r}]"
            )
    else:
        problems.append("<missing chain source>")

    ledger = baseline.get("ledger")
    ledger_files = ledger.get("files") if isinstance(ledger, dict) else []
    if not ledger_files:
        problems.append("plan state missing from captured ledger")
    elif not any(
        isinstance(record, dict) and plan in str(record.get("path") or "")
        for record in ledger_files
    ):
        problems.append(f"captured ledger does not reference plan {plan!r}")

    return {"passed": not problems, "problems": problems}


def check_session_current(baseline: Mapping[str, Any]) -> dict[str, Any]:
    """The pinned session must be classified ``current`` by its liveness."""
    session_source = baseline.get("sources", {}).get("session")
    if not isinstance(session_source, dict):
        return {
            "passed": False,
            "status": "unknown",
            "detail": "<missing session source>",
        }
    classification = session_source.get("classification")
    if not isinstance(classification, dict):
        return {
            "passed": False,
            "status": "unknown",
            "detail": "<missing session classification>",
        }
    status = str(classification.get("status") or "unknown")
    detail = json.dumps(
        {
            "latest_activity": classification.get("latest_activity"),
            "latest_source": classification.get("latest_source"),
            "stale_statuses": classification.get("stale_statuses"),
        },
        sort_keys=True,
    )
    return {"passed": status == "current", "status": status, "detail": detail}


def check_source_sha_bound(
    baseline: Mapping[str, Any],
    source_sha: str,
    git_root: Path | None,
) -> dict[str, Any]:
    """``--source-sha`` must be a real commit whose tree matches the worktree."""
    detail: dict[str, Any] = {"source_sha": source_sha}
    if not _FULL_SHA_RE.match(source_sha):
        detail["error"] = f"source_sha is not a 40-hex SHA: {source_sha!r}"
        return {"passed": False, "detail": detail}
    root = git_root
    if root is None:
        reconcile = baseline.get("sources", {}).get("reconcile")
        if isinstance(reconcile, dict):
            root = Path(str(reconcile.get("git_root") or ""))
    root = root.expanduser().resolve(strict=False) if root else None
    if root is None or not root.is_dir():
        detail["error"] = f"git root unavailable for source binding: {root}"
        return {"passed": False, "detail": detail}
    detail["git_root"] = str(root)
    verify = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"{source_sha}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if verify.returncode != 0:
        detail["error"] = f"{source_sha} does not resolve to a commit in {root}"
        return {"passed": False, "detail": detail}
    resolved = verify.stdout.strip().splitlines()[-1] if verify.stdout.strip() else source_sha
    detail["resolved"] = resolved
    tree = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", source_sha],
        capture_output=True,
        text=True,
        check=False,
    )
    if tree.returncode != 0:
        detail["error"] = (
            f"working tree differs from {source_sha} (git diff exit {tree.returncode})"
        )
        return {"passed": False, "detail": detail}
    detail["tree_matches"] = True
    # The pin must CONTAIN the gate tooling itself (untracked files are
    # invisible to ``git diff``); an un-committed gate cannot be trusted to
    # have produced the baseline under this SHA.
    missing_gate = [
        relative
        for relative in SOURCE_SHA_GATE_FILES
        if subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{resolved}:{relative}"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        != 0
    ]
    if missing_gate:
        detail["missing_gate_files"] = missing_gate
        detail["error"] = (
            f"{source_sha} does not contain the gate tooling: "
            + ", ".join(missing_gate)
        )
        return {"passed": False, "detail": detail}
    detail["gate_files_present"] = True
    return {"passed": True, "detail": detail}


# ── verdict assembly ────────────────────────────────────────────────────────


def run_predeploy(
    baseline_path: Path,
    source_sha: str,
    *,
    initiative_dir: Path | None = None,
    git_root: Path | None = None,
    session: str = DEFAULT_SESSION,
    plan: str = DEFAULT_PLAN,
    chain_record: str = DEFAULT_CHAIN_RECORD,
) -> dict[str, Any]:
    """Compute the fail-closed predeploy verdict from a captured baseline."""
    checks: dict[str, Any] = {}
    reasons: list[dict[str, str]] = []

    baseline_proof, baseline = check_baseline_proof(baseline_path)
    checks["baseline_proof"] = {
        "passed": baseline_proof["valid"],
        "detail": baseline_proof.get("error", "ok"),
    }
    if baseline is None:
        reasons.append({"code": FAIL_INVALID_BASELINE, "detail": baseline_proof.get("error", "invalid baseline")})
        return _verdict_payload(checks, reasons, baseline_path, source_sha, None)

    checks["pinned_target"] = check_pinned_target(baseline, session, plan, chain_record)
    if not checks["pinned_target"]["passed"]:
        reasons.append(
            {
                "code": FAIL_NOT_PINNED,
                "detail": "; ".join(checks["pinned_target"]["problems"]),
            }
        )

    checks["session_current"] = check_session_current(baseline)
    if not checks["session_current"]["passed"]:
        reasons.append(
            {
                "code": FAIL_STALE_SESSION,
                "detail": (
                    "status=" + str(checks["session_current"].get("status") or "unknown")
                    + " " + str(checks["session_current"].get("detail") or "")
                ),
            }
        )

    checks["source_sha_bound"] = check_source_sha_bound(baseline, source_sha, git_root)
    if not checks["source_sha_bound"]["passed"]:
        reasons.append(
            {
                "code": FAIL_SOURCE_SHA,
                "detail": json.dumps(checks["source_sha_bound"]["detail"], sort_keys=True),
            }
        )

    checks["source_proof"] = check_source_proof(baseline)
    if not checks["source_proof"]["passed"]:
        reasons.append(
            {
                "code": FAIL_MISSING_PROOF,
                "detail": _summarize_source_proof(checks["source_proof"]),
            }
        )

    checks["window_integrity"] = check_window_integrity(baseline)
    if not checks["window_integrity"]["passed"]:
        reasons.append(
            {
                "code": FAIL_INCOHERENT_CAPTURE,
                "detail": (
                    "torn=" + ",".join(checks["window_integrity"]["torn"])
                    + " overlaps=" + ",".join(checks["window_integrity"]["overlaps"])
                ),
            }
        )

    checks["canonical_router"] = check_canonical_router(baseline)
    if not checks["canonical_router"]["passed"]:
        reasons.append(
            {
                "code": FAIL_NON_CANONICAL_ACTION,
                "detail": json.dumps(checks["canonical_router"]["violations"], sort_keys=True),
            }
        )

    checks["mixed_versions"] = check_mixed_versions(baseline, source_sha)
    if not checks["mixed_versions"]["passed"]:
        reasons.append(
            {
                "code": FAIL_MIXED_VERSIONS,
                "detail": (
                    "observed lineage=" + ",".join(checks["mixed_versions"]["observed"])
                    + f" expected={source_sha}"
                    + " manifest_expected_head="
                    + str(checks["mixed_versions"].get("manifest_expected_head") or "")
                ),
            }
        )

    checks["selectors"] = check_selectors(baseline)
    if not checks["selectors"]["passed"]:
        reasons.append(
            {
                "code": FAIL_SELECTORS,
                "detail": json.dumps(
                    {
                        "file_hits": checks["selectors"]["file_hits"],
                        "env_hits": checks["selectors"]["env_hits"],
                    },
                    sort_keys=True,
                ),
            }
        )

    checks["editable_install"] = check_editable_install(baseline)
    if not checks["editable_install"]["passed"]:
        reasons.append(
            {
                "code": FAIL_EDITABLE_INSTALL,
                "detail": "; ".join(checks["editable_install"]["findings"]),
            }
        )

    checks["ledger_bypass"] = check_ledger_bypass(baseline)
    if not checks["ledger_bypass"]["passed"]:
        reasons.append(
            {
                "code": FAIL_LEDGER_BYPASS,
                "detail": json.dumps(checks["ledger_bypass"]["violations"], sort_keys=True),
            }
        )

    live_initiative_dir = initiative_dir or Path(str(baseline.get("initiative", {}).get("initiative_dir") or ""))
    checks["initiative_snapshot"] = check_initiative_snapshot(
        baseline, live_initiative_dir, git_root=git_root
    )
    if not checks["initiative_snapshot"]["passed"]:
        reasons.append(
            {
                "code": FAIL_UNSNAPSHOTTED_INPUTS,
                "detail": (
                    "drifted=" + ",".join(checks["initiative_snapshot"]["drifted"])
                    + " missing=" + ",".join(checks["initiative_snapshot"]["missing"])
                ),
            }
        )

    return _verdict_payload(checks, reasons, baseline_path, source_sha, baseline)


def _summarize_source_proof(proof: Mapping[str, Any]) -> str:
    parts = []
    if proof.get("missing"):
        parts.append("missing=" + ",".join(proof["missing"]))
    if proof.get("mismatched"):
        parts.append("mismatched=" + ",".join(proof["mismatched"]))
    if proof.get("reconcile_ref_drift"):
        parts.append("reconcile_ref_drift=" + ",".join(proof["reconcile_ref_drift"]))
    return "; ".join(parts)


def _verdict_payload(
    checks: Mapping[str, Any],
    reasons: list[dict[str, str]],
    baseline_path: Path,
    source_sha: str,
    baseline: Mapping[str, Any] | None,
) -> dict[str, Any]:
    verdict = "PASS" if not reasons else "FAIL"
    baseline_id = str(baseline.get("baseline_id") or "") if baseline else ""
    payload = {
        "schema": PREDEPLOY_SCHEMA,
        "verdict": verdict,
        "reasons": reasons,
        "baseline_id": baseline_id,
        "baseline_path": str(baseline_path),
        "source_sha": source_sha,
        "checks": dict(checks),
    }
    content_sha256 = _digest(payload)
    payload["content_sha256"] = content_sha256
    payload["checked_at"] = _utc_now()
    return payload


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="baseline envelope JSON (fixer_recovery_baseline.py --out)")
    parser.add_argument("--source-sha", required=True, help="G13-approved 40-hex source SHA (must resolve to a commit in the repo)")
    parser.add_argument("--initiative-dir", default=None, help="override initiative dir (default: recorded in baseline)")
    parser.add_argument("--git-root", default=None, help="git root for --source-sha binding (default: recorded in baseline)")
    parser.add_argument("--session", default=DEFAULT_SESSION, help=f"expected pinned session (default: {DEFAULT_SESSION})")
    parser.add_argument("--plan", default=DEFAULT_PLAN, help=f"expected pinned plan (default: {DEFAULT_PLAN})")
    parser.add_argument("--chain-record", default=DEFAULT_CHAIN_RECORD, help=f"expected pinned chain record (default: {DEFAULT_CHAIN_RECORD})")
    parser.add_argument("--evidence-dir", default="docs/fixer-recovery-evidence", help="verdict receipt directory")
    parser.add_argument("--no-write", action="store_true", help="collector mode: print verdict, write nothing")
    args = parser.parse_args(argv)

    try:
        verdict = run_predeploy(
            Path(args.baseline),
            args.source_sha,
            initiative_dir=Path(args.initiative_dir) if args.initiative_dir else None,
            git_root=Path(args.git_root) if args.git_root else None,
            session=args.session,
            plan=args.plan,
            chain_record=args.chain_record,
        )
    except PredeployError as exc:
        print(f"predeploy: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(verdict, indent=2, sort_keys=True)
    if args.no_write:
        print(rendered)
        return 0 if verdict["verdict"] == "PASS" else 1

    evidence_dir = Path(args.evidence_dir).expanduser().resolve(strict=False)
    receipt_path = evidence_dir / VERDICT_RECEIPT_NAME
    _atomic_write(receipt_path, verdict)
    print(rendered)
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
