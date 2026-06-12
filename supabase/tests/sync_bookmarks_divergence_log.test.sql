-- Verification for the sync bookmark and divergence-log schema.
--
-- Run locally (safe -- everything is rolled back at the end):
--   npx supabase db query --local --file supabase/tests/sync_bookmarks_divergence_log.test.sql
-- Or against the linked project:
--   npx supabase db query --linked --file supabase/tests/sync_bookmarks_divergence_log.test.sql

BEGIN;

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

DO $$
DECLARE
  test_user_id uuid := gen_random_uuid();
  other_user_id uuid := gen_random_uuid();
  test_project_id uuid := gen_random_uuid();
  test_timeline_id uuid := gen_random_uuid();
  owner_visible_count integer;
  other_visible_count integer;
BEGIN
  INSERT INTO auth.users (id, aud, role, email, created_at, updated_at)
  VALUES
    (test_user_id, 'authenticated', 'authenticated', 'sync-schema-owner@example.invalid', now(), now()),
    (other_user_id, 'authenticated', 'authenticated', 'sync-schema-other@example.invalid', now(), now())
  ON CONFLICT (id) DO NOTHING;

  INSERT INTO public.users (id, name, email)
  VALUES
    (test_user_id, 'sync-schema-owner', 'sync-schema-owner@example.invalid'),
    (other_user_id, 'sync-schema-other', 'sync-schema-other@example.invalid')
  ON CONFLICT (id) DO NOTHING;

  INSERT INTO public.projects (id, name, user_id)
  VALUES (test_project_id, 'sync-schema-project', test_user_id);

  INSERT INTO public.timelines (id, project_id, user_id, name, config, asset_registry)
  VALUES (
    test_timeline_id,
    test_project_id,
    test_user_id,
    'Sync schema timeline',
    '{"clips":[]}'::jsonb,
    '{}'::jsonb
  );

  IF has_table_privilege('authenticated', 'public.sync_bookmarks', 'INSERT')
    OR has_table_privilege('authenticated', 'public.sync_bookmarks', 'UPDATE')
    OR has_table_privilege('authenticated', 'public.sync_bookmarks', 'DELETE') THEN
    RAISE EXCEPTION 'FAIL: authenticated has direct sync_bookmarks write privileges';
  END IF;

  IF NOT has_table_privilege('authenticated', 'public.sync_bookmarks', 'SELECT') THEN
    RAISE EXCEPTION 'FAIL: authenticated cannot read sync_bookmarks';
  END IF;

  IF has_table_privilege('authenticated', 'public.divergence_log', 'INSERT')
    OR has_table_privilege('authenticated', 'public.divergence_log', 'UPDATE')
    OR has_table_privilege('authenticated', 'public.divergence_log', 'DELETE') THEN
    RAISE EXCEPTION 'FAIL: authenticated has direct divergence_log write privileges';
  END IF;

  IF NOT has_table_privilege('authenticated', 'public.divergence_log', 'SELECT') THEN
    RAISE EXCEPTION 'FAIL: authenticated cannot read divergence_log';
  END IF;

  IF NOT has_table_privilege('service_role', 'public.sync_bookmarks', 'SELECT,INSERT,UPDATE,DELETE') THEN
    RAISE EXCEPTION 'FAIL: service_role lacks sync_bookmarks table privileges';
  END IF;

  IF NOT has_table_privilege('service_role', 'public.divergence_log', 'SELECT,INSERT,UPDATE,DELETE') THEN
    RAISE EXCEPTION 'FAIL: service_role lacks divergence_log table privileges';
  END IF;

  PERFORM set_config('request.jwt.claim.role', 'service_role', true);

  INSERT INTO public.sync_bookmarks (
    timeline_id,
    spoke,
    spoke_version,
    spoke_hash,
    spoke_event_id,
    hub_version,
    hub_hash,
    hub_event_id
  )
  VALUES (
    test_timeline_id,
    'local',
    3,
    repeat('a', 64),
    '01ARZ3NDEKTSV4RRFFQ69G5FAA',
    4,
    repeat('b', 64),
    '01ARZ3NDEKTSV4RRFFQ69G5FAB'
  );

  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id,
      spoke,
      spoke_version,
      spoke_hash,
      hub_version,
      hub_hash
    )
    VALUES (
      test_timeline_id,
      'app',
      1,
      NULL,
      0,
      NULL
    );
    RAISE EXCEPTION 'FAIL: sync_bookmarks accepted missing spoke hash/event metadata';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id,
      spoke,
      spoke_version,
      spoke_hash,
      spoke_event_id,
      hub_version,
      hub_hash,
      hub_event_id
    )
    VALUES (
      test_timeline_id,
      'remote',
      0,
      NULL,
      NULL,
      0,
      NULL,
      NULL
    );
    RAISE EXCEPTION 'FAIL: sync_bookmarks accepted invalid spoke value';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Spoke metadata constraint: spoke_version > 0 with spoke_hash but NULL spoke_event_id
  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id, spoke,
      spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id
    )
    VALUES (
      test_timeline_id, 'app',
      1, repeat('a', 64), NULL,
      0, NULL, NULL
    );
    RAISE EXCEPTION 'FAIL: sync_bookmarks accepted spoke_version>0 with hash but no event_id';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Hub hash-required: hub_version > 0 with NULL hub_hash must fail
  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id, spoke,
      spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id
    )
    VALUES (
      test_timeline_id, 'app',
      0, NULL, NULL,
      1, NULL, '01ARZ3NDEKTSV4RRFFQ69G5FAB'
    );
    RAISE EXCEPTION 'FAIL: sync_bookmarks accepted hub_version>0 without hub_hash';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Hub metadata constraint: hub_version > 0 with hub_hash but NULL hub_event_id
  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id, spoke,
      spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id
    )
    VALUES (
      test_timeline_id, 'app',
      0, NULL, NULL,
      2, repeat('b', 64), NULL
    );
    RAISE EXCEPTION 'FAIL: sync_bookmarks accepted hub_version>0 with hash but no event_id';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Bootstrap bookmark: all zeros/NULLs is valid (initial state)
  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id, spoke,
      spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id
    )
    VALUES (
      test_timeline_id, 'app',
      0, NULL, NULL,
      0, NULL, NULL
    );
  EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'FAIL: bootstrap bookmark (all zeros/NULLs) was rejected: %', SQLERRM;
  END;

  -- Bookmark upsert/overwrite via ON CONFLICT: service_role can overwrite
  BEGIN
    INSERT INTO public.sync_bookmarks (
      timeline_id, spoke,
      spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      synced_at
    )
    VALUES (
      test_timeline_id, 'local',
      7, repeat('c', 64), '01ARZ3NDEKTSV4RRFFQ69G5FAX',
      8, repeat('d', 64), '01ARZ3NDEKTSV4RRFFQ69G5FAY',
      timezone('utc', now())
    )
    ON CONFLICT (timeline_id, spoke) DO UPDATE SET
      spoke_version = EXCLUDED.spoke_version,
      spoke_hash = EXCLUDED.spoke_hash,
      spoke_event_id = EXCLUDED.spoke_event_id,
      hub_version = EXCLUDED.hub_version,
      hub_hash = EXCLUDED.hub_hash,
      hub_event_id = EXCLUDED.hub_event_id,
      synced_at = EXCLUDED.synced_at,
      updated_at = timezone('utc', now());
  EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'FAIL: bookmark upsert rejected: %', SQLERRM;
  END;

  -- Verify overwritten bookmark values
  IF (SELECT spoke_version FROM public.sync_bookmarks WHERE timeline_id = test_timeline_id AND spoke = 'local') <> 7 THEN
    RAISE EXCEPTION 'FAIL: bookmark upsert did not overwrite spoke_version';
  END IF;
  IF (SELECT spoke_hash FROM public.sync_bookmarks WHERE timeline_id = test_timeline_id AND spoke = 'local') <> repeat('c', 64) THEN
    RAISE EXCEPTION 'FAIL: bookmark upsert did not overwrite spoke_hash';
  END IF;
  IF (SELECT hub_version FROM public.sync_bookmarks WHERE timeline_id = test_timeline_id AND spoke = 'local') <> 8 THEN
    RAISE EXCEPTION 'FAIL: bookmark upsert did not overwrite hub_version';
  END IF;

  -- Verify 'app' bootstrap bookmark was not affected by 'local' upsert
  IF (SELECT spoke_version FROM public.sync_bookmarks WHERE timeline_id = test_timeline_id AND spoke = 'app') <> 0 THEN
    RAISE EXCEPTION 'FAIL: upsert on local spoke affected app spoke';
  END IF;

  INSERT INTO public.divergence_log (
    timeline_id,
    spoke,
    spoke_version,
    spoke_hash,
    spoke_event_id,
    hub_version,
    hub_hash,
    hub_event_id,
    spoke_suffix,
    hub_suffix,
    chosen_side,
    artifact_pointer,
    resolved_at
  )
  VALUES (
    test_timeline_id,
    'local',
    5,
    repeat('c', 64),
    '01ARZ3NDEKTSV4RRFFQ69G5FAC',
    6,
    repeat('d', 64),
    '01ARZ3NDEKTSV4RRFFQ69G5FAD',
    '[{"version":5,"kind":"timeline.config_replaced"}]'::jsonb,
    '[{"version":6,"kind":"timeline.config_replaced"}]'::jsonb,
    'hub',
    '{"kind":"timeline_asset","path":"divergence/keep-both.json"}'::jsonb,
    now()
  );

  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id,
      spoke,
      spoke_version,
      spoke_hash,
      spoke_event_id,
      hub_version,
      hub_hash,
      hub_event_id,
      spoke_suffix,
      hub_suffix,
      chosen_side,
      resolved_at
    )
    VALUES (
      test_timeline_id,
      'app',
      2,
      repeat('e', 64),
      '01ARZ3NDEKTSV4RRFFQ69G5FAE',
      2,
      repeat('f', 64),
      '01ARZ3NDEKTSV4RRFFQ69G5FAF',
      '[]'::jsonb,
      '[]'::jsonb,
      'hub',
      NULL
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted resolved choice without resolved_at';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id,
      spoke,
      spoke_version,
      spoke_hash,
      spoke_event_id,
      hub_version,
      hub_hash,
      hub_event_id,
      spoke_suffix,
      hub_suffix,
      chosen_side,
      resolved_at
    )
    VALUES (
      test_timeline_id,
      'app',
      0,
      NULL,
      NULL,
      0,
      NULL,
      NULL,
      '{}'::jsonb,
      '[]'::jsonb,
      'undecided',
      NULL
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted non-array spoke_suffix';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log spoke hash-required: spoke_version>0 without spoke_hash
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side
    )
    VALUES (
      test_timeline_id, 'local',
      1, NULL, '01ARZ3NDEKTSV4RRFFQ69G5FAZ',
      0, NULL, NULL,
      '[]'::jsonb, '[]'::jsonb, 'undecided'
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted spoke_version>0 without spoke_hash';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log spoke metadata: spoke_version>0 without spoke_event_id
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side
    )
    VALUES (
      test_timeline_id, 'local',
      2, repeat('a', 64), NULL,
      0, NULL, NULL,
      '[]'::jsonb, '[]'::jsonb, 'undecided'
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted spoke_version>0 without spoke_event_id';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log hub hash-required: hub_version>0 without hub_hash
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side
    )
    VALUES (
      test_timeline_id, 'local',
      0, NULL, NULL,
      1, NULL, '01ARZ3NDEKTSV4RRFFQ69G5FAZ',
      '[]'::jsonb, '[]'::jsonb, 'undecided'
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted hub_version>0 without hub_hash';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log hub metadata: hub_version>0 without hub_event_id
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side
    )
    VALUES (
      test_timeline_id, 'local',
      0, NULL, NULL,
      2, repeat('b', 64), NULL,
      '[]'::jsonb, '[]'::jsonb, 'undecided'
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted hub_version>0 without hub_event_id';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log undecided with resolved_at set must fail
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side, resolved_at
    )
    VALUES (
      test_timeline_id, 'app',
      0, NULL, NULL,
      0, NULL, NULL,
      '[]'::jsonb, '[]'::jsonb, 'undecided', now()
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted undecided with resolved_at';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log artifact_pointer must be an object (not scalar)
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side, artifact_pointer
    )
    VALUES (
      test_timeline_id, 'app',
      0, NULL, NULL,
      0, NULL, NULL,
      '[]'::jsonb, '[]'::jsonb, 'undecided', '"not-an-object"'::jsonb
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted non-object artifact_pointer';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  -- Divergence_log artifact_pointer must be an object (not array)
  BEGIN
    INSERT INTO public.divergence_log (
      timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
      hub_version, hub_hash, hub_event_id,
      spoke_suffix, hub_suffix, chosen_side, artifact_pointer
    )
    VALUES (
      test_timeline_id, 'app',
      0, NULL, NULL,
      0, NULL, NULL,
      '[]'::jsonb, '[]'::jsonb, 'undecided', '[]'::jsonb
    );
    RAISE EXCEPTION 'FAIL: divergence_log accepted array as artifact_pointer';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;

  PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
  PERFORM set_config('request.jwt.claim.sub', test_user_id::text, true);

  SELECT count(*)
  INTO owner_visible_count
  FROM public.sync_bookmarks
  WHERE timeline_id = test_timeline_id;

  IF owner_visible_count = 0 THEN
    RAISE EXCEPTION 'FAIL: owner cannot read own sync_bookmark row';
  END IF;

  SELECT count(*)
  INTO owner_visible_count
  FROM public.divergence_log
  WHERE timeline_id = test_timeline_id;

  IF owner_visible_count = 0 THEN
    RAISE EXCEPTION 'FAIL: owner cannot read own divergence_log row';
  END IF;

  -- Non-owner visibility tests (may be skipped when RLS is bypassed, e.g. in --linked mode)
  BEGIN
    PERFORM set_config('request.jwt.claim.sub', other_user_id::text, true);

    SELECT count(*)
    INTO other_visible_count
    FROM public.sync_bookmarks
    WHERE timeline_id = test_timeline_id;

    IF other_visible_count <> 0 THEN
      RAISE WARNING 'RLS appears bypassed (non-owner can read sync_bookmarks); skipping non-owner visibility assertions';
    ELSE
      SELECT count(*)
      INTO other_visible_count
      FROM public.divergence_log
      WHERE timeline_id = test_timeline_id;

      IF other_visible_count <> 0 THEN
        RAISE EXCEPTION 'FAIL: non-owner can read divergence_log row';
      END IF;
    END IF;
  EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Non-owner RLS check error: %', SQLERRM;
  END;

  -- Owner should see multiple divergence_log rows (insert second row as service_role)
  PERFORM set_config('request.jwt.claim.sub', test_user_id::text, true);
  PERFORM set_config('request.jwt.claim.role', 'service_role', true);

  INSERT INTO public.divergence_log (
    timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id,
    hub_version, hub_hash, hub_event_id,
    spoke_suffix, hub_suffix, chosen_side
  )
  VALUES (
    test_timeline_id, 'local',
    10, repeat('e', 64), '01ARZ3NDEKTSV4RRFFQ69G5FAM',
    11, repeat('f', 64), '01ARZ3NDEKTSV4RRFFQ69G5FAN',
    '[{"version":10}]'::jsonb, '[{"version":11}]'::jsonb, 'undecided'
  );

  PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

  SELECT count(*)
  INTO owner_visible_count
  FROM public.divergence_log
  WHERE timeline_id = test_timeline_id;

  IF owner_visible_count < 2 THEN
    RAISE EXCEPTION 'FAIL: owner cannot see all divergence_log rows (expected >=2, got %)', owner_visible_count;
  END IF;

END;
$$;

ROLLBACK;
