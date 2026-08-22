# Combined B6+B7 Rework Triage — Attempt 3

Verified at HEAD `133bc4e396`; `c522810273..HEAD` leaves all five regions open. Attempt-2 documentation, service, evidence-matrix, sdist, and `.gitattributes` work is out of scope.

## Findings

1. **ACCEPT — blocking.** `agentbox/cli.py:755,775-781` has a TOCTOU window: `os.replace` can overwrite a concurrent creator, and later rollback can unlink that file, violating frozen T9. **Outcome:** publish staged files with `os.link(..., follow_symlinks=False)`; append `created` only after successful linking; rollback only invocation-created links. **[XHARD] `openrouter:stealth/ox-alpha`**: concurrent publication/rollback custody is subtle and mutation-sensitive. **Acceptance/validation:** race at first and later publications preserves concurrent bytes, removes invocation outputs/temps, and creates no later files. Run `python -m pytest tests/agentbox/test_cli.py::test_cli_new_resident_race_does_not_clobber tests/agentbox/test_cli.py::test_cli_new_resident_rolls_back_without_deleting_concurrent_collision tests/agentbox/test_cli.py::test_cli_new_resident_rolls_back_mid_publication -q`.

2. **ACCEPT — advisory.** `resident/cli.py:1491,1509` overwrites profile-supplied backends. **Outcome:** assign `CloudCliBackend()` only when `getattr(profile_instance, "cloud_backend", None) is None`. **normal — `codex:gpt-5.6-luna`**: localized fallback semantics. **Acceptance/validation:** preserve custom backend identity while injecting the default for `None`; run `python -m pytest tests/agentbox/test_resident_profile.py::test_external_profile_preserves_profile_supplied_cloud_backend -q`.

3. **ACCEPT — advisory.** `resident/cli.py:1398-1411` executes external source with bytecode enabled, so dry-run can mutate the user repo. **Outcome:** suppress bytecode during load and restore prior process state on success/failure. **normal — `codex:gpt-5.6-luna`**: bounded import hygiene. **Acceptance/validation:** dry-run creates no `__pycache__`/`.pyc` and restores suppression state; run `python -m pytest tests/agentbox/test_resident_profile.py::test_external_profile_dry_run_does_not_write_bytecode -q`.

4. **ACCEPT — advisory.** `agentbox/cli.py:707-711` rescans inserted values, replacing user `{{REPO}}` text. **Outcome:** single-pass placeholder substitution. **normal — `codex:gpt-5.6-luna`**: mechanical renderer correction. **Acceptance/validation:** description `{{REPO}}` stays literal while template slots render; run `python -m pytest tests/agentbox/test_cli.py::test_cli_new_resident_substitution_is_single_pass -q`.

5. **ACCEPT — advisory.** `agentbox/cli.py:312-317,630-682` lets installer `OSError` escape as traceback. **Outcome:** convert it to `_diagnostic`, retaining cleanup. **normal — `codex:gpt-5.6-luna`**: bounded CLI error handling. **Acceptance/validation:** injected link `OSError` returns 1, emits concise text/JSON, and leaves no target/temp; run `python -m pytest tests/agentbox/test_cli.py::test_cli_install_omp_agent_oserror_is_diagnostic -q`.

## Minimal parallel dispatch

- **Agentbox executor (effective [XHARD]):** exclusively `agentbox/cli.py`, `tests/agentbox/test_cli.py`; findings 1, 4, 5.
- **Resident executor (normal):** exclusively `arnold_pipelines/megaplan/resident/cli.py`, `tests/agentbox/test_resident_profile.py`; findings 2, 3.

Final validation: `python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q`.
