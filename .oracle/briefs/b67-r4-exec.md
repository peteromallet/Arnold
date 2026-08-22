# [XHARD] Rework batch 6-7 (attempt 4) — stealth/ox-alpha via OpenRouter

Worktree: `/Users/peteromalley/Documents/arnold-oracle`. Execute `.oracle/rework/batch-6-7-attempt-4.md` VERBATIM — it is the frozen two-root design decision. Summary of scope:
1. `cloud/runtime_attestation.py`: standalone seed requires digest-covered `project_root`, `expected_project_revision`, `live_project_revision`, `runtime_root`, `expected_runtime_revision`, `live_runtime_revision` (+ existing schema/authority/generated_at/vectors/ready/content_sha256), no legacy fallback. Project Git admission, state dir, pointer, receipt, process-status custody bind to `project_root`+HEAD; provenance/module/PTH/wrapper/interpreter vectors + runtime revision bind to `runtime_root`. Re-collect vectors at startup against runtime_root.
2. `cloud/runtime_provenance.py`: keep strict `import_root == expected RUNTIME root` + exact revision checks — no weakening.
3. `resident/cli.py` `resident attest`: retain `--repo-root`/`--expected-head` (project) + add `--runtime-root`/`--expected-runtime-head`. Mismatch exits before pointer advance/Discord startup. State stays `<project_root>/.megaplan/resident/runtime-launch`.
4. `agentbox/templates/resident/run-resident.tmpl`: resolve imported Arnold runtime root via the launch interpreter (`import arnold_pipelines; print(dirname(dirname(...)))` pattern or equivalent), pass both roots to attest.
5. Docs (`docs/custom-resident-agents.md`): two-root invocation + editable/PYTHONPATH runtime contract.
6. Tests: replace the Arnold-clone-masked integration test with a GENUINE distinct git project + external Arnold runtime (unequal roots asserted); full issuance → profile construction → process attestation → one mocked service start; fail-closed drift for either root/HEAD and every vector. Update `tests/cloud/test_standalone_runtime_attestation.py` for the new schema fields.

Cloud/chain authority behavior unchanged. Validation: run the five-suite command from the spec + `bash -n agentbox/templates/resident/run-resident.tmpl`. Do not commit. Report: hunks, tests, one successful two-root `attest --json`, acceptance confirmations. Under 350 words.
