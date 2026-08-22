# Brief — Area 5: omp project-agent behavior (fresh repo)

Explore this area in depth. Worktree: `/Users/peteromalley/Documents/arnold-oracle`; omp source at `/Users/peteromalley/Documents/oh-my-pi` (read-only reference). Link: `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Goal: R3 generates `.omp/agents/<name>.md` inside ANOTHER repo and expects omp to discover it there. Verify the discovery contract precisely.

Read:
- `/Users/peteromalley/Documents/oh-my-pi/packages/coding-agent/src/task/discovery.ts` — `discoverAgents(cwd, home)`: project `.omp/agents/*.md` precedence vs user `~/.omp/agent/agents/*.md` vs bundled; first-wins by exact name; what counts as a project root (nearest `.omp` walking up?).
- `/Users/peteromalley/Documents/oh-my-pi/packages/coding-agent/src/task/agents.ts` — `parseAgent()`: required frontmatter fields (`name`, `description`), allowed `tools`/`model`/`thinking-level` grammar, name grammar (charset, length), what makes a file skipped.
- `/Users/peteromalley/Documents/oh-my-pi/packages/coding-agent/test/task/discovery.test.ts` — behavioral assertions (project dir shadowing, collisions, malformed files).
- `/Users/peteromalley/Documents/oh-my-pi/packages/coding-agent/scripts/agent` — the CLI launcher: how `agent run <name>` resolves and what `agent list` shows; `OMP_BIN` env.
- Optionally `docs/agents.md` in the omp repo.

Report (verified facts, file:line): (1) exact discovery precedence and project-root determination for a fresh repo; (2) name/frontmatter grammar the generator must satisfy (so generated files are always discoverable); (3) whether a project agent file shadows a same-named user agent and what that means for a second-repo bot named like an existing agent; (4) the `agent run <name>` / `agent list` invocation from within the fresh repo; (5) any gotchas (hidden dirs, gitignored `.omp`, cache, case-sensitivity); (6) unknowns and risks. Ranked findings, <300 words.
