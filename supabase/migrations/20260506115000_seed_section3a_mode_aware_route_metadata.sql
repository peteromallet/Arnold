-- Sprint 9: Section 3A mode-aware route selector/capability seed data.
--
-- The executable Section 3A fixture is synchronized with docs in
-- reigh-worker/scripts/dual_run_compare/fixtures/section3a_matrix.fixture.
-- Keep this SQL in sync with that fixture: capabilities are explicit for every
-- non-FALL-BACK row, while selectors are seeded only for canary-promoted rows.

BEGIN;

WITH section3a_routes (
  row_id,
  route_key,
  disposition,
  expected_backend,
  support_state,
  blocking_reason
) AS (
  VALUES
    (1, 'travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template before Wan-family travel rows can be promoted.'),
    (2, 'travel_segment__model-wan22_vace__guidance-vace_flow__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and optical-flow guide preprocessing before promotion.'),
    (3, 'travel_segment__model-wan22_vace__guidance-vace_canny__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and Canny guide preprocessing before promotion.'),
    (4, 'travel_segment__model-wan22_vace__guidance-vace_depth__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and depth guide handling before promotion.'),
    (5, 'travel_segment__model-wan22_vace__guidance-vace_raw__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and raw guide-video passthrough before promotion.'),
    (6, 'travel_segment__model-wan22_vace__guidance-uni3c__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and Uni3C patch before promotion.'),
    (7, 'travel_segment__model-ltx2__guidance-none__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The LTX first/last ready template is not yet wired through the Reigh travel child adapter with first/last image inputs and completion semantics.'),
    (8, 'travel_segment__model-ltx2_distilled__guidance-none__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The LTX first/last ready template is not yet wired through the Reigh travel child adapter with first/last image inputs and completion semantics.'),
    (9, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_video__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for a full-length control guide.'),
    (10, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_pose__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for pose-preprocessed full-length guides.'),
    (11, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_depth__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for depth-preprocessed full-length guides.'),
    (12, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_canny__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for Canny-preprocessed full-length guides.'),
    (13, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_cameraman__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for cameraman full-length guides.')
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
  'wgp',
  route_key,
  true,
  true,
  9,
  jsonb_build_object(
    'seeded_by', '20260506115000_seed_section3a_mode_aware_route_metadata',
    'source', 'section3a_matrix',
    'row_id', row_id,
    'disposition', disposition,
    'expected_backend', expected_backend,
    'support_state', support_state,
    'blocking_reason', blocking_reason
  )
FROM section3a_routes
ON CONFLICT (backend, route_key) DO UPDATE SET
  supports_route = EXCLUDED.supports_route,
  supports_missing_selector = EXCLUDED.supports_missing_selector,
  capability_version = EXCLUDED.capability_version,
  metadata = public.route_backend_capabilities.metadata || EXCLUDED.metadata,
  updated_at = now();

WITH section3a_routes (
  row_id,
  route_key,
  disposition,
  expected_backend,
  support_state,
  blocking_reason
) AS (
  VALUES
    (1, 'travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template before Wan-family travel rows can be promoted.'),
    (2, 'travel_segment__model-wan22_vace__guidance-vace_flow__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and optical-flow guide preprocessing before promotion.'),
    (3, 'travel_segment__model-wan22_vace__guidance-vace_canny__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and Canny guide preprocessing before promotion.'),
    (4, 'travel_segment__model-wan22_vace__guidance-vace_depth__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and depth guide handling before promotion.'),
    (5, 'travel_segment__model-wan22_vace__guidance-vace_raw__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and raw guide-video passthrough before promotion.'),
    (6, 'travel_segment__model-wan22_vace__guidance-uni3c__continuity-first_last__profile-default', 'NEW', 'wgp', 'vibecomfy_unsupported', 'Requires the NEW Wan 2.2 VACE cocktail template and Uni3C patch before promotion.'),
    (7, 'travel_segment__model-ltx2__guidance-none__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The LTX first/last ready template is not yet wired through the Reigh travel child adapter with first/last image inputs and completion semantics.'),
    (8, 'travel_segment__model-ltx2_distilled__guidance-none__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The LTX first/last ready template is not yet wired through the Reigh travel child adapter with first/last image inputs and completion semantics.'),
    (9, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_video__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for a full-length control guide.'),
    (10, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_pose__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for pose-preprocessed full-length guides.'),
    (11, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_depth__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for depth-preprocessed full-length guides.'),
    (12, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_canny__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for Canny-preprocessed full-length guides.'),
    (13, 'travel_segment__model-ltx2_distilled__guidance-ltx_control_cameraman__continuity-first_last__profile-default', 'BLOCKED', 'wgp', 'vibecomfy_unsupported', 'The pinned LTX first/last template is not yet proven control-capable for cameraman full-length guides.')
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
  support_state = 'vibecomfy_supported',
  false,
  9,
  jsonb_build_object(
    'seeded_by', '20260506115000_seed_section3a_mode_aware_route_metadata',
    'source', 'section3a_matrix',
    'row_id', row_id,
    'disposition', disposition,
    'expected_backend', expected_backend,
    'support_state', support_state,
    'blocking_reason', blocking_reason
  )
FROM section3a_routes
ON CONFLICT (backend, route_key) DO UPDATE SET
  supports_route = EXCLUDED.supports_route,
  supports_missing_selector = EXCLUDED.supports_missing_selector,
  capability_version = EXCLUDED.capability_version,
  metadata = public.route_backend_capabilities.metadata || EXCLUDED.metadata,
  updated_at = now();

DELETE FROM public.route_backend_selectors
WHERE selector_namespace = 'production'
  AND route_key IN (
    'travel_segment__model-ltx2__guidance-none__continuity-first_last__profile-default',
    'travel_segment__model-ltx2_distilled__guidance-none__continuity-first_last__profile-default'
  );

COMMIT;
