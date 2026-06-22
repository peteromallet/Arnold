-- ============================================================================
-- M2 Provider Persistence Spine: Extension persistence tables
-- ============================================================================
-- Creates the Supabase schema for durable extension state, settings, and
-- proposal storage.  All tables are scoped to (user_id, timeline_id) and
-- enforce cross-tenant isolation via RLS policies aligned with the existing
-- public.timelines ownership model.
--
-- Tables:
--   1. extension_install_state  — enablement, install state, lifecycle flags
--   2. extension_settings       — per-extension settings snapshots with
--                                  schema-version tracking
--   3. extension_proposals      — proposal payload persistence (M2 foundation;
--                                  create/read/status-update/list only)
--
-- RLS design:
--   - Every table has a user_id column aligned with auth.uid().
--   - Policies allow authenticated users to read/insert/update/delete only
--     their own rows (auth.uid() = user_id).
--   - Timeline-scoped queries are additionally constrained by timeline
--     ownership through the public.timelines parent.
--   - Service role bypasses RLS for edge-function / admin operations.
--   - Cleanup / maintenance is service-role-only (no authenticated-user
--     delete grants beyond ownership).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. extension_install_state
-- ----------------------------------------------------------------------------
-- Stores per-extension enablement/install state keyed by (user_id, timeline_id,
-- extension_id).  Preserved on disable; deleted on uninstall.
-- ----------------------------------------------------------------------------

create table if not exists public.extension_install_state (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  timeline_id uuid not null references public.timelines(id) on delete cascade,
  extension_id text not null
    constraint extension_install_state_extension_id_nonempty_check
      check (length(trim(extension_id)) > 0),
  enabled boolean not null default true,
  installed_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  last_toggled_at timestamptz,
  toggle_reason text,
  pack_version text,
  schema_version integer not null default 1
    constraint extension_install_state_schema_version_check
      check (schema_version > 0),
  metadata jsonb not null default '{}'::jsonb
    constraint extension_install_state_metadata_object_check
      check (jsonb_typeof(metadata) = 'object'),

  -- At most one install-state row per (user, timeline, extension)
  constraint extension_install_state_user_timeline_extension_unique
    unique (user_id, timeline_id, extension_id)
);

comment on table public.extension_install_state is
  'Per-extension enablement and install state scoped to a user+timeline pair. Preserved on disable; deleted on uninstall.';

comment on column public.extension_install_state.extension_id is
  'Unique extension identifier (matches ExtensionManifest.id).';

comment on column public.extension_install_state.enabled is
  'Whether the extension is currently enabled in this (user, timeline) scope.';

comment on column public.extension_install_state.last_toggled_at is
  'ISO 8601 timestamp of the most recent enable/disable toggle.';

comment on column public.extension_install_state.toggle_reason is
  'Human-readable reason for the last toggle (e.g. "user disabled via manager").';

comment on column public.extension_install_state.pack_version is
  'Manifest version at install time.';

comment on column public.extension_install_state.schema_version is
  'Schema version of the install-state record shape.';

comment on column public.extension_install_state.metadata is
  'Extensible JSONB payload for provider-specific install metadata (pack record, lifecycle events, lock metadata, etc.).';

-- Indexes
create index if not exists extension_install_state_user_id_idx
  on public.extension_install_state (user_id);

create index if not exists extension_install_state_timeline_id_idx
  on public.extension_install_state (timeline_id);

create index if not exists extension_install_state_timeline_id_extension_id_idx
  on public.extension_install_state (timeline_id, extension_id);

-- RLS
alter table public.extension_install_state enable row level security;

drop policy if exists "Users can view own extension install state" on public.extension_install_state;
create policy "Users can view own extension install state"
  on public.extension_install_state
  for select
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can insert own extension install state" on public.extension_install_state;
create policy "Users can insert own extension install state"
  on public.extension_install_state
  for insert
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can update own extension install state" on public.extension_install_state;
create policy "Users can update own extension install state"
  on public.extension_install_state
  for update
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  )
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can delete own extension install state" on public.extension_install_state;
create policy "Users can delete own extension install state"
  on public.extension_install_state
  for delete
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Service role can manage all extension install state" on public.extension_install_state;
create policy "Service role can manage all extension install state"
  on public.extension_install_state
  for all
  to service_role
  using (true)
  with check (true);

-- Grants
revoke all on public.extension_install_state from public;
revoke all on public.extension_install_state from anon;
revoke all on public.extension_install_state from authenticated;
grant select, insert, update, delete on public.extension_install_state to authenticated;
grant select, insert, update, delete on public.extension_install_state to service_role;

-- ----------------------------------------------------------------------------
-- 2. extension_settings
-- ----------------------------------------------------------------------------
-- Stores per-extension settings snapshots with schema-version tracking.
-- Preserved on disable; deleted on uninstall.
-- ----------------------------------------------------------------------------

create table if not exists public.extension_settings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  timeline_id uuid not null references public.timelines(id) on delete cascade,
  extension_id text not null
    constraint extension_settings_extension_id_nonempty_check
      check (length(trim(extension_id)) > 0),
  schema_version integer not null
    constraint extension_settings_schema_version_check
      check (schema_version > 0),
  values jsonb not null default '{}'::jsonb
    constraint extension_settings_values_object_check
      check (jsonb_typeof(values) = 'object'),
  last_written_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),

  -- At most one settings row per (user, timeline, extension)
  constraint extension_settings_user_timeline_extension_unique
    unique (user_id, timeline_id, extension_id)
);

comment on table public.extension_settings is
  'Per-extension settings snapshots with schema-version tracking, scoped to a user+timeline pair. Preserved on disable; deleted on uninstall.';

comment on column public.extension_settings.schema_version is
  'The settings schema version active when this snapshot was written. Used for migration compatibility checks.';

comment on column public.extension_settings.values is
  'The settings key-value map (JSONB object).';

comment on column public.extension_settings.last_written_at is
  'ISO 8601 timestamp of the most recent settings write.';

-- Indexes
create index if not exists extension_settings_user_id_idx
  on public.extension_settings (user_id);

create index if not exists extension_settings_timeline_id_idx
  on public.extension_settings (timeline_id);

create index if not exists extension_settings_timeline_id_extension_id_idx
  on public.extension_settings (timeline_id, extension_id);

-- RLS
alter table public.extension_settings enable row level security;

drop policy if exists "Users can view own extension settings" on public.extension_settings;
create policy "Users can view own extension settings"
  on public.extension_settings
  for select
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can insert own extension settings" on public.extension_settings;
create policy "Users can insert own extension settings"
  on public.extension_settings
  for insert
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can update own extension settings" on public.extension_settings;
create policy "Users can update own extension settings"
  on public.extension_settings
  for update
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  )
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can delete own extension settings" on public.extension_settings;
create policy "Users can delete own extension settings"
  on public.extension_settings
  for delete
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Service role can manage all extension settings" on public.extension_settings;
create policy "Service role can manage all extension settings"
  on public.extension_settings
  for all
  to service_role
  using (true)
  with check (true);

-- Grants
revoke all on public.extension_settings from public;
revoke all on public.extension_settings from anon;
revoke all on public.extension_settings from authenticated;
grant select, insert, update, delete on public.extension_settings to authenticated;
grant select, insert, update, delete on public.extension_settings to service_role;

-- ----------------------------------------------------------------------------
-- 3. extension_proposals
-- ----------------------------------------------------------------------------
-- Stores extension proposal payloads for M2 foundation (M3 policy execution).
-- Supports create / read / status-update / list operations only.
-- ----------------------------------------------------------------------------

create table if not exists public.extension_proposals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  timeline_id uuid not null references public.timelines(id) on delete cascade,
  extension_id text not null
    constraint extension_proposals_extension_id_nonempty_check
      check (length(trim(extension_id)) > 0),
  status text not null default 'draft'
    constraint extension_proposals_status_check
      check (status in ('draft', 'submitted', 'accepted', 'rejected', 'cancelled', 'expired')),
  payload jsonb not null default '{}'::jsonb
    constraint extension_proposals_payload_object_check
      check (jsonb_typeof(payload) = 'object'),
  label text,
  schema_version integer not null default 1
    constraint extension_proposals_schema_version_check
      check (schema_version > 0),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

comment on table public.extension_proposals is
  'M2 foundation for extension proposal persistence. Stores proposals keyed by (user, timeline, extension) with lifecycle status. M3 owns proposal policy execution.';

comment on column public.extension_proposals.status is
  'Lifecycle status: draft, submitted, accepted, rejected, cancelled, or expired.';

comment on column public.extension_proposals.payload is
  'Arbitrary proposal payload (JSONB object).';

comment on column public.extension_proposals.label is
  'Optional human-readable label for UI display.';

comment on column public.extension_proposals.schema_version is
  'Schema version of the proposal record shape.';

-- Indexes
create index if not exists extension_proposals_user_id_idx
  on public.extension_proposals (user_id);

create index if not exists extension_proposals_timeline_id_idx
  on public.extension_proposals (timeline_id);

create index if not exists extension_proposals_timeline_id_extension_id_idx
  on public.extension_proposals (timeline_id, extension_id);

create index if not exists extension_proposals_status_idx
  on public.extension_proposals (status);

create index if not exists extension_proposals_timeline_id_status_idx
  on public.extension_proposals (timeline_id, status);

-- RLS
alter table public.extension_proposals enable row level security;

drop policy if exists "Users can view own extension proposals" on public.extension_proposals;
create policy "Users can view own extension proposals"
  on public.extension_proposals
  for select
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can insert own extension proposals" on public.extension_proposals;
create policy "Users can insert own extension proposals"
  on public.extension_proposals
  for insert
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can update own extension proposals" on public.extension_proposals;
create policy "Users can update own extension proposals"
  on public.extension_proposals
  for update
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  )
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Users can delete own extension proposals" on public.extension_proposals;
create policy "Users can delete own extension proposals"
  on public.extension_proposals
  for delete
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.timelines
      where id = timeline_id and user_id = auth.uid()
    )
  );

drop policy if exists "Service role can manage all extension proposals" on public.extension_proposals;
create policy "Service role can manage all extension proposals"
  on public.extension_proposals
  for all
  to service_role
  using (true)
  with check (true);

-- Grants
revoke all on public.extension_proposals from public;
revoke all on public.extension_proposals from anon;
revoke all on public.extension_proposals from authenticated;
grant select, insert, update, delete on public.extension_proposals to authenticated;
grant select, insert, update, delete on public.extension_proposals to service_role;

-- ----------------------------------------------------------------------------
-- Verification
-- ----------------------------------------------------------------------------

do $$
declare
  install_state_rls boolean;
  settings_rls boolean;
  proposals_rls boolean;
begin
  select relrowsecurity into install_state_rls
    from pg_class where relname = 'extension_install_state';
  select relrowsecurity into settings_rls
    from pg_class where relname = 'extension_settings';
  select relrowsecurity into proposals_rls
    from pg_class where relname = 'extension_proposals';

  if not install_state_rls then
    raise exception 'CRITICAL: RLS not enabled on extension_install_state table';
  end if;

  if not settings_rls then
    raise exception 'CRITICAL: RLS not enabled on extension_settings table';
  end if;

  if not proposals_rls then
    raise exception 'CRITICAL: RLS not enabled on extension_proposals table';
  end if;

  raise notice 'M2 Extension persistence tables created successfully';
  raise notice '  - extension_install_state: RLS enabled, auth.uid() ownership policies';
  raise notice '  - extension_settings: RLS enabled, auth.uid() ownership policies';
  raise notice '  - extension_proposals: RLS enabled, auth.uid() ownership policies';
  raise notice '  - Service role has full access to all three tables';
end $$;
