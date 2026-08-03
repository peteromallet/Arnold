"""Explicit authority-bearing repair identities for cloud tests.

These helpers model facts a production owner must already have persisted.  They
must never be imported by production code or used to turn labels, PIDs, mtimes,
or defaults into repair authority.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.cloud import repair_requests


def repair_identity(
    *,
    session: str,
    plan: str,
    failure_kind: str,
    phase: str,
    task: str,
    attempt: int = 1,
    environment: str | None = None,
    chain: str | None = None,
    plan_revision: str | None = None,
    run_id: str | None = None,
    run_incarnation_id: str | None = None,
    coordinator_attempt_id: str | None = None,
    fence_token: int = 1,
    blocker_hash: str = "sha256:test-blocker",
    chain_identity: str = "test-chain-incarnation",
    run_authority_grant_id: str | None = None,
    lease_id: str | None = None,
    custody_epoch: int = 1,
) -> dict[str, object]:
    """Build a complete normalized identity from explicit test-owned facts."""

    environment = environment or f"/workspace/{session}"
    chain = chain or f"{environment}/{plan}/chain.yaml"
    plan_revision = plan_revision or f"sha256:test-plan-revision:{plan}"
    run_id = run_id or f"test-run:{session}:{plan}"
    run_incarnation_id = run_incarnation_id or f"test-incarnation:{session}:{plan}"
    coordinator_attempt_id = coordinator_attempt_id or f"test-attempt:{attempt}"
    run_authority_grant_id = run_authority_grant_id or f"test-grant:{session}:{plan}"
    lease_id = lease_id or f"test-lease:{session}:{plan}"

    target = repair_requests.build_custody_target_key(
        environment=environment,
        session=session,
        chain=chain,
        plan_revision=plan_revision,
        phase=phase,
        task=task,
        attempt=str(attempt),
        normalized_failure_kind=failure_kind,
        blocker_or_phase_result_hash=blocker_hash,
        fence=f"runner-fence:{fence_token}",
        chain_identity=chain_identity,
    )
    assert target is not None
    identity = repair_requests.build_normalized_repair_identity(
        target=target,
        run_id=run_id,
        run_revision=plan_revision,
        run_incarnation_id=run_incarnation_id,
        coordinator_attempt_id=coordinator_attempt_id,
        fence_token=fence_token,
        wbc_attempt_reference=coordinator_attempt_id,
        run_authority_grant_id=run_authority_grant_id,
        lease_id=lease_id,
        custody_epoch=custody_epoch,
    )
    assert identity is not None, f"invalid explicit repair identity for {plan}"
    return identity


def identity_for_signature(
    *,
    session: str,
    signature: dict[str, object],
    plan: str | None = None,
    **facts: object,
) -> dict[str, object]:
    """Bind a fixture signature to a complete explicit repair identity."""

    phase = str(signature.get("phase_or_step") or "driver")
    task = str(signature.get("blocked_task_id") or f"phase:{phase}")
    failure_kind = str(signature.get("failure_kind") or "unknown_failure")
    plan_name = str(plan or signature.get("milestone_or_plan") or "test-plan")
    return repair_identity(
        session=session,
        plan=plan_name,
        failure_kind=failure_kind,
        phase=phase,
        task=task,
        **facts,
    )
