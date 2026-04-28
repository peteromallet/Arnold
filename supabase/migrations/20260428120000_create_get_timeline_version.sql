-- Sprint 6 (Phase 6 / SD-013): expose the current `config_version` of a
-- timeline so the publish CLI (`tools/publish.py`) can fetch
-- expected_version before calling `update_timeline_config_versioned` /
-- `update_timeline_versioned`.
--
-- SECURITY DEFINER + a hand-rolled ownership check rather than RLS-as-invoker
-- because the timelines table doesn't currently expose a row to PostgREST
-- under the calling user JWT for read; the function is the narrow surface.
-- The check uses auth.uid() so PATs and service-role calls are scoped to
-- the JWT subject, not the underlying API key.

create or replace function public.get_timeline_version(
  p_timeline_id uuid
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_caller uuid := auth.uid();
  v_owner uuid;
  v_version integer;
begin
  if v_caller is null then
    raise exception 'auth.uid() is null; user JWT required';
  end if;

  select t.config_version, p.user_id
    into v_version, v_owner
    from public.timelines t
    join public.projects p on p.id = t.project_id
    where t.id = p_timeline_id;

  if v_version is null then
    return null;
  end if;

  if v_owner is distinct from v_caller then
    raise exception 'forbidden: caller does not own this timeline';
  end if;

  return v_version;
end;
$$;

grant execute on function public.get_timeline_version(uuid) to authenticated;
grant execute on function public.get_timeline_version(uuid) to service_role;
