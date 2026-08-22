# [XHARD] Rework attempt 3, agentbox group — stealth/ox-alpha via OpenRouter

Worktree: `/Users/peteromalley/Documents/arnold-oracle`. Execute findings **1, 4, 5** of `.oracle/rework/batch-6-7-attempt-3.md` verbatim. FILE CONSTRAINT: only `agentbox/cli.py` + `tests/agentbox/test_cli.py` (another agent owns resident files).
1. TOCTOU: publish staged new-resident files via `os.link(..., follow_symlinks=False)`; append to `created` only after link success; rollback removes ONLY invocation-created links; concurrent creator's bytes preserved.
2. Single-pass placeholder substitution (description containing `{{REPO}}` stays literal).
3. Installer OSError → `_diagnostic` (exit 1, no target/temp left).
Add exactly the named tests (`test_cli_new_resident_race_does_not_clobber…`, `test_cli_new_resident_substitution_is_single_pass`, `test_cli_install_omp_agent_oserror_is_diagnostic`). Run them + `python -m pytest tests/agentbox/test_cli.py -q`. Do not commit. Report under 200 words.
