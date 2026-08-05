from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.spec import ChainSpec
from arnold_pipelines.megaplan.types import CliError


def _base(enabled: bool = True) -> dict[str, object]:
    return {
        "milestones": [{"label": "plan", "idea": "make progress"}],
        "fresh_child_admission": {
            "enabled": enabled,
            "authority_journal_path": ".megaplan/authority/journal.sqlite",
            "wbc_ledger_path": ".megaplan/wbc/attempts.sqlite",
            "custody_lease_dir": ".megaplan/custody/leases",
            "approval_receipt": "operator-approved-independent-child:v1",
            "approval_actor": "operator",
            "parent_occurrence_digest": "sha256:parent",
            "blocker_or_phase_result_hash": "sha256:blocker",
            "normalized_failure_kind": "stalled",
            "chain_identity": "critique-ledger-accountability-v3-r7",
            "source_revision": "r7-source",
        },
    }


def test_legacy_chain_specs_have_no_fresh_child_admission() -> None:
    spec = ChainSpec.from_dict({"milestones": []})
    assert spec.fresh_child_admission is None


def test_fresh_child_admission_parses_strict_owner_and_lineage_bindings() -> None:
    spec = ChainSpec.from_dict(_base())
    admission = spec.fresh_child_admission
    assert admission is not None and admission.enabled
    assert admission.chain_identity == "critique-ledger-accountability-v3-r7"
    assert admission.authority_journal_path == ".megaplan/authority/journal.sqlite"


def test_enabled_fresh_child_admission_requires_source_revision() -> None:
    raw = _base()
    config = raw["fresh_child_admission"]
    assert isinstance(config, dict)
    config.pop("source_revision")
    with pytest.raises(CliError, match="source_revision"):
        ChainSpec.from_dict(raw)


def test_fresh_child_admission_rejects_unknown_keys() -> None:
    raw = _base()
    config = raw["fresh_child_admission"]
    assert isinstance(config, dict)
    config["projection_path"] = ".megaplan/status.json"
    with pytest.raises(CliError, match="projection_path"):
        ChainSpec.from_dict(raw)


def test_owned_path_rejects_escape_and_symlink(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.chain.fresh_child_launch import (
        FreshChildLaunchError,
        _resolve_owned_path,
    )

    with pytest.raises(FreshChildLaunchError, match="below the child workspace"):
        _resolve_owned_path(tmp_path, "../outside.sqlite", "owner")

    external = tmp_path.parent / "external-owner-dir"
    external.mkdir(exist_ok=True)
    link = tmp_path / "link"
    link.symlink_to(external, target_is_directory=True)
    with pytest.raises(FreshChildLaunchError, match="child workspace|symlink"):
        _resolve_owned_path(tmp_path, "link/journal.sqlite", "owner")
