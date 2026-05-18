-- Conservative gap-fill for individual_travel_segment__ capability rows.
--
-- Follows 20260518000000 (wan22_i2v) and 20260518001000 (supports_missing_selector
-- correction). This migration adds capability rows for cases where the parent
-- travel_segment__ row is "wgp default with vibecomfy promotion via selector"
-- (wgp.supports_missing_selector=TRUE) but no individual_travel_segment__
-- counterpart exists. Without these rows, Regenerate Segment on those segment
-- types hits tasks_assert_claimable with missing_capability.
--
-- Scope (5 routes, 9 rows):
--   ltx2_distilled control_cameraman / control_canny / control_depth / control_pose
--     — each: wgp(supports_missing_selector=TRUE) + vibecomfy(FALSE), mirroring
--     the parent travel_segment__ pattern exactly.
--   wan22_vace uni3c first_last — wgp only (parent has no vibecomfy row),
--     supports_missing_selector=TRUE.
--
-- Routes deliberately NOT seeded here (need follow-up of a different shape):
--   * ltx2/ltx2_distilled "none" guidance and ltx_control_video — parent has
--     wgp.supports_missing_selector=FALSE (wgp cannot run them); these
--     individual_ routes need a route_backend_selectors row pointing to
--     vibecomfy rather than a capability gap-fill. Addressed when next hit.
--   * wan22_vace vace_canny/depth/flow/raw individual_ — already functional
--     via existing vibecomfy selector rows; no capability gap to fix.

BEGIN;

INSERT INTO public.route_backend_capabilities
  (route_key, backend, supports_route, supports_missing_selector, enabled)
VALUES
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_cameraman__continuity-first_last__profile-default', 'wgp',       TRUE, TRUE,  TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_cameraman__continuity-first_last__profile-default', 'vibecomfy', TRUE, FALSE, TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_canny__continuity-first_last__profile-default',     'wgp',       TRUE, TRUE,  TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_canny__continuity-first_last__profile-default',     'vibecomfy', TRUE, FALSE, TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_depth__continuity-first_last__profile-default',     'wgp',       TRUE, TRUE,  TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_depth__continuity-first_last__profile-default',     'vibecomfy', TRUE, FALSE, TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_pose__continuity-first_last__profile-default',      'wgp',       TRUE, TRUE,  TRUE),
  ('individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_pose__continuity-first_last__profile-default',      'vibecomfy', TRUE, FALSE, TRUE),
  ('individual_travel_segment__model-wan22_vace__guidance-uni3c__continuity-first_last__profile-default',                     'wgp',       TRUE, TRUE,  TRUE)
ON CONFLICT (route_key, backend) DO NOTHING;

DO $$
DECLARE
  v_total integer;
  v_wgp_fallback integer;
BEGIN
  SELECT count(*) INTO v_total
  FROM public.route_backend_capabilities
  WHERE route_key IN (
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_cameraman__continuity-first_last__profile-default',
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_canny__continuity-first_last__profile-default',
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_depth__continuity-first_last__profile-default',
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_pose__continuity-first_last__profile-default',
      'individual_travel_segment__model-wan22_vace__guidance-uni3c__continuity-first_last__profile-default'
    )
    AND enabled = TRUE
    AND supports_route = TRUE;

  IF v_total < 9 THEN
    RAISE EXCEPTION
      'seed_individual_travel_segment_remaining_gap_capabilities: expected at least 9 enabled rows across the 5 target routes, found %',
      v_total;
  END IF;

  SELECT count(*) INTO v_wgp_fallback
  FROM public.route_backend_capabilities
  WHERE route_key IN (
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_cameraman__continuity-first_last__profile-default',
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_canny__continuity-first_last__profile-default',
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_depth__continuity-first_last__profile-default',
      'individual_travel_segment__model-ltx2_distilled__guidance-ltx_control_pose__continuity-first_last__profile-default',
      'individual_travel_segment__model-wan22_vace__guidance-uni3c__continuity-first_last__profile-default'
    )
    AND backend = 'wgp'
    AND supports_missing_selector = TRUE
    AND enabled = TRUE;

  IF v_wgp_fallback <> 5 THEN
    RAISE EXCEPTION
      'seed_individual_travel_segment_remaining_gap_capabilities: expected 5 wgp rows with supports_missing_selector=true, found %',
      v_wgp_fallback;
  END IF;
END $$;

COMMIT;
