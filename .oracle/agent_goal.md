# Agent goal — megado run: custom-agent implementation (R1–R3)

Frozen operational contract for this run. Links [North Star](./northstar.md).
This run advances the North Star by turning the branded `arnold` agent into a
**runnable, customisable, cross-repo-reproducible** platform deliverable.

## Objective
Implement and prove, end to end, the custom-agent capability on the Arnold repo
(in a worktree, never on `main`):

- **R1 — runnable**: `arnold` runs as an omp named agent whose system prompt is
  the current Discord resident prompt (`agentbox-operator-v1`, byte-identical
  to `AgentBoxOperatorProfile.system_prompt()`). Foundation committed
  (`agentbox/agents/arnold.md` + `agentbox install-omp-agent arnold` + tests).
  Deliverable: verified invocation (`agent run arnold`), docs.
- **R2 — basic customisations**: `agentbox install-omp-agent` gains
  `--name` / `--description` (output name + frontmatter); users customise
  prompt/model/thinking/tools by editing the markdown file; canonical persona
  changes follow the 3-step discipline (agent file + `resident_profile.py` +
  version bump) with a byte-parity test.
- **R3 — generalisable**: `agentbox new-resident <name> --repo <path>` scaffolds
  a custom Discord bot in another repo: project `.omp/agents/<name>.md`,
  `.agentbox/resident_profile.py` (subclass of `AgentBoxOperatorProfile`),
  `.agentbox/resident.env.example`, `.agentbox/run-resident` launcher,
  `.agentbox/<name>-resident.service`. Resident profile loading becomes
  extensible (`resident/config.py` profile string; `resident/cli.py` loads
  repo-relative `path.py:Class`). Zero omp fork changes.

## Authoritative inputs
- Source ref: `744a417198` (see `.oracle/custody.md`); foundation commit `b7c682798e`.
- Prior planning artifacts (facts + Codex R1–R3 plan): `/tmp/arnold-custom-agent/plan2-out.txt`,
  `/tmp/arnold-custom-agent/results/*.txt` (research reports), `.oracle/custody.md` facts.

## In-scope
- `agentbox/cli.py` (installer flags, `new-resident`), `agentbox/agents/`,
  `agentbox/templates/resident/*`, `pyproject.toml` artifacts,
  `arnold_pipelines/megaplan/resident/config.py` + `cli.py` (extensible profile
  loading), docs (`docs/custom-resident-agents.md`), tests for all of the above.

## Non-goals / out of scope (do NOT do)
- The hermes→omp label purge — it is in flight in the main tree (separate job);
  this worktree predates it. Do not re-implement or conflict with it; treat the
  resident as omp-based and build on the current tree's reality.
- Renaming compat surfaces: `arnold.megaplan.*`, `arnold-resident-*`,
  `ARNOLD_RESIDENT_DELEGATION_CONTEXT`, `arnold:resident-delivery:` UUID ns.
- Renaming omp identities (`@oh-my-pi/*`, `omp` binary, `APP_NAME`, `.omp`).
- Any mutation of `main` or other worktrees; no pushes except the oracle-run branch at the end.
- Discord developer-portal setup (external, manual, documented only).
- Megaplan phase machinery, the Discord transport internals (`discord.py`), or
  the tool catalog — unless a generated profile demonstrably requires a seam.

## Authorization boundaries
- Mutate: this worktree (`/Users/peteromalley/Documents/arnold-oracle`) only.
- Commit: per-batch commits on `oracle-run`; `.oracle/` artifacts may be committed.
- Sync: at completion, push `oracle-run` to `origin` (`HEAD:oracle-run`). NEVER main.
- Open: `open` the worktree at completion.
- Escalate to user: any change to the frozen goal, North Star, model policy,
  or any discovered need to touch `main` or rename compat surfaces.

## Model policy (user-declared; no automatic routing)
- **Normal tasks (explore, execute, review passes): GPT-5.6 Luna** (`codex:gpt-5.6-luna`). UNCHANGED.
- **[XHARD] tasks: stealth/ox-alpha via OpenRouter** (`openrouter:stealth/ox-alpha`) — user switch 2026-08-21, replacing GPT-5.6 Sol. Probe verified (PROBE-OK, 6.5s).
- **Planner / Oracle / sense checker: GPT-5.6 Sol** (`gpt-5.6-sol`, high reasoning). UNCHANGED unless user says otherwise.
- Switching any class requires user approval; record every receipt with model + rationale.

## Done criteria (all must pass)
1. `agent run arnold` (via `~/.bun/bin/agent`) returns behavior governed by the
   agentbox-operator-v1 prompt; body byte-parity test green.
2. `agentbox install-omp-agent <template> --name <n> --description "<d>" --target <dir>`
   produces a renamed, re-described agent file; tests green.
3. `agentbox new-resident <name> --repo <path>` scaffolds the five files; the
   generated profile imports and passes a dry-run (`run-resident --dry-run`
   or equivalent no-network validation); external profile loading works with
   validation + clear rejection of bad profiles.
4. Tests: `pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py`
   green; full targeted suite (affected areas) green.
5. Evidence matrix maps every criterion above to a receipt/evidence path.
6. Final oracle review (Sol) passes; North Star alignment confirmed; anti-patterns avoided.

## Validation commands
- `python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q`
- `python -c "import agentbox.cli"`
- `~/.bun/bin/agent list` (shows arnold) and one `~/.bun/bin/agent run arnold "…"` probe
- `agentbox new-resident demo --repo /tmp/demo-resident` + `python -c "import …"` on the generated profile
- No live Discord call required for this run; dry-run/structural validation only.

## Sync/promotion policy
- End of run: final verification → final oracle review → commit → push `oracle-run`
  to `origin` → `open` worktree → report phase-by-phase evidence.
- Merging `oracle-run` into `main` is a separate, user-authorized action; not performed here.
