# M2: Semantic Finding Custody And Repair Queue

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

Semantic-health findings become first-class repair evidence, not prompt-only
hints.

When a semantic finding requires repair, the system writes durable structured
evidence and enqueues a repair request into the watched cloud repair queue.

## Scope

IN:

- Define serializable `SemanticFinding` schema:
  - `schema_version`;
  - `evaluator_version`;
  - `generated_at`;
  - `source`;
  - `boundary_id`;
  - `plan_dir`;
  - `state_path`;
  - `phase`;
  - `kind`;
  - `severity`;
  - `repair_domain`;
  - `recommended_action`;
  - `current_state`;
  - `missing_contract`;
  - `artifact_fingerprints`;
  - `active_evidence`;
  - `suppression_reason`;
  - `human_summary`.
- Define the finding lifecycle:
  - `observed`;
  - `queued`;
  - `claimed`;
  - `repairing`;
  - `cleared`;
  - `unchanged_after_repair`;
  - `stale`;
  - `suppressed`;
  - `waived`;
  - `human_required`;
  - `escalated`;
  - `terminal`.
- Store findings in a durable sidecar keyed by request id or problem signature.
- Store rich evidence as content-addressable or warrant-compatible records where
  existing store/warrant/capsule APIs can support it.
- Ensure `arnold-repair-loop` can read findings even when there is no
  `latest_failure`.
- Encode stable identity using existing `PROBLEM_SIGNATURE_FIELDS`.
- Prove producer/watchdog enqueues land in the queue watched by
  `megaplan-repair-trigger.path`.

OUT:

- Reworking repair request schema unless unavoidable.
- Prompt-only evidence.
- Storing raw rich evidence only in `root_cause_hint`; it is hashed and not
  sufficient for custody.

## Locked Decisions

- Rich evidence lives outside the signature.
- Signatures exclude timestamps and volatile summaries.
- Coalesced requests must not hide fresher evidence; update or reference latest
  evidence by signature.
- Findings are cleared by an evaluator proving the contract is now satisfied,
  not by repair code declaring success.
- Waivers and suppressions are authority-bearing records with actor, scope,
  expiry where applicable, and evidence refs.
- Queue path correctness is tested.

## Done Criteria

1. A semantic finding can be serialized and reloaded losslessly.
2. Repair request identity is stable across repeated evaluations of the same
   unchanged finding.
3. Newer evidence for the same signature remains discoverable.
4. `arnold-repair-loop` context includes semantic findings.
5. Tests prove lifecycle producers do not write to an unwatched repair queue.

## Touchpoints

- `arnold_pipelines/megaplan/cloud/repair_requests.py`
- `arnold_pipelines/megaplan/cloud/repair_contract.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
- `tests/cloud/test_watchdog_wrappers.py`
- `tests/cloud/test_repair_request_hooks.py`
