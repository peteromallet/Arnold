# Strict Ready Exceptions

This inventory is the only place for temporary strict-ready exceptions on
protected repo templates. A protected template is one where `app_active` is
`true` or `coverage_tier` is `required`.

As of May 16, 2026, the strict-ready gate reports 11 protected-template
violations that are tracked as exact temporary exceptions below. All entries
are categorized as `blocked` because they belong to required/app-active
templates and must be removed before those templates can be considered clean
strict-ready examples. The Sprint 8 static-vs-built comparison still has 0
public contract drift offenders after fixing extractor/template gaps.

## Entry Rules

Exceptions must be exact, violation-scoped records in
`strict_ready_exceptions.json`. Matching uses all three fields:

- `ready_id`
- `violation_code`
- `target`

Each entry must include:

- `id`: stable exception id.
- `ready_id`: template id, such as `video/wan_t2v`.
- `violation_code`: strict-ready diagnostic code.
- `target`: exact node, field, output, or descriptor target for the violation.
- `owner`: default `workflow-porting` unless another owner is accountable.
- `ticket`: follow-up ticket id or issue URL.
- `reason`: why the violation cannot be fixed now.
- `allowed_until`: concrete expiry date.
- `removal_condition`: objective condition that removes the exception.
- `final_category`: one of `reference`, `supplemental`, `blocked`, or `scratchpad-only`.

False positives caused by static extraction drift are not valid exceptions.
Fix the extractor, static index, or ready template so static and built
contracts agree before adding any exception.

## Current Inventory

| Exception | Template | Violation | Target | Owner | Ticket | Until | Category |
|---|---|---|---|---|---|---|---|
| `sre-20260516-ltx23-iclora-hdr-hidden-model-5020-widget3` | `video/ltx2_3_lightricks_iclora_hdr` | `hidden_model_filename` | `node:5020.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-hdr-hidden-model-5021-widget2` | `video/ltx2_3_lightricks_iclora_hdr` | `hidden_model_filename` | `node:5021.widget_2` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-hdr-hidden-model-5021-widget3` | `video/ltx2_3_lightricks_iclora_hdr` | `hidden_model_filename` | `node:5021.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-hidden-model-5020-widget3` | `video/ltx2_3_lightricks_iclora_motion_track` | `hidden_model_filename` | `node:5020.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-hidden-model-5021-widget2` | `video/ltx2_3_lightricks_iclora_motion_track` | `hidden_model_filename` | `node:5021.widget_2` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-hidden-model-5021-widget3` | `video/ltx2_3_lightricks_iclora_motion_track` | `hidden_model_filename` | `node:5021.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-widget-5044-widget1` | `video/ltx2_3_lightricks_iclora_motion_track` | `strict_ready_unresolved_widgets` | `node:5044.widget_1` | `workflow-porting` | `01KRKQGP81Z5XR0FAK19T5CAC8` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-hidden-model-4980-widget2` | `video/ltx2_3_lightricks_two_stage` | `hidden_model_filename` | `node:4980.widget_2` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-hidden-model-4980-widget3` | `video/ltx2_3_lightricks_two_stage` | `hidden_model_filename` | `node:4980.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-hidden-model-4981-widget3` | `video/ltx2_3_lightricks_two_stage` | `hidden_model_filename` | `node:4981.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-widget-4988-widget1` | `video/ltx2_3_lightricks_two_stage` | `strict_ready_unresolved_widgets` | `node:4988.widget_1` | `workflow-porting` | `01KRKQGP81Z5XR0FAK19T5CAC8` | 2026-06-30 | `blocked` |

Removal conditions are stored on each JSON entry. In summary:

- `01KRNDP7S3BW6DMNKAWPNVVYMB`: expose the hidden
  `ltx-2.3-22b-dev-fp8.safetensors` Gemma text encoder selections as named
  public inputs or authored model assets.
- `01KRKQGP81Z5XR0FAK19T5CAC8`: rewrite the remaining schema-backed
  `PrimitiveInt` positional widgets with named inputs or add committed widget
  schema alias evidence.

Generated-template style warnings are not strict-ready exceptions and are not
listed here. They remain reported by the strict-ready gate as non-enforced
warnings.
