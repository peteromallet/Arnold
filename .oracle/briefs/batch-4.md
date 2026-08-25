# Executor brief — Batch 4 (Triggers)
North Star: headless stays fail-closed byte-for-byte; offer only on interactive TTY; never nag.
Worktree /Users/peteromalley/Documents/Arnold-onboard-oracle. Commit NOTHING.

Read first: agentbox/arnold_agent.py (main, _split_flags, _select_omp_bin), arnold_pipelines/megaplan/preflight.py preflight_or_raise L325-414 (existing unimplemented TTY menu handlers!), arnold_pipelines/megaplan/cli/run.py _validate_profile_for_run L628-640, doctor registrations (megaplan cli/__init__.py parser L649 dispatch L2917/L3732; agentbox/cli.py L176/L304).

## Task 1: T1 primary trigger in agentbox/arnold_agent.py main()
Insert before launcher resolution/execvp:
  from agentbox.onboarding.flow import offer_and_repreflight (lazy import INSIDE the guarded branch to keep startup cost zero and avoid import cycles)
Guards come from flow.should_offer(message=..., flags=..., environ=os.environ). When offering: repreflight = quick zero-route check (detect.scan_providers has >=1 ready). Keep the block tiny (<25 lines); any exception in onboarding code must NEVER break launch: wrap in try/except Exception -> proceed silently.

## Task 2: T2 megaplan preflight menu handler
preflight_or_raise already renders a TTY menu with unimplemented option handlers. Wire the relevant handler(s) to flow.run_flow then re-run the preflight checks; if now passing continue, else original exit 7 path unchanged. Non-TTY branch untouched. Study the existing structure FIRST and make the minimal change consistent with its style.

## Task 3: T3 doctor --onboard
Add --onboard flag to megaplan doctor parser + handler (runs flow.run_flow directly, reports exit code) AND agentbox doctor if trivially symmetric; skip if agentbox doctor plumbing makes it awkward (report choice).

## Task 4: tests tests/agentbox/test_onboarding_triggers.py (+ extend preflight tests if needed)
- T1: guard-matrix integration: one-shot/resume/non-TTY/CI -> no prompt (monkeypatch flow.offer_and_repreflight to record calls); interactive empty-message TTY session -> called once; onboarding exception swallowed -> launch proceeds.
- Golden regression [W1/R1]: capture stderr of `arnold` non-TTY invocation pre/post change — assert identical. Implement as: run main() twice in-process with capsys/captured fds? Prefer subprocess-free approach: monkeypatch os.execvp to raise a sentinel, compare stderr bytes with/without onboarding importable but guards failing. If truly impractical, assert that with guards failing NO output is written by the onboarding block (byte-identical by construction + unit proof).
- Old-pin [W1/R2]: PATH without omp -> offer returns None path exercised (already unit-tested in B3; here assert T1/T2 call sites propagate None -> original failure).
- T2: preflight TTY handler invokes flow when creds missing; exit 7 preserved non-TTY (use existing preflight test fixtures).
Run: uv run pytest tests/agentbox -q -k onboarding AND uv run pytest tests/agentbox/test_onboarding_triggers.py plus any touched preflight tests. Report verbatim + deviations.
