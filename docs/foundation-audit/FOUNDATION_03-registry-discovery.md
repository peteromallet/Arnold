First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the pack REGISTRY & discovery mechanism

Pack-ification relocates planning into a *discovered* pack and deletes its `_BUILTIN_NAMES`
privilege. Discovery becomes load-bearing for the core flow. Is discovery trustworthy enough?

Investigate (cite path:line):
- `registry.py`: `discover_python_pipelines`, `_module_metadata` (~343-407), `get_pipeline`,
  `_BUILTIN_NAMES` (~53) and its builders (~415-440), `read_skill_md`, name normalization
  (`_`→`-`). How does discovery handle: import errors in a pack? name collisions (builtin vs
  discovered vs `~/.megaplan/pipelines/` user packs)? a pack that imports something broken?
  partial/malformed packs? ordering / shadowing precedence?
- Is discovery import-time or lazy? Side effects on import (prompt registration is "imported for
  effect")? What happens if two packs register the same prompt key?
- The metadata contract: what's required vs optional, what happens when a key is missing — silent
  default or loud failure? (The brief wants `capabilities` added here.)
- Failure mode the brief flags as the one real risk: "silent discovery failure of the core flow."
  Verify how a discovery failure surfaces TODAY — exception? swallowed? logged? Is the proposed
  §8 discovery-integrity guard sufficient, or is the discovery layer itself too lenient/silent?

Key question: is the discovery/registry layer robust and fail-loud enough to host the crown-jewel
flow, or is it a best-effort plugin loader full of silent skips that will hide the day planning
fails to load? Find the silent-failure paths and precedence ambiguities.
