# Brief — Area 7: Canonical launch-seed provisioning for a second repo

Explore in `/Users/peteromalley/Documents/arnold-oracle` (worktree; omp source read-only at `/Users/peteromalley/Documents/oh-my-pi`). Link `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Context: live resident startup requires a runtime-attestation launch seed (`MEGAPLAN_RUNTIME_LAUNCH_SEED` or equivalent — verify the exact env/mechanism in `arnold_pipelines/megaplan/resident/cli.py` ~1086-1099 and anywhere the seed is produced/validated, e.g. `arnold_pipelines/megaplan/cloud/` wrappers, watchdog, `resident/` attestation code). R3's generated `.agentbox/run-resident` must arrange a VALID seed honestly (never counterfeit).

Questions:
1. What exactly does the attestation check? Read the cli.py attestation block and the seed producer: is it a secret token, a signature, a file, an env var? Where is it validated and what fails when absent/wrong?
2. What produces a canonical valid seed today: cloud deploy wrappers? watchdog? a CLI command (e.g. `resident attest` / `ensure`)? Find the exact producer command and its inputs.
3. Can a standalone (non-cloud) generated repo obtain a valid seed through an existing supported path — or does one need to be created (small, e.g. a `resident seed` subcommand or documented env) as part of R3? Recommend the smallest honest mechanism consistent with the repo's custody/attestation philosophy.
4. Is the seed per-process, per-session, or per-deployment; does it rotate; is it logged anywhere (receipt safety)?

Report: verified facts with file:line, the recommendation, unknowns/risks. Ranked findings, <300 words.
