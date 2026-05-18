-- Follow-up to 20260518000000_seed_individual_travel_segment_wan22_i2v_capability.sql.
--
-- The initial seed used supports_missing_selector=FALSE for the wgp row,
-- mirroring the qwen_image_style / animate_character pattern from
-- 20260513120100_cleanup_and_capabilities.sql. That pattern is correct for
-- vibecomfy-promoted routes where an explicit selector row in
-- public.route_backend_selectors picks the backend. The wan22_i2v route is
-- wgp-default with no selector row, so eligibility falls through to the
-- supports_missing_selector path in route_backend_claim_decision:
--
--   WHEN s.id IS NULL THEN n.worker_backend = 'wgp'
--     AND COALESCE(c.supports_missing_selector AND c.enabled AND ..., false)
--
-- With supports_missing_selector=FALSE on the wgp row, that branch returned
-- 'missing_selector_capability_unsupported' and the trigger rejected the
-- task. The parallel travel_segment__model-wan22_i2v__guidance-none__... row
-- already has supports_missing_selector=TRUE for wgp; align the individual_
-- counterpart with the same shape.
--
-- The vibecomfy row stays as-is — the wgp-only CHECK constraint
-- (route_backend_capabilities_missing_selector_wgp_only_check) forbids
-- supports_missing_selector=TRUE for non-wgp backends. vibecomfy will simply
-- not be claimable for this route until a selector row exists, matching the
-- wan22_i2v travel_segment row's current behavior.

BEGIN;

UPDATE public.route_backend_capabilities
SET supports_missing_selector = TRUE,
    updated_at = now()
WHERE route_key = 'individual_travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default'
  AND backend = 'wgp';

DO $$
DECLARE
  v_ok integer;
BEGIN
  SELECT count(*) INTO v_ok
  FROM public.route_backend_capabilities
  WHERE route_key = 'individual_travel_segment__model-wan22_i2v__guidance-none__continuity-first_last__profile-default'
    AND backend = 'wgp'
    AND supports_missing_selector = TRUE
    AND enabled = TRUE;
  IF v_ok <> 1 THEN
    RAISE EXCEPTION
      'fix_individual_travel_segment_wan22_i2v_supports_missing_selector: expected 1 wgp row with supports_missing_selector=true, found %',
      v_ok;
  END IF;
END $$;

COMMIT;
