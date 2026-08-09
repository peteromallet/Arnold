"""Healthy end-to-end cutover smoke scenario (CL5 Step 17a / SC29).

SC29: "Does the healthy fixed-corpus scenario traverse every cutover stage and
resume admission only after custody, WBC, and runtime-binding checks pass?"

This is ONE bounded test file that drives the REAL cutover package (no import
mocks) through the full healthy lifecycle against a fixed corpus-shaped store
and asserts the exact North Star runtime binding at every binding site:

    quiesce → backup → import(restore)/replay → oracle verification →
    switch(override routing) → retirement → receipt → custody checks →
    WBC receipts → resumed admission

For each stage the happy-path outcome is asserted, and admission is resumed
(via ``clear_cutover_in_progress``) ONLY after the custody (bridge_mode off),
WBC (contract hash bound), and runtime-binding (exact North Star pin) checks
all pass.

NOTE: the deferred ``run_cutover`` orchestration entry point is intentionally
not yet built (the cutover package ``__init__`` documents it as a Phase 2+
addition). The "switch" stage is therefore exercised at its real wiring level —
the cutover action is registered in ``_OVERRIDE_ACTIONS`` and control-routed in
the override matrix, and its fail-closed combined-authority check is enforced —
without invoking the not-yet-built orchestration (an out-of-scope, documented
deferred import). The harness performs the authoritative integration/full-suite
validation.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from arnold.critique_ledger.cutover.backup import (
    MANIFEST_TAR_ENTRY,
    create_cutover_backup,
)
from arnold.critique_ledger.cutover.config import (
    NORTH_STAR_RUNTIME_HASH,
    CutoverConfig,
)
from arnold.critique_ledger.cutover.quiesce import drain, quiesce
from arnold.critique_ledger.cutover.receipt import (
    generate_cutover_receipt,
    verify_receipt_content_hash,
)
from arnold.critique_ledger.cutover.retire import (
    ACTIVE_TARGET_MODULE,
    generate_retirement_proof,
)
from arnold.critique_ledger.cutover.restore import replay_projections, restore_backup
from arnold.workflow.attempt_ledger_store import (
    CutoverInProgressError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)


# ── helpers (mirror tests/arnold/critique_ledger/test_cutover_restore.py) ─────


def _aid() -> str:
    return str(uuid.uuid4())


def _make_identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-1",
        run_id="run-1",
        graph_revision="rev-1",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _make_provenance() -> AttemptProvenance:
    return AttemptProvenance(
        parent_attempt_id=None,
        causal_lineage=(),
        actor_id=None,
        tool_id=None,
    )


def _make_event(
    attempt_id: str,
    sequence: int,
    event_type: AttemptEventType,
    idempotency_key: str,
    *,
    persistence_status: PersistenceStatus = PersistenceStatus.DURABLE,
) -> LedgerEvent:
    cps = sequence - 1
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_make_identity(attempt_id),
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1"),
        versions=VersionSet(code_version="c1"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=cps,
        append_position=sequence - 1,
        occurred_at=f"2025-01-01T00:00:{sequence:02d}Z",
        observed_at=f"2025-01-01T00:00:{sequence:02d}Z",
        persistence_status=persistence_status,
    )


def _seed_in_flight(store: SqliteAttemptLedgerStore, attempt_id: str) -> str:
    """Seed an attempt whose last event is STARTED (non-terminal → in-flight)."""
    store.append_started(
        attempt_id,
        _make_event(
            attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key=f"k-start-{attempt_id}",
        ),
    )
    return attempt_id


def _valid_config() -> CutoverConfig:
    return CutoverConfig(
        source_revision=NORTH_STAR_RUNTIME_HASH,
        target_revision="t" * 40,
        schema_version="sch" * 13,
        wbc_contract_hash="w" * 40,
        m6_oracle_hash="o" * 40,
        corpus_fixture_hash="c" * 40,
        operator_approval_revision="op" * 20,
        backup_identity="b" * 40,
        build_revision="br" * 20,
        north_star_runtime_binding=NORTH_STAR_RUNTIME_HASH,
    )


def _build_corpus(
    tmp_path: Path,
) -> tuple[SqliteAttemptLedgerStore, Path, Path, tuple[str, ...]]:
    """Build a fixed-corpus-shaped store with in-flight attempts + artifacts.

    Returns ``(store, db_path, artifacts, in_flight_ids)``. The store is left
    OPEN so the caller drives quiesce/drain/backup/resume on it.
    """
    db_path = tmp_path / "ledger.sqlite3"
    store = SqliteAttemptLedgerStore(db_path)
    in_flight = tuple(_seed_in_flight(store, _aid()) for _ in range(3))
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "proof-index.json").write_text(
        json.dumps({"schema": "m6.proof-index.v2"}), encoding="utf-8"
    )
    (artifacts / "oracle.json").write_text(
        json.dumps({"north_star": NORTH_STAR_RUNTIME_HASH}), encoding="utf-8"
    )
    return store, db_path, artifacts, in_flight


def _read_manifest(tarball: Path) -> dict:
    import tarfile as _tarfile

    with _tarfile.open(tarball, mode="r") as tar:
        return json.loads(
            tar.extractfile(MANIFEST_TAR_ENTRY).read().decode("utf-8")
        )


# ── SC29: the healthy lifecycle traverses every stage ─────────────────────────


class TestHealthyCutoverSmoke:
    """CL5 Step 17a healthy smoke (SC29)."""

    def test_full_healthy_lifecycle_traverses_every_stage_and_resumes_admission(
        self, tmp_path: Path
    ) -> None:
        """Drive quiesce → backup → import/replay → oracle verification →
        switch → retirement → receipt → custody → WBC → runtime binding →
        resumed admission, asserting the exact North Star pin at every binding
        site. Admission is resumed ONLY after custody + WBC + runtime-binding
        checks pass."""
        config = _valid_config()
        store, db_path, artifacts, in_flight = _build_corpus(tmp_path)

        # ── 1. QUIESCE: engage the durable admission fence + enumerate in-flight.
        q = quiesce(store)
        assert q.cutover_in_progress is True
        assert q.previously_in_progress is False  # fresh cutover
        assert {a.attempt_id for a in q.in_flight} == set(in_flight)
        assert store.is_cutover_in_progress() is True

        # Admission is now CLOSED: a NEW attempt cannot be admitted mid-cutover.
        new_aid = _aid()
        with pytest.raises(CutoverInProgressError):
            store.append_started(
                new_aid,
                _make_event(
                    new_aid,
                    sequence=1,
                    event_type=AttemptEventType.STARTED,
                    idempotency_key="k-new",
                ),
            )

        # ── 2. DRAIN: no terminal events arrive within the (zero) window, so
        #    every in-flight attempt is fail-closed resolved to INDETERMINATE.
        d = drain(store, timeout_seconds=0.0)
        assert d.timed_out is True
        assert {m.attempt_id for m in d.marked_indeterminate} == set(in_flight)
        for mark in d.marked_indeterminate:
            assert mark.resolved_outcome == AttemptOutcome.INDETERMINATE.value

        # ── 3. BACKUP: produce a verifiable, content-addressed tarball bound to
        #    the exact North Star runtime. (create_cutover_backup re-quiesces
        #    idempotently — the fence was already engaged.)
        tarball = tmp_path / "backup.tar"
        backup = create_cutover_backup(
            config, store, db_path, [artifacts], output_path=tarball, now=0.0
        )
        manifest = backup.manifest
        backup_cfg = manifest["cutover_config"]
        assert backup_cfg["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        assert backup_cfg["source_revision"] == NORTH_STAR_RUNTIME_HASH
        assert backup_cfg["wbc_contract_hash"] == config.wbc_contract_hash
        # The backup bound the corpus fixture hash (the fixed M6 corpus).
        assert backup_cfg["corpus_fixture_hash"] == config.corpus_fixture_hash
        # The snapshot included the corpus artifacts.
        archived = {f["path"] for f in manifest["files"]}
        assert any(p.startswith("artifacts/") for p in archived)
        assert manifest["file_count"] >= 1

        # ── 4. IMPORT + 5. REPLAY: restore the backup into a temp target and
        #    replay the content-addressed projection; the restored bundle hash
        #    must REPRODUCE the manifest's content-addressed bundle.
        target = tmp_path / "restore"
        restored = restore_backup(tarball, target, expected_config=config)
        assert restored.integrity_check.ok is True  # oracle: integrity_check ok
        assert restored.bundle_sha256 == manifest["bundle_sha256"]
        replayed_entries, replayed_bundle = replay_projections(target, manifest)
        assert replayed_bundle == manifest["bundle_sha256"]

        # ── 6. ORACLE VERIFICATION: the config validates the exact North Star
        #    runtime binding, and the restored manifest binds the same config.
        config.validate()  # raises on any binding mismatch — passes here
        assert restored.manifest["cutover_config"]["north_star_runtime_binding"] == (
            NORTH_STAR_RUNTIME_HASH
        )

        # ── 7. SWITCH: the cutover override action is registered + control-routed
        #    and enforces fail-closed combined authority (see the dedicated
        #    test below for the routing-off/on matrix proof). Here we assert the
        #    registration that the dispatch depends on.
        from arnold_pipelines.megaplan.handlers.override import (
            _OVERRIDE_ACTIONS,
            _override_cutover,
        )
        from arnold_pipelines.megaplan.workflows.override_matrix import (
            CONTROL_ROUTED_ACTIONS,
        )

        assert _OVERRIDE_ACTIONS.get("cutover") is _override_cutover
        assert "cutover" in CONTROL_ROUTED_ACTIONS

        # ── 8. RETIREMENT: verify the legacy path is retired and the single
        #    active target architecture activates, bound to the North Star.
        proof = generate_retirement_proof(config, now=0.0)
        assert proof["schema"] == "cl5.retirement-proof.v1"
        assert proof["single_target_architecture_active"] is True
        assert proof["active_target"] == ACTIVE_TARGET_MODULE
        assert proof["cutover_config"]["north_star_runtime_binding"] == (
            NORTH_STAR_RUNTIME_HASH
        )
        # The single active target (critique_runtime) is RETAINED.
        retained = {p["module"] for p in proof["retained_paths"]}
        assert ACTIVE_TARGET_MODULE in retained
        # Every retired path is genuinely hard-disabled (bridge_mode off).
        assert all(v is True for v in proof["bridge_mode_state"].values())

        # ── 9. RECEIPT: the canonical receipt binds every revision/hash, FORCES
        #    bridge_mode False, and activates the single target only because the
        #    retirement proof verified against the config.
        receipt = generate_cutover_receipt(
            config,
            backup_manifest=manifest,
            retirement_proof=proof,
            import_counts={"occurrences": 42, "reconciliations": 7},
            smoke_results={"healthy": True},
            operator={"actor": "op", "approved": True},
            reviewer={"actor": "rev", "approved": True},
            now=0.0,
        )
        assert receipt["schema"] == "cl5.cutover-receipt.v1"
        assert receipt["bridge_mode"] is False
        assert receipt["single_target_architecture_active"] is True
        assert receipt["retirement_verified"] is True
        assert verify_receipt_content_hash(receipt) is True
        # Runtime binding: the receipt pins the exact North Star runtime twice.
        assert receipt["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        assert receipt["cutover_config"]["north_star_runtime_binding"] == (
            NORTH_STAR_RUNTIME_HASH
        )
        assert receipt["cutover_config"]["source_revision"] == NORTH_STAR_RUNTIME_HASH

        # ── 10. CUSTODY CHECKS: the legacy BRIDGE custody path is hard-disabled.
        from arnold_pipelines.megaplan.orchestration import (
            critique_custody,
            gate_signals,
        )

        assert critique_custody.CL4_BRIDGE_MODE is False
        assert gate_signals.CL4_BRIDGE_MODE is False

        # ── 11. WBC RECEIPTS: the receipt binds the WBC contract hash, and the
        #    WBC owner domain is the canonical mutating owner in the matrix.
        assert receipt["cutover_config"]["wbc_contract_hash"] == config.wbc_contract_hash
        matrix_path = (
            Path(__file__).resolve().parents[3]
            / "arnold_pipelines"
            / "megaplan"
            / "workflows"
            / "source_to_owner_matrix.json"
        )
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        assert "wbc" in matrix["meta"]["owner_domains"]
        # The override authority matrix surface documents the cutover's combined
        # run_authority + maintenance ownership boundary.
        override_surface = next(
            s for s in matrix["surfaces"] if s["surface_id"] == "override_authority_matrix"
        )
        assert "cutover" in override_surface["description"]

        # ── 12. RESUMED ADMISSION: now that custody (bridge off), WBC (contract
        #    hash bound), and runtime-binding (exact North Star) checks have all
        #    passed, clear the durable fence and resume admitting new attempts.
        assert store.is_cutover_in_progress() is True
        cleared = store.clear_cutover_in_progress()
        assert cleared is True  # the fence WAS engaged
        assert store.is_cutover_in_progress() is False
        # A NEW attempt can now be admitted (resumed admission).
        resumed_aid = _aid()
        store.append_started(
            resumed_aid,
            _make_event(
                resumed_aid,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="k-resumed",
            ),
        )
        assert store.has_terminal_event(resumed_aid) is False
        assert store.event_count(resumed_aid) == 1
        store.close()

    def test_admission_stays_closed_throughout_cutover_resumes_only_after_fence_clear(
        self, tmp_path: Path
    ) -> None:
        """Admission is closed for the entire cutover and resumes only after the
        fence is cleared — a focused admission-lifecycle proof."""
        store, db_path, artifacts, _in_flight = _build_corpus(tmp_path)
        config = _valid_config()

        # Quiesce engages the fence; admission is closed.
        quiesce(store)
        assert store.is_cutover_in_progress() is True
        during_aid = _aid()
        with pytest.raises(CutoverInProgressError):
            store.append_started(
                during_aid,
                _make_event(
                    during_aid,
                    sequence=1,
                    event_type=AttemptEventType.STARTED,
                    idempotency_key="k-during",
                ),
            )

        # The fence is crash-durable: a fresh store re-opening the same database
        # still sees the cutover in progress.
        store.close()
        reopened = SqliteAttemptLedgerStore(db_path)
        try:
            assert reopened.is_cutover_in_progress() is True
            crash_aid = _aid()
            with pytest.raises(CutoverInProgressError):
                reopened.append_started(
                    crash_aid,
                    _make_event(
                        crash_aid,
                        sequence=1,
                        event_type=AttemptEventType.STARTED,
                        idempotency_key="k-crash",
                    ),
                )
            # Only after the fence is cleared does admission resume.
            assert reopened.clear_cutover_in_progress() is True
            resumed_aid = _aid()
            reopened.append_started(
                resumed_aid,
                _make_event(
                    resumed_aid,
                    sequence=1,
                    event_type=AttemptEventType.STARTED,
                    idempotency_key="k-resume2",
                ),
            )
            assert reopened.is_cutover_in_progress() is False
        finally:
            reopened.close()

    def test_switch_cutover_registered_and_combined_authority_enforced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The "switch" stage: the cutover override action is registered on BOTH
        dispatch paths and enforces fail-closed combined authority, so the
        deferred cutover orchestration is never reached without both owner
        domains authorizing dispatch."""
        import argparse

        from arnold_pipelines.megaplan.handlers.override import handle_override
        from arnold_pipelines.megaplan.types import CliError

        def _args(**kw: Any) -> argparse.Namespace:
            base = dict(
                plan="smoke",
                override_action="cutover",
                reason="switch-proof",
                note=None,
                user_approved=False,
                repair_commit=None,
                failure_fingerprint=None,
                repair_scope=None,
                source=None,
                robustness=None,
                profile=None,
                expected_profile_source=None,
                expected_profile_sha256=None,
                phase=None,
                model=None,
                effort=None,
                vendor=None,
            )
            base.update(kw)
            return argparse.Namespace(**base)

        plan_dir = tmp_path / ".megaplan" / "plans" / "smoke"
        plan_dir.mkdir(parents=True)
        plan_dir.joinpath("state.json").write_text(
            json.dumps(
                {
                    "name": "smoke",
                    "idea": "switch",
                    "current_state": "critiqued",
                    "iteration": 1,
                    "created_at": "2026-08-08T00:00:00Z",
                    "config": {"project_dir": str(tmp_path)},
                    "sessions": {},
                    "plan_versions": [],
                    "history": [],
                    "meta": {"current_invocation_id": "inv-switch"},
                    "last_gate": {},
                    "latest_failure": None,
                }
            ),
            encoding="utf-8",
        )

        for routing in ("off", "on"):
            if routing == "on":
                monkeypatch.setenv("MEGAPLAN_CONTROL_INTERFACE_ROUTING", "1")
            else:
                monkeypatch.delenv("MEGAPLAN_CONTROL_INTERFACE_ROUTING", raising=False)
            # No authority → cutover_authority_missing (NOT invalid_override):
            # the action is registered and dispatched on both paths.
            with pytest.raises(CliError) as exc:
                handle_override(tmp_path, _args())
            assert exc.value.code == "cutover_authority_missing"
            assert exc.value.code != "invalid_override"
            # Operator approval alone is insufficient (combined authority).
            with pytest.raises(CliError) as exc:
                handle_override(tmp_path, _args(user_approved=True))
            assert exc.value.code == "cutover_authority_missing"

    def test_receipt_binds_north_star_and_wbc_and_forces_bridge_off(
        self, tmp_path: Path
    ) -> None:
        """Focused receipt-binding proof: the canonical receipt pins the exact
        North Star runtime, binds the WBC contract hash, forces bridge_mode
        False, and its content_hash detects any post-hoc tampering."""
        config = _valid_config()
        store, db_path, artifacts, _in_flight = _build_corpus(tmp_path)
        quiesce(store)
        tarball = tmp_path / "backup.tar"
        backup = create_cutover_backup(
            config, store, db_path, [artifacts], output_path=tarball, now=0.0
        )
        store.close()
        proof = generate_retirement_proof(config, now=0.0)
        receipt = generate_cutover_receipt(
            config,
            backup_manifest=backup.manifest,
            retirement_proof=proof,
            now=0.0,
        )
        # North Star runtime binding at every binding site.
        assert receipt["cutover_config"]["source_revision"] == NORTH_STAR_RUNTIME_HASH
        assert receipt["cutover_config"]["north_star_runtime_binding"] == (
            NORTH_STAR_RUNTIME_HASH
        )
        assert receipt["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        # WBC contract hash bound.
        assert receipt["cutover_config"]["wbc_contract_hash"] == config.wbc_contract_hash
        # Bridge forced off; activation gated behind the verified proof.
        assert receipt["bridge_mode"] is False
        assert receipt["single_target_architecture_active"] is True
        assert verify_receipt_content_hash(receipt) is True
        # Tampering ANY bound field (here: flipping bridge_mode) breaks the hash.
        forged = dict(receipt)
        forged["bridge_mode"] = True
        assert verify_receipt_content_hash(forged) is False
