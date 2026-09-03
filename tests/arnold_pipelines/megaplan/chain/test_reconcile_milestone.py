"""P6 end-of-epic reconcile milestone: spec fields, scaffold append,
``ensure_reconcile_milestone`` idempotency, controller-side skip detection
(``compute_reconcile_scope``) with the reconcile-verification.json waiver,
completion-guard acceptance, recorded-target validation, and per-milestone
merge policy.

Settled contract (2026-08-09 plan + codex corrections): reconciliation is a
generated final ``kind: reconcile`` milestone, default ON
(``ChainSpec.reconciliation.enabled``); legacy chains materialize it via the
idempotent ``ensure_reconcile_milestone`` BEFORE any state load / execution
identity binding; skip detection is engine-source allowlist minus promotion
evidence, uncertainty degrades to PR-required (never a silent no-op); the
completion guard accepts merged / intentionally rejected / verified no-op and
validates merged reconcile PRs against the RECORDED target (main), not
``spec.base_branch``.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

import arnold_pipelines.megaplan.chain as chain_module
from arnold_pipelines.megaplan.chain import spec as chain_spec_module
from arnold_pipelines.megaplan.chain.advancement import policy_for_spec
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    MilestoneSpec,
    MilestoneValidationSpec,
    load_spec,
)
from arnold_pipelines.megaplan.briefs import scaffold_epic
from arnold_pipelines.megaplan.types import CliError


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_sha(root: Path, ref: str = "HEAD") -> str:
    return (
        subprocess.run(
            ["git", "rev-parse", ref],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
    )


def _git_repo(root: Path) -> Path:
    """A git repo at *root* with a single initial commit on ``main``."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "initial",
    )
    return root


def _commit(root: Path, path: str, content: str = "x\n", message: str = "change") -> str:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        message,
    )
    return _git_sha(root)


def _initiative(root: Path, slug: str = "demo") -> Path:
    """A valid legacy chain spec: one product milestone with an idea file."""
    initiative = root / ".megaplan" / "initiatives" / slug
    briefs = initiative / "briefs"
    briefs.mkdir(parents=True)
    (initiative / "NORTHSTAR.md").write_text("# North Star\n", encoding="utf-8")
    (briefs / "m1.md").write_text("# M1\n", encoding="utf-8")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "\n".join(
            [
                "base_branch: main",
                "anchors:",
                "  north_star: NORTHSTAR.md",
                "milestones:",
                "  - label: m1",
                "    idea: .megaplan/initiatives/demo/briefs/m1.md",
                "    branch: megaplan/demo/m1",
                "merge_policy: auto",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return spec


def _plan_dir(root: Path, plan: str, base_sha: str, current_state: str = "prepped") -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    plan_dir.joinpath("state.json").write_text(
        json.dumps(
            {
                "current_state": current_state,
                "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
            }
        ),
        encoding="utf-8",
    )
    return plan_dir


# ── scaffold append (briefs.scaffold_epic) ────────────────────────────────


def test_scaffold_appends_reconcile_milestone_when_enabled(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    chain_path, written = scaffold_epic(root, "demo", ["m1"], reconciliation=True)
    raw = yaml.safe_load(chain_path.read_text(encoding="utf-8"))
    assert raw["reconciliation"] == {"enabled": True}
    milestones = raw["milestones"]
    assert [m["label"] for m in milestones] == ["m1", "reconcile"]
    reconcile = milestones[-1]
    assert reconcile["kind"] == "reconcile"
    assert reconcile["target_branch"] == "main"
    assert reconcile["merge_policy"] == "review"
    assert reconcile["phase_model"] == ["execute=codex"]
    assert reconcile["depends_on"] == ["m1"]
    assert reconcile["branch"].startswith("reconcile/demo-")
    assert reconcile["branch"].count("-") >= 1
    # idea points at the generated brief, which exists and cites both rubrics
    assert reconcile["idea"].endswith("briefs/reconcile.md")
    brief = root / reconcile["idea"]
    assert brief.exists()
    body = brief.read_text(encoding="utf-8")
    assert "docs/megaplan-reference-architecture-20260807.md" in body
    assert "docs/per-epic-runtime-end-state-20260809.md" in body
    # the spec round-trips through the strict loader
    spec = load_spec(chain_path)
    assert [m.kind for m in spec.milestones] == ["product", "reconcile"]
    assert spec.reconciliation == {"enabled": True}


def test_scaffold_opt_out_omits_reconcile(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    chain_path, written = scaffold_epic(root, "demo", ["m1"], reconciliation=False)
    raw = yaml.safe_load(chain_path.read_text(encoding="utf-8"))
    assert raw["reconciliation"] == {"enabled": False}
    assert [m["label"] for m in raw["milestones"]] == ["m1"]
    assert not (root / ".megaplan" / "initiatives" / "demo" / "briefs" / "reconcile.md").exists()
    spec = load_spec(chain_path)
    assert spec.reconciliation == {"enabled": False}
    assert all(m.kind == "product" for m in spec.milestones)


def test_scaffold_depends_on_previous_terminal_when_multiple(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    chain_path, _ = scaffold_epic(root, "demo", ["m1", "m2"], reconciliation=True)
    milestones = yaml.safe_load(chain_path.read_text(encoding="utf-8"))["milestones"]
    assert milestones[-1]["depends_on"] == ["m2"]


# ── spec field parsing / validation ────────────────────────────────────────


def test_milestone_spec_parses_reconcile_fields(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    chain_path, _ = scaffold_epic(root, "demo", ["m1"], reconciliation=True)
    spec = load_spec(chain_path)
    reconcile = spec.milestones[-1]
    assert reconcile.kind == "reconcile"
    assert reconcile.target_branch == "main"
    assert reconcile.merge_policy == "review"
    assert reconcile.depends_on == ["m1"]
    assert reconcile.phase_model == ["execute=codex"]
    # product milestones keep the defaults
    assert spec.milestones[0].kind == "product"
    assert spec.milestones[0].target_branch is None
    assert spec.milestones[0].merge_policy is None


def test_milestone_spec_rejects_unknown_kind(tmp_path: Path) -> None:
    spec = tmp_path / "chain.yaml"
    spec.write_text(
        "milestones:\n  - label: m1\n    idea: briefs/m1.md\n    kind: sidequest\n",
        encoding="utf-8",
    )
    with pytest.raises(CliError, match="kind must be one of"):
        load_spec(spec)


def test_reconcile_kind_rejects_non_review_merge_policy(tmp_path: Path) -> None:
    spec = tmp_path / "chain.yaml"
    spec.write_text(
        "milestones:\n  - label: reconcile\n    kind: reconcile\n"
        "    idea: briefs/reconcile.md\n    merge_policy: auto\n",
        encoding="utf-8",
    )
    with pytest.raises(CliError, match="forces merge_policy review"):
        load_spec(spec)


def test_reconciliation_unknown_key_rejected(tmp_path: Path) -> None:
    spec = tmp_path / "chain.yaml"
    spec.write_text(
        "milestones: []\nreconciliation:\n  enabled: true\n  snooze: true\n",
        encoding="utf-8",
    )
    with pytest.raises(CliError, match="reconciliation.*unknown key"):
        load_spec(spec)


def test_reconciliation_enabled_default_true() -> None:
    spec = ChainSpec(milestones=[])
    assert spec.reconciliation == {"enabled": True}
    assert MilestoneSpec(label="m1", idea="briefs/m1.md").kind == "product"


# ── ensure_reconcile_milestone (legacy chains, idempotent) ─────────────────


def test_ensure_reconcile_milestone_idempotent_same_branch_date(
    tmp_path: Path, monkeypatch
) -> None:
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)

    first = chain_module.ensure_reconcile_milestone(
        spec_path, root=root, now=datetime(2026, 8, 11, tzinfo=timezone.utc)
    )
    reconcile = [m for m in first.milestones if m.kind == "reconcile"]
    assert len(reconcile) == 1
    branch_first = reconcile[0].branch
    assert branch_first == f"reconcile/demo-20260811"
    assert reconcile[0].target_branch == "main"
    assert reconcile[0].merge_policy == "review"
    assert reconcile[0].depends_on == ["m1"]
    assert reconcile[0].phase_model == ["execute=codex"]

    # brief written next to the other milestone briefs, relative idea resolves
    brief = root / ".megaplan" / "initiatives" / "demo" / "briefs" / "reconcile.md"
    assert brief.exists()
    assert reconcile[0].idea == str(
        brief.relative_to(root)
    )

    # second run with a LATER date: same branch/date, no duplicate milestone
    second = chain_module.ensure_reconcile_milestone(
        spec_path, root=root, now=datetime(2026, 8, 12, tzinfo=timezone.utc)
    )
    reconcile_second = [m for m in second.milestones if m.kind == "reconcile"]
    assert len(reconcile_second) == 1
    assert reconcile_second[0].branch == branch_first
    # persisted spec still parses through the strict loader
    reloaded = load_spec(spec_path)
    assert len([m for m in reloaded.milestones if m.kind == "reconcile"]) == 1
    assert reloaded.milestones[-1].branch == branch_first


def test_ensure_reconcile_milestone_respects_opt_out(tmp_path: Path, monkeypatch) -> None:
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["reconciliation"] = {"enabled": False}
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    spec = chain_module.ensure_reconcile_milestone(
        spec_path, root=root, now=datetime(2026, 8, 11, tzinfo=timezone.utc)
    )
    assert all(m.kind == "product" for m in spec.milestones)
    reloaded = load_spec(spec_path)
    assert all(m.kind == "product" for m in reloaded.milestones)
    assert not (
        root / ".megaplan" / "initiatives" / "demo" / "briefs" / "reconcile.md"
    ).exists()


def test_run_chain_rejects_implicit_reconcile_for_protected_spec_without_writes(
    tmp_path: Path, monkeypatch
) -> None:
    """A source-bound legacy spec must not dirty its own tracked precondition."""
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["launch_preconditions"] = [
        {
            "name": "chain spec is committed",
            "kind": "git_tracked",
            "path": ".megaplan/initiatives/demo/chain.yaml",
        }
    ]
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    _git(root, "add", ".")
    _git(
        root,
        "-c", "user.name=Test", "-c", "user.email=test@example.com",
        "commit", "-m", "guarded chain",
    )
    before = spec_path.read_bytes()
    reconcile_brief = spec_path.parent / "briefs" / "reconcile.md"

    with pytest.raises(CliError) as excinfo:
        chain_module.run_chain(spec_path, root, writer=lambda _msg: None)

    assert excinfo.value.code == "reconcile_requires_committed_spec"
    assert spec_path.read_bytes() == before
    assert not reconcile_brief.exists()


def test_protected_reconcile_helper_allows_explicit_opt_out_and_precommitted_reconcile(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["reconciliation"] = {"enabled": False}
    raw["launch_preconditions"] = [
        {
            "name": "chain spec is committed",
            "kind": "git_tracked",
            "path": ".megaplan/initiatives/demo/chain.yaml",
        }
    ]
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    spec = load_spec(spec_path)
    assert not chain_module._reconcile_would_mutate_protected_spec(
        spec, root=root, spec_path=spec_path
    )


def test_ensure_reconcile_milestone_skips_final_conformance_gate_chains(
    tmp_path: Path, monkeypatch
) -> None:
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["milestones"][0]["validate"] = [
        {
            "kind": "final_conformance_gate",
            "traceability": "traceability.yaml",
            "conformance": "conformance.yaml",
            "validator": "validator.py",
            "proof_map": "proof-map.json",
        }
    ]
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    messages: list[str] = []
    spec = chain_module.ensure_reconcile_milestone(
        spec_path,
        root=root,
        writer=messages.append,
        now=datetime(2026, 8, 11, tzinfo=timezone.utc),
    )
    # reconciliation is RECORDED as skipped: the final-gate invariant wins
    assert all(m.kind == "product" for m in spec.milestones)
    assert any("reconciliation skipped" in message for message in messages)
    reloaded = load_spec(spec_path)
    assert all(m.kind == "product" for m in reloaded.milestones)
    # the skip is DURABLE: an atomic sidecar next to the spec, not a log-only
    # event — written with the declared gate + terminal milestone recorded
    skip_path = spec_path.parent / chain_module.RECONCILE_SKIP_FILENAME
    assert skip_path.is_file()
    record = json.loads(skip_path.read_text(encoding="utf-8"))
    assert record["schema"] == chain_module.RECONCILE_SKIP_SCHEMA
    assert record["gate"] == "final_conformance_gate"
    assert record["terminal_milestone"] == "m1"
    assert record["epic"] == "demo"
    # the skip is NARROW: it fires for a DECLARED final_conformance_gate on the
    # terminal milestone — not for any terminal validate block
    assert chain_module._declares_final_conformance_gate(reloaded.milestones[-1])
    # restart reads the durable record: the sidecar is untouched (no re-write,
    # no re-run) and the reconcile milestone is never materialized
    first_bytes = skip_path.read_bytes()
    messages.clear()
    restarted = chain_module.ensure_reconcile_milestone(
        spec_path,
        root=root,
        writer=messages.append,
        now=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    assert all(m.kind == "product" for m in restarted.milestones)
    assert skip_path.read_bytes() == first_bytes
    assert len([m for m in load_spec(spec_path).milestones if m.kind == "reconcile"]) == 0


def test_ensure_reconcile_milestone_skip_is_narrow_to_declared_gate() -> None:
    # The skip trigger is the DECLARED final_conformance_gate kind on the
    # terminal milestone, not the mere presence of any terminal validate block.
    gate = MilestoneValidationSpec(kind="final_conformance_gate")
    other = MilestoneValidationSpec(kind="smoke_test")
    with_gate = MilestoneSpec(label="m1", idea="briefs/m1.md", validate=[gate])
    with_other = MilestoneSpec(label="m1", idea="briefs/m1.md", validate=[other])
    assert chain_module._declares_final_conformance_gate(with_gate)
    assert not chain_module._declares_final_conformance_gate(with_other)
    assert not chain_module._declares_final_conformance_gate(
        MilestoneSpec(label="m1", idea="briefs/m1.md")
    )


def test_ensure_reconcile_milestone_non_gate_terminal_validate_materializes(
    tmp_path: Path, monkeypatch
) -> None:
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    # A terminal milestone whose validate is NOT a final_conformance_gate must
    # NOT skip reconciliation: with the pre-fix truthiness check this chain
    # was wrongly suppressed; the narrow check materializes it.
    non_gate_spec = ChainSpec(
        milestones=[
            MilestoneSpec(
                label="m1",
                idea="briefs/m1.md",
                branch="megaplan/demo/m1",
                validate=[MilestoneValidationSpec(kind="smoke_test")],
            )
        ]
    )
    monkeypatch.setattr(chain_spec_module, "load_spec", lambda _path: non_gate_spec)
    chain_module.ensure_reconcile_milestone(
        spec_path, root=root, now=datetime(2026, 8, 11, tzinfo=timezone.utc)
    )
    # the generated milestone is persisted even though the patched loader keeps
    # returning the pre-append spec: assert against the real on-disk spec
    reloaded = load_spec(spec_path)
    assert [m.kind for m in reloaded.milestones] == ["product", "reconcile"]
    assert not (spec_path.parent / chain_module.RECONCILE_SKIP_FILENAME).exists()


def test_ensure_reconcile_milestone_crash_between_temp_write_and_rename_heals(
    tmp_path: Path, monkeypatch
) -> None:
    import tempfile

    import arnold.runtime.state_persistence as rt_state_persistence

    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    before = spec_path.read_bytes()
    assert b"reconcile" not in before  # sanity: legacy chain, no milestone yet
    resolved_spec = spec_path.resolve()
    real_atomic_write_bytes = rt_state_persistence.atomic_write_bytes

    def _crash_mid_persist(path: Path, content: bytes) -> None:
        path = Path(path)
        if path.resolve() == resolved_spec:
            # interruption between the temp write and the atomic rename: the
            # temp file is fully written, the spec is never touched
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
                handle.write(content)
                handle.flush()
            raise OSError("simulated crash between temp write and rename")
        real_atomic_write_bytes(path, content)

    monkeypatch.setattr(
        rt_state_persistence, "atomic_write_bytes", _crash_mid_persist
    )
    with pytest.raises(CliError, match="simulated crash between temp write and rename"):
        chain_module.ensure_reconcile_milestone(
            spec_path, root=root, now=datetime(2026, 8, 11, tzinfo=timezone.utc)
        )
    # crash mid-persist leaves the OLD VALID spec — never truncated/corrupt
    assert spec_path.read_bytes() == before
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert [m["label"] for m in raw["milestones"]] == ["m1"]

    # restart heals: the same call without the interruption appends and
    # atomically persists the generated milestone
    monkeypatch.setattr(
        rt_state_persistence, "atomic_write_bytes", real_atomic_write_bytes
    )
    healed = chain_module.ensure_reconcile_milestone(
        spec_path, root=root, now=datetime(2026, 8, 11, tzinfo=timezone.utc)
    )
    assert [m.kind for m in healed.milestones] == ["product", "reconcile"]
    reloaded = load_spec(spec_path)
    assert [m.kind for m in reloaded.milestones] == ["product", "reconcile"]
    assert reloaded.milestones[-1].branch == "reconcile/demo-20260811"


def test_ensure_reconcile_milestone_preserves_existing_chain(tmp_path: Path, monkeypatch) -> None:
    root = _git_repo(tmp_path / "repo")
    spec_path = _initiative(root)
    before = spec_path.read_text(encoding="utf-8")
    spec = chain_module.ensure_reconcile_milestone(
        spec_path, root=root, now=datetime(2026, 8, 11, tzinfo=timezone.utc)
    )
    assert spec.milestones[-1].kind == "reconcile"
    # original milestones untouched
    assert [m.label for m in spec.milestones] == ["m1", "reconcile"]
    # m1's own fields preserved through the round-trip
    assert spec.milestones[0].idea == ".megaplan/initiatives/demo/briefs/m1.md"
    assert spec.milestones[0].branch == "megaplan/demo/m1"
    assert before  # sanity: fixture non-empty


# ── compute_reconcile_scope (skip detection) ───────────────────────────────


def _scope_kwargs(root: Path, base_sha: str, **extra: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "spec": ChainSpec(milestones=[]),
        "manifest": None,
        "root": root,
        "chain_base_sha": base_sha,
    }
    kwargs.update(extra)
    return kwargs


def test_compute_reconcile_scope_no_engine_changes_writes_waiver(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _commit(root, "docs/note.md", message="docs only")
    plan_dir = _plan_dir(root, "plan-x", base_sha)

    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(
            root,
            base_sha,
            plan_dir=plan_dir,
            plan_name="plan-x",
            milestone_label="reconcile",
        )
    )
    assert scope["decision"] == "noop"
    assert scope["engine_changes"] == []
    assert "no engine-source changes" in scope["reason"]
    assert scope["waiver_path"] is not None
    waiver = json.loads(Path(scope["waiver_path"]).read_text(encoding="utf-8"))
    assert waiver["schema"] == chain_module.RECONCILE_VERIFICATION_SCHEMA
    assert waiver["plan"] == "plan-x"
    assert waiver["milestone_label"] == "reconcile"
    # the waiver pins the CURRENT HEAD (what milestone_base_sha records at
    # plan init), not the chain's launch-time base snapshot
    assert waiver["base_sha"] == _git_sha(root)
    assert waiver["scope"] == "no_engine_changes"
    assert waiver["engine_changes"] == []


def test_compute_reconcile_scope_engine_change_requires_pr(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _commit(root, "arnold_pipelines/engine.py", message="engine change")

    scope = chain_module.compute_reconcile_scope(**_scope_kwargs(root, base_sha))
    assert scope["decision"] == "pr_required"
    assert len(scope["engine_changes"]) == 1
    assert scope["engine_changes"][0]["paths"] == ["arnold_pipelines/engine.py"]
    assert scope["waiver_path"] is None
    assert "not covered by promotion evidence" in scope["reason"]


def test_compute_reconcile_scope_promoted_changes_noop(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    head = _commit(root, "arnold_pipelines/engine.py", message="engine change")
    plan_dir = _plan_dir(root, "plan-x", base_sha)
    # promotion evidence: the manifest's verified_head IS the current head
    manifest = {
        "indirection": {"verified_head": head},
        "promotions": [{"previous_commit": base_sha, "reason": "canary ok"}],
    }

    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(
            root,
            base_sha,
            manifest=manifest,
            plan_dir=plan_dir,
            plan_name="plan-x",
            milestone_label="reconcile",
        )
    )
    assert scope["decision"] == "noop"
    assert scope["reason"] == "all engine-source changes already promoted"
    assert scope["waiver_path"] is not None
    waiver = json.loads(Path(scope["waiver_path"]).read_text(encoding="utf-8"))
    assert waiver["scope"] == "already_promoted"
    assert waiver["promotion_evidence"]  # the manifest head is recorded


def test_compute_reconcile_scope_unreadable_journal_uncertain(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _commit(root, "arnold_pipelines/engine.py", message="engine change")
    # manifest dir whose promotion-journal.jsonl is a DIRECTORY => unreadable
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "promotion-journal.jsonl").mkdir()
    manifest_path = manifest_dir / "runtime-manifest.json"

    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(root, base_sha, manifest_path=manifest_path)
    )
    assert scope["decision"] == "uncertain"
    assert scope["waiver_path"] is None
    assert "promotion journal unreadable" in scope["reason"]


def test_compute_reconcile_scope_no_engine_changes_noop_without_plan_dir(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _commit(root, "docs/note.md", message="docs only")
    scope = chain_module.compute_reconcile_scope(**_scope_kwargs(root, base_sha))
    assert scope["decision"] == "noop"
    # no plan dir provided: no waiver is written, but the decision is still
    # a verified no-op (the caller decides where the evidence lands)
    assert scope["waiver_path"] is None


# ── T-0501: real-Git reconcile-scope fixtures ──────────────────────────────
#
# Every fixture is a REAL git repo with real commits in the reconcile range:
# (a) product change -> reconcile REQUIRED (pr_required, never waived);
# (b) fully promoted change (merged to main, promotion evidence in the bound
#     runtime manifest) -> verified no-op; (c) verified no-op (no diff) ->
#     waiver recorded, never an agent dispatch; (d) invalid/missing evidence
#     -> REQUIRES reconcile (uncertain/pr_required, never a silent no-op).


def test_reconcile_scope_real_git_product_change_requires_reconcile(
    tmp_path: Path,
) -> None:
    """(a) A real product change — an engine-source commit inside the
    milestone range — requires reconcile: the scope reports the actual
    SHA/subject/paths from git, writes NO waiver, and the completion guard
    refuses a terminal outcome for a reconcile record that carries neither a
    merged PR nor a verified-noop waiver."""
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    head = _commit(root, "arnold_pipelines/engine.py", message="engine change")
    plan_dir = _plan_dir(root, "plan-x", base_sha, current_state="executed")

    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(
            root,
            base_sha,
            plan_dir=plan_dir,
            plan_name="plan-x",
            milestone_label="reconcile",
        )
    )
    assert scope["decision"] == "pr_required"
    assert scope["waiver_path"] is None
    assert len(scope["engine_changes"]) == 1
    assert scope["engine_changes"][0]["sha"] == head
    assert scope["engine_changes"][0]["subject"] == "engine change"
    assert scope["engine_changes"][0]["paths"] == ["arnold_pipelines/engine.py"]
    assert "not covered by promotion evidence" in scope["reason"]
    # the change is NOT terminal without a reconcile PR: the completion guard
    # fails closed (no merged PR, no verified-noop waiver)
    ok, reason = chain_module._chain_completion_guard(
        root,
        _reconcile_record(plan="plan-x"),
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is False
    assert "execution evidence blocked completion" in reason


def _reconcile_promoted_manifest(path: Path, verified_head: str) -> Path:
    """Write a schema-valid runtime manifest whose promotion evidence covers
    *verified_head* (the change is already merged to main) and return it."""
    from arnold_pipelines.megaplan.cloud.runtime_manifest import (
        RuntimeManifest,
        write_manifest,
    )

    _reconcile_valid_manifest(path)  # seed a schema-valid payload
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["indirection"]["verified_head"] = verified_head
    raw["promotions"] = [{"previous_commit": verified_head, "reason": "canary ok"}]
    write_manifest(RuntimeManifest.from_dict(raw), path)
    return path


def test_reconcile_scope_real_git_promoted_change_is_verified_noop(
    tmp_path: Path,
) -> None:
    """(b) A change that was ALREADY merged to main — the bound runtime
    manifest's promotion evidence covers the commit — is a verified no-op:
    ``already_promoted`` waiver with the real SHA recorded, and the
    completion guard accepts the waiver as terminal (no PR, no agent)."""
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    head = _commit(root, "arnold_pipelines/engine.py", message="engine change")
    manifest_path = _reconcile_promoted_manifest(
        tmp_path / "manifests" / "runtime-manifest.json", verified_head=head
    )
    # the plan's milestone base is main's head at reconcile time (the merged
    # commit) — the value the chain writes on milestone init
    plan_dir = _plan_dir(root, "plan-x", head, current_state="prepped")

    manifest = chain_module._reconcile_scope_manifest(
        manifest_path, milestone_label="reconcile"
    )
    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(
            root,
            base_sha,
            manifest=manifest,
            manifest_path=manifest_path,
            plan_dir=plan_dir,
            plan_name="plan-x",
            milestone_label="reconcile",
        )
    )
    assert scope["decision"] == "noop"
    assert scope["reason"] == "all engine-source changes already promoted"
    assert scope["waiver_path"] is not None
    waiver = json.loads(Path(scope["waiver_path"]).read_text(encoding="utf-8"))
    assert waiver["schema"] == chain_module.RECONCILE_VERIFICATION_SCHEMA
    assert waiver["scope"] == "already_promoted"
    assert waiver["engine_changes"][0]["sha"] == head
    assert head in waiver["promotion_evidence"]
    # terminal without an agent: the guard accepts the waiver as the
    # reconcile outcome
    ok, reason = chain_module._chain_completion_guard(
        root,
        _reconcile_record(plan="plan-x"),
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is True
    assert "reconcile verification waiver accepted" in reason


def test_reconcile_scope_real_git_verified_noop_never_dispatches_agent(
    tmp_path: Path,
) -> None:
    """(c) A verified no-op (docs-only diff in the reconcile range) records
    the waiver and is terminal WITHOUT any agent dispatch: the completion
    guard accepts the reconcile record purely on the waiver — no PR context,
    no execution batches, no agent."""
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    docs_head = _commit(root, "docs/note.md", message="docs only")
    # the plan's milestone base is main's head at reconcile time (the docs
    # commit), matching the waiver's pinned base
    plan_dir = _plan_dir(root, "plan-x", docs_head, current_state="prepped")

    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(
            root,
            base_sha,
            plan_dir=plan_dir,
            plan_name="plan-x",
            milestone_label="reconcile",
        )
    )
    assert scope["decision"] == "noop"
    assert scope["engine_changes"] == []
    assert scope["waiver_path"] is not None
    waiver = json.loads(Path(scope["waiver_path"]).read_text(encoding="utf-8"))
    assert waiver["scope"] == "no_engine_changes"
    # the waiver ALONE is the terminal evidence: guard accepts with no PR and
    # no execution batch — the verified no-op never dispatches an agent
    ok, reason = chain_module._chain_completion_guard(
        root,
        _reconcile_record(plan="plan-x"),
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is True
    assert "reconcile verification waiver accepted" in reason


def test_reconcile_scope_real_git_invalid_evidence_requires_reconcile(
    tmp_path: Path,
) -> None:
    """(d) MISSING or UNCERTAIN evidence REQUIRES reconcile — never a
    silent no-op: with an engine change in range, a missing manifest
    degrades to ``pr_required`` and an unreadable promotion journal to
    ``uncertain``; neither writes a waiver, and the completion guard refuses
    a terminal outcome for the reconcile record."""
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _commit(root, "arnold_pipelines/engine.py", message="engine change")

    # (i) missing manifest -> pr_required (the reconcile is REQUIRED)
    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(root, base_sha, manifest=None)
    )
    assert scope["decision"] == "pr_required"
    assert scope["waiver_path"] is None

    # (ii) unreadable promotion journal -> uncertain (also REQUIRED)
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "promotion-journal.jsonl").mkdir()  # journal as DIRECTORY
    manifest_path = manifest_dir / "runtime-manifest.json"
    scope = chain_module.compute_reconcile_scope(
        **_scope_kwargs(root, base_sha, manifest_path=manifest_path)
    )
    assert scope["decision"] == "uncertain"
    assert scope["waiver_path"] is None
    assert "promotion journal unreadable" in scope["reason"]

    # both evidence-less outcomes fail the completion guard: the reconcile
    # record has no merged PR and no verified-noop waiver
    plan_dir = _plan_dir(root, "plan-x", base_sha, current_state="executed")
    ok, reason = chain_module._chain_completion_guard(
        root,
        _reconcile_record(plan="plan-x"),
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is False
    assert "execution evidence blocked completion" in reason


# ── T-0024: reconcile-scope manifest reader (absent vs invalid) ─────────────


def _reconcile_valid_manifest(path: Path) -> Path:
    """Write a schema-valid session runtime manifest and return *path*."""
    from arnold_pipelines.megaplan.cloud.runtime_manifest import (
        RuntimeManifest,
        write_manifest,
    )

    now = datetime.now(timezone.utc).isoformat()
    manifest = RuntimeManifest.from_dict(
        {
            "runtime_id": "reconcile-reader-test",
            "schema": "1",
            "generation": 1,
            "epic_id": "epic-reconcile",
            "state": "active",
            "owner": "test",
            "base": {
                "ref": "main",
                "commit": "0" * 40,
                "editable_install_path": "/tmp/editable",
                "venv_path": "/tmp/venv",
            },
            "epic": {
                "branch": "fixer/epic-reconcile",
                "worktree_path": "/tmp/wt",
                "venv_path": "/tmp/venv",
                "runtime_root": "/tmp/wt",
                "expected_head": "0" * 40,
                "repair_bin": "/usr/local/bin/arnold-babysitter",
                "deps_lockfile": "requirements.lock",
            },
            "indirection": {
                "host_path": "/tmp/host",
                "container_path": "/tmp/container",
                "mount_table": [],
                "execution_namespace": "test",
                "verified_head": "0" * 40,
                "last_verified_at": now,
                "attestation": {
                    "module_file": "arnold_pipelines/__init__.py",
                    "module_digest": "0" * 64,
                    "mount_id": "mount-test",
                },
            },
            "policy": {
                "policy_sha": "0" * 64,
                "model_policy_sha": "0" * 64,
                "sync_policy": "manifest-only",
            },
            "promotions": [],
            "timestamps": {"created": now, "updated": now, "closed": None},
            "gc_policy": "keep",
            "commands": [],
        }
    )
    write_manifest(manifest, path)
    return path


def test_reconcile_scope_manifest_absent_returns_none(tmp_path: Path) -> None:
    """A genuinely ABSENT manifest (no binding, or a missing file) yields
    None — the scope computation then degrades to pr_required/uncertain,
    never a silent no-op."""
    assert (
        chain_module._reconcile_scope_manifest(None, milestone_label="reconcile")
        is None
    )
    assert (
        chain_module._reconcile_scope_manifest(
            tmp_path / "missing.json", milestone_label="reconcile"
        )
        is None
    )


def test_reconcile_scope_manifest_present_but_invalid_blocks(tmp_path: Path) -> None:
    """A PRESENT-but-invalid manifest must FAIL CLOSED with a typed error —
    never collapse to None, which would let compute_reconcile_scope treat it
    as absent and waive the reconcile (noop) on top of a corrupt manifest."""
    # (a) corrupt JSON
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CliError) as excinfo:
        chain_module._reconcile_scope_manifest(corrupt, milestone_label="reconcile")
    assert excinfo.value.code == "reconcile_manifest_invalid"
    assert "present but unreadable/invalid" in excinfo.value.message
    assert "reconcile" in excinfo.value.message

    # (b) valid JSON but schema-invalid (missing required fields) — same
    #     fail-closed block, still distinguishable from absent.
    schema_bad = tmp_path / "schema-bad.json"
    schema_bad.write_text('{"epic_id": "epic-x"}', encoding="utf-8")
    with pytest.raises(CliError) as excinfo:
        chain_module._reconcile_scope_manifest(schema_bad, milestone_label="reconcile")
    assert excinfo.value.code == "reconcile_manifest_invalid"
    assert "present but unreadable/invalid" in excinfo.value.message


def test_reconcile_scope_manifest_present_valid_returns_payload(tmp_path: Path) -> None:
    """A present, valid manifest loads into the dict the scope computation
    consumes — the valid case still works end to end."""
    valid = _reconcile_valid_manifest(tmp_path / "valid.json")
    payload = chain_module._reconcile_scope_manifest(valid, milestone_label="reconcile")
    assert isinstance(payload, dict)
    assert payload["epic_id"] == "epic-reconcile"
    assert payload["state"] == "active"


def test_reconcile_scope_manifest_dangling_symlink_fails_closed(tmp_path: Path) -> None:
    """A DANGLING symlink at the manifest path is PRESENT but unreadable —
    never absent.  ``Path.exists()``/``stat()`` follow the link and report
    ENOENT, so a naive exists() check collapses it to absent; with no
    engine-source changes in range that would let ``compute_reconcile_scope``
    waive the reconcile (noop) on top of a broken manifest.  The reader must
    BLOCK with the typed error instead, while the genuinely-absent and valid
    cases keep their existing behavior."""
    # (i) dangling symlink -> reconcile BLOCKED (CliError
    #     reconcile_manifest_invalid), never collapsed to absent/waived
    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "missing-target.json")
    assert dangling.is_symlink()
    assert not dangling.exists()  # stat() follows the link: ENOENT
    with pytest.raises(CliError) as excinfo:
        chain_module._reconcile_scope_manifest(dangling, milestone_label="reconcile")
    assert excinfo.value.code == "reconcile_manifest_invalid"
    assert "reconcile milestone reconcile blocked" in excinfo.value.message
    assert "present but unreadable/invalid" in excinfo.value.message

    # (ii) genuinely absent path stays absent -> None (the scope computation
    #     then degrades to pr_required/uncertain — no waiver of the noop kind)
    assert (
        chain_module._reconcile_scope_manifest(
            tmp_path / "never-existed.json", milestone_label="reconcile"
        )
        is None
    )

    # (iii) present, valid manifest still returns the payload (existing
    #     behavior, exercised through the same reader entry point)
    valid = _reconcile_valid_manifest(tmp_path / "valid.json")
    payload = chain_module._reconcile_scope_manifest(valid, milestone_label="reconcile")
    assert isinstance(payload, dict)
    assert payload["epic_id"] == "epic-reconcile"
    assert payload["state"] == "active"


# ── completion guard: waiver acceptance / rejection ────────────────────────


def _reconcile_record(plan: str = "plan-x", **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "label": "reconcile",
        "plan": plan,
        "status": "done",
        "pr_number": None,
        "pr_state": None,
        "kind": "reconcile",
        "target_branch": "main",
    }
    record.update(overrides)
    return record


def test_completion_guard_accepts_reconcile_waiver(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    plan_dir = _plan_dir(root, "plan-x", base_sha, current_state="prepped")
    chain_module._write_reconcile_verification_waiver(
        plan_dir,
        plan="plan-x",
        milestone_label="reconcile",
        base_sha=base_sha,
        scope="no_engine_changes",
        engine_changes=[],
        promotion_evidence=[],
        reason="no engine-source changes in reconcile range",
    )
    ok, reason = chain_module._chain_completion_guard(
        root,
        _reconcile_record(),
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is True
    assert "reconcile verification waiver accepted" in reason


def test_completion_guard_rejects_mismatched_reconcile_waiver(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    plan_dir = _plan_dir(root, "plan-x", base_sha, current_state="prepped")
    chain_module._write_reconcile_verification_waiver(
        plan_dir,
        plan="plan-x",
        milestone_label="reconcile",
        base_sha="0" * 40,
        scope="no_engine_changes",
        engine_changes=[],
        promotion_evidence=[],
        reason="stale base",
    )
    ok, reason = chain_module._chain_completion_guard(
        root,
        _reconcile_record(),
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is False
    assert "base_sha" in reason


def test_completion_guard_accepts_intentionally_rejected_reconcile(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _plan_dir(root, "plan-x", base_sha, current_state="executed")
    record = _reconcile_record(
        pr_number=42,
        pr_state="closed",
        rejection_reason="operator reviewed and declined the reconcile PR",
    )
    ok, reason = chain_module._chain_completion_guard(
        root,
        record,
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is True
    assert "intentionally rejected reconcile PR accepted" in reason


def test_completion_guard_rejects_reconcile_closed_without_reason(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _plan_dir(root, "plan-x", base_sha, current_state="executed")
    record = _reconcile_record(pr_number=42, pr_state="closed")
    ok, _reason = chain_module._chain_completion_guard(
        root,
        record,
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is False  # accidental close is NOT a terminal reconcile outcome


def test_completion_guard_rejects_unknown_reconcile_pr_state(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    _plan_dir(root, "plan-x", base_sha, current_state="executed")
    record = _reconcile_record(pr_number=42, pr_state="open")
    ok, _reason = chain_module._chain_completion_guard(
        root,
        record,
        implementation_milestone=True,
        chain_state=None,
    )
    assert ok is False  # unknown PR state must fail closed, never close


# ── recorded-target validation (reconcile PR base = main, not base_branch) ─


def test_published_target_validated_against_recorded_target_branch(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    merge_sha = _commit(root, "arnold_pipelines/engine.py", message="engine change")
    record = _reconcile_record(
        pr_number=7,
        pr_state="merged",
        pr_merge_sha=merge_sha,
        target_branch="main",
    )
    ok, reason = chain_module._published_pr_semantic_diff_nonempty_from_base(
        root,
        base_sha,
        record,
        chain_state=None,
    )
    assert ok is True
    assert "semantic diff files: arnold_pipelines/engine.py" in reason
    # the lineage check itself validates against the RECORDED target (main),
    # not spec.base_branch
    landed_ok, landed_reason = chain_module._published_target_is_in_chain_target(
        root, merge_sha, None, target_branch="main"
    )
    assert landed_ok is True
    assert "recorded target main" in landed_reason


def test_published_target_rejected_when_not_on_recorded_target_lineage(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    # sibling branch FORKED AT THE BASE: neither side reaches the other
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "checkout", "-b", "other")
    other_sha = _commit(root, "arnold_pipelines/side.py", message="side branch change")
    _git(root, "checkout", "main")
    _commit(root, "arnold_pipelines/engine.py", message="engine change on main")
    record = _reconcile_record(
        pr_number=8,
        pr_state="merged",
        pr_merge_sha=other_sha,
        target_branch="main",
    )
    ok, reason = chain_module._published_pr_semantic_diff_nonempty_from_base(
        root,
        base_sha,
        record,
        chain_state=None,
    )
    assert ok is False
    assert "not contained in recorded target" in reason


def test_published_target_unresolvable_recorded_target_is_uncertain(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    merge_sha = _commit(root, "arnold_pipelines/engine.py", message="engine change")
    record = _reconcile_record(
        pr_number=9,
        pr_state="merged",
        pr_merge_sha=merge_sha,
        target_branch="does-not-exist",
    )
    ok, reason = chain_module._published_pr_semantic_diff_nonempty_from_base(
        root,
        base_sha,
        record,
        chain_state=None,
    )
    assert ok is None
    assert "unresolvable" in reason
    # and the GUARD fails closed for such a record (never local-diff accept)
    plan_dir = _plan_dir(root, "plan-x", base_sha, current_state="executed")
    record["plan"] = "plan-x"
    guard_ok, guard_reason = chain_module._chain_completion_guard(
        root,
        record,
        implementation_milestone=True,
        chain_state=None,
    )
    assert guard_ok is False
    assert "not validated against recorded target" in guard_reason


# ── per-milestone merge policy ─────────────────────────────────────────────


def test_policy_for_spec_forces_review_for_reconcile_milestone() -> None:
    spec = ChainSpec(milestones=[], merge_policy="auto")
    reconcile = MilestoneSpec(label="reconcile", idea="briefs/reconcile.md", kind="reconcile")
    product = MilestoneSpec(label="m1", idea="briefs/m1.md", kind="product")
    assert policy_for_spec(spec, milestone=reconcile).merge_policy == "review"
    assert policy_for_spec(spec, milestone=product).merge_policy == "auto"
    # explicit per-milestone override on a product milestone
    reviewed = MilestoneSpec(label="m1", idea="briefs/m1.md", merge_policy="review")
    assert policy_for_spec(spec, milestone=reviewed).merge_policy == "review"
    # no milestone: chain policy unchanged (backward compatible)
    assert policy_for_spec(spec).merge_policy == "auto"


# ── run_chain: verified-no-op reconcile milestone completes without agent ───


def test_run_chain_completes_reconcile_noop_without_driving_agent(
    tmp_path: Path, monkeypatch
) -> None:
    from unittest.mock import patch

    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    root = _git_repo(tmp_path / "repo")
    base_sha = _git_sha(root)
    initiative = root / ".megaplan" / "initiatives" / "demo"
    (initiative / "briefs").mkdir(parents=True)
    (initiative / "NORTHSTAR.md").write_text("# North Star\n", encoding="utf-8")
    (initiative / "briefs" / "reconcile.md").write_text(
        "# Reconcile\n", encoding="utf-8"
    )
    spec_path = initiative / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: reconcile\n"
        "    kind: reconcile\n"
        "    idea: .megaplan/initiatives/demo/briefs/reconcile.md\n"
        "    branch: reconcile/demo-20260811\n"
        "    target_branch: main\n"
        "    merge_policy: review\n"
        "    phase_model: [execute=codex]\n",
        encoding="utf-8",
    )
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "scaffold initiative",
    )
    _git(root, "remote", "add", "origin", str(root))
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "push", "-u", "origin", "main")
    # a plan dir so the waiver has a durable home (init is patched, not run)
    _plan_dir(root, "plan-reconcile", base_sha, current_state="prepped")

    driven: list[str] = []

    def _fake_init(*_args: Any, **kwargs: Any) -> str:
        driven.append("init")
        return "plan-reconcile"

    with (
        patch(
            "arnold_pipelines.megaplan.chain._init_plan",
            side_effect=_fake_init,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            side_effect=AssertionError("agent must not run for a verified no-op"),
        ),
    ):
        result = chain_module.run_chain(spec_path, root, writer=lambda _msg: None)

    assert result.get("status") == "done"
    assert driven == ["init"]
    state = chain_spec_module.load_chain_state(spec_path)
    completed = [r for r in state.completed if r.get("label") == "reconcile"]
    assert len(completed) == 1
    assert completed[0]["kind"] == "reconcile"
    assert completed[0]["target_branch"] == "main"
    assert completed[0]["pr_number"] is None
    waiver = root / ".megaplan" / "plans" / "plan-reconcile" / "reconcile-verification.json"
    assert waiver.exists()
    payload = json.loads(waiver.read_text(encoding="utf-8"))
    assert payload["schema"] == chain_module.RECONCILE_VERIFICATION_SCHEMA
    assert payload["scope"] == "no_engine_changes"
    # the chain's own state file records the milestone advance
    assert state.current_milestone_index >= len(
        chain_spec_module.load_spec(spec_path).milestones
    )


# ── run_chain ordering: ensure_reconcile_milestone before binding ──────────


def test_run_chain_invokes_ensure_reconcile_before_binding(
    tmp_path: Path, monkeypatch
) -> None:
    from unittest.mock import Mock

    from arnold_pipelines.megaplan.chain import execution_binding as eb_module

    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    root = _git_repo(tmp_path / "repo")
    # an EMPTY-milestone chain: the ordering contract (ensure before state
    # load / binding) is what this test proves; no plan is ever driven
    initiative = root / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "NORTHSTAR.md").write_text("# North Star\n", encoding="utf-8")
    spec_path = initiative / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n  north_star: NORTHSTAR.md\n"
        "milestones: []\n"
        "merge_policy: auto\n",
        encoding="utf-8",
    )
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "scaffold initiative",
    )
    # run_chain refreshes the base from origin; a local path remote suffices
    _git(root, "remote", "add", "origin", str(root))
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "push", "-u", "origin", "main")

    order: list[str] = []

    def _fake_ensure(spec_path_arg: Path, **kwargs: Any) -> ChainSpec:
        order.append("ensure")
        # load WITHOUT materializing, so the milestone loop stays empty
        return chain_spec_module.load_spec(spec_path_arg)

    monkeypatch.setattr(chain_module, "ensure_reconcile_milestone", Mock(side_effect=_fake_ensure))

    def _fake_bind(spec_path_arg: Path, state: Any) -> Any:
        order.append("bind")
        return None

    monkeypatch.setattr(eb_module, "bind_execution_identity", Mock(side_effect=_fake_bind))

    result = chain_module.run_chain(spec_path, root, writer=lambda _msg: None)
    assert result.get("status") in {"done", "completed", "stopped"}
    assert order == ["ensure", "bind"]


# ── T-0501: completed legacy chain (no reconcile) stays terminal ────────────


def _completed_legacy_chain(
    root: Path, *, engine_change_after_completion: bool = False
) -> tuple[Path, str]:
    """A pre-P6 legacy epic that is DURABLY complete and has NO
    ``kind: reconcile`` milestone: one product milestone (local-only, no PR
    branch) with a terminal ``done`` plan, plus a persisted chain state whose
    ``last_state == "done"`` and whose completed records cover every spec
    milestone.

    Returns ``(spec_path, base_sha)``.  With
    *engine_change_after_completion*, a real engine-source commit lands on
    main AFTER *base_sha*, so a naively appended reconcile milestone would
    compute PR-required scope and dispatch the agent — the regression this
    suite must keep terminal.
    """
    initiative = root / ".megaplan" / "initiatives" / "demo"
    briefs = initiative / "briefs"
    briefs.mkdir(parents=True)
    (initiative / "NORTHSTAR.md").write_text("# North Star\n", encoding="utf-8")
    (briefs / "m1.md").write_text("# M1\n", encoding="utf-8")
    spec_path = initiative / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n"
        "merge_policy: auto\n",
        encoding="utf-8",
    )
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "scaffold initiative",
    )
    base_sha = _git_sha(root)

    # terminal plan for the one product milestone (local-only, no PR)
    plan_dir = root / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    plan_dir.joinpath("state.json").write_text(
        json.dumps(
            {
                "current_state": "done",
                "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
            }
        ),
        encoding="utf-8",
    )

    if engine_change_after_completion:
        _commit(root, "arnold_pipelines/engine.py", message="engine change after completion")

    # durable completed chain state: last_state done + every milestone completed
    state = chain_spec_module.ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="done",
        completed=[
            {
                "label": "m1",
                "plan": "plan-m1",
                "status": "done",
                "pr_number": None,
                "pr_state": None,
            }
        ],
        target_base_ref=base_sha,
    )
    chain_spec_module.save_chain_state(spec_path, state)
    return spec_path, base_sha


def test_ensure_reconcile_milestone_completed_legacy_chain_stays_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    """(e) Rerunning a COMPLETED legacy epic is an idempotent terminal
    observation, never a regression to pending reconcile: the durable chain
    state (``last_state == done`` with every milestone completed) wins over
    the missing synthetic milestone — the spec file is untouched and the
    reconcile brief is never materialized."""
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    root = _git_repo(tmp_path / "repo")
    spec_path, _base = _completed_legacy_chain(root)
    before = spec_path.read_bytes()

    messages: list[str] = []
    spec = chain_module.ensure_reconcile_milestone(
        spec_path,
        root=root,
        writer=messages.append,
        now=datetime(2026, 8, 11, tzinfo=timezone.utc),
    )
    assert [m.kind for m in spec.milestones] == ["product"]
    # the SPEC FILE is untouched: no synthetic milestone persisted
    assert spec_path.read_bytes() == before
    assert [m.kind for m in load_spec(spec_path).milestones] == ["product"]
    assert not (spec_path.parent / "briefs" / "reconcile.md").exists()
    # the terminal observation is announced, never silently swallowed
    assert any(
        "reconcile milestone" in m and "not appended" in m.lower()
        for m in messages
    )

    # idempotent: a second run (later date) behaves identically
    messages.clear()
    spec_again = chain_module.ensure_reconcile_milestone(
        spec_path,
        root=root,
        writer=messages.append,
        now=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    assert [m.kind for m in spec_again.milestones] == ["product"]
    assert spec_path.read_bytes() == before
    assert any(
        "reconcile milestone" in m and "not appended" in m.lower()
        for m in messages
    )


def test_run_chain_completed_legacy_chain_stays_terminal_no_agent(
    tmp_path: Path, monkeypatch
) -> None:
    """(e) ``run_chain`` on a durably-completed legacy epic returns a
    terminal observation — status ``done``, no plan initialization, no agent
    drive — and the spec file STILL has no reconcile milestone.  Without the
    durable-completion guard the chain would regress to a pending reconcile
    milestone (PR-required scope: the engine change lands after the milestone
    base) and dispatch the agent."""
    from unittest.mock import patch

    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    root = _git_repo(tmp_path / "repo")
    spec_path, _base = _completed_legacy_chain(
        root, engine_change_after_completion=True
    )
    _git(root, "remote", "add", "origin", str(root))
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "push", "-u", "origin", "main")

    with (
        patch(
            "arnold_pipelines.megaplan.chain._init_plan",
            side_effect=AssertionError(
                "reconcile milestone must not be initialized for a "
                "durably-completed legacy chain"
            ),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            side_effect=AssertionError(
                "agent must not run for a durably-completed legacy chain"
            ),
        ),
    ):
        result = chain_module.run_chain(
            spec_path, root, writer=lambda _msg: None, no_push=True
        )

    assert result.get("status") == "done"
    # the completed epic did not regress: still no reconcile milestone on disk
    assert [m.kind for m in load_spec(spec_path).milestones] == ["product"]
    state = chain_spec_module.load_chain_state(spec_path)
    assert state.last_state == "done"
    assert [r.get("label") for r in state.completed] == ["m1"]
