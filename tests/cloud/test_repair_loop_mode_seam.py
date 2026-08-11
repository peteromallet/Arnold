"""Phase 3A seam tests for `arnold-repair-loop --mode=reactive|proactive`.

Covers the single entry seam added by the fixer-unification design: the
--mode flag, the --dry-run path (pure read of inputs: no locks, no marker
mutation, no agent spawn, no git), the mode model policy, and the proactive
NO-OP guard.  Only safe paths are executed: --dry-run invocations plus
bash -n; everything else is asserted against the script text.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPAIR_LOOP = (
    REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-repair-loop"
)

# Test-only escape hatch documented in the wrapper: skip the immutable
# snapshot self-copy so tests execute the checked-out script directly.
_SKIP_ENV = {"ARNOLD_REPAIR_LOOP_SKIP_SELF_COPY": "1"}


def _write_allow_manifestless_policy(tmp_path: Path) -> Path:
    """A valid unexpired allow_manifestless permit sidecar.

    These tests exercise the mode/dry-run seam, NOT admission: since the P1
    admission kernel (G2 correction 3) the repair-loop entry gate requires a
    valid permit for manifestless invocations, so every subprocess run pins
    ``ARNOLD_RUNTIME_POLICY`` to a freshly-written sidecar.
    """
    now = datetime.now(timezone.utc)
    policy = {
        "permits": [
            {
                "kind": "allow_manifestless",
                "id": "permit-mode-seam-1",
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "actor": "mode-seam-test",
                "reason": "mode-seam dry-run harness (admission not under test)",
                "evidence": ["mode-seam harness injects a valid permit"],
                "chain_digest": "deadbeef" * 4,
            }
        ]
    }
    policy_path = tmp_path / ".runtime_policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return policy_path


def _policy_env(tmp_path: Path) -> dict[str, str]:
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    env["ARNOLD_RUNTIME_POLICY"] = str(_write_allow_manifestless_policy(tmp_path))
    env.pop("ARNOLD_RUNTIME_MANIFEST", None)
    # These tests exercise the mode/dry-run seam, not runtime selection.  The
    # box launch env injects runtime-source overrides (MEGAPLAN_RUNTIME_SRC /
    # CLOUD_WATCHDOG_ARNOLD_SRC / ARNOLD_REPAIR_RUNTIME_SRC) that point at a
    # deployed runtime candidate; pin them to the checked-out source so the
    # model-policy module resolves from this tree.
    for name in (
        "MEGAPLAN_RUNTIME_SRC",
        "MEGAPLAN_META_ARNOLD_SRC",
        "MEGAPLAN_AUDIT_ARNOLD_SRC",
        "MEGAPLAN_LAUNCH_RUNTIME_SRC",
        "CLOUD_WATCHDOG_ARNOLD_SRC",
        "ARNOLD_REPAIR_RUNTIME_SRC",
    ):
        env.pop(name, None)
    env["MEGAPLAN_RUNTIME_SRC"] = str(REPO_ROOT)
    env["CLOUD_WATCHDOG_ARNOLD_SRC"] = str(REPO_ROOT)
    return env


def _script_text() -> str:
    return REPAIR_LOOP.read_text(encoding="utf-8")


def _run_dry_run(tmp_path: Path, *extra_args: str, skip_self_copy: bool = True) -> subprocess.CompletedProcess[str]:
    env = _policy_env(tmp_path)
    if skip_self_copy:
        env.update(_SKIP_ENV)
    return subprocess.run(
        ["bash", str(REPAIR_LOOP), *extra_args, "--dry-run", "sess-test", str(tmp_path / "ws"), "spec.yaml"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=90,
    )


def _approval_evidence(tmp_path: Path) -> Path:
    """Write a schema-bound replay-approval record (matches approve_replay)."""

    evidence = tmp_path / "replay-approval.json"
    evidence.write_text(
        "{\n"
        '  "schema_version": 1,\n'
        '  "approved": true,\n'
        '  "generated_at_utc": "2026-08-09T00:00:00+00:00",\n'
        '  "thresholds": {"unsafe_mutation_rate": 0.0},\n'
        '  "aggregate": {"unsafe_mutation_rate": 0.0},\n'
        '  "per_metric": {"unsafe_mutation_rate": {"observed": 0.0, "ok": true}}\n'
        "}\n",
        encoding="utf-8",
    )
    return evidence


def test_usage_text_documents_mode_and_dry_run() -> None:
    text = _script_text()
    assert "--mode=reactive|proactive" in text
    assert "--dry-run" in text


def test_bash_n_passes() -> None:
    result = subprocess.run(
        ["bash", "-n", str(REPAIR_LOOP)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


def test_proactive_dry_run_fails_closed_without_replay_approval(
    tmp_path: Path,
) -> None:
    """Proactive is the NEW path: without durable replay approval evidence the
    gated Flash row fails closed with a typed error instead of dry-running."""
    result = _run_dry_run(tmp_path, "--mode=proactive")
    assert result.returncode == 69
    assert "model policy" in result.stderr
    assert "gated" in result.stderr

def test_reactive_dry_run_exits_zero_with_report(tmp_path: Path) -> None:
    result = _run_dry_run(tmp_path, "--mode=reactive")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "dry-run" in result.stdout
    assert "mode=reactive" in result.stdout


def test_default_mode_is_reactive(tmp_path: Path) -> None:
    result = _run_dry_run(tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "mode=reactive" in result.stdout


def test_proactive_dry_run_works_with_self_copy_snapshot(tmp_path: Path) -> None:
    """The immutable-snapshot self-copy path must also reach the dry-run exit."""
    evidence = _approval_evidence(tmp_path)
    env = {
        **_policy_env(tmp_path),
        "FIXER_REPLAY_APPROVED": "1",
        "FIXER_REPLAY_EVIDENCE_PATH": str(evidence),
    }
    result = subprocess.run(
        ["bash", str(REPAIR_LOOP), "--mode=proactive", "--dry-run", "sess-test", str(tmp_path / "ws"), "spec.yaml"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "mode=proactive" in result.stdout
    assert "dry-run" in result.stdout


def test_select_mode_models_maps_proactive_to_flash(tmp_path: Path) -> None:
    text = _script_text()
    assert "select_mode_models" in text
    assert "resolve_policy_model" in text
    assert "fixer_model_policy" in text
    # Proactive without durable replay approval fails closed with a typed
    # error (the gated Flash row cannot be resolved from bare env).
    blocked = _run_dry_run(tmp_path, "--mode=proactive")
    assert blocked.returncode == 69
    assert "model_policy" in blocked.stderr or "gated" in blocked.stderr
    # Proactive WITH replay approval evidence projects the Flash model set.
    evidence = _approval_evidence(tmp_path)
    env = {
        **_policy_env(tmp_path),
        **_SKIP_ENV,
        "FIXER_REPLAY_APPROVED": "1",
        "FIXER_REPLAY_EVIDENCE_PATH": str(evidence),
    }
    approved = subprocess.run(
        ["bash", str(REPAIR_LOOP), "--mode=proactive", "--dry-run", "sess-test", str(tmp_path / "ws"), "spec.yaml"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert approved.returncode == 0, f"stderr: {approved.stderr}"
    assert "investigator_model=deepseek:deepseek-v4-flash" in approved.stdout
    assert "owner_model=deepseek:deepseek-v4-flash" in approved.stdout
    # Reactive keeps today's defaults untouched while Flash is still gated,
    # with a loud warning instead of a policy error.
    reactive = _run_dry_run(tmp_path, "--mode=reactive")
    assert reactive.returncode == 0, f"stderr: {reactive.stderr}"
    assert "investigator_model=gpt-5.6-sol" in reactive.stdout
    assert "brokered_investigator_model=deepseek/deepseek-v4-pro" in reactive.stdout
    assert "owner_model=gpt-5.6-sol" in reactive.stdout
    assert "model policy gated" in reactive.stderr


def test_reactive_dry_run_warns_on_hot_env_model_overrides(tmp_path: Path) -> None:
    """*_MODEL overrides are flagged (credentials-only hot-env) but reactive
    continues with a loud warning; the override never routes the models."""
    env = {
        **_policy_env(tmp_path),
        **_SKIP_ENV,
        "CLOUD_WATCHDOG_REPAIR_OWNER_MODEL": "some:override-model",
    }
    result = subprocess.run(
        ["bash", str(REPAIR_LOOP), "--mode=reactive", "--dry-run", "s", str(tmp_path / "ws"), "spec.yaml"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0
    assert "model policy violation" in result.stderr
    assert "CLOUD_WATCHDOG_REPAIR_OWNER_MODEL" in result.stderr
    assert "owner_model=gpt-5.6-sol" in result.stdout


def test_proactive_dry_run_fails_closed_on_hot_env_model_overrides(
    tmp_path: Path,
) -> None:
    evidence = _approval_evidence(tmp_path)
    env = {
        **_policy_env(tmp_path),
        **_SKIP_ENV,
        "FIXER_REPLAY_APPROVED": "1",
        "FIXER_REPLAY_EVIDENCE_PATH": str(evidence),
        "CLOUD_WATCHDOG_REPAIR_INVESTIGATOR_MODEL": "some:override-model",
    }
    result = subprocess.run(
        ["bash", str(REPAIR_LOOP), "--mode=proactive", "--dry-run", "s", str(tmp_path / "ws"), "spec.yaml"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert result.returncode == 69
    assert "model_policy_invalid" in result.stderr
    assert "CLOUD_WATCHDOG_REPAIR_INVESTIGATOR_MODEL" in result.stderr


def test_proactive_noop_guard_exists_in_script() -> None:
    text = _script_text()
    assert "NOOP exit 0" in text
    assert "repair_loop_noop_decision" in text


def test_invalid_mode_rejected(tmp_path: Path) -> None:
    env = {**_policy_env(tmp_path), **_SKIP_ENV}
    result = subprocess.run(
        ["bash", str(REPAIR_LOOP), "--mode=bogus", "--dry-run", "s", "w", "r"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    assert result.returncode == 64
    assert "invalid --mode" in result.stderr
