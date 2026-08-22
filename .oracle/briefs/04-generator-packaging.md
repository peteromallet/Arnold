# Brief — Area 4: Generator mechanics and packaging

Explore this area in depth in `/Users/peteromalley/Documents/arnold-oracle` (worktree). Link: `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Goal: R3 adds `agentbox new-resident <name> --repo <path>` to `agentbox/cli.py`, plus packaged templates in `agentbox/templates/resident/*` shipped in the wheel. Establish the mechanics to reuse.

Read:
- `agentbox/cli.py` — argparse subcommand pattern, `_emit`/`_diagnostic` JSON conventions, atomic-write usage (the existing `install-omp-agent` handler is the pattern: `_packaged_omp_agent_path`, `_agent_frontmatter_name`, `os.replace` tmp dance), error handling in `main()`.
- `pyproject.toml` — hatch `[tool.hatch.build.targets.wheel]` `packages` + `artifacts` lists (note `agentbox/agents/*.md` and `agentbox/systemd/*.service` already ship).
- `tests/agentbox/test_package_smoke.py` and `tests/agentbox/test_cli.py` — how packaging and CLI are tested.
- Any existing template/slug validation in the repo (search `slugify`, `slug`, name validation in `arnold_pipelines/megaplan/tickets/files.py` and `agentbox/`).
- How the package locates its own resources at runtime (does `agentbox/` use `Path(__file__)` lookups that survive wheel installs? check `_packaged_omp_agent_path` and any `importlib.resources` usage).

Report (verified facts, file:line): (1) the subcommand/emit/diagnostic conventions to follow; (2) existing atomic-write + preflight patterns; (3) the exact `artifacts` mechanism for adding `agentbox/templates/resident/*` and whether `Path(__file__).parent / "templates"` works in a wheel; (4) reusable slug/name-validation code (file:line) and its grammar; (5) how package-smoke tests inspect the installed distribution; (6) unknowns and risks. Ranked findings, <300 words.
