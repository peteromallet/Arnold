create table if not exists public.timeline_events (
  event_id text not null
    constraint timeline_events_event_id_ulid_check
      check (event_id ~ '^[0-9A-HJKMNP-TV-Z]{26}$'),
  timeline_id uuid not null references public.timelines(id) on delete cascade,
  version integer not null
    constraint timeline_events_version_check
      check (version > 0),
  prev_hash text
    constraint timeline_events_prev_hash_format_check
      check (prev_hash is null or prev_hash ~ '^[0-9a-f]{64}$'),
  hash text not null
    constraint timeline_events_hash_format_check
      check (hash ~ '^[0-9a-f]{64}$'),
  kind text not null
    constraint timeline_events_kind_nonempty_check
      check (length(trim(kind)) > 0),
  payload jsonb not null
    constraint timeline_events_payload_object_check
      check (jsonb_typeof(payload) = 'object'),
  schema_version integer not null
    constraint timeline_events_schema_version_check
      check (schema_version > 0),
  idempotency_key text,
  ts timestamptz not null,
  actor jsonb not null default '{}'::jsonb
    constraint timeline_events_actor_object_check
      check (jsonb_typeof(actor) = 'object'),
  expected_version integer
    constraint timeline_events_expected_version_check
      check (expected_version is null or expected_version >= 0),
  txn_id uuid,
  source_backend text,
  source_timeline_id text,
  source_event_id text,
  source_version integer
    constraint timeline_events_source_version_check
      check (source_version is null or source_version > 0),
  source_hash text
    constraint timeline_events_source_hash_format_check
      check (source_hash is null or source_hash ~ '^[0-9a-f]{64}$'),
  primary key (timeline_id, version),
  unique (timeline_id, event_id)
);

create unique index if not exists timeline_events_timeline_id_idempotency_key_idx
  on public.timeline_events (timeline_id, idempotency_key)
  where idempotency_key is not null;

alter table public.timeline_events enable row level security;

drop policy if exists "Users can view own timeline events" on public.timeline_events;
create policy "Users can view own timeline events"
  on public.timeline_events
  for select
  using (
    exists (
      select 1
      from public.timelines
      where timelines.id = timeline_events.timeline_id
        and timelines.user_id = auth.uid()
    )
  );

revoke all on public.timeline_events from public;
revoke all on public.timeline_events from anon;
revoke all on public.timeline_events from authenticated;
grant select on public.timeline_events to authenticated;
grant select, insert, update, delete on public.timeline_events to service_role;

create table if not exists public.timeline_event_contract (
  id integer primary key
    constraint timeline_event_contract_singleton_id_check
      check (id = 1),
  current_schema_version integer not null
    constraint timeline_event_contract_schema_version_check
      check (current_schema_version > 0)
);

insert into public.timeline_event_contract (id, current_schema_version)
values (1, 2)
on conflict (id) do update
set current_schema_version = excluded.current_schema_version;

alter table public.timeline_event_contract enable row level security;

drop policy if exists "Authenticated users can read timeline event contract" on public.timeline_event_contract;
create policy "Authenticated users can read timeline event contract"
  on public.timeline_event_contract
  for select
  using (auth.role() = 'authenticated');

revoke all on public.timeline_event_contract from public;
revoke all on public.timeline_event_contract from anon;
revoke all on public.timeline_event_contract from authenticated;
grant select on public.timeline_event_contract to authenticated;
grant select, insert, update, delete on public.timeline_event_contract to service_role;

comment on table public.timeline_events is
  'Append-only timeline event log. Hashes and projections are computed in Python; SQL stores and validates only the persisted contract.';

comment on column public.timeline_events.version is
  'Per-timeline contiguous event sequence. Separate from timelines.config_version, which remains the optimistic save counter.';

comment on table public.timeline_event_contract is
  'Singleton SQL-side contract row for timeline event schema compatibility. Initialized to match Astrid EVENT_SCHEMA_VERSION for this release.';

comment on column public.timeline_events.idempotency_key is
  'Deterministic key for append retries or seed inserts. Seed rollback removes only rows prefixed with seed:config_replaced:.';

create or replace function public.append_timeline_event(
  p_timeline_id uuid,
  p_events jsonb,
  p_projected_config jsonb,
  p_expected_config_version integer,
  p_projected_asset_registry jsonb default null
)
returns table (config_version integer, inserted_event_ids text[])
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_current_config_version integer;
  v_contract_schema_version integer;
  v_tail_version integer;
  v_previous_hash text;
  v_next_version integer;
  v_event jsonb;
  v_event_ids text[] := array[]::text[];
  v_has_registry_event boolean := false;
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'append_timeline_event requires service_role'
      using errcode = '42501';
  end if;

  if p_expected_config_version is null or p_expected_config_version < 0 then
    raise exception 'p_expected_config_version must be a non-negative integer'
      using errcode = '22023';
  end if;

  if p_events is null
    or jsonb_typeof(p_events) <> 'array'
    or jsonb_array_length(p_events) = 0 then
    raise exception 'p_events must be a non-empty JSON array'
      using errcode = '22023';
  end if;

  if p_projected_config is null then
    raise exception 'p_projected_config is required'
      using errcode = '22004';
  end if;

  if p_projected_asset_registry is not null
    and jsonb_typeof(p_projected_asset_registry) <> 'object' then
    raise exception 'p_projected_asset_registry must be a JSON object when supplied'
      using errcode = '22023';
  end if;

  select c.current_schema_version
    into v_contract_schema_version
    from public.timeline_event_contract c
    where c.id = 1;

  if v_contract_schema_version is null then
    raise exception 'timeline_event_contract singleton row is missing'
      using errcode = '23514';
  end if;

  select t.config_version
    into v_current_config_version
    from public.timelines t
    where t.id = p_timeline_id
    for update;

  if v_current_config_version is null then
    raise exception 'timeline % does not exist', p_timeline_id
      using errcode = 'P0002';
  end if;

  if v_current_config_version <> p_expected_config_version then
    raise exception 'timeline config_version mismatch: expected %, found %',
      p_expected_config_version,
      v_current_config_version
      using errcode = '40001';
  end if;

  select e.version, e.hash
    into v_tail_version, v_previous_hash
    from public.timeline_events e
    where e.timeline_id = p_timeline_id
    order by e.version desc
    limit 1;

  v_next_version := coalesce(v_tail_version, 0) + 1;

  for v_event in
    select value
    from jsonb_array_elements(p_events) with ordinality as incoming(value, ordinal)
    order by ordinal
  loop
    if jsonb_typeof(v_event) <> 'object' then
      raise exception 'timeline event entries must be JSON objects'
        using errcode = '22023';
    end if;

    if nullif(v_event ->> 'timeline_id', '') is null
      or nullif(v_event ->> 'timeline_id', '')::uuid <> p_timeline_id then
      raise exception 'event % timeline_id does not match target timeline',
        coalesce(v_event ->> 'event_id', '<missing>')
        using errcode = '23514';
    end if;

    if (v_event ->> 'version')::integer <> v_next_version then
      raise exception 'event % has version %, expected %',
        coalesce(v_event ->> 'event_id', '<missing>'),
        v_event ->> 'version',
        v_next_version
        using errcode = '23514';
    end if;

    if (v_event ->> 'schema_version')::integer > v_contract_schema_version then
      raise exception 'event % schema_version % exceeds contract %',
        coalesce(v_event ->> 'event_id', '<missing>'),
        v_event ->> 'schema_version',
        v_contract_schema_version
        using errcode = '23514';
    end if;

    if (v_event ->> 'schema_version')::integer <= 0 then
      raise exception 'event % schema_version must be positive',
        coalesce(v_event ->> 'event_id', '<missing>')
        using errcode = '23514';
    end if;

    if v_event ? 'expected_version'
      and v_event ->> 'expected_version' is not null
      and (v_event ->> 'expected_version')::integer <> p_expected_config_version then
      raise exception 'event % expected_version % does not match CAS version %',
        coalesce(v_event ->> 'event_id', '<missing>'),
        v_event ->> 'expected_version',
        p_expected_config_version
        using errcode = '40001';
    end if;

    if coalesce(v_event ->> 'prev_hash', '') <> coalesce(v_previous_hash, '') then
      raise exception 'event % prev_hash does not link to the current tail',
        coalesce(v_event ->> 'event_id', '<missing>')
        using errcode = '23514';
    end if;

    if v_event ->> 'kind' = 'timeline.asset_registry_replaced' then
      v_has_registry_event := true;
    end if;

    insert into public.timeline_events (
      event_id,
      timeline_id,
      version,
      prev_hash,
      hash,
      kind,
      payload,
      schema_version,
      idempotency_key,
      ts,
      actor,
      expected_version,
      txn_id,
      source_backend,
      source_timeline_id,
      source_event_id,
      source_version,
      source_hash
    )
    values (
      v_event ->> 'event_id',
      p_timeline_id,
      (v_event ->> 'version')::integer,
      nullif(v_event ->> 'prev_hash', ''),
      v_event ->> 'hash',
      v_event ->> 'kind',
      v_event -> 'payload',
      (v_event ->> 'schema_version')::integer,
      nullif(v_event ->> 'idempotency_key', ''),
      (v_event ->> 'ts')::timestamptz,
      coalesce(v_event -> 'actor', '{}'::jsonb),
      nullif(v_event ->> 'expected_version', '')::integer,
      nullif(v_event ->> 'txn_id', '')::uuid,
      nullif(v_event ->> 'source_backend', ''),
      nullif(v_event ->> 'source_timeline_id', ''),
      nullif(v_event ->> 'source_event_id', ''),
      nullif(v_event ->> 'source_version', '')::integer,
      nullif(v_event ->> 'source_hash', '')
    );

    v_event_ids := array_append(v_event_ids, v_event ->> 'event_id');
    v_previous_hash := v_event ->> 'hash';
    v_next_version := v_next_version + 1;
  end loop;

  if p_projected_asset_registry is not null and not v_has_registry_event then
    raise exception 'p_projected_asset_registry may only be supplied with timeline.asset_registry_replaced events'
      using errcode = '23514';
  end if;

  update public.timelines t
  set
    config = p_projected_config,
    asset_registry = case
      when v_has_registry_event and p_projected_asset_registry is not null
        then p_projected_asset_registry
      else t.asset_registry
    end,
    config_version = t.config_version + 1,
    updated_at = timezone('utc', now())
  where t.id = p_timeline_id
  returning t.config_version into config_version;

  inserted_event_ids := v_event_ids;
  return next;
end;
$$;

create or replace function public.create_timeline_with_initial_event(
  p_timeline jsonb,
  p_event jsonb,
  p_projected_config jsonb,
  p_projected_asset_registry jsonb default null
)
returns table (timeline_id uuid, config_version integer, inserted_event_ids text[])
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_timeline_id uuid;
  v_contract_schema_version integer;
  v_inserted_config_version integer;
  v_has_registry_event boolean := false;
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'create_timeline_with_initial_event requires service_role'
      using errcode = '42501';
  end if;

  if p_timeline is null or jsonb_typeof(p_timeline) <> 'object' then
    raise exception 'p_timeline must be a JSON object'
      using errcode = '22023';
  end if;

  if p_event is null or jsonb_typeof(p_event) <> 'object' then
    raise exception 'p_event must be a JSON object'
      using errcode = '22023';
  end if;

  if p_projected_config is null then
    raise exception 'p_projected_config is required'
      using errcode = '22004';
  end if;

  if p_projected_asset_registry is not null
    and jsonb_typeof(p_projected_asset_registry) <> 'object' then
    raise exception 'p_projected_asset_registry must be a JSON object when supplied'
      using errcode = '22023';
  end if;

  select c.current_schema_version
    into v_contract_schema_version
    from public.timeline_event_contract c
    where c.id = 1;

  if v_contract_schema_version is null then
    raise exception 'timeline_event_contract singleton row is missing'
      using errcode = '23514';
  end if;

  v_timeline_id := coalesce(
    nullif(p_timeline ->> 'id', '')::uuid,
    nullif(p_event ->> 'timeline_id', '')::uuid,
    gen_random_uuid()
  );

  if nullif(p_event ->> 'timeline_id', '') is null
    or nullif(p_event ->> 'timeline_id', '')::uuid <> v_timeline_id then
    raise exception 'initial event timeline_id does not match new timeline'
      using errcode = '23514';
  end if;

  if (p_event ->> 'version')::integer <> 1 then
    raise exception 'initial event version must be 1'
      using errcode = '23514';
  end if;

  if p_event ->> 'prev_hash' is not null then
    raise exception 'initial event prev_hash must be null'
      using errcode = '23514';
  end if;

  if (p_event ->> 'schema_version')::integer > v_contract_schema_version then
    raise exception 'initial event schema_version % exceeds contract %',
      p_event ->> 'schema_version',
      v_contract_schema_version
      using errcode = '23514';
  end if;

  if (p_event ->> 'schema_version')::integer <= 0 then
    raise exception 'initial event schema_version must be positive'
      using errcode = '23514';
  end if;

  if p_event ? 'expected_version'
    and p_event ->> 'expected_version' is not null
    and (p_event ->> 'expected_version')::integer <> 0 then
    raise exception 'initial event expected_version must be null or 0'
      using errcode = '40001';
  end if;

  if p_event ->> 'kind' = 'timeline.asset_registry_replaced' then
    v_has_registry_event := true;
  end if;

  if p_projected_asset_registry is not null and not v_has_registry_event then
    raise exception 'p_projected_asset_registry may only be supplied with timeline.asset_registry_replaced events'
      using errcode = '23514';
  end if;

  insert into public.timelines (
    id,
    project_id,
    user_id,
    name,
    config,
    asset_registry
  )
  values (
    v_timeline_id,
    (p_timeline ->> 'project_id')::uuid,
    (p_timeline ->> 'user_id')::uuid,
    p_timeline ->> 'name',
    p_projected_config,
    case
      when v_has_registry_event and p_projected_asset_registry is not null
        then p_projected_asset_registry
      else '{"assets": {}}'::jsonb
    end
  )
  returning timelines.config_version into v_inserted_config_version;

  insert into public.timeline_events (
    event_id,
    timeline_id,
    version,
    prev_hash,
    hash,
    kind,
    payload,
    schema_version,
    idempotency_key,
    ts,
    actor,
    expected_version,
    txn_id,
    source_backend,
    source_timeline_id,
    source_event_id,
    source_version,
    source_hash
  )
  values (
    p_event ->> 'event_id',
    v_timeline_id,
    1,
    null,
    p_event ->> 'hash',
    p_event ->> 'kind',
    p_event -> 'payload',
    (p_event ->> 'schema_version')::integer,
    nullif(p_event ->> 'idempotency_key', ''),
    (p_event ->> 'ts')::timestamptz,
    coalesce(p_event -> 'actor', '{}'::jsonb),
    nullif(p_event ->> 'expected_version', '')::integer,
    nullif(p_event ->> 'txn_id', '')::uuid,
    nullif(p_event ->> 'source_backend', ''),
    nullif(p_event ->> 'source_timeline_id', ''),
    nullif(p_event ->> 'source_event_id', ''),
    nullif(p_event ->> 'source_version', '')::integer,
    nullif(p_event ->> 'source_hash', '')
  );

  timeline_id := v_timeline_id;
  config_version := v_inserted_config_version;
  inserted_event_ids := array[p_event ->> 'event_id'];
  return next;
end;
$$;

revoke execute on function public.append_timeline_event(uuid, jsonb, jsonb, integer, jsonb)
  from public, anon, authenticated;
grant execute on function public.append_timeline_event(uuid, jsonb, jsonb, integer, jsonb)
  to service_role;

revoke execute on function public.create_timeline_with_initial_event(jsonb, jsonb, jsonb, jsonb)
  from public, anon, authenticated;
grant execute on function public.create_timeline_with_initial_event(jsonb, jsonb, jsonb, jsonb)
  to service_role;

comment on function public.append_timeline_event(uuid, jsonb, jsonb, integer, jsonb) is
  'Service-role-only append path. SQL validates CAS, schema version, event sequence, and hash-chain links, then stores precomputed events and materialized config atomically.';

comment on function public.create_timeline_with_initial_event(jsonb, jsonb, jsonb, jsonb) is
  'Service-role-only timeline creation path that atomically inserts a timeline row and its version-1 precomputed event.';
