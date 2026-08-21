# North Star — Arnold custom-agent platform

## Desirable end state
Anyone can run a **named, branded agent** ("arnold", then "astrid", then any repo's bot) that carries the current Discord resident prompt as its system prompt, tweak it with basic customisations (name, description, prompt, model, tools), and create a **new custom bot in another repo** from the same approach — without touching omp internals, without renaming compatibility surfaces, and without re-architecting the resident runtime.

Concretely: `agent run arnold` speaks the agentbox-operator-v1 persona; `agentbox install-omp-agent <name> --name/--description` ships a customised agent; `agentbox new-resident <name> --repo <path>` scaffolds a working Discord bot in a fresh repo (agent file + resident profile + env + launcher + systemd unit), backed by the existing resident platform.

## Enduring qualities / invariants
- **One runtime, one seam.** omp is the only model runtime; named agents are markdown files; the agent file is the entire identity surface. No second dispatch path.
- **Elegance over machinery.** The smallest surface that covers the need: markdown is the declarative config; CLI flags only for the two things users actually change (name, description). No flag duplication of file-editable fields.
- **Compatibility is a contract.** Never rename `arnold.megaplan.*`, `arnold-resident-*`, `ARNOLD_RESIDENT_DELEGATION_CONTEXT`, `arnold:resident-delivery:`; never rename omp's `@oh-my-pi/*`, binary, `APP_NAME`, `.omp`. Existing stores and cloud runs keep working.
- **Fork-clean omp.** Zero changes to omp source; everything ships via `.omp/` config, agent files, and the Arnold repo.
- **User-owned.** The human can run, customise, and extend without reading harness internals; every generated bot is understandable from its five scaffold files.

## Anti-patterns / hollow success
- Re-architecting the resident runtime to "make it general" — the platform exists; add seams, not engines.
- A generator that generates more than it documents — the scaffold must be readable and hand-editable, not a magic tree.
- Flag soup on the installer (--model/--tools/--prompt-file) duplicating markdown — precedence and quoting hell.
- Renaming compatibility surfaces for cosmetics (schema ids, env names, package names).
- Any mutation of `main` from this run; any silent scope widening (purge, unrelated refactors).
- Touching the Discord tool catalog semantics via agent-file `tools` — Discord actions come from the resident profile's tool registry; the agent file governs omp named-agent runs only.
- Working on a different prompt than the one the Discord resident actually runs — byte-parity with `AgentBoxOperatorProfile.system_prompt()` is the invariant.

## What aligned progress feels like
Each batch leaves the worktree green and the run closer to a working second-repo bot: installer customisation proven, external profile loading proven, one generated repo passing named-agent execution and a Discord dry-run, then one live round trip. Small commits, oracle-gated checkpoints, no dead ends.
