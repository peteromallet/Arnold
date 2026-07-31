"""Static gates for cloud wrapper authority-risk bypasses."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETED_WRAPPERS = {
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop",
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop",
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-supervise",
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog",
}
GATED_CALL_RE = re.compile(
    r"authority_(?:gap_continue|fail_closed|gap_record)\s+\"(T29-BYPASS-\d+)\""
)
EXPECTED_AUTHORITY_RISK_IDS = {
    f"T29-BYPASS-{number:03d}"
    for number in (
        24,
        25,
        30,
        31,
        *range(33, 39),
        *range(40, 45),
        56,
        59,
        61,
        *range(63, 68),
        74,
        75,
        *range(77, 80),
        *range(90, 93),
        *range(95, 117),
        *range(121, 125),
        *range(126, 129),
        *range(131, 134),
        136,
        140,
        142,
        *range(144, 150),
        *range(151, 165),
        177,
        *range(180, 206),
        207,
        208,
        *range(212, 215),
    )
} - {"T29-BYPASS-163"}


def test_authority_risk_bypass_audit_entries_are_typed_or_fail_closed() -> None:
    gated_ids: set[str] = set()
    for module_path in TARGETED_WRAPPERS:
        text = (REPO_ROOT / module_path).read_text(encoding="utf-8")
        assert "schema_version\": \"arnold.megaplan.cloud.wrapper_authority_gap.v1\"" in text
        gated_ids.update(GATED_CALL_RE.findall(text))

    assert EXPECTED_AUTHORITY_RISK_IDS <= gated_ids


def test_no_audited_authority_risk_id_is_silenced_with_naked_true() -> None:
    for module_path in TARGETED_WRAPPERS:
        for line_number, line in enumerate(
            (REPO_ROOT / module_path).read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if "T29-BYPASS-" not in line:
                continue
            assert "|| true" not in line, f"{module_path}:{line_number}: {line}"
            assert "authority_gap_continue" in line or "authority_fail_closed" in line or "authority_gap_record" in line


def test_non_authoritative_cleanup_best_effort_remains_allowed() -> None:
    examples = {
        "arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-resident": (
            'docker exec "$CONTAINER" tmux kill-session -t "$SESSION" >/dev/null 2>&1 || true'
        ),
        "arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog": (
            'docker exec "$CONTAINER" bash -lc "tmux kill-session -t watchdog 2>/dev/null || true"'
        ),
        "arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl": (
            'arnold config set execution.auto_approve true >/dev/null 2>&1 || true'
        ),
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat": (
            "pids=$(pgrep -f 'codex exec' || true)"
        ),
    }
    for module_path, snippet in examples.items():
        assert snippet in (REPO_ROOT / module_path).read_text(encoding="utf-8")


# ── T43: Step 81-85 systemd / deploy / hot-upload materializer gates ────────

_LEGACY_REPAIR_BINS = (
    "/usr/local/bin/arnold-watchdog",
    "/usr/local/bin/arnold-heartbeat",
    "/usr/local/bin/arnold-repair-trigger",
    "/usr/local/bin/arnold-repair-loop",
    "/usr/local/bin/arnold-meta-repair-loop",
    "/usr/local/bin/arnold-progress-auditor",
    "/usr/local/bin/arnold-supervise",
    "/usr/local/bin/arnold-kimi-goal-operator",
    "/usr/local/bin/mp-refresh-megaplan",
)

_CANONICAL_WORKSPACE_PREFIX = "/workspace/arnold/arnold_pipelines/megaplan/cloud/"


def _systemd_execstart_lines(unit_path: str) -> list[str]:
    return [
        line.strip()
        for line in (REPO_ROOT / unit_path).read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("ExecStart=")
    ]


def test_repair_trigger_systemd_uses_canonical_delegation() -> None:
    """Step 81: repair-trigger systemd units execute only canonical delegation."""
    service_text = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service"
    ).read_text(encoding="utf-8")

    # The service must use the canonical workspace wrapper path (not a legacy
    # /usr/local/bin binary), delegated through the supervisor python.
    assert "/workspace/arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger" in service_text
    assert "MEGAPLAN_SUPERVISOR_PYTHON" in service_text

    # No legacy repair bin paths may appear in the ExecStart line.
    exec_lines = _systemd_execstart_lines(
        "arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service"
    )
    for line in exec_lines:
        for legacy in _LEGACY_REPAIR_BINS:
            assert legacy not in line, f"legacy bin {legacy!r} found in repair-trigger service: {line}"

    # The path unit monitors the workspace repair-queue, which is correct.
    path_text = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.path"
    ).read_text(encoding="utf-8")
    assert "DirectoryNotEmpty=/workspace/.megaplan/repair-queue/requests" in path_text


def test_progress_audit_systemd_is_three_hour_reconciliation_only() -> None:
    """Step 82: progress-audit systemd uses three-hour reconciliation only."""
    timer_text = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.timer"
    ).read_text(encoding="utf-8")
    service_text = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.service"
    ).read_text(encoding="utf-8")

    # Timer must use OnUnitActiveSec=3h (next-three-hour reconciliation).
    assert "OnUnitActiveSec=3h" in timer_text

    # Service description must reference next-three-hour, not six-hour.
    assert "next-three-hour" in service_text.lower() or "3h" in service_text.lower()

    # Service must use the workspace checkout wrapper path, not a legacy binary.
    assert "/workspace/arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor" in service_text

    # No legacy repair bin paths in ExecStart.
    exec_lines = _systemd_execstart_lines(
        "arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.service"
    )
    for line in exec_lines:
        for legacy in _LEGACY_REPAIR_BINS:
            assert legacy not in line, f"legacy bin {legacy!r} found in progress-audit service: {line}"


def test_hot_upload_rejects_legacy_bins_and_session_commands() -> None:
    """Step 85: hot-upload rejects legacy-bin destinations and caller session commands."""
    import importlib.util
    import sys

    # Load the hot-upload module to verify its constants and guards.
    spec = importlib.util.spec_from_file_location(
        "cloud_hot_upload",
        REPO_ROOT / "scripts/cloud_hot_upload.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["cloud_hot_upload"] = module
    spec.loader.exec_module(module)

    # KNOWN_SESSION_COMMANDS must use canonical workspace paths, not legacy bins.
    for session_name, command in module.KNOWN_SESSION_COMMANDS.items():
        assert command not in module.FORBIDDEN_LEGACY_BIN_PATHS, (
            f"KNOWN_SESSION_COMMANDS[{session_name!r}] = {command!r} is a forbidden legacy bin"
        )
        assert command.startswith("/workspace/arnold/"), (
            f"KNOWN_SESSION_COMMANDS[{session_name!r}] = {command!r} must use workspace path"
        )

    # FORBIDDEN_LEGACY_BIN_PATHS covers all known legacy repair surfaces.
    for legacy in _LEGACY_REPAIR_BINS:
        is_covered = legacy in module.FORBIDDEN_LEGACY_BIN_PATHS or any(
            legacy.startswith(prefix) for prefix in module.FORBIDDEN_LEGACY_BIN_PREFIXES
        )
        assert is_covered, f"legacy bin {legacy!r} not covered by forbidden lists"

    # _is_forbidden_legacy_bin rejects all known legacy bins.
    for legacy in _LEGACY_REPAIR_BINS:
        assert module._is_forbidden_legacy_bin(legacy), (
            f"_is_forbidden_legacy_bin should reject {legacy!r}"
        )

    # _is_forbidden_legacy_bin accepts canonical workspace paths.
    assert not module._is_forbidden_legacy_bin(
        "/workspace/arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    )
    assert not module._is_forbidden_legacy_bin("/usr/local/bin/some-other-tool")

    # parse_session_commands rejects caller-supplied legacy commands.
    try:
        module.parse_session_commands(["custom=/usr/local/bin/arnold-watchdog"])
        raise AssertionError("expected HotUploadError for legacy session command")
    except module.HotUploadError:
        pass

    # parse_session_commands accepts non-legacy commands.
    result = module.parse_session_commands(["custom=/workspace/arnold/some/tool"])
    assert result["custom"] == "/workspace/arnold/some/tool"

    # parse_upload rejects legacy-bin destinations.
    try:
        module.parse_upload("local.txt:/usr/local/bin/arnold-watchdog")
        raise AssertionError("expected HotUploadError for legacy upload destination")
    except module.HotUploadError:
        pass

    # parse_upload accepts non-legacy destinations.
    upload = module.parse_upload("local.txt:/workspace/arnold/some/file")
    assert upload.dest == "/workspace/arnold/some/file"
