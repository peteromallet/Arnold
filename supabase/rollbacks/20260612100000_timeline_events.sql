-- Roll back the timeline event-log contract objects introduced by
-- 20260612100000_create_timeline_events_contract.sql.
--
-- Seed cleanup remains Python-owned. Before dropping the table in an
-- environment that ran the seed tool, delete only rows whose
-- idempotency_key starts with `seed:config_replaced:`.

drop function if exists public.create_timeline_with_initial_event(jsonb, jsonb, jsonb, jsonb);
drop function if exists public.append_timeline_event(uuid, jsonb, jsonb, integer, jsonb);

drop table if exists public.timeline_event_contract;
drop table if exists public.timeline_events;
