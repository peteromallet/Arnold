# Resident user-time localization

Arnold stores, exchanges, compares, and replays authoritative timestamps in UTC.
Localization is a presentation concern only. No scheduler, evidence record,
manifest, cloud snapshot, message `sent_at`, or control-plane timestamp is
rewritten into local wall time.

## Preference and precedence

The canonical durable preference is `resident_user_preferences.timezone_name`,
keyed by `(transport, user_id)`. Values are IANA timezone identifiers resolved
with Python `zoneinfo`; fixed UTC offsets are not accepted as preferences.

Resolution is deterministic:

1. The Discord user's durable profile preference.
2. `resident_conversations.metadata.timezone_name` (or legacy `timezone`) as a
   backward-compatible, operator-managed conversation override.
3. The guild entry in `MEGAPLAN_RESIDENT_GUILD_TIMEZONES`, a JSON object mapping
   Discord guild IDs to IANA names.
4. `MEGAPLAN_RESIDENT_DEFAULT_TIMEZONE`.
5. UTC.

The user preference intentionally wins in both DMs and guild channels. A
missing candidate falls through to the next level. An invalid candidate fails
closed to UTC and is surfaced in hot context with a fallback reason; preference
updates reject invalid zones before persistence.

## Presentation boundaries

`resident.timezone.TimezoneService` is the only resolver. Its formatters add
`*_local` siblings to structured hot context/tool results while preserving the
original UTC values. Final resident prose, scheduled cloud notifications, and
managed terminal delivery pass through the same deterministic ISO-timestamp
localizer. Prompts also receive the resolved IANA zone so model-authored times
and delegated work follow the same rule.

Users can read or set the preference with `/timezone` and
`/timezone America/New_York`. The Megaplan profile also exposes authenticated
`get_timezone_preference` and `set_timezone_preference` tools; they derive the
owner from the runtime authorization subject, so a model cannot select another
user ID.

## DST and local wall times

UTC-to-local rendering is unambiguous and follows the installed IANA database.
The central `localize_wall_time` helper rejects nonexistent spring-forward wall
times and requires an explicit PEP 495 `fold` choice for fall-back ambiguity.
This keeps future schedule-input surfaces from silently guessing.

## Compatibility and activation

Existing users have no profile row and therefore continue to resolve to UTC
unless a conversation/guild/system default is configured. FileStore profiles
need no migration. DB/MultiStore deployments must apply
`202607130002_resident_user_timezones.sql`, then restart the Discord resident to
load this code and command surface. No existing timestamp data is migrated.
