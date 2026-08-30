# NBF-01 execution report — GPT-5.6 Luna

Date: 2026-08-29

## Gate and custody

- Frozen tasklist: `.oracle/tasklist.md`, SHA-256
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
- Freeze receipt: `.oracle/receipts/tasklist-freeze-v8.md`, verdict
  `PASS_FREEZE`.
- Settled plan SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`.
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Branch: `megado-nbf-guard-0826`.
- No commit, push, merge, reset, clean, or staging was performed.

## Changed owned paths

- `arnold_pipelines/megaplan/orchestration/phase_result.py`: strict
  `SchedulingCondition`, `DispatchOutcome`, launch/kind enums, PhaseResult
  transport and validation, including explicit worker disposition.
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`: typed
  dispatch classification and scheduling bypass helpers.
- `arnold_pipelines/megaplan/incident/schema.py`: closed disposition, observed
  death, non-worker, fingerprint, provider-key, changed-precondition,
  reconciliation, confirmation, receipt, and NBF event codecs/producers.
- `arnold_pipelines/megaplan/incident/ledger.py`: one existing-journal NBF append
  door, deterministic replay projection, reservation CAS, terminal linkage,
  provider observation/probe primitives, composite child reservation, receipt
  derivation, reconciliation, confirmation, and single-use change consumption.
- `arnold_pipelines/megaplan/incident/disposition.py`: canonical validating
  helpers and non-signalling JSON-stdin CLI with documented exit statuses.
- `arnold_pipelines/megaplan/incident/__init__.py`: public exports.
- Eight focused test modules listed by NBF-01 were added.

No admission caller, scheduler, T7/T8 policy, physical door, launch adapter, or
signal-site wiring was changed.

## Validation

1. `python -m py_compile arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/disposition.py` — exit 0.
2. Required focused command (the eight new modules plus
   `test_incident_ledger.py`) — exit 0, **61 passed** (including contention,
   torn-line replay, keyed streak, terminal conflict, ambiguity, and TTL
   branches added during handoff).
3. Narrow legacy regressions:
   `pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py` — exit 0, **78 passed**.
4. CLI smoke test with a valid worker disposition — exit 0; one JSON
   acknowledgement emitted and no signal attempted.
5. `git diff --check` — exit 0.

Evidence covered by focused tests includes strict round trips/unknown-field
rejection, explicit worker-disposition identity and non-coercion, no-launch
distinction, volatile-excluding fingerprint/provider-key derivation, one
reservation projection and cross-logical-ID contention, torn-line replay,
terminal linkage idempotency/conflict, positive and ambiguous reconciliation,
evidence-bound changed-precondition production, confirmation TTL/separation and
single consumption, keyed provider replay, and CLI validation.

## Diff and residual issues

Tracked owned production diff SHA-256 (binary unified diff):
`4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`.

The worktree retains the pre-existing orchestrator-owned `.oracle` changes and
untracked planning/review artifacts. A concurrent `.oracle/briefs/oracle-nbf01-grok.md`
also appeared during execution; it was not touched. No non-owned source path was
modified. The implementation is intentionally primitive-only; real caller and
signal integration remains for later batches and requires independent Sol
Oracle review before any Batch 1 commit.
