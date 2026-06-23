# M4: Discord Thin Path

Overall plan difficulty: 5/5; selected profile: partnered-5; because this milestone makes Arnold operations feel like a human Discord product without creating a parallel resident runtime.

## Outcome

Make v0 genuinely Discord-first: Peter can add a ticket, launch an existing Megaplan chain operation, ask status/blocked/logs, get help, and receive an operation id through Discord.

## Scope

In:

- add an AgentBox Operator profile on the existing resident runtime;
- decide and document which resident runtime pieces are Arnold interfaces, Megaplan implementation details, or AgentBox adapters;
- expose tools for `ticket_new`, `chain_launch`, `status`, `logs`, `help`, and `resolve`;
- route natural-language messages to Arnold operations and Megaplan-specific tools;
- use resident conversation context for pending-question behavior;
- enforce existing single-user allowlist/auth boundaries;
- connect Discord chain launch to `megaplan_chain` operation from M3;
- ensure outbound responses include operation id and concise next state.

Out:

- full natural-language epic authoring;
- Guardian autonomous supervision;
- merge/cleanup approvals;
- daily briefing;
- rich Discord buttons/slash-command completeness.

## Locked Decisions

- Reuse `ResidentDiscordService`, resident runtime, resident auth, outbound sink, and Store-backed confirmations.
- Do not build a fresh Discord bot loop.
- Do not make AgentBox depend on Megaplan-private resident internals without an explicit transitional adapter.
- Discord-first v0 is required; CLI-only is not complete.
- Operator writes Arnold operation records; Guardian later supervises them through scheduled tasks.

## Open Questions

- Exact profile/tool registration point.
- Whether resident runtime interfaces need to move to Arnold or remain Megaplan-owned with AgentBox adapters.
- How much operation/status context to load per Operator turn.
- How resolver ranks operations/repos/tickets when several match a user phrase.

## Constraints

- Single-user allowlist remains simple.
- Ambiguous intent asks one concrete question.
- Ambiguous machine state is inspected before asking Peter.
- No direct process-to-process coupling with Guardian.

## Done Criteria

- From Discord, Peter can create a Megaplan ticket.
- From Discord, Peter can launch an existing chain spec and receive an operation id.
- From Discord, Peter can ask what is running or blocked.
- From Discord, Peter can request recent logs for an operation.
- Tests/fakes cover authorization, message routing, and tool results.
- A package-boundary note records the resident runtime ownership decision before broader AgentBox tooling is built on it.

## Touchpoints

- `arnold_pipelines/megaplan/resident/discord.py`
- `arnold_pipelines/megaplan/resident/runtime.py`
- `arnold_pipelines/megaplan/resident/auth.py`
- `arnold_pipelines/megaplan/resident/profile.py`
- ticket APIs and handlers
- Arnold operation registry and AgentBox host provider

## Anti-Scope

- No new bot service.
- No multi-user role hierarchy.
- No dashboards.
- No destructive actions.
