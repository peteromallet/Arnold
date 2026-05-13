-- Layer 2 (centralize route derivation in the DB).
--
-- Single source of truth for route_key derivation that the create-task edge
-- function and worker child-task creators both call via supabase.rpc(). The
-- TS helper `deriveRouteKey` and the Python helper `derive_route_key` are
-- reduced to thin wrappers around this function in a follow-up migration.
--
-- Single-mechanism resolution: this function IGNORES `params->>'model_family'`
-- and `params->>'model_family_class'` overrides. Family is resolved purely from
-- `params->>'model_name'` via the seeded `model_family_for_model` table. This
-- structurally prevents the bug-#3 enum collision documented in the brief
-- where `params.model_family` was overloaded with two incompatible enums.
--
-- Returns NULL when the input is not derivable (caller — typically the Layer 1
-- trigger — RAISES on NULL with a clear violated-invariant message).

BEGIN;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.route_alias_map (
  alias       text PRIMARY KEY,
  route_key   text NOT NULL
);

COMMENT ON TABLE public.route_alias_map IS
  'Maps direct task_type aliases to canonical route_keys. Seeded from DIRECT_ROUTE_ALIASES in supabase/functions/_shared/selectedRoute.ts (Layer 2 of contract enforcement).';

CREATE TABLE IF NOT EXISTS public.model_family_for_model (
  model_name    text PRIMARY KEY,
  route_family  text NOT NULL
    CHECK (route_family IN ('wan22_i2v','wan22_vace','ltx2','ltx2_distilled','qwen','z_image'))
);

COMMENT ON TABLE public.model_family_for_model IS
  'Maps params.model_name to its route family. Single source of truth — derive_route_key IGNORES params.model_family overrides. Seeded from routeModelFamily heuristics in selectedRoute.ts plus the matrix.py fixture audit (T3).';

-- ---------------------------------------------------------------------------
-- Seeds: route_alias_map (mirrors DIRECT_ROUTE_ALIASES)
-- ---------------------------------------------------------------------------

INSERT INTO public.route_alias_map (alias, route_key) VALUES
  ('z_image',              'z_image_turbo'),
  ('z_image_turbo',        'z_image_turbo'),
  ('z_image_turbo_i2i',    'z_image_turbo_i2i'),
  ('qwen_image',           'qwen_image'),
  ('qwen_image_2512',      'qwen_image_2512'),
  ('optimised_t2i',        'wan_2_2_t2i'),
  ('wan_2_2_t2i',          'wan_2_2_t2i'),
  ('qwen_image_edit',      'qwen_image_edit'),
  ('qwen_image_style',     'qwen_image_style'),
  ('image_inpaint',        'image_inpaint'),
  ('annotated_image_edit', 'annotated_image_edit')
ON CONFLICT (alias) DO UPDATE SET route_key = EXCLUDED.route_key;

-- ---------------------------------------------------------------------------
-- Seeds: model_family_for_model
--   Canonical pairs from the T3 matrix.py fixture audit, plus extras covering
--   common model_name spellings reachable by routeModelFamily heuristics.
-- ---------------------------------------------------------------------------

INSERT INTO public.model_family_for_model (model_name, route_family) VALUES
  -- T3 audit canonical set (matrix.py fixtures)
  ('wan_2_2_i2v',                                'wan22_i2v'),
  ('wan_2_2_vace_lightning_baseline_2_2_2',      'wan22_vace'),
  ('ltx2_22B_distilled_1_1',                     'ltx2_distilled'),
  ('ltx2_22B',                                   'ltx2'),
  -- Common spellings reachable from routeModelFamily slug heuristics
  ('wan_2_2_t2i',                                'wan22_i2v'),
  ('wan_2_2_vace',                               'wan22_vace'),
  ('z_image_turbo',                              'z_image'),
  ('z_image_turbo_i2i',                          'z_image'),
  ('qwen_image',                                 'qwen'),
  ('qwen_image_2512',                            'qwen'),
  ('qwen_image_edit',                            'qwen'),
  ('qwen_image_style',                           'qwen')
ON CONFLICT (model_name) DO UPDATE SET route_family = EXCLUDED.route_family;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

-- Mirrors the JS slug() in selectedRoute.ts:
--   lower, trim, '+' -> '_plus_', collapse non-alnum to '_',
--   trim leading/trailing '_', empty -> 'none'.
CREATE OR REPLACE FUNCTION public._route_slug(p_value text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  s text;
BEGIN
  s := lower(trim(coalesce(p_value, 'none')));
  s := replace(s, '+', '_plus_');
  s := regexp_replace(s, '[^a-z0-9]+', '_', 'g');
  s := regexp_replace(s, '_+', '_', 'g');
  s := regexp_replace(s, '^_+|_+$', '', 'g');
  IF s = '' THEN
    s := 'none';
  END IF;
  RETURN s;
END;
$$;

-- ---------------------------------------------------------------------------
-- public.derive_route_key
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.derive_route_key(
  p_task_type text,
  p_params    jsonb
)
RETURNS text
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_params              jsonb;
  v_source_task_type    text;
  v_effective_task_type text;
  v_alias_hit           text;
  v_model_family        text;
  v_guidance_kind       text;
  v_guidance_mode       text;
  v_guidance_key        text;
  v_continuity_case     text;
  v_profile             text;
BEGIN
  IF p_task_type IS NULL OR length(trim(p_task_type)) = 0 THEN
    RETURN NULL;
  END IF;

  v_params := COALESCE(p_params, '{}'::jsonb);

  -- Honor _source_task_type (mirrors deriveRouteKey TS at selectedRoute.ts:240).
  v_source_task_type := v_params->>'_source_task_type';
  IF v_source_task_type IS NOT NULL
     AND v_source_task_type IN ('travel_segment','individual_travel_segment','join_clips_segment') THEN
    v_effective_task_type := v_source_task_type;
  ELSE
    v_effective_task_type := p_task_type;
  END IF;

  -- Dimensional child route key for travel/segment families.
  IF v_effective_task_type IN ('travel_segment','individual_travel_segment','join_clips_segment') THEN
    -- Single-mechanism: family is resolved purely from model_name lookup.
    -- IGNORES params->>'model_family' AND params->>'model_family_class'.
    SELECT route_family INTO v_model_family
    FROM public.model_family_for_model
    WHERE model_name = v_params->>'model_name';

    IF v_model_family IS NULL THEN
      -- Not derivable; trigger will RAISE.
      RETURN NULL;
    END IF;

    -- Guidance kind (ports routeGuidanceKind heuristics).
    v_guidance_kind := v_params->>'guidance_kind';
    IF v_guidance_kind IS NULL THEN
      v_guidance_kind := v_params->>'travel_guidance_kind';
    END IF;
    IF v_guidance_kind IS NULL
       AND jsonb_typeof(v_params->'travel_guidance') = 'object'
       AND v_params->'travel_guidance'->>'kind' IS NOT NULL THEN
      v_guidance_kind := v_params->'travel_guidance'->>'kind';
    END IF;
    IF v_guidance_kind IS NULL THEN
      IF (v_params ? 'use_uni3c') OR (v_params ? 'uni3c_guide_video') THEN
        v_guidance_kind := 'uni3c';
      ELSIF v_params ? 'svi2pro' THEN
        v_guidance_kind := 'vace';
      ELSIF (v_params ? 'video_guide') OR (v_params ? 'video_mask') THEN
        v_guidance_kind := 'vace';
      ELSIF v_effective_task_type = 'join_clips_segment' AND v_model_family = 'wan22_vace' THEN
        v_guidance_kind := 'vace';
      ELSE
        v_guidance_kind := 'none';
      END IF;
    END IF;

    -- Guidance mode (ports routeGuidanceMode heuristics).
    v_guidance_mode := v_params->>'guidance_mode';
    IF v_guidance_mode IS NULL THEN
      v_guidance_mode := v_params->>'travel_guidance_mode';
    END IF;
    IF v_guidance_mode IS NULL
       AND jsonb_typeof(v_params->'travel_guidance') = 'object'
       AND v_params->'travel_guidance'->>'mode' IS NOT NULL THEN
      v_guidance_mode := v_params->'travel_guidance'->>'mode';
    END IF;
    IF v_guidance_mode IS NULL THEN
      v_guidance_mode := 'none';
    END IF;

    -- Combine kind+mode for vace/ltx_control (mirrors routeGuidanceKey TS).
    IF v_guidance_kind IN ('vace','ltx_control') AND v_guidance_mode <> 'none' THEN
      v_guidance_key := v_guidance_kind || '_' || v_guidance_mode;
    ELSE
      v_guidance_key := v_guidance_kind;
    END IF;

    -- Continuity case (ports routeContinuityCase heuristics).
    v_continuity_case := v_params->>'continuity_case';
    IF v_continuity_case IS NULL THEN
      IF v_effective_task_type = 'join_clips_segment' THEN
        v_continuity_case := 'join_bridge';
      ELSIF v_params ? 'video_source' THEN
        v_continuity_case := 'video_source';
      ELSE
        v_continuity_case := 'first_last';
      END IF;
    END IF;

    -- Profile (ports routeProfile heuristics).
    v_profile := COALESCE(
      v_params->>'profile',
      v_params->>'wgp_profile',
      v_params->>'override_profile',
      'default'
    );

    RETURN format(
      '%s__model-%s__guidance-%s__continuity-%s__profile-%s',
      public._route_slug(v_effective_task_type),
      public._route_slug(v_model_family),
      public._route_slug(v_guidance_key),
      public._route_slug(v_continuity_case),
      public._route_slug(v_profile)
    );
  END IF;

  -- Direct route key path: alias map lookup, fallback to slug(task_type).
  SELECT route_key INTO v_alias_hit
  FROM public.route_alias_map
  WHERE alias = public._route_slug(p_task_type);

  IF v_alias_hit IS NOT NULL THEN
    RETURN v_alias_hit;
  END IF;

  -- Mirrors directRouteKey TS: alias-miss returns the original task_type.
  RETURN p_task_type;
END;
$$;

COMMENT ON FUNCTION public.derive_route_key(text, jsonb) IS
  'Single source of truth for route_key derivation. IGNORES params.model_family and params.model_family_class — family resolves via model_family_for_model lookup on params.model_name. Returns NULL when not derivable (Layer 1 trigger RAISES on NULL).';

-- ---------------------------------------------------------------------------
-- In-migration sanity asserts. Cover all 6 enum families + orchestrator.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  v_actual text;
BEGIN
  -- wan22_i2v (travel_segment with wan_2_2_i2v model)
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object('model_name', 'wan_2_2_i2v')
  );
  IF v_actual IS NULL OR position('model-wan22_i2v' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key wan22_i2v assert failed: got %', v_actual;
  END IF;

  -- wan22_vace (travel_segment with vace model + video_source continuity)
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object(
      'model_name', 'wan_2_2_vace_lightning_baseline_2_2_2',
      'video_source', 'foo.mp4'
    )
  );
  IF v_actual IS NULL OR position('model-wan22_vace' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key wan22_vace assert failed: got %', v_actual;
  END IF;
  IF position('continuity-video_source' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key continuity assert failed: got %', v_actual;
  END IF;

  -- ltx2 (travel_segment)
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object('model_name', 'ltx2_22B')
  );
  IF v_actual IS NULL OR position('model-ltx2' in v_actual) = 0
     OR position('model-ltx2_distilled' in v_actual) <> 0 THEN
    RAISE EXCEPTION 'derive_route_key ltx2 assert failed: got %', v_actual;
  END IF;

  -- ltx2_distilled (travel_segment)
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object('model_name', 'ltx2_22B_distilled_1_1')
  );
  IF v_actual IS NULL OR position('model-ltx2_distilled' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key ltx2_distilled assert failed: got %', v_actual;
  END IF;

  -- qwen (direct route via alias map)
  v_actual := public.derive_route_key('qwen_image_edit', '{}'::jsonb);
  IF v_actual IS DISTINCT FROM 'qwen_image_edit' THEN
    RAISE EXCEPTION 'derive_route_key qwen direct assert failed: got %', v_actual;
  END IF;

  -- qwen via dimensional path (individual_travel_segment + qwen model)
  v_actual := public.derive_route_key(
    'individual_travel_segment',
    jsonb_build_object('model_name', 'qwen_image')
  );
  IF v_actual IS NULL OR position('model-qwen' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key qwen dimensional assert failed: got %', v_actual;
  END IF;

  -- z_image (direct route via alias map)
  v_actual := public.derive_route_key('z_image', '{}'::jsonb);
  IF v_actual IS DISTINCT FROM 'z_image_turbo' THEN
    RAISE EXCEPTION 'derive_route_key z_image alias assert failed: got %', v_actual;
  END IF;

  -- Orchestrator-parent (no alias, returns task_type).
  v_actual := public.derive_route_key('travel_orchestrator', '{}'::jsonb);
  IF v_actual IS DISTINCT FROM 'travel_orchestrator' THEN
    RAISE EXCEPTION 'derive_route_key orchestrator-parent assert failed: got %', v_actual;
  END IF;

  v_actual := public.derive_route_key('join_clips_orchestrator', '{}'::jsonb);
  IF v_actual IS DISTINCT FROM 'join_clips_orchestrator' THEN
    RAISE EXCEPTION 'derive_route_key join_clips_orchestrator assert failed: got %', v_actual;
  END IF;

  -- IGNORES params.model_family override: a misleading override should NOT
  -- change the resolved family — model_name='wan_2_2_i2v' must still produce
  -- model-wan22_i2v even when params.model_family says 'qwen'.
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object('model_name', 'wan_2_2_i2v', 'model_family', 'qwen')
  );
  IF v_actual IS NULL OR position('model-wan22_i2v' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key model_family override-ignored assert failed: got %', v_actual;
  END IF;

  -- IGNORES params.model_family_class override too.
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object('model_name', 'wan_2_2_i2v', 'model_family_class', 'wan')
  );
  IF v_actual IS NULL OR position('model-wan22_i2v' in v_actual) = 0 THEN
    RAISE EXCEPTION 'derive_route_key model_family_class override-ignored assert failed: got %', v_actual;
  END IF;

  -- Unknown model_name on dimensional task -> NULL (trigger will RAISE).
  v_actual := public.derive_route_key(
    'travel_segment',
    jsonb_build_object('model_name', 'totally_unknown_model_xyz')
  );
  IF v_actual IS NOT NULL THEN
    RAISE EXCEPTION 'derive_route_key unknown-model NULL assert failed: got %', v_actual;
  END IF;
END
$$;

COMMIT;

-- ---------------------------------------------------------------------------
-- Reversibility (manual rollback only — Supabase migrations are forward-only):
--   BEGIN;
--   DROP FUNCTION IF EXISTS public.derive_route_key(text, jsonb);
--   DROP FUNCTION IF EXISTS public._route_slug(text);
--   DROP TABLE IF EXISTS public.model_family_for_model;
--   DROP TABLE IF EXISTS public.route_alias_map;
--   COMMIT;
-- ---------------------------------------------------------------------------
