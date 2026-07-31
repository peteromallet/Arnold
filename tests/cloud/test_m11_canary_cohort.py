from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.m11_canary_cohort import (
    aggregate_cohort,
    fanout_delayed_verifiers,
    provision_private_authority,
    run_singleton_mutation,
)
from arnold_pipelines.megaplan.cloud.m11_live_canary import (
    CanarySafetyError,
    _default_authority_check,
    _atomic_json,
    _digest,
)
from arnold_pipelines.megaplan.cloud.simple_fixer import build_simple_fixer_occurrence


def _occurrence(index: int) -> dict[str, str]:
    return {
        "environment": "canary",
        "session": f"cohort-session-{index}",
        "chain": "cohort-chain",
        "plan_revision": f"revision-{index}",
        "phase": "execute",
        "task": f"T{index}",
        "attempt": "1",
        "normalized_failure_kind": "supervised_run_exhausted",
        "blocker_or_phase_result_hash": f"sha256:blocker-{index}",
        "fence": f"fence:{index}",
    }


def _sample(root: Path, index: int) -> None:
    root.mkdir(parents=True)
    fingerprint = f"sha256:{index:064x}"
    manifest = {
        "occurrence_fingerprint": fingerprint,
        "complete": True,
    }
    manifest["content_sha256"] = _digest(manifest)
    _atomic_json(root / "manifest.json", manifest, exclusive=True)
    ledger = {
        "latency_ledger_rows": [
            {
                "occurrence_fingerprint": fingerprint,
                "durable_event_kind": "process_exit",
                "durable_event_timestamp": "2026-07-31T00:00:00+00:00",
                "terminal_receipt_kind": "accepted_repair",
                "terminal_receipt_timestamp": "2026-07-31T00:00:01+00:00",
                "terminal_receipt_id": f"receipt-{index}",
                "latency_seconds": float(index),
                "cohort_eligible": True,
                "eligibility_reason": "eligible",
            }
        ]
    }
    ledger["content_sha256"] = _digest(ledger)
    _atomic_json(root / "latency-ledger.json", ledger, exclusive=True)


def test_twenty_private_roots_aggregate_nearest_rank_p95(tmp_path: Path) -> None:
    base = tmp_path / "m11-canaries"
    roots = [base / f"m11-genuine-block-{index:02d}" for index in range(1, 21)]
    for index, root in enumerate(roots, start=1):
        _sample(root, index)
    result = aggregate_cohort(
        roots,
        destination=base / "cohort.json",
        base_root=base,
    )
    assert result["complete"] is True
    assert result["slo_met"] is True
    assert result["ledger"]["sample_count"] == 20
    assert result["ledger"]["p95_seconds"] == 19.0
    assert len(set(result["sample_roots"])) == 20


def test_twenty_roots_provision_independent_real_authority(tmp_path: Path) -> None:
    base = tmp_path / "m11-canaries"
    seen_leases: set[str] = set()
    for index in range(1, 21):
        root = base / f"m11-genuine-block-authority-{index:02d}"
        payload = _occurrence(index)
        authority = provision_private_authority(
            root=root,
            occurrence_payload=payload,
            index=index,
            base_root=base,
        )
        occurrence = build_simple_fixer_occurrence(payload)
        assert occurrence is not None
        assert _default_authority_check(occurrence, authority).authorized
        assert authority["custody_lease_id"] not in seen_leases
        seen_leases.add(authority["custody_lease_id"])


def test_global_mutation_lock_rejects_overlap(tmp_path: Path) -> None:
    base = tmp_path / "m11-canaries"
    first_root = base / "m11-genuine-block-first"
    second_root = base / "m11-genuine-block-second"
    first_root.mkdir(parents=True)
    second_root.mkdir(parents=True)
    entered = threading.Event()
    release = threading.Event()

    def blocking_runner(**kwargs):
        entered.set()
        assert release.wait(2)
        return {"root": str(kwargs["root"])}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            run_singleton_mutation,
            {"root": first_root},
            base_root=base,
            runner=blocking_runner,
        )
        assert entered.wait(1)
        with pytest.raises(CanarySafetyError, match="mutation is active"):
            run_singleton_mutation(
                {"root": second_root},
                base_root=base,
                runner=blocking_runner,
            )
        release.set()
        assert first.result()["root"] == str(first_root.resolve())


def test_delayed_verifier_fanout_is_bounded_and_parallel() -> None:
    gate = threading.Barrier(20)
    jobs = [
        (lambda index=index: (gate.wait(timeout=2), {"index": index})[1])
        for index in range(20)
    ]
    results = fanout_delayed_verifiers(jobs)
    assert {row["index"] for row in results} == set(range(20))
    with pytest.raises(CanarySafetyError, match="exceeds"):
        fanout_delayed_verifiers([lambda: {}] * 21)
