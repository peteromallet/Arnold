First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the layer ABOVE planning — `chain.py` (epics), cloud providers, bakeoff

Planning isn't driven directly; it's driven by `chain.py` (epics), `cloud/` (provider-managed runs
shelling `megaplan` over SSH), and `bakeoff` (subprocess isolation). When planning moves into a pack
and dispatch unifies, these CONSUMERS are the blast radius. They are foundational because they pin
the external contract the refactor must preserve. Find the coupling the brief under-mapped.

Investigate (cite path:line):
- `chain.py` (~1846 LOC): how it drives `auto`/planning, its direct `current_state` write at
  `_mark_blocked_execute_as_executed` (~1517), `chain_state.json`, how it reads `DriverOutcome`/
  `--outcome-file`, ordering/failure semantics. What internal megaplan APIs does it bind to that
  will change?
- `cloud/providers/{ssh,railway,local}.py`: exactly which `megaplan` subcommands + JSON contracts
  they shell over SSH (`status`, `init`, `phase_result.json`, `chain_state.json`). Version-skew
  risk: new-local + old-remote. Is there ANY compat-window enforcement? (Brief says no.)
- `bakeoff`: its subprocess isolation, its own `state.py` (which HAS a schema_version — contrast).
  What does it assume about planning's CLI surface?
- The user-facing skills (`megaplan`, `-decision`, `-epic`, `-observe`, `-bakeoff`, `-cloud`,
  `-tickets`) "consume the pack's SKILL.md" — do any encode planning internals they shouldn't?

Key question: the refactor preserves an "irreducible CLI/JSON boundary" — but is that boundary
actually well-defined and stable today, or do chain/cloud/bakeoff reach PAST the CLI into internal
state/files/APIs in ways that make "thin front doors" impossible without breaking them? Enumerate
every place a consumer bypasses the public CLI contract and touches internals directly.
