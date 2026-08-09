# Luna review brief — VJ9 adapter idempotency failure

You are GPT-5.6 Luna at high reasoning. Perform a read-only, evidence-first
root-cause review. Do not edit files, launch subagents, change cloud state, or
retry the run.

Question: Is the current VJ9 failure the same issue as the earlier VJ8
validation/provider failures, or a distinct defect? Explain the relationship
precisely and recommend the smallest safe next action plus the deeper shared
fix.

Working repository: `/Users/peteromalley/Documents/Arnold`

Cloud target (read-only evidence is already captured remotely):
- session: `critique-ledger-accountability-v3-r5-20260803`
- plan: `cl2-wbc-backed-ledger-20260803-1357`
- target workspace: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`

Facts:
- VJ8 occurrence-bound validation was repaired and later passed.
- The cloud resume wrapper initially failed because it used the pinned runtime
  without sourcing `/workspace/.cloud-hot-env`; this produced
  `provider_credentials_missing` for DeepSeek. With the hot-env sourced, the
  same session acquired a live PID and executed.
- The retry then stopped at VJ9. Current authoritative validation artifact:
  `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/verification/validation_VJ9_382d5165e610.json`
- VJ9 command:
  `timeout 120s pytest tests/arnold/adapters/test_ledger_store_adapter.py tests/arnold/workflow/test_attempt_ledger_store.py --tb=short -q --tb=no --no-header -rA`
- VJ9 result: 164 passed, 1 failed:
  `tests/arnold/adapters/test_ledger_store_adapter.py::TestIdempotencyThroughAdapter::test_duplicate_idempotency_key_returns_existing`
- VJ9 raw log:
  `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/verification/raw_382d5165e610.log`
- Introspect after stop reports no live process, `active_phase.liveness=stalled`,
  `last event 1590s ago`, while the plan remains `finalized/ready` and
  `latest_failure=null`.

Inspect only the relevant local production/test surfaces and the captured
evidence. Prefer these files:
- `arnold/workflow/attempt_ledger_store.py`
- `arnold/adapters/ledger_store_adapter.py`
- `tests/arnold/adapters/test_ledger_store_adapter.py`
- `tests/arnold/workflow/test_attempt_ledger_store.py`
- `arnold/workflow/ledger_outbox.py` if needed
- `evidence/critique-ledger-recovery/current-provider-preflight-20260804.md`
- `evidence/critique-ledger-recovery/sol-final-plan-20260804.md`

Return under 1200 words with:
1. A firm verdict: same, related, or distinct (and why).
2. The exact failing contract and likely code path.
3. Whether the failure is a product defect, test/evidence mismatch, or both.
4. The smallest safe repair/revalidation sequence; do not suggest blindly
   clearing the failure or creating a new chain.
5. Shared control-plane changes needed so this failure is surfaced accurately
   and cannot loop or produce stale “ready/running” status.
6. Five concrete acceptance tests.
