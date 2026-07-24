# M8: Repair Loop, Status, And Auditor Consumption

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

Repair-loop, cloud status, and the 6h progress auditor consume the same
structured semantic-health findings.

No layer has to infer boundary failures from vague activity labels or prompt-only
summaries.

## Scope

IN:

- Add semantic findings to repair-loop context and initial facts.
- Add repair-loop prompt guidance that preserves state integrity:
  - diagnose writer/reconciliation/promotion first;
  - do not manually edit lifecycle state as primary repair unless evidence
    proves code is correct and only durable state was interrupted;
  - do not weaken guards.
- Add cloud status fields:
  - `lifecycle_state`;
  - `activity_phase`;
  - `semantic_health_status`;
  - `repair_state`;
  - `custody_state`;
  - `repairable_issue`.
- Add 6h auditor deterministic gather reasons from semantic-health findings.
- Add support for consuming cloud custody findings when they exist, including:
  - `stale_active_step_worker`;
  - `live_unmanaged_process`;
  - `repair_success_without_custody`;
  - `watchdog_status_disagrees_with_custody`.
- Count findings by session, boundary, phase, kind, and repair domain.
- Add meta-repair trigger for repeated unchanged semantic findings after repair
  attempts.

OUT:

- Making the auditor decide facts that the gather layer can compute.
- Collapsing semantic health into lifecycle status.

## Locked Decisions

- Status renders derived views but does not become the source of truth.
- Auditor gather surfaces suspicious facts deterministically.
- A finding unchanged after 2 consecutive independently verified repair
  attempts escalates automatically to meta-repair.
- M8 consumes and displays custody findings produced by M9; the chain therefore
  runs M9 before M8 even though the original draft numbering is preserved.
- Repair-stack custody must reconcile with existing `repair_contract.py`
  concepts instead of creating a second, parallel semantic repair-custody model.

## Done Criteria

1. Repair-loop can repair a semantic finding without `latest_failure`.
2. Cloud status displays semantic health separately from activity.
3. Cloud status displays custody state separately from process liveness.
4. 6h auditor report includes explicit semantic and custody finding reasons.
5. Meta-repair triggers on repeated unchanged semantic/custody findings.
6. Tests cover status separation, custody warning rendering, and auditor gather
   regression.

## Touchpoints

- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
- `arnold_pipelines/megaplan/cloud/six_hour_auditor.py`
- `arnold_pipelines/megaplan/cloud/cli.py`
- `tests/cloud/test_cloud_status.py`
- `tests/cloud/test_watchdog_wrappers.py`
