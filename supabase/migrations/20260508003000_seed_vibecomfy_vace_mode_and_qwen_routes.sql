-- Sprint 9 post-chain parity: seed production metadata for routes proved after
-- the initial VibeComfy production selector seed.

BEGIN;

WITH supported_routes(route_key, template_id, source) AS (
  VALUES
    ('qwen_image', 'image/qwen_image_2512', 'sprint2_direct_routes'),
    ('travel_segment__model-wan22_vace__guidance-vace_raw__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_flow__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_canny__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_depth__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_flow__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_canny__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_depth__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract')
)
INSERT INTO public.route_backend_capabilities (
  backend,
  route_key,
  supports_route,
  supports_missing_selector,
  capability_version,
  metadata
)
SELECT
  'vibecomfy',
  route_key,
  true,
  false,
  11,
  jsonb_build_object(
    'seeded_by', '20260508003000_seed_vibecomfy_vace_mode_and_qwen_routes',
    'source', source,
    'support_state', 'vibecomfy_supported',
    'template_id', template_id
  )
FROM supported_routes
ON CONFLICT (backend, route_key) DO UPDATE SET
  supports_route = EXCLUDED.supports_route,
  supports_missing_selector = EXCLUDED.supports_missing_selector,
  capability_version = EXCLUDED.capability_version,
  metadata = public.route_backend_capabilities.metadata || EXCLUDED.metadata,
  updated_at = now();

WITH supported_routes(route_key, template_id, source) AS (
  VALUES
    ('qwen_image', 'image/qwen_image_2512', 'sprint2_direct_routes'),
    ('travel_segment__model-wan22_vace__guidance-vace_raw__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_flow__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_canny__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_depth__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_flow__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_canny__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_depth__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract')
)
INSERT INTO public.route_backend_selectors (
  selector_namespace,
  route_key,
  selected_backend,
  selector_version,
  enabled,
  reason,
  metadata
)
SELECT
  'production',
  route_key,
  'vibecomfy',
  11,
  true,
  'VibeComfy production parity route validated by worker/VibeComfy contract',
  jsonb_build_object(
    'seeded_by', '20260508003000_seed_vibecomfy_vace_mode_and_qwen_routes',
    'source', source,
    'support_state', 'vibecomfy_supported',
    'template_id', template_id
  )
FROM supported_routes
ON CONFLICT (selector_namespace, route_key) DO UPDATE SET
  selected_backend = EXCLUDED.selected_backend,
  selector_version = EXCLUDED.selector_version,
  enabled = EXCLUDED.enabled,
  reason = EXCLUDED.reason,
  metadata = public.route_backend_selectors.metadata || EXCLUDED.metadata,
  updated_at = now();

COMMIT;
