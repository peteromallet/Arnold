# Combined B6+B7 rework check-in — fresh independent review pass (GPT-5.6 Luna)

> DELEGATION MANDATE — Critique passes optimize for elegance: KISS, YAGNI. Direct, then validate.

Fresh INDEPENDENT REVIEW PASS after the combined B6+B7 rework (new check-in). Read-only. Worktree: `/Users/peteromalley/Documents/arnold-oracle`.

Read `.oracle/rework/batch-6-7-attempt-1.md`, full delta `git diff c522810273..HEAD`, `.oracle/northstar.md`, `.oracle/agent_goal.md`.

Verify FULL combined acceptance:
- B6: exactly-five-file generation (executable launcher, collision refusal, rollback), launcher wires exact-root startup + real env + external profile + repo store + exact-HEAD attest + seed export + resident exec; missing/forged evidence fails pre-Discord; relocatable generated profile (root from `__file__`).
- B7: wheel/sdist ships templates; clean-install generation works; docs complete and accurate; evidence matrix maps R1-R3 + checkpoints.
- Rework F1: resident dispatch creates ONLY resident-owned state; generic commands still init plans/initiatives/schemas.
- Rework F2: one no-network integration test chains attest → profile construction → process attestation → one mocked service start.
- Rework F3: env example deduplicated (profile/store-root via launcher), tests aligned.
Host verified 100 passed across test_cli.py + test_resident_profile.py.

Output: verdict `PASS` or `ISSUES` + numbered findings. Under 250 words.
