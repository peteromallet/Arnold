from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.chain_done_gate import check_chain_done, main


def _write_chain(tmp_path: Path, *, mode: str = "enforce", backstop: str = "enforce") -> tuple[Path, Path, Path]:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        yaml.safe_dump({"milestones": [{"label": "m1", "idea": "m1.md"}]}),
        encoding="utf-8",
    )
    plans_root = tmp_path / ".megaplan" / "plans"
    plan_dir = plans_root / "plan-m1"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "plan-m1", "current_state": "done"}) + "\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "chain-state.json"
    state_path.write_text(
        json.dumps(
            {
                "completion_contract_mode": mode,
                "full_suite_backstop_mode": backstop,
                "completed": [{"label": "m1", "plan": "plan-m1", "status": "done"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return spec_path, state_path, plans_root


def test_chain_done_gate_passes_when_plan_state_and_modes_are_blocking(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(tmp_path)

    assert check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    ) == []


def test_chain_done_gate_fails_shadow_modes_and_non_done_plan_state(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="shadow", backstop="shadow"
    )
    (plans_root / "plan-m1" / "state.json").write_text(
        json.dumps({"name": "plan-m1", "current_state": "planned"}) + "\n",
        encoding="utf-8",
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("completion_contract_mode" in error for error in errors)
    assert any("full_suite_backstop_mode" in error for error in errors)
    assert any("current_state='planned'" in error for error in errors)


def test_chain_done_gate_fails_open_review_blockers(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(tmp_path)
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(
        json.dumps(
            {
                "blockers": [
                    {
                        "id": "b1",
                        "title": "dynamic import trap",
                        "source": "review.txt",
                        "status": "open",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
        blockers_path=blockers_path,
    )

    assert any("unresolved blocker 'b1'" in error for error in errors)


def test_chain_done_gate_blockers_only_fails_unresolved_without_chain_inputs(tmp_path: Path) -> None:
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(
        json.dumps(
            {
                "blockers": [
                    {
                        "id": "b1",
                        "title": "dynamic import trap",
                        "source": "review.txt",
                        "status": "open",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["--blockers-only", "--blockers", str(blockers_path)]) == 1


def test_chain_done_gate_blockers_only_passes_resolved_without_chain_inputs(tmp_path: Path) -> None:
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(
        json.dumps(
            {
                "blockers": [
                    {
                        "id": "b1",
                        "title": "dynamic import trap",
                        "source": "review.txt",
                        "status": "resolved",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["--blockers-only", "--blockers", str(blockers_path)]) == 0


def test_chain_done_gate_blockers_only_fails_malformed_blocker_rows(tmp_path: Path) -> None:
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(
        json.dumps({"blockers": ["not an object"]}) + "\n",
        encoding="utf-8",
    )

    assert main(["--blockers-only", "--blockers", str(blockers_path)]) == 1


def test_chain_done_gate_blockers_only_fails_malformed_blockers_field(tmp_path: Path) -> None:
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(
        json.dumps({"blockers": {"id": "b1", "status": "open"}}) + "\n",
        encoding="utf-8",
    )

    assert main(["--blockers-only", "--blockers", str(blockers_path)]) == 2


def test_chain_done_gate_blockers_only_requires_blockers() -> None:
    try:
        main(["--blockers-only"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected --blockers-only without --blockers to fail parsing")


def test_chain_done_gate_blockers_only_rejects_full_mode_inputs(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(tmp_path)
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(json.dumps({"blockers": []}) + "\n", encoding="utf-8")

    for extra_arg, value in (
        ("--spec", spec_path),
        ("--state", state_path),
        ("--plans-root", plans_root),
    ):
        try:
            main(["--blockers-only", "--blockers", str(blockers_path), extra_arg, str(value)])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"expected --blockers-only with {extra_arg} to fail parsing")


def test_chain_done_gate_full_mode_still_requires_spec(tmp_path: Path) -> None:
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(json.dumps({"blockers": []}) + "\n", encoding="utf-8")

    try:
        main(["--blockers", str(blockers_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected full mode without --spec to fail parsing")


def test_chain_done_gate_full_mode_still_validates_chain_state(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(tmp_path, mode="shadow")
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(json.dumps({"blockers": []}) + "\n", encoding="utf-8")

    assert (
        main(
            [
                "--spec",
                str(spec_path),
                "--state",
                str(state_path),
                "--plans-root",
                str(plans_root),
                "--blockers",
                str(blockers_path),
            ]
        )
        == 1
    )


# ---------------------------------------------------------------------------
# T33: Chain-done gate — atomic mode, acceptance receipts, normalization
# ---------------------------------------------------------------------------


def test_chain_done_gate_atomic_mode_passes(tmp_path: Path) -> None:
    """Atomic mode (synonym for enforce) must pass chain-done gate."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="atomic", backstop="atomic"
    )

    assert (
        check_chain_done(
            spec_path=spec_path,
            state_path=state_path,
            plans_root=plans_root,
        )
        == []
    )


def test_chain_done_gate_atomic_completion_mode_fails_if_backstop_shadow(
    tmp_path: Path,
) -> None:
    """Atomic completion mode with shadow backstop must still fail chain-done."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="atomic", backstop="shadow"
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("full_suite_backstop_mode" in error for error in errors)


def test_chain_done_gate_atomic_backstop_fails_if_completion_shadow(
    tmp_path: Path,
) -> None:
    """Atomic backstop with shadow completion mode must still fail chain-done."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="shadow", backstop="atomic"
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("completion_contract_mode" in error for error in errors)


def test_chain_done_gate_enforce_mode_passes(tmp_path: Path) -> None:
    """Enforce mode (original blocking-mode name) must pass chain-done gate."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="enforce", backstop="enforce"
    )

    assert (
        check_chain_done(
            spec_path=spec_path,
            state_path=state_path,
            plans_root=plans_root,
        )
        == []
    )


def test_chain_done_gate_accepts_atomic_with_acceptance_receipts(
    tmp_path: Path,
) -> None:
    """Chain-done gate must accept atomic mode with acceptance receipts present."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="atomic", backstop="enforce"
    )
    # Add acceptance receipts to completed records
    state_path.write_text(
        json.dumps(
            {
                "completion_contract_mode": "atomic",
                "full_suite_backstop_mode": "enforce",
                "completed": [
                    {
                        "label": "m1",
                        "plan": "plan-m1",
                        "status": "done",
                        "acceptance_receipt": {
                            "transaction_id": "tx-001",
                            "snapshot_hash": "sha256:abc123",
                            "milestone_label": "m1",
                            "plan_name": "plan-m1",
                            "milestone_index": 0,
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        check_chain_done(
            spec_path=spec_path,
            state_path=state_path,
            plans_root=plans_root,
        )
        == []
    )


def test_chain_done_gate_missing_milestone_in_atomic_mode(tmp_path: Path) -> None:
    """Chain-done gate in atomic mode must catch missing milestone records."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="atomic", backstop="enforce"
    )
    # Remove completed record
    state_path.write_text(
        json.dumps(
            {
                "completion_contract_mode": "atomic",
                "full_suite_backstop_mode": "enforce",
                "completed": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("is not recorded in chain_state.completed" in error for error in errors)


def test_chain_done_gate_atomic_without_acceptance_receipt_passes_if_plan_done(
    tmp_path: Path,
) -> None:
    """Chain-done gate does NOT require acceptance receipts to pass;
    it only checks contract mode, backstop mode, plan state, and blockers.
    Acceptance receipts are checked at completion time, not gate time."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="atomic", backstop="enforce"
    )
    # Completed record without acceptance receipt — still valid for chain-done gate
    state_path.write_text(
        json.dumps(
            {
                "completion_contract_mode": "atomic",
                "full_suite_backstop_mode": "enforce",
                "completed": [
                    {"label": "m1", "plan": "plan-m1", "status": "done"}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        check_chain_done(
            spec_path=spec_path,
            state_path=state_path,
            plans_root=plans_root,
        )
        == []
    )


def test_chain_done_gate_normalized_atomic_passes(tmp_path: Path) -> None:
    """Chain-done gate normalizes 'atomic' to 'enforce' and passes."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="atomic", backstop="atomic"
    )

    assert (
        main(
            [
                "--spec",
                str(spec_path),
                "--state",
                str(state_path),
                "--plans-root",
                str(plans_root),
            ]
        )
        == 0
    )


def test_chain_done_gate_fails_warn_even_with_atomic_backstop(
    tmp_path: Path,
) -> None:
    """Warn completion mode must fail chain-done even with atomic backstop."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="warn", backstop="atomic"
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("completion_contract_mode" in error for error in errors)


def test_chain_done_gate_fails_off_mode_even_with_enforce_backstop(
    tmp_path: Path,
) -> None:
    """Off completion mode must fail chain-done even with enforce backstop."""
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="off", backstop="enforce"
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("completion_contract_mode" in error for error in errors)
