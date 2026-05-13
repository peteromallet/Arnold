-- Extend public.model_family_for_model with production model variants that
-- the original 20260513120000_derive_route_key.sql seed did not cover.
--
-- Discovered while reviving Hannah's travel_orchestrator task
-- (0168dcc3-2a42-415d-84b5-a28cf6033850) after the Layer 1/2/4 rollout:
-- her model_name 'wan_2_2_i2v_lightning_baseline_2_2_2' (3373 production
-- task uses) was not in the seed and derive_route_key returned NULL,
-- causing the new stampTaskRouteContract Layer-2 path in create-task to
-- reject every child spawn with route_contract_stamp_failed.
--
-- This migration adds the production-traffic variants found by querying
-- distinct model_name values from real tasks. Mapping rules follow the
-- old worker _route_model_family heuristics (now deleted): substring
-- 'vace' -> wan22_vace, otherwise wan22_i2v for wan-family, and
-- 'distilled' -> ltx2_distilled for ltx2.
--
-- Idempotent: ON CONFLICT preserves existing rows. Safe to re-run.

BEGIN;

INSERT INTO public.model_family_for_model (model_name, route_family) VALUES
  -- wan22_i2v family
  ('wan_2_2_i2v_lightning_baseline_2_2_2',                    'wan22_i2v'),
  ('wan_2_2_i2v_lightning_baseline_3_3',                      'wan22_i2v'),
  ('wan_2_2_i2v_480p',                                        'wan22_i2v'),
  ('lightning_baseline_2_2_2',                                'wan22_i2v'),
  ('lightning_baseline_3_3',                                  'wan22_i2v'),
  -- wan22_vace family
  ('vace_14B',                                                'wan22_vace'),
  ('vace_14B_fake_cocktail_2_2',                              'wan22_vace'),
  ('vace_14B_cocktail_2_2',                                   'wan22_vace'),
  ('vace_14B_fakeface',                                       'wan22_vace'),
  ('vace_fun_14B_2_2',                                        'wan22_vace'),
  ('vace_fun_14B_cocktail_2_2',                               'wan22_vace'),
  ('vace_fun_14B_cocktail_lightning',                         'wan22_vace'),
  ('vace_fun_14B_cocktail_lightning_3phase_light_distill',    'wan22_vace'),
  ('wan_2_1_vace',                                            'wan22_vace'),
  -- ltx2_distilled family
  ('ltx2_22B_distilled',                                      'ltx2_distilled')
ON CONFLICT (model_name) DO UPDATE SET route_family = EXCLUDED.route_family;

COMMIT;
