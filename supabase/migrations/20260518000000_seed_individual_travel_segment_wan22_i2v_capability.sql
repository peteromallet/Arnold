-- Seed route_backend_capabilities for individual_travel_segment + wan22_i2v.
--
-- Background: prior seed migrations (20260507160011, 20260508003000) enumerated
-- routes under both the `travel_segment__` (hidden child) and
-- `individual_travel_segment__` (user-facing "Regenerate Segment") prefixes,
-- but only for the wan22_vace family. The wan22_i2v family was seeded under
-- `travel_segment__` only, so the equivalent "Regenerate Segment" action on
-- a wan22_i2v segment derives a route_key with no capability row.
--
-- After 20260513120200_tasks_claimable_trigger.sql went live, tasks_assert_claimable
-- rejects such inserts with:
--   route_contract validation failed: no backend eligible for
--   route_key=individual_travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default
--   (reasons: wgp: missing_capability; vibecomfy: missing_capability)
--
-- This migration mirrors the existing travel_segment__model-wan22_i2v… row by
-- seeding both wgp and vibecomfy. Idempotent via ON CONFLICT DO NOTHING so
-- environments that already have it converge.

BEGIN;

INSERT INTO public.route_backend_capabilities
  (route_key, backend, supports_route, supports_missing_selector, enabled)
VALUES
  ('individual_travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default', 'wgp',       TRUE, FALSE, TRUE),
  ('individual_travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default', 'vibecomfy', TRUE, FALSE, TRUE)
ON CONFLICT (route_key, backend) DO NOTHING;

DO $$
DECLARE
  v_caps integer;
BEGIN
  SELECT count(*) INTO v_caps
  FROM public.route_backend_capabilities
  WHERE route_key = 'individual_travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default'
    AND backend IN ('wgp', 'vibecomfy')
    AND enabled = TRUE
    AND supports_route = TRUE;
  IF v_caps <> 2 THEN
    RAISE EXCEPTION
      'seed_individual_travel_segment_wan22_i2v_capability: expected 2 enabled capability rows, found %',
      v_caps;
  END IF;
END $$;

COMMIT;
