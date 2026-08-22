# Combined B6+B7 Rework Triage — Attempt 2

## F1-ext — ACCEPT (blocking)

**Evidence:** `_main()` calls `maybe_auto_sync_repo_editor_support(Path.cwd())` before resident dispatch. In a Git repository that call can create or modify `.gitattributes` and `.vscode/settings.json`, violating resident-only state semantics despite the earlier `ensure_runtime_layout` bypass.

**Required outcome:** Skip repo editor auto-sync for every top-level `resident` dispatch while preserving it for all non-resident commands. Extend `test_resident_dispatch_creates_only_resident_owned_state` to prove an absent `.gitattributes` remains absent and pre-existing sentinel content remains byte-identical; also assert `.vscode/settings.json` is not created.

**Criterion / North Star:** R3 / Done criterion 3; **User-owned**.

**Classification/model:** **[XHARD]** — custody-sensitive shared dispatch. `openrouter:stealth/ox-alpha`.

**Validation:**

`python -m pytest tests/agentbox/test_cli.py::test_resident_dispatch_creates_only_resident_owned_state tests/agentbox/test_cli.py::test_non_resident_dispatch_still_initializes_generic_layout tests/arnold_pipelines/megaplan/test_editor_setup.py -q`

## F2 — ACCEPT (blocking)

**Evidence:** The docs claim the env example contains profile/store settings, but those were intentionally removed; launcher arguments own both values. `service.tmpl` advertises drop-in token injection although `run-resident` requires and sources `.agentbox/<name>.env`, so drop-in-only startup fails.

**Required outcome:** Establish one deployment story: `.agentbox/<name>.env` is required and is the sole secret/deployment source. Describe the example as token, mode, and allowlists. Remove the drop-in instructions and empty `Environment=DISCORD_BOT_TOKEN=` directive; replace them with a comment requiring the name-specific env file before service startup. Do not retain a drop-in alternative without changing launcher semantics.

**Classification/model:** **normal** → `codex:gpt-5.6-luna`.

**Validation:** Add a generated-service assertion for the required env-file story and absence of token `Environment=` directives; run `python -m pytest tests/agentbox/test_cli.py -q`.

## F3 — ACCEPT (advisory)

**Evidence:** `.oracle/evidence-matrix.md` stops at Batch 6 and records no sdist receipt.

**Required outcome:** Save `.oracle/evidence/sdist-contents.txt` with the successful sdist build and all five shipped resident-template paths. Add Batch 7 matrix rows for (1) wheel/sdist template shipping and (2) clean-installed generation plus corrected operational documentation; reference the sdist receipt under T11 packaging receipts.

**Classification/model:** **normal** → `codex:gpt-5.6-luna`.

**Validation:** Build and inspect the sdist, assert exactly five resident templates, then run `python -m pytest tests/agentbox/test_package_smoke.py -q`.
