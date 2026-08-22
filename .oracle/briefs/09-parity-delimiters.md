# Brief — Area 9: Frontmatter/parity delimiter conventions (omp agent files)

Explore in `/Users/peteromalley/Documents/oh-my-pi` (omp source; read-only) and `/Users/peteromalley/Documents/arnold-oracle` (worktree). Link `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Context: R3 requires RAW byte parity between the omp agent-file body and `AgentBoxOperatorProfile.system_prompt()`, plus generated agent files that parse identically. Freeze the exact frontmatter/body delimiter and terminal-newline rule.

Questions:
1. omp's agent parser (`/Users/peteromalley/Documents/oh-my-pi/packages/coding-agent/src/task/agents.ts`, `parseAgentFields` in `src/discovery/helpers.ts`): exactly how does it split frontmatter from body? (`---` delimiters, first line? trailing newline handling? `\n` vs `\r\n`? does it trim?) Quote the splitting code.
2. What does the `agent` launcher script (`packages/coding-agent/scripts/agent`) pass to `--system-prompt` — the body verbatim after `awk` frontmatter strip, with what trailing-newline behavior?
3. Current files: `agentbox/agents/arnold.md` (worktree) and `agentbox/resident_profile.py` `system_prompt()` (~lines 131-142): compare exact bytes — line wrapping, trailing newline(s) in the markdown body vs the Python string. What exact body text (same wrapping as the Python string, single trailing newline?) makes the parsed body bytes EQUAL the Python string bytes?
4. Any terminal-newline conventions in the repo (`.gitattributes`, editorconfig, CI checks)?

Report: verified facts with file:line, the exact delimiter + terminal-newline rule the generator and parity test must use, unknowns/risks. Ranked findings, <250 words.
