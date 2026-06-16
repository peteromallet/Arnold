create table if not exists public.sync_bookmarks (
  timeline_id uuid not null references public.timelines(id) on delete cascade,
  spoke text not null
    constraint sync_bookmarks_spoke_check
      check (spoke in ('local', 'app')),
  spoke_version integer not null default 0
    constraint sync_bookmarks_spoke_version_check
      check (spoke_version >= 0),
  spoke_hash text
    constraint sync_bookmarks_spoke_hash_format_check
      check (spoke_hash is null or spoke_hash ~ '^[0-9a-f]{64}$'),
  spoke_event_id text
    constraint sync_bookmarks_spoke_event_id_ulid_check
      check (spoke_event_id is null or spoke_event_id ~ '^[0-9A-HJKMNP-TV-Z]{26}$'),
  hub_version integer not null default 0
    constraint sync_bookmarks_hub_version_check
      check (hub_version >= 0),
  hub_hash text
    constraint sync_bookmarks_hub_hash_format_check
      check (hub_hash is null or hub_hash ~ '^[0-9a-f]{64}$'),
  hub_event_id text
    constraint sync_bookmarks_hub_event_id_ulid_check
      check (hub_event_id is null or hub_event_id ~ '^[0-9A-HJKMNP-TV-Z]{26}$'),
  synced_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint sync_bookmarks_spoke_head_consistency_check
    check (
      (spoke_version = 0 and spoke_hash is null and spoke_event_id is null)
      or (spoke_version > 0 and spoke_hash is not null and spoke_event_id is not null)
    ),
  constraint sync_bookmarks_hub_head_consistency_check
    check (
      (hub_version = 0 and hub_hash is null and hub_event_id is null)
      or (hub_version > 0 and hub_hash is not null and hub_event_id is not null)
    ),
  primary key (timeline_id, spoke)
);

create index if not exists sync_bookmarks_timeline_id_synced_at_idx
  on public.sync_bookmarks (timeline_id, synced_at desc);

alter table public.sync_bookmarks enable row level security;

drop policy if exists "Users can view own sync bookmarks" on public.sync_bookmarks;
create policy "Users can view own sync bookmarks"
  on public.sync_bookmarks
  for select
  using (
    exists (
      select 1
      from public.timelines
      where timelines.id = sync_bookmarks.timeline_id
        and timelines.user_id = auth.uid()
    )
  );

revoke all on public.sync_bookmarks from public;
revoke all on public.sync_bookmarks from anon;
revoke all on public.sync_bookmarks from authenticated;
grant select on public.sync_bookmarks to authenticated;
grant select, insert, update, delete on public.sync_bookmarks to service_role;

create table if not exists public.divergence_log (
  id uuid primary key default gen_random_uuid(),
  timeline_id uuid not null references public.timelines(id) on delete cascade,
  spoke text not null
    constraint divergence_log_spoke_check
      check (spoke in ('local', 'app')),
  spoke_version integer not null default 0
    constraint divergence_log_spoke_version_check
      check (spoke_version >= 0),
  spoke_hash text
    constraint divergence_log_spoke_hash_format_check
      check (spoke_hash is null or spoke_hash ~ '^[0-9a-f]{64}$'),
  spoke_event_id text
    constraint divergence_log_spoke_event_id_ulid_check
      check (spoke_event_id is null or spoke_event_id ~ '^[0-9A-HJKMNP-TV-Z]{26}$'),
  hub_version integer not null default 0
    constraint divergence_log_hub_version_check
      check (hub_version >= 0),
  hub_hash text
    constraint divergence_log_hub_hash_format_check
      check (hub_hash is null or hub_hash ~ '^[0-9a-f]{64}$'),
  hub_event_id text
    constraint divergence_log_hub_event_id_ulid_check
      check (hub_event_id is null or hub_event_id ~ '^[0-9A-HJKMNP-TV-Z]{26}$'),
  spoke_suffix jsonb not null
    constraint divergence_log_spoke_suffix_array_check
      check (jsonb_typeof(spoke_suffix) = 'array'),
  hub_suffix jsonb not null
    constraint divergence_log_hub_suffix_array_check
      check (jsonb_typeof(hub_suffix) = 'array'),
  chosen_side text not null default 'undecided'
    constraint divergence_log_chosen_side_check
      check (chosen_side in ('spoke', 'hub', 'undecided')),
  artifact_pointer jsonb
    constraint divergence_log_artifact_pointer_object_check
      check (artifact_pointer is null or jsonb_typeof(artifact_pointer) = 'object'),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  resolved_at timestamptz,
  constraint divergence_log_spoke_head_consistency_check
    check (
      (spoke_version = 0 and spoke_hash is null and spoke_event_id is null)
      or (spoke_version > 0 and spoke_hash is not null and spoke_event_id is not null)
    ),
  constraint divergence_log_hub_head_consistency_check
    check (
      (hub_version = 0 and hub_hash is null and hub_event_id is null)
      or (hub_version > 0 and hub_hash is not null and hub_event_id is not null)
    ),
  constraint divergence_log_resolution_consistency_check
    check (
      (chosen_side = 'undecided' and resolved_at is null)
      or (chosen_side in ('spoke', 'hub') and resolved_at is not null)
    )
);

create index if not exists divergence_log_timeline_id_created_at_idx
  on public.divergence_log (timeline_id, created_at desc);

create index if not exists divergence_log_timeline_id_spoke_created_at_idx
  on public.divergence_log (timeline_id, spoke, created_at desc);

alter table public.divergence_log enable row level security;

drop policy if exists "Users can view own divergence log" on public.divergence_log;
create policy "Users can view own divergence log"
  on public.divergence_log
  for select
  using (
    exists (
      select 1
      from public.timelines
      where timelines.id = divergence_log.timeline_id
        and timelines.user_id = auth.uid()
    )
  );

revoke all on public.divergence_log from public;
revoke all on public.divergence_log from anon;
revoke all on public.divergence_log from authenticated;
grant select on public.divergence_log to authenticated;
grant select, insert, update, delete on public.divergence_log to service_role;

comment on table public.sync_bookmarks is
  'Authoritative per-link sync bookmark keyed by timeline and spoke. Stores exact spoke and hub heads, including mandatory hashes, for divergence detection.';

comment on table public.divergence_log is
  'Durable keep-both records for sync divergence. Stores spoke/hub heads, suffix event copies, the chosen winning side when known, and optional artifact metadata.';

comment on column public.sync_bookmarks.spoke is
  'Hub link endpoint represented by this bookmark. S5 currently supports only local<->DB and app<->DB links.';

comment on column public.sync_bookmarks.spoke_hash is
  'Mandatory whenever spoke_version is non-zero so same-version forks remain distinguishable.';

comment on column public.sync_bookmarks.hub_hash is
  'Mandatory whenever hub_version is non-zero; version-only hub comparison is prohibited by the S5 sync contract.';

comment on column public.divergence_log.spoke_suffix is
  'JSON array copy of the losing-or-pending spoke-side suffix preserved before any LWW replay.';

comment on column public.divergence_log.hub_suffix is
  'JSON array copy of the losing-or-pending hub-side suffix preserved before any LWW replay.';

comment on column public.divergence_log.chosen_side is
  'Resolution choice once a human or higher-level sync flow picks which side wins the visible head.';

comment on column public.divergence_log.artifact_pointer is
  'Typed reference to the persisted keep-both artifact returned by sync flows; JSON object keeps the pointer shape transport-agnostic.';

comment on column public.divergence_log.resolved_at is
  'Resolution timestamp. Must be null while chosen_side is undecided and non-null once a winning side is recorded.';
