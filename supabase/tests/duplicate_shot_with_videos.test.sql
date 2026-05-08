-- Verification for duplicate_shot_with_videos graph cloning.
--
-- Invariant under test:
--   Duplicate-with-videos creates a new shot, shares positioned image generation
--   rows through new shot_generation slots, clones parent/final video and child
--   segment generation rows into independent IDs, remaps typed and JSON
--   relationships into the cloned graph, preserves shared image arrays, leaves
--   the source graph untouched, and exposes the cloned final video.
--
-- Run locally (safe -- everything is rolled back at the end):
--   psql "$SUPABASE_DB_URL" -f supabase/tests/duplicate_shot_with_videos.test.sql
-- or against a linked project:
--   npx supabase db execute --linked --file supabase/tests/duplicate_shot_with_videos.test.sql

BEGIN;

DO $$
DECLARE
  test_user_id uuid := gen_random_uuid();
  test_project_id uuid := gen_random_uuid();
  source_shot_id uuid := gen_random_uuid();
  image_generation_a_id uuid := gen_random_uuid();
  image_generation_b_id uuid := gen_random_uuid();
  source_image_slot_a_id uuid := gen_random_uuid();
  source_image_slot_b_id uuid := gen_random_uuid();
  source_parent_id uuid;
  source_child_a_id uuid := gen_random_uuid();
  source_child_b_id uuid := gen_random_uuid();
  source_parent_variant_id uuid := gen_random_uuid();
  source_child_a_variant_id uuid := gen_random_uuid();
  source_child_b_variant_id uuid := gen_random_uuid();
  result jsonb;
  cloned_shot_id uuid;
  cloned_image_slot_a_id uuid;
  cloned_image_slot_b_id uuid;
  cloned_parent_id uuid;
  cloned_child_a_id uuid;
  cloned_child_b_id uuid;
  cloned_parent_params jsonb;
  cloned_child_a_params jsonb;
  cloned_parent_variant_params jsonb;
  cloned_child_a_variant_params jsonb;
  source_parent_params_before jsonb;
  source_parent_variant_params_before jsonb;
  source_video_ids text[];
  source_slot_ids text[];
  leaked_refs text;
  row_count integer;
BEGIN
  INSERT INTO public.users (id, name, email)
  VALUES (test_user_id, 'duplicate-video-test', 'duplicate-video-test@example.invalid');

  INSERT INTO public.projects (id, name, user_id)
  VALUES (test_project_id, 'duplicate-video-test-project', test_user_id);

  INSERT INTO public.shots (id, name, project_id, position, aspect_ratio, settings)
  VALUES (
    source_shot_id,
    'Source shot',
    test_project_id,
    7,
    '16:9',
    '{"camera":"wide"}'::jsonb
  );

  SELECT g.id
  INTO source_parent_id
  FROM public.shot_generations sg
  JOIN public.generations g ON g.id = sg.generation_id
  WHERE sg.shot_id = source_shot_id
    AND g.type = 'video'
    AND g.parent_generation_id IS NULL
  ORDER BY g.created_at ASC
  LIMIT 1;

  IF source_parent_id IS NULL THEN
    RAISE EXCEPTION 'FAIL: shot creation did not create a parent video generation';
  END IF;

  INSERT INTO public.generations (
    id,
    project_id,
    type,
    location,
    thumbnail_url,
    params,
    name
  )
  VALUES
    (
      image_generation_a_id,
      test_project_id,
      'image',
      'https://example.invalid/source-a.png',
      'https://example.invalid/source-a-thumb.jpg',
      '{"role":"start"}'::jsonb,
      'Source image A'
    ),
    (
      image_generation_b_id,
      test_project_id,
      'image',
      'https://example.invalid/source-b.png',
      'https://example.invalid/source-b-thumb.jpg',
      '{"role":"end"}'::jsonb,
      'Source image B'
    );

  INSERT INTO public.shot_generations (
    id,
    shot_id,
    generation_id,
    timeline_frame,
    metadata
  )
  VALUES
    (
      source_image_slot_a_id,
      source_shot_id,
      image_generation_a_id,
      0,
      '{"slot":"start"}'::jsonb
    ),
    (
      source_image_slot_b_id,
      source_shot_id,
      image_generation_b_id,
      81,
      '{"slot":"end"}'::jsonb
    );

  INSERT INTO public.generations (
    id,
    tasks,
    params,
    location,
    thumbnail_url,
    type,
    project_id,
    name,
    parent_generation_id,
    is_child,
    child_order,
    children,
    starred,
    pair_shot_generation_id
  )
  VALUES
    (
      source_child_a_id,
      '["segment-task-a"]'::jsonb,
      jsonb_build_object(
        'originalParams', jsonb_build_object(
          'orchestrator_details', jsonb_build_object(
            'shot_id', source_shot_id::text,
            'parent_generation_id', source_parent_id::text,
            'child_generation_id', source_child_a_id::text,
            'pair_shot_generation_id', source_image_slot_a_id::text,
            'pair_shot_generation_ids', jsonb_build_array(source_image_slot_a_id::text, source_image_slot_b_id::text)
          )
        ),
        'parent_generation_id', source_parent_id::text,
        'child_generation_id', source_child_a_id::text,
        'pair_shot_generation_id', source_image_slot_a_id::text,
        'input_image_generation_ids', jsonb_build_array(image_generation_a_id::text, image_generation_b_id::text)
      ),
      NULL,
      NULL,
      'video',
      test_project_id,
      'Source child A',
      source_parent_id,
      true,
      0,
      NULL,
      true,
      source_image_slot_a_id
    ),
    (
      source_child_b_id,
      '["segment-task-b"]'::jsonb,
      jsonb_build_object(
        'originalParams', jsonb_build_object(
          'orchestrator_details', jsonb_build_object(
            'shot_id', source_shot_id::text,
            'parent_generation_id', source_parent_id::text,
            'child_generation_id', source_child_b_id::text,
            'pair_shot_generation_id', source_image_slot_b_id::text,
            'pair_shot_generation_ids', jsonb_build_array(source_image_slot_a_id::text, source_image_slot_b_id::text)
          )
        ),
        'parent_generation_id', source_parent_id::text,
        'child_generation_id', source_child_b_id::text,
        'pair_shot_generation_id', source_image_slot_b_id::text,
        'input_image_generation_ids', jsonb_build_array(image_generation_a_id::text, image_generation_b_id::text)
      ),
      NULL,
      NULL,
      'video',
      test_project_id,
      'Source child B',
      source_parent_id,
      true,
      1,
      NULL,
      false,
      source_image_slot_b_id
    );

  UPDATE public.generations
  SET
    tasks = '["parent-task"]'::jsonb,
    params = jsonb_build_object(
      'originalParams', jsonb_build_object(
        'orchestrator_details', jsonb_build_object(
          'shot_id', source_shot_id::text,
          'parent_generation_id', source_parent_id::text,
          'child_generation_id', source_child_a_id::text,
          'pair_shot_generation_id', source_image_slot_a_id::text,
          'pair_shot_generation_ids', jsonb_build_array(source_image_slot_a_id::text, source_image_slot_b_id::text)
        )
      ),
      'metadata', jsonb_build_object(
        'shot_id', source_shot_id::text,
        'parent_generation_id', source_parent_id::text,
        'child_generation_id', source_child_b_id::text
      ),
      'input_image_generation_ids', jsonb_build_array(
        image_generation_a_id::text,
        image_generation_b_id::text,
        source_child_a_id::text
      )
    ),
    children = jsonb_build_array(source_child_a_id::text, source_child_b_id::text),
    name = 'Source final video',
    starred = true,
    child_order = 12
  WHERE id = source_parent_id;

  INSERT INTO public.generation_variants (
    id,
    generation_id,
    location,
    thumbnail_url,
    params,
    is_primary,
    variant_type,
    name,
    project_id,
    starred
  )
  VALUES
    (
      source_parent_variant_id,
      source_parent_id,
      'https://example.invalid/source-final.mp4',
      'https://example.invalid/source-final-thumb.jpg',
      jsonb_build_object(
        'originalParams', jsonb_build_object(
          'orchestrator_details', jsonb_build_object(
            'shot_id', source_shot_id::text,
            'parent_generation_id', source_parent_id::text,
            'child_generation_id', source_child_a_id::text,
            'pair_shot_generation_id', source_image_slot_a_id::text,
            'pair_shot_generation_ids', jsonb_build_array(source_image_slot_a_id::text, source_image_slot_b_id::text)
          )
        ),
        'input_image_generation_ids', jsonb_build_array(image_generation_a_id::text, image_generation_b_id::text, source_child_a_id::text)
      ),
      true,
      'original',
      'Source parent primary',
      test_project_id,
      true
    ),
    (
      source_child_a_variant_id,
      source_child_a_id,
      'https://example.invalid/source-segment-a.mp4',
      'https://example.invalid/source-segment-a-thumb.jpg',
      jsonb_build_object(
        'originalParams', jsonb_build_object(
          'orchestrator_details', jsonb_build_object(
            'shot_id', source_shot_id::text,
            'parent_generation_id', source_parent_id::text,
            'child_generation_id', source_child_a_id::text,
            'pair_shot_generation_id', source_image_slot_a_id::text,
            'pair_shot_generation_ids', jsonb_build_array(source_image_slot_a_id::text, source_image_slot_b_id::text)
          )
        ),
        'parent_generation_id', source_parent_id::text,
        'child_generation_id', source_child_a_id::text,
        'pair_shot_generation_id', source_image_slot_a_id::text
      ),
      true,
      'segment',
      'Source child A primary',
      test_project_id,
      false
    ),
    (
      source_child_b_variant_id,
      source_child_b_id,
      'https://example.invalid/source-segment-b.mp4',
      'https://example.invalid/source-segment-b-thumb.jpg',
      jsonb_build_object(
        'originalParams', jsonb_build_object(
          'orchestrator_details', jsonb_build_object(
            'shot_id', source_shot_id::text,
            'parent_generation_id', source_parent_id::text,
            'child_generation_id', source_child_b_id::text,
            'pair_shot_generation_id', source_image_slot_b_id::text,
            'pair_shot_generation_ids', jsonb_build_array(source_image_slot_a_id::text, source_image_slot_b_id::text)
          )
        ),
        'parent_generation_id', source_parent_id::text,
        'child_generation_id', source_child_b_id::text,
        'pair_shot_generation_id', source_image_slot_b_id::text
      ),
      true,
      'segment',
      'Source child B primary',
      test_project_id,
      false
    );

  SELECT params INTO source_parent_params_before
  FROM public.generations
  WHERE id = source_parent_id;

  SELECT params INTO source_parent_variant_params_before
  FROM public.generation_variants
  WHERE id = source_parent_variant_id;

  result := public.duplicate_shot_with_videos(source_shot_id, test_project_id);
  cloned_shot_id := (result->>'shot_id')::uuid;
  cloned_image_slot_a_id := (result->'shot_generation_id_map'->>source_image_slot_a_id::text)::uuid;
  cloned_image_slot_b_id := (result->'shot_generation_id_map'->>source_image_slot_b_id::text)::uuid;
  cloned_parent_id := (result->'generation_id_map'->>source_parent_id::text)::uuid;
  cloned_child_a_id := (result->'generation_id_map'->>source_child_a_id::text)::uuid;
  cloned_child_b_id := (result->'generation_id_map'->>source_child_b_id::text)::uuid;

  IF cloned_shot_id IS NULL OR cloned_shot_id = source_shot_id THEN
    RAISE EXCEPTION 'FAIL: duplicate did not create a distinct shot (%)', cloned_shot_id;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.shots
    WHERE id = cloned_shot_id
      AND project_id = test_project_id
      AND name = 'Source shot (copy)'
      AND position = 8
      AND aspect_ratio = '16:9'
      AND settings = '{"camera":"wide"}'::jsonb
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned shot did not preserve shot scalar fields and next position';
  END IF;

  IF cloned_image_slot_a_id IS NULL OR cloned_image_slot_b_id IS NULL THEN
    RAISE EXCEPTION 'FAIL: image shot_generation slots were not mapped (%)', result;
  END IF;

  IF cloned_parent_id IS NULL OR cloned_child_a_id IS NULL OR cloned_child_b_id IS NULL THEN
    RAISE EXCEPTION 'FAIL: video generation IDs were not mapped (%)', result;
  END IF;

  SELECT count(*) INTO row_count
  FROM public.shot_generations
  WHERE shot_id = cloned_shot_id
    AND id IN (cloned_image_slot_a_id, cloned_image_slot_b_id)
    AND generation_id IN (image_generation_a_id, image_generation_b_id);

  IF row_count <> 2 THEN
    RAISE EXCEPTION 'FAIL: cloned image slots did not share source image generation IDs (count=%)', row_count;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.shot_generations
    WHERE id = cloned_image_slot_a_id
      AND shot_id = cloned_shot_id
      AND generation_id = image_generation_a_id
      AND timeline_frame = 0
      AND metadata = '{"slot":"start"}'::jsonb
  ) OR NOT EXISTS (
    SELECT 1
    FROM public.shot_generations
    WHERE id = cloned_image_slot_b_id
      AND shot_id = cloned_shot_id
      AND generation_id = image_generation_b_id
      AND timeline_frame = 81
      AND metadata = '{"slot":"end"}'::jsonb
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned image slots did not preserve timeline_frame and metadata';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.generations
    WHERE id IN (cloned_parent_id, cloned_child_a_id, cloned_child_b_id)
      AND id IN (source_parent_id, source_child_a_id, source_child_b_id)
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned video generation IDs overlap source IDs';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.generations
    WHERE id = cloned_parent_id
      AND based_on = source_parent_id
      AND location = 'https://example.invalid/source-final.mp4'
      AND thumbnail_url = 'https://example.invalid/source-final-thumb.jpg'
      AND name = 'Source parent primary'
      AND starred = true
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned parent did not preserve output fields and based_on provenance';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.generations
    WHERE id = cloned_child_a_id
      AND based_on = source_child_a_id
      AND parent_generation_id = cloned_parent_id
      AND pair_shot_generation_id = cloned_image_slot_a_id
      AND child_order = 0
      AND location = 'https://example.invalid/source-segment-a.mp4'
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned child A did not remap typed parent/pair relationships';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.generations
    WHERE id = cloned_child_b_id
      AND based_on = source_child_b_id
      AND parent_generation_id = cloned_parent_id
      AND pair_shot_generation_id = cloned_image_slot_b_id
      AND child_order = 1
      AND location = 'https://example.invalid/source-segment-b.mp4'
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned child B did not remap typed parent/pair relationships';
  END IF;

  SELECT params INTO cloned_parent_params
  FROM public.generations
  WHERE id = cloned_parent_id;

  SELECT params INTO cloned_child_a_params
  FROM public.generations
  WHERE id = cloned_child_a_id;

  SELECT params INTO cloned_parent_variant_params
  FROM public.generation_variants
  WHERE generation_id = cloned_parent_id
    AND is_primary = true;

  SELECT params INTO cloned_child_a_variant_params
  FROM public.generation_variants
  WHERE generation_id = cloned_child_a_id
    AND is_primary = true;

  IF cloned_parent_params #>> '{originalParams,orchestrator_details,shot_id}' <> cloned_shot_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent params did not remap originalParams.orchestrator_details.shot_id';
  END IF;

  IF cloned_parent_params #>> '{originalParams,orchestrator_details,parent_generation_id}' <> cloned_parent_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent params did not remap parent_generation_id';
  END IF;

  IF cloned_parent_params #>> '{originalParams,orchestrator_details,child_generation_id}' <> cloned_child_a_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent params did not remap child_generation_id';
  END IF;

  IF cloned_parent_params #>> '{originalParams,orchestrator_details,pair_shot_generation_id}' <> cloned_image_slot_a_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent params did not remap pair_shot_generation_id';
  END IF;

  IF cloned_parent_params #>> '{originalParams,orchestrator_details,pair_shot_generation_ids,0}' <> cloned_image_slot_a_id::text
    OR cloned_parent_params #>> '{originalParams,orchestrator_details,pair_shot_generation_ids,1}' <> cloned_image_slot_b_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent params did not remap pair_shot_generation_ids array';
  END IF;

  IF cloned_parent_params #>> '{input_image_generation_ids,0}' <> image_generation_a_id::text
    OR cloned_parent_params #>> '{input_image_generation_ids,1}' <> image_generation_b_id::text
    OR cloned_parent_params #>> '{input_image_generation_ids,2}' <> cloned_child_a_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent params did not preserve shared image IDs while remapping child generation IDs';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.generations
    WHERE id = cloned_parent_id
      AND children #>> '{0}' = cloned_child_a_id::text
      AND children #>> '{1}' = cloned_child_b_id::text
  ) THEN
    RAISE EXCEPTION 'FAIL: cloned parent children array did not remap child generation IDs';
  END IF;

  IF cloned_child_a_params #>> '{parent_generation_id}' <> cloned_parent_id::text
    OR cloned_child_a_params #>> '{child_generation_id}' <> cloned_child_a_id::text
    OR cloned_child_a_params #>> '{pair_shot_generation_id}' <> cloned_image_slot_a_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned child generation params did not remap top-level relationships';
  END IF;

  IF cloned_parent_variant_params #>> '{originalParams,orchestrator_details,shot_id}' <> cloned_shot_id::text
    OR cloned_parent_variant_params #>> '{originalParams,orchestrator_details,parent_generation_id}' <> cloned_parent_id::text
    OR cloned_parent_variant_params #>> '{originalParams,orchestrator_details,child_generation_id}' <> cloned_child_a_id::text
    OR cloned_parent_variant_params #>> '{originalParams,orchestrator_details,pair_shot_generation_ids,0}' <> cloned_image_slot_a_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned parent primary variant params were not remapped';
  END IF;

  IF cloned_child_a_variant_params #>> '{parent_generation_id}' <> cloned_parent_id::text
    OR cloned_child_a_variant_params #>> '{child_generation_id}' <> cloned_child_a_id::text
    OR cloned_child_a_variant_params #>> '{pair_shot_generation_id}' <> cloned_image_slot_a_id::text THEN
    RAISE EXCEPTION 'FAIL: cloned child primary variant params were not remapped';
  END IF;

  source_video_ids := ARRAY[
    source_parent_id::text,
    source_child_a_id::text,
    source_child_b_id::text
  ];
  source_slot_ids := ARRAY[
    source_image_slot_a_id::text,
    source_image_slot_b_id::text
  ];

  WITH RECURSIVE docs(label, doc) AS (
    SELECT 'generation:' || g.id::text, g.params
    FROM public.generations g
    WHERE g.id IN (cloned_parent_id, cloned_child_a_id, cloned_child_b_id)
    UNION ALL
    SELECT 'primary_variant:' || gv.generation_id::text, gv.params
    FROM public.generation_variants gv
    WHERE gv.generation_id IN (cloned_parent_id, cloned_child_a_id, cloned_child_b_id)
      AND gv.is_primary = true
  ),
  walk(label, key, value) AS (
    SELECT docs.label, NULL::text, docs.doc
    FROM docs
    UNION ALL
    SELECT walk.label, COALESCE(entry.key, walk.key), entry.value
    FROM walk
    CROSS JOIN LATERAL (
      SELECT object_entry.key, object_entry.value
      FROM jsonb_each(
        CASE
          WHEN jsonb_typeof(walk.value) = 'object' THEN walk.value
          ELSE '{}'::jsonb
        END
      ) AS object_entry(key, value)
      UNION ALL
      SELECT NULL::text, array_item.value
      FROM jsonb_array_elements(
        CASE
          WHEN jsonb_typeof(walk.value) = 'array' THEN walk.value
          ELSE '[]'::jsonb
        END
      ) AS array_item(value)
    ) AS entry(key, value)
  )
  SELECT string_agg(label || ':' || key || '=' || (value #>> '{}'), ', ')
  INTO leaked_refs
  FROM walk
  WHERE jsonb_typeof(value) = 'string'
    AND (
      (key = 'shot_id' AND value #>> '{}' = source_shot_id::text)
      OR (key IN ('parent_generation_id', 'child_generation_id') AND value #>> '{}' = ANY(source_video_ids))
      OR (key IN ('pair_shot_generation_id', 'pair_shot_generation_ids') AND value #>> '{}' = ANY(source_slot_ids))
    );

  IF leaked_refs IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: cloned relationship params still reference source graph: %', leaked_refs;
  END IF;

  SELECT count(*) INTO row_count
  FROM public.generation_variants
  WHERE generation_id IN (cloned_parent_id, cloned_child_a_id, cloned_child_b_id);

  IF row_count <> 3 THEN
    RAISE EXCEPTION 'FAIL: expected 3 cloned variants, found %', row_count;
  END IF;

  SELECT count(*) INTO row_count
  FROM public.generation_variants
  WHERE generation_id IN (cloned_parent_id, cloned_child_a_id, cloned_child_b_id)
    AND is_primary = true;

  IF row_count <> 3 THEN
    RAISE EXCEPTION 'FAIL: expected 3 cloned primary variants, found %', row_count;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.generations
    WHERE id = source_parent_id
      AND params IS DISTINCT FROM source_parent_params_before
  ) THEN
    RAISE EXCEPTION 'FAIL: source parent generation params changed during clone';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.generation_variants
    WHERE id = source_parent_variant_id
      AND params IS DISTINCT FROM source_parent_variant_params_before
  ) THEN
    RAISE EXCEPTION 'FAIL: source parent primary variant params changed during clone';
  END IF;

  SELECT count(*) INTO row_count
  FROM public.shot_final_videos
  WHERE shot_id = cloned_shot_id
    AND id = cloned_parent_id
    AND location = 'https://example.invalid/source-final.mp4'
    AND thumbnail_url = 'https://example.invalid/source-final-thumb.jpg'
    AND variant_fetch_generation_id = cloned_parent_id;

  IF row_count <> 1 THEN
    RAISE EXCEPTION 'FAIL: shot_final_videos did not expose the cloned final video (count=%)', row_count;
  END IF;

  RAISE NOTICE 'PASS: duplicate_shot_with_videos cloned an independent graph and remapped typed/JSON relationships';
END $$;

ROLLBACK;
