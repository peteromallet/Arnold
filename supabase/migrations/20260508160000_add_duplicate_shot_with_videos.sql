BEGIN;

CREATE OR REPLACE FUNCTION public._duplicate_shot_with_videos_remap_jsonb(
  p_value jsonb,
  p_source_shot_id uuid,
  p_new_shot_id uuid,
  p_generation_id_map jsonb,
  p_shot_generation_id_map jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
AS $function$
DECLARE
  v_type text;
BEGIN
  IF p_value IS NULL THEN
    RETURN NULL;
  END IF;

  v_type := jsonb_typeof(p_value);

  IF v_type = 'object' THEN
    RETURN (
      SELECT COALESCE(jsonb_object_agg(entry.key, mapped.value), '{}'::jsonb)
      FROM jsonb_each(p_value) AS entry(key, value)
      CROSS JOIN LATERAL (
        SELECT CASE
          WHEN entry.key = 'shot_id'
            AND jsonb_typeof(entry.value) = 'string'
            AND entry.value #>> '{}' = p_source_shot_id::text
            THEN to_jsonb(p_new_shot_id::text)

          WHEN entry.key IN ('parent_generation_id', 'child_generation_id')
            AND jsonb_typeof(entry.value) = 'string'
            AND p_generation_id_map ? (entry.value #>> '{}')
            THEN to_jsonb(p_generation_id_map ->> (entry.value #>> '{}'))

          WHEN entry.key = 'pair_shot_generation_id'
            AND jsonb_typeof(entry.value) = 'string'
            AND p_shot_generation_id_map ? (entry.value #>> '{}')
            THEN to_jsonb(p_shot_generation_id_map ->> (entry.value #>> '{}'))

          WHEN entry.key = 'pair_shot_generation_ids'
            AND jsonb_typeof(entry.value) = 'array'
            THEN (
              SELECT COALESCE(jsonb_agg(
                CASE
                  WHEN jsonb_typeof(array_item.value) = 'string'
                    AND p_shot_generation_id_map ? (array_item.value #>> '{}')
                    THEN to_jsonb(p_shot_generation_id_map ->> (array_item.value #>> '{}'))
                  ELSE public._duplicate_shot_with_videos_remap_jsonb(
                    array_item.value,
                    p_source_shot_id,
                    p_new_shot_id,
                    p_generation_id_map,
                    p_shot_generation_id_map
                  )
                END
                ORDER BY array_item.ordinality
              ), '[]'::jsonb)
              FROM jsonb_array_elements(entry.value) WITH ORDINALITY AS array_item(value, ordinality)
            )

          ELSE public._duplicate_shot_with_videos_remap_jsonb(
            entry.value,
            p_source_shot_id,
            p_new_shot_id,
            p_generation_id_map,
            p_shot_generation_id_map
          )
        END AS value
      ) AS mapped
    );
  END IF;

  IF v_type = 'array' THEN
    RETURN (
      SELECT COALESCE(jsonb_agg(
        CASE
          WHEN jsonb_typeof(array_item.value) = 'string'
            AND p_generation_id_map ? (array_item.value #>> '{}')
            THEN to_jsonb(p_generation_id_map ->> (array_item.value #>> '{}'))
          ELSE public._duplicate_shot_with_videos_remap_jsonb(
            array_item.value,
            p_source_shot_id,
            p_new_shot_id,
            p_generation_id_map,
            p_shot_generation_id_map
          )
        END
        ORDER BY array_item.ordinality
      ), '[]'::jsonb)
      FROM jsonb_array_elements(p_value) WITH ORDINALITY AS array_item(value, ordinality)
    );
  END IF;

  IF v_type = 'string' AND p_generation_id_map ? (p_value #>> '{}') THEN
    RETURN to_jsonb(p_generation_id_map ->> (p_value #>> '{}'));
  END IF;

  RETURN p_value;
END;
$function$;

CREATE OR REPLACE FUNCTION public.duplicate_shot_with_videos(
  original_shot_id uuid,
  project_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
AS $function$
DECLARE
  v_new_shot_id uuid;
  v_original_name text;
  v_original_aspect_ratio text;
  v_original_settings jsonb;
  v_next_position integer;
  v_generation_id_map jsonb := '{}'::jsonb;
  v_shot_generation_id_map jsonb := '{}'::jsonb;
  v_image_slot_count integer := 0;
  v_parent_video_count integer := 0;
  v_child_video_count integer := 0;
  v_variant_count integer := 0;
BEGIN
  IF auth.role() <> 'service_role' AND NOT EXISTS (
    SELECT 1
    FROM public.projects p
    WHERE p.id = duplicate_shot_with_videos.project_id
      AND p.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Not authorized to duplicate shots in this project';
  END IF;

  SELECT s.name, s.aspect_ratio, s.settings
  INTO v_original_name, v_original_aspect_ratio, v_original_settings
  FROM public.shots s
  WHERE s.id = original_shot_id
    AND s.project_id = duplicate_shot_with_videos.project_id;

  IF v_original_name IS NULL THEN
    RAISE EXCEPTION 'Shot not found or does not belong to the specified project';
  END IF;

  PERFORM pg_advisory_xact_lock(
    hashtext('duplicate_shot_with_videos'),
    hashtext(original_shot_id::text)
  );

  SELECT COALESCE(MAX(s.position), 0) + 1
  INTO v_next_position
  FROM public.shots s
  WHERE s.project_id = duplicate_shot_with_videos.project_id;

  INSERT INTO public.shots (name, project_id, position, aspect_ratio, settings)
  VALUES (
    v_original_name || ' (copy)',
    duplicate_shot_with_videos.project_id,
    v_next_position,
    v_original_aspect_ratio,
    v_original_settings
  )
  RETURNING id INTO v_new_shot_id;

  DROP TABLE IF EXISTS tmp_duplicate_shot_generation_map;
  DROP TABLE IF EXISTS tmp_duplicate_shot_generation_slot_map;

  CREATE TEMP TABLE tmp_duplicate_shot_generation_map (
    old_generation_id uuid PRIMARY KEY,
    new_generation_id uuid NOT NULL,
    clone_kind text NOT NULL
  ) ON COMMIT DROP;

  CREATE TEMP TABLE tmp_duplicate_shot_generation_slot_map (
    old_shot_generation_id uuid PRIMARY KEY,
    new_shot_generation_id uuid NOT NULL,
    old_generation_id uuid NOT NULL,
    new_generation_id uuid NOT NULL,
    slot_kind text NOT NULL
  ) ON COMMIT DROP;

  INSERT INTO tmp_duplicate_shot_generation_map (
    old_generation_id,
    new_generation_id,
    clone_kind
  )
  SELECT DISTINCT
    g.id,
    gen_random_uuid(),
    'parent_video'
  FROM public.shot_generations sg
  JOIN public.generations g ON g.id = sg.generation_id
  WHERE sg.shot_id = original_shot_id
    AND g.type = 'video'
    AND g.parent_generation_id IS NULL;

  INSERT INTO tmp_duplicate_shot_generation_map (
    old_generation_id,
    new_generation_id,
    clone_kind
  )
  SELECT DISTINCT
    child.id,
    gen_random_uuid(),
    'child_segment'
  FROM public.generations child
  JOIN tmp_duplicate_shot_generation_map parent_map
    ON parent_map.old_generation_id = child.parent_generation_id
  WHERE parent_map.clone_kind = 'parent_video'
    AND child.type = 'video'
    AND child.parent_generation_id IS NOT NULL
  ON CONFLICT (old_generation_id) DO NOTHING;

  IF EXISTS (
    SELECT 1
    FROM tmp_duplicate_shot_generation_map
    WHERE clone_kind = 'parent_video'
  ) THEN
    DELETE FROM public.generations auto_parent
    WHERE auto_parent.id IN (
      SELECT sg.generation_id
      FROM public.shot_generations sg
      WHERE sg.shot_id = v_new_shot_id
    )
      AND auto_parent.type = 'video'
      AND auto_parent.parent_generation_id IS NULL
      AND auto_parent.location IS NULL
      AND auto_parent.params->>'created_from' IN (
        'shot_parent_generation',
        'shot_parent_generation_backfill'
      )
      AND NOT EXISTS (
        SELECT 1
        FROM public.generations child
        WHERE child.parent_generation_id = auto_parent.id
      );
  END IF;

  INSERT INTO tmp_duplicate_shot_generation_slot_map (
    old_shot_generation_id,
    new_shot_generation_id,
    old_generation_id,
    new_generation_id,
    slot_kind
  )
  SELECT
    sg.id,
    gen_random_uuid(),
    sg.generation_id,
    sg.generation_id,
    'image'
  FROM public.shot_generations sg
  JOIN public.generations g ON g.id = sg.generation_id
  WHERE sg.shot_id = original_shot_id
    AND sg.timeline_frame IS NOT NULL
    AND sg.timeline_frame >= 0
    AND (g.type IS NULL OR g.type NOT LIKE '%video%');

  INSERT INTO tmp_duplicate_shot_generation_slot_map (
    old_shot_generation_id,
    new_shot_generation_id,
    old_generation_id,
    new_generation_id,
    slot_kind
  )
  SELECT
    sg.id,
    gen_random_uuid(),
    sg.generation_id,
    gen_map.new_generation_id,
    'parent_video'
  FROM public.shot_generations sg
  JOIN tmp_duplicate_shot_generation_map gen_map
    ON gen_map.old_generation_id = sg.generation_id
  WHERE sg.shot_id = original_shot_id
    AND gen_map.clone_kind = 'parent_video';

  SELECT COALESCE(jsonb_object_agg(old_generation_id::text, new_generation_id::text), '{}'::jsonb)
  INTO v_generation_id_map
  FROM tmp_duplicate_shot_generation_map;

  SELECT COALESCE(jsonb_object_agg(old_shot_generation_id::text, new_shot_generation_id::text), '{}'::jsonb)
  INTO v_shot_generation_id_map
  FROM tmp_duplicate_shot_generation_slot_map;

  INSERT INTO public.shot_generations (
    id,
    shot_id,
    generation_id,
    timeline_frame,
    metadata
  )
  SELECT
    slot_map.new_shot_generation_id,
    v_new_shot_id,
    slot_map.new_generation_id,
    sg.timeline_frame,
    sg.metadata
  FROM tmp_duplicate_shot_generation_slot_map slot_map
  JOIN public.shot_generations sg
    ON sg.id = slot_map.old_shot_generation_id
  WHERE slot_map.slot_kind = 'image'
  ORDER BY sg.timeline_frame ASC, sg.created_at ASC NULLS LAST;

  GET DIAGNOSTICS v_image_slot_count = ROW_COUNT;

  INSERT INTO public.generations (
    id,
    tasks,
    params,
    location,
    thumbnail_url,
    type,
    project_id,
    name,
    based_on,
    parent_generation_id,
    is_child,
    child_order,
    children,
    copied_from_share,
    starred,
    storage_mode,
    local_handle_id,
    local_file_name,
    local_file_size,
    local_file_mime,
    created_at,
    updated_at
  )
  SELECT
    gen_map.new_generation_id,
    source.tasks,
    public._duplicate_shot_with_videos_remap_jsonb(
      COALESCE(source.params, '{}'::jsonb),
      original_shot_id,
      v_new_shot_id,
      v_generation_id_map,
      v_shot_generation_id_map
    ),
    NULL,
    NULL,
    source.type,
    source.project_id,
    source.name,
    source.id,
    NULL,
    false,
    source.child_order,
    public._duplicate_shot_with_videos_remap_jsonb(
      source.children,
      original_shot_id,
      v_new_shot_id,
      v_generation_id_map,
      v_shot_generation_id_map
    ),
    source.copied_from_share,
    source.starred,
    source.storage_mode,
    source.local_handle_id,
    source.local_file_name,
    source.local_file_size,
    source.local_file_mime,
    statement_timestamp() + (row_number() OVER (ORDER BY source.created_at ASC, source.id ASC) * interval '1 millisecond'),
    source.updated_at
  FROM tmp_duplicate_shot_generation_map gen_map
  JOIN public.generations source
    ON source.id = gen_map.old_generation_id
  WHERE gen_map.clone_kind = 'parent_video'
  ORDER BY source.created_at ASC, source.id ASC;

  GET DIAGNOSTICS v_parent_video_count = ROW_COUNT;

  INSERT INTO public.shot_generations (
    id,
    shot_id,
    generation_id,
    timeline_frame,
    metadata
  )
  SELECT
    slot_map.new_shot_generation_id,
    v_new_shot_id,
    slot_map.new_generation_id,
    sg.timeline_frame,
    sg.metadata
  FROM tmp_duplicate_shot_generation_slot_map slot_map
  JOIN public.shot_generations sg
    ON sg.id = slot_map.old_shot_generation_id
  WHERE slot_map.slot_kind = 'parent_video'
  ORDER BY sg.created_at ASC NULLS LAST, sg.id ASC;

  INSERT INTO public.generations (
    id,
    tasks,
    params,
    location,
    thumbnail_url,
    type,
    project_id,
    name,
    based_on,
    parent_generation_id,
    is_child,
    child_order,
    children,
    copied_from_share,
    starred,
    pair_shot_generation_id,
    storage_mode,
    local_handle_id,
    local_file_name,
    local_file_size,
    local_file_mime,
    created_at,
    updated_at
  )
  SELECT
    gen_map.new_generation_id,
    source.tasks,
    public._duplicate_shot_with_videos_remap_jsonb(
      COALESCE(source.params, '{}'::jsonb),
      original_shot_id,
      v_new_shot_id,
      v_generation_id_map,
      v_shot_generation_id_map
    ),
    NULL,
    NULL,
    source.type,
    source.project_id,
    source.name,
    source.id,
    parent_map.new_generation_id,
    true,
    source.child_order,
    public._duplicate_shot_with_videos_remap_jsonb(
      source.children,
      original_shot_id,
      v_new_shot_id,
      v_generation_id_map,
      v_shot_generation_id_map
    ),
    source.copied_from_share,
    source.starred,
    CASE
      WHEN source.pair_shot_generation_id IS NOT NULL
        AND v_shot_generation_id_map ? source.pair_shot_generation_id::text
        THEN (v_shot_generation_id_map ->> source.pair_shot_generation_id::text)::uuid
      ELSE NULL
    END,
    source.storage_mode,
    source.local_handle_id,
    source.local_file_name,
    source.local_file_size,
    source.local_file_mime,
    statement_timestamp() + (row_number() OVER (ORDER BY source.created_at ASC, source.id ASC) * interval '1 millisecond'),
    source.updated_at
  FROM tmp_duplicate_shot_generation_map gen_map
  JOIN public.generations source
    ON source.id = gen_map.old_generation_id
  JOIN tmp_duplicate_shot_generation_map parent_map
    ON parent_map.old_generation_id = source.parent_generation_id
  WHERE gen_map.clone_kind = 'child_segment'
  ORDER BY source.created_at ASC, source.id ASC;

  GET DIAGNOSTICS v_child_video_count = ROW_COUNT;

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
    viewed_at,
    starred,
    created_at
  )
  SELECT
    gen_random_uuid(),
    gen_map.new_generation_id,
    variant.location,
    variant.thumbnail_url,
    public._duplicate_shot_with_videos_remap_jsonb(
      variant.params,
      original_shot_id,
      v_new_shot_id,
      v_generation_id_map,
      v_shot_generation_id_map
    ),
    variant.is_primary,
    variant.variant_type,
    variant.name,
    duplicate_shot_with_videos.project_id,
    variant.viewed_at,
    variant.starred,
    statement_timestamp() + (
      row_number() OVER (
        PARTITION BY variant.generation_id
        ORDER BY variant.created_at ASC, variant.id ASC
      ) * interval '1 millisecond'
    )
  FROM tmp_duplicate_shot_generation_map gen_map
  JOIN public.generation_variants variant
    ON variant.generation_id = gen_map.old_generation_id
  ORDER BY variant.generation_id, variant.created_at ASC, variant.id ASC;

  GET DIAGNOSTICS v_variant_count = ROW_COUNT;

  UPDATE public.generations cloned
  SET
    location = source.location,
    thumbnail_url = source.thumbnail_url,
    name = source.name,
    params = public._duplicate_shot_with_videos_remap_jsonb(
      source.params,
      original_shot_id,
      v_new_shot_id,
      v_generation_id_map,
      v_shot_generation_id_map
    )
  FROM tmp_duplicate_shot_generation_map gen_map
  JOIN public.generations source
    ON source.id = gen_map.old_generation_id
  WHERE cloned.id = gen_map.new_generation_id
    AND NOT EXISTS (
      SELECT 1
      FROM public.generation_variants variant
      WHERE variant.generation_id = gen_map.old_generation_id
    );

  RETURN jsonb_build_object(
    'shot_id', v_new_shot_id,
    'image_slot_count', v_image_slot_count,
    'parent_video_count', v_parent_video_count,
    'child_video_count', v_child_video_count,
    'variant_count', v_variant_count,
    'generation_id_map', v_generation_id_map,
    'shot_generation_id_map', v_shot_generation_id_map,
    'success', true
  );

EXCEPTION WHEN OTHERS THEN
  RAISE LOG '[DuplicateShotWithVideos] Error duplicating shot %: %', original_shot_id, SQLERRM;
  RAISE;
END;
$function$;

GRANT EXECUTE ON FUNCTION public.duplicate_shot_with_videos(uuid, uuid) TO authenticated;

COMMENT ON FUNCTION public.duplicate_shot_with_videos(uuid, uuid) IS
'Duplicates a shot with positioned image slot rows sharing image generation IDs, and clones parent/final video generations, child segment generations, and variants into an independent graph.';

COMMIT;
