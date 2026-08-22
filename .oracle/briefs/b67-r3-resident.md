# [normal] Rework attempt 3, resident group — GPT-5.6 Luna

Worktree: `/Users/peteromalley/Documents/arnold-oracle`. Execute findings **2 and 3** of `.oracle/rework/batch-6-7-attempt-3.md` verbatim. FILE CONSTRAINT: only `arnold_pipelines/megaplan/resident/cli.py` + `tests/agentbox/test_resident_profile.py` (another agent owns agentbox files).
2. `_resident_profile()`: assign `CloudCliBackend()` only when `getattr(profile_instance, "cloud_backend", None) is None` — preserve profile-supplied backends.
3. Suppress bytecode during external-profile load in dry-run (restore prior state on success/failure; no `__pycache__`/`.pyc` written into the user repo).
Add exactly the named tests (`test_external_profile_preserves_profile_supplied_cloud_backend`, `test_external_profile_dry_run_does_not_write_bytecode`). Run them + `python -m pytest tests/agentbox/test_resident_profile.py -q`. Do not commit. Report under 150 words.
