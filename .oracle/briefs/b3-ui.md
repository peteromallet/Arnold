# Executor brief — B3 (Arnold switch: prefer `omp onboard`)
North Star: headless fail-closed preserved; graceful fallback; no fork coupling beyond CLI.
Worktree /Users/peteromalley/Documents/Arnold-onboard-oracle (branch onboard-oracle, already merged to main — sync with origin/main first: git fetch && git merge origin/main). Commit NOTHING.

## Change (agentbox/arnold_agent.py main(), --onboard branch)
Current: `--onboard` runs Python flow.run_flow() directly.
New behavior:
1. Resolve omp binary using the SAME preference as _select_omp_bin (branded fork dist/omp if present, OMP_BIN override, else PATH 'omp'). Extract/reuse that resolution — do not duplicate logic; refactor minimally into a helper both call.
2. If a binary resolves AND it supports onboard (probe: subprocess run [bin, "onboard", "--help"], timeout 15s, exit 0/2 = supported; FileNotFoundError/OSError/other = unsupported), exec it interactively: os.execvp or subprocess.run inheriting stdio (execvp preferred — matches the launcher's process-replacement style); propagate its exit code as main()'s return when not execvp'ing.
   - IMPORTANT: branded fork binary at ~/Documents/oh-my-pi checkout is the DEV runtime — `omp onboard` there now exists only on the onboard-ui worktree branch. For testing before fork merge, allow env override ARNOLD_ONBOARD_BIN pointing at /tmp/oh-my-pi-onboard-ui's cli entry (bun --cwd ... src/cli.ts won't execvp cleanly; document instead of over-engineering: probe uses --help so unsupported forks fall back gracefully).
3. Fallback: any failure to resolve/probe -> existing Python flow.run_flow() path unchanged.

## Tests (extend tests/agentbox/test_onboarding_triggers.py)
- monkeypatched bin resolution: branded-bin-present + supported -> exec called with resolved path (mock os.execvp/subprocess).
- probe-unsupported -> python flow invoked.
- no bin at all -> python flow invoked.
- non-TTY still skips everything (existing guards upstream).
Run: uv run pytest tests/agentbox -q -k onboarding AND uv run pytest tests/agentbox/test_arnold_agent.py -q. Report verbatim tails + deviations.
