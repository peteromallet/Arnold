-- Sprint 9 live parity: seed production selectors/capabilities for every
-- VibeComfy-supported route currently advertised by the worker contract.

BEGIN;

WITH supported_routes(route_key, template_id, source) AS (
  VALUES
    ('z_image_turbo', 'image/z_image', 'sprint2_direct_routes'),
    ('z_image_turbo_i2i', 'image/z_image_img2img', 'sprint2_direct_routes'),
    ('qwen_image_2512', 'image/qwen_image_2512', 'sprint2_direct_routes'),
    ('qwen_image_edit', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('qwen_image_style', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('image_inpaint', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('annotated_image_edit', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('wan_2_2_t2i', 'video/wanvideo_wrapper_22_14b_t2i', 'sprint2_direct_routes'),
    ('travel_segment__model-wan22_vace__guidance-vace_flow__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_canny__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_depth__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_raw__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_raw__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('join_clips_segment__model-wan22_vace__guidance-vace__continuity-join_bridge__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract')
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
  10,
  jsonb_build_object(
    'seeded_by', '20260507160011_seed_vibecomfy_production_route_metadata',
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
    ('z_image_turbo', 'image/z_image', 'sprint2_direct_routes'),
    ('z_image_turbo_i2i', 'image/z_image_img2img', 'sprint2_direct_routes'),
    ('qwen_image_2512', 'image/qwen_image_2512', 'sprint2_direct_routes'),
    ('qwen_image_edit', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('qwen_image_style', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('image_inpaint', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('annotated_image_edit', 'edit/qwen_image_edit', 'sprint2_direct_routes'),
    ('wan_2_2_t2i', 'video/wanvideo_wrapper_22_14b_t2i', 'sprint2_direct_routes'),
    ('travel_segment__model-wan22_vace__guidance-vace_flow__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_canny__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_depth__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace_raw__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('travel_segment__model-wan22_vace__guidance-vace__continuity-video_source__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('individual_travel_segment__model-wan22_vace__guidance-vace_raw__continuity-first_last__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract'),
    ('join_clips_segment__model-wan22_vace__guidance-vace__continuity-join_bridge__profile-default', 'video/wanvideo_wrapper_22_14b_vace_cocktail', 'section3a_worker_contract')
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
  10,
  true,
  'VibeComfy production parity route validated by worker/VibeComfy contract',
  jsonb_build_object(
    'seeded_by', '20260507160011_seed_vibecomfy_production_route_metadata',
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
