# Batch 5 rework — attempt 1

All three findings are accepted.

## 1. Worker-refresh authority bypass

**Finding + evidence:** Accepted, blocking. `refresh_runtime_launch_seed_for_worker_dispatch()` (`runtime_attestation.py:1824–1830`) returns the configured seed when `ARNOLD_RUNTIME_MANIFEST` is absent before loading it or requiring cloud-chain authority. This lets a standalone seed cross the worker-dispatch custody boundary, contrary to frozen gate §1.

**Criterion + North Star:** Batch 5/T8 requires cloud/standalone mismatches to fail closed while chain behavior remains unchanged. **Compatibility is a contract**—existing cloud runs must keep working.

**Required outcome + scope:** When a seed is configured, load it and require cloud-chain authority before the no-manifest return. Preserve `None` for no configured seed and all existing cloud refresh behavior. Focused code and tests only.

**Classification/model:** **[XHARD]**—custody-boundary correction with cloud-regression risk. `openrouter:stealth/ox-alpha`.

**Acceptance + exact validation:** Standalone seed plus absent/blank manifest raises typed `runtime_launch_attestation_mismatch`; cloud seed retains existing behavior; no seed returns `None`; manifest-present refresh remains unchanged. Run:
`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_worker_refresh_rejects_standalone_seed_without_manifest -q`
`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

## 2. Unsafe reused state-directory permissions

**Finding + evidence:** Accepted, blocking. `standalone_runtime_launch_dir()` secures only the root; `standalone_dispatch_paths()` silently chmods reused `seeds/`, `receipts/`, and `status/`; pointer loading validates files, not parent modes; process creation can write through reused unsafe `status/`.

**Criterion + North Star:** T8 requires root-custodied state and fail-closed custody. **Compatibility is a contract**—cloud paths remain unchanged.

**Required outcome + scope:** Centrally require real, contained `0700` operational directories on every standalone publication, load, and process create/read path; reject unsafe reuse before mutation. Preserve `0600` object checks.

**Classification/model:** **[XHARD]**—multi-path custody enforcement. `openrouter:stealth/ox-alpha`.

**Acceptance + exact validation:** Parameterize each directory at `0755`; relevant operations reject it, never repair it, and leave pointer/status bytes unchanged. Fresh modes remain `0700/0600`. Run the two-file suite above.

## 3. Non-string authority crash

**Finding + evidence:** Accepted, advisory. Membership checks at `runtime_attestation.py:1867` and `:2383` allow list/dict authorities to raise raw `TypeError`.

**Criterion + North Star:** T8 fail-closed mismatch behavior; **Compatibility is a contract** through typed errors.

**Required outcome + scope:** Guard with `isinstance(authority, str)` before membership; preserve valid strings.

**Classification/model:** **normal**—mechanical validation fix. `codex:gpt-5.6-luna`.

**Acceptance + exact validation:** List/dict values raise typed mismatch, never `TypeError`; valid authorities remain unchanged. Add the focused parameterized test, then run the two-file suite.
