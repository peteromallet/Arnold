# User-timezone localization architecture and implementation

Design and, where safely scoped, implement a deep structural time-localization layer for the Arnold Discord resident and its delegated-agent delivery path.

## User intent

The resident currently communicates operational times in UTC (for example, cloud snapshot timestamps). The user wants one durable, easily updateable timezone preference so all user-visible times are rendered in that user's local time without scattered one-off conversions.

## Required investigation and outcome

1. Inspect the resident stores, conversation/user identity model, hot-context builder, prompt construction, cloud/status renderers, terminal delegated-agent delivery, Discord commands/tool surfaces, and tests. Preserve concurrent/uncommitted work and avoid overwriting unrelated edits.
2. Establish a canonical preference model based on an IANA timezone identifier (for example `America/New_York`), not a fixed UTC offset. Decide and document precedence across user, conversation, guild, and system defaults. The durable user-level preference should be easy to update. Default safely to UTC when absent or invalid.
3. Keep authoritative timestamps stored and exchanged in UTC. Localize only at the user-facing presentation boundary. Do not mutate evidence timestamps or structured control-plane records.
4. Create or identify one central timezone resolution and formatting service rather than duplicating conversion logic. Use Python `zoneinfo`, handle DST correctly, and render enough context to avoid ambiguity (local date/time plus timezone abbreviation and/or numeric offset where appropriate).
5. Make the resolved timezone available in resident hot context and prompt instructions so model-authored responses, deterministic status rendering, and delegated terminal replies follow the same rule. Do not rely only on prompt compliance where deterministic formatting is possible.
6. Provide an authorized, durable way to read and update the preference. Reuse existing profile/settings seams where appropriate; avoid inventing a parallel identity store. Updates must survive restart and take effect on subsequent messages.
7. Audit user-visible timestamp surfaces, including cloud snapshot/status messages, scheduled checks, human gates, special-request/todo output, resident-agent lifecycle/delivery summaries, reply-chain context, and error/attention messages. Clearly distinguish absolute localized times from relative durations.
8. Add migration/backward-compatibility behavior and focused tests covering persistence, preference updates, invalid/missing zones, DST transitions, ambiguous/nonexistent local wall times, DM/guild precedence, restart/replay, deterministic status formatting, prompt/hot-context propagation, and terminal Discord delivery.
9. If implementation is unsafe because of overlapping changes, produce a concrete architecture and integration plan with exact seams, dependency ordering, acceptance criteria, and conflict notes; otherwise implement and verify it. Do not restart the Discord resident, deploy, push, or mutate cloud chains.

## Acceptance criteria

- One canonical IANA timezone preference governs all user-facing time rendering for a resident user.
- Stored/control-plane timestamps remain UTC and machine-readable.
- A preference change is durable, authorized, restart-safe, and reflected in the next applicable response.
- Deterministic renderers and model/delegated-agent prompts receive the same resolved timezone.
- DST and fallback behavior are proven by tests.
- Existing UTC-only users remain compatible until they set a preference.
- The final result clearly states what was implemented, verification performed, any remaining gaps, and whether a resident restart/migration is required before it is live.
