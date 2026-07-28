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
