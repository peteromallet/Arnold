# Combined B6+B7 Rework Triage — Attempt 4

## Decision — ACCEPT blocker; choose the two-root model

Choose **(a)**. Cross-repo startup is R3’s frozen product contract, and the docs already promise Arnold may be installed or exposed from another checkout. Requiring every target repository to contain Arnold would bless the clone-masked test, duplicate runtime source into user bots, and violate **User-owned** and **Compatibility is a contract**. Two roots are not two runtimes: one interpreter and one imported Arnold runtime still pass through one fail-closed attestation seam; the project is a separately admitted custody identity.

## Required outcome and exact scope

- In `arnold_pipelines/megaplan/cloud/runtime_attestation.py`, keep the existing seed schema and standalone authority identifiers. The standalone seed must require these digest-covered fields with no legacy/missing-field fallback: `project_root`, `expected_project_revision`, `live_project_revision`, `runtime_root`, `expected_runtime_revision`, `live_runtime_revision`, `schema`, `authority`, `generated_at`, `runtime_provenance`, `loaded_modules`, `interpreter`, `site_pth`, `wrappers`, `errors`, `ready`, and `content_sha256`. Bind project Git admission, state directory, pointer, receipt, and process-status custody to `project_root` and its exact HEAD. Bind provenance, module/PTH/wrapper/interpreter vectors and runtime revision to `runtime_root`; re-collect both domains on validation.
- In `arnold_pipelines/megaplan/cloud/runtime_provenance.py`, preserve strict `import_root == expected runtime root` and exact runtime revision checks; do not weaken vector validation.
- In `arnold_pipelines/megaplan/resident/cli.py` and `agentbox/templates/resident/run-resident.tmpl`, resolve the imported runtime with the launch interpreter and pass both roots: retain `--repo-root` and `--expected-head` for the project contract, and add `--runtime-root` and `--expected-runtime-head`. State remains `<project_root>/.megaplan/resident/runtime-launch`. Any mismatch exits before pointer advancement or Discord startup.
- Update `docs/custom-resident-agents.md` to document the two-root invocation and editable/PYTHONPATH runtime contract.
- Update `tests/cloud/test_standalone_runtime_attestation.py`, `tests/agentbox/test_cli.py`, and `tests/agentbox/test_resident_profile.py`. Replace the Arnold-clone integration with a genuine distinct Git project plus separately imported Arnold runtime; assert unequal roots, full issuance → profile construction → process attestation → exactly one mocked service start, and fail-closed drift for either root/HEAD and every runtime vector.

**Classification:** `[XHARD] → openrouter:stealth/ox-alpha presumably`.

## Acceptance and exact validation

Cloud/chain authority behavior is unchanged. Missing, swapped, stale, foreign, edited, or vector-drifted evidence fails with `runtime_launch_attestation_mismatch`, never advances custody state, and never starts Discord. A fresh non-Arnold repository succeeds using an external Arnold checkout.

`python -m pytest tests/cloud/test_runtime_provenance.py tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q`

`bash -n agentbox/templates/resident/run-resident.tmpl`
