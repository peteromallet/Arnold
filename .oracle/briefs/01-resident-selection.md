# Brief — Area 1: Resident selection and import lifecycle

Explore this area in depth in `/Users/peteromalley/Documents/arnold-oracle` (worktree). Link: `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Goal: R3 needs `arnold_pipelines/megaplan/resident/cli.py` to load a repo-relative external profile (`path.py:Class`). Establish the current mechanics precisely.

Read:
- `arnold_pipelines/megaplan/resident/cli.py` — symbols `_register_resident_subcommands`, `_resident_config`, `_resident_discord`, `_resident_profile`, and the argparse `choices` on the profile argument (~line 1115 area); how the profile is selected and constructed; where the resident project root comes from (config/env/store root); when profile import happens relative to token/network validation; how errors surface as CLI diagnostics.
- `arnold_pipelines/megaplan/resident/config.py` — `ResidentConfig.profile` field (lines ~30-40, ~110-120), env names, defaults, validation.
- Any existing tests exercising profile selection (`tests/resident/`, `tests/agentbox/test_resident_profile.py`).

Report (verified facts, file:line): (1) exact current profile-selection flow and all touchpoints that hard-code the two-value literal; (2) where project root is derived and whether `_resident_profile` can receive it; (3) construction signature of the profile (what it receives: store/authorizer/config/confirmation_manager — where those come from in cli.py); (4) timing: import before or after token validation; (5) how `path.py:Class`-style loading could fit with minimal change; (6) unknowns and risks. Ranked findings, <300 words.
