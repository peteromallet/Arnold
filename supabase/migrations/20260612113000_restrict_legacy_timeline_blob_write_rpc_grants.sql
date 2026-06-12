-- Restrict legacy timeline blob-write RPCs after browser, Edge, and Astrid
-- writers have migrated to the Python append-service path.
--
-- Keep service_role access for internal fallback/ops use during rollout, but
-- remove direct authenticated execute access so external callers cannot keep
-- mutating timelines.config without corresponding timeline_events rows.

revoke execute on function public.update_timeline_config_versioned(uuid, integer, jsonb)
  from public, anon, authenticated;
grant execute on function public.update_timeline_config_versioned(uuid, integer, jsonb)
  to service_role;

revoke execute on function public.update_timeline_versioned(uuid, integer, jsonb, jsonb)
  from public, anon, authenticated;
grant execute on function public.update_timeline_versioned(uuid, integer, jsonb, jsonb)
  to service_role;

comment on function public.update_timeline_config_versioned(uuid, integer, jsonb) is
  'Legacy internal-only blob-write fallback. External writes must go through the Python append service so every timelines.config mutation emits timeline_events rows.';

comment on function public.update_timeline_versioned(uuid, integer, jsonb, jsonb) is
  'Legacy internal-only blob-write fallback for config+asset_registry saves. External writes must go through the Python append service so every materialized update is backed by timeline_events rows.';
