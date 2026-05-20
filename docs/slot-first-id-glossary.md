# Slot-First Identity Glossary

Generated: 2026-05-20T09:40:30Z

## Kernel

Slot-first code uses five domain nouns:

| Noun | Meaning | Lifecycle owner |
| --- | --- | --- |
| `project_id` | Project boundary and ownership scope. It remains the high-level domain container and is also used to reach auth ownership through the project row. | Existing project/RLS model |
| `shot_id` | A shot inside a project. Shots group slots and shot-level settings. | Existing shot model |
| `slot_id` | A shot-local position/input/output slot. This is the successor to `shot_generations.id`. | M1 `shot_slots` |
| `attempt_id` | A single generation/render/work attempt. This replaces legacy output identity carried by `generations.id` and most `*_generation_id` fields. | M1 attempt lifecycle |
| `task_id` | A queued or completed worker task. Tasks produce or update attempts. | Existing task queue, rewritten contract |

Optional noun: `clip_id` identifies timeline/editor media when a rendered asset is placed in the video editor. It is optional because some attempts have no editor clip and some slots exist before output media is available.

## No Compatibility Aliases

No compatibility aliases are allowed. Legacy IDs are deleted during M1-M4, not renamed and carried forward. In particular, `generation_id`, `shot_generation_id`, `child_generation_id`, `pair_shot_generation_id`, `parent_generation_id`, `variant_id`, `source_variant_id`, and `primary_variant_id` must not survive as compatibility fields in new service contracts, generated types, RPC arguments, edge payloads, or frontend DTOs.

## Retained Non-Domain Identifiers

`user_id` is retained as an auth/RLS ownership identifier, not as slot-first domain identity. It appears in RLS joins such as `supabase/migrations/20251201000000_create_generation_variants_table.sql`, where generation-variant access is checked through `projects.user_id = auth.uid()`. Future cleanup passes must not rename or drop `user_id` while enforcing the five-noun domain kernel.

`project_id` is both a slot-first kernel noun and the retained ownership boundary for project-scoped records. It survives unchanged, and M1 constraints must ensure `slot_id`, `shot_id`, `attempt_id`, and `task_id` rows remain inside the same `project_id`.

## Legacy Replacement Map

| Legacy name | Replacement | Rule |
| --- | --- | --- |
| `shot_generations` table | `shot_slots` | One row per shot-local placement/input slot. Drop legacy table in M4. |
| `shot_generations.id` | `slot_id` | The UI already treats this as the unique per-entry identity. |
| `shot_generation_id` | `slot_id` | Delete the alias. Use `slot_id` in props, payloads, tests, and generated types. |
| `shotImageEntryId` | `slot_id` | Delete the frontend compatibility alias. |
| `generation_id` on a shot entry | `attempt_id` or `clip_id` | Use `attempt_id` for produced work/output lineage; use `clip_id` only for editor media placement. Do not overload `slot_id`. |
| `generations` table | `attempts` plus optional clips | Attempt lifecycle absorbs generation rows; rendered media belongs to clip/asset records when present. |
| `generation_variants` table | attempts/clips | Variants are not a domain noun. Preserve output alternatives as attempts and media references. |
| `variant_id` | `attempt_id` or `clip_id` | If the caller means work lineage, use `attempt_id`; if it means selected media, use `clip_id`. |
| `primary_variant_id` | current `attempt_id` or current `clip_id` | Model primary output explicitly through the slot/attempt current pointer; no primary-variant alias. |
| `source_variant_id` | source `attempt_id` or source `clip_id` | Match the actual relationship; do not create source-variant compatibility fields. |
| `parent_generation_id` | parent `attempt_id` plus source `slot_id` when placement matters | Parent-child output lineage is attempt-to-attempt. Shot-local context is slot-to-attempt. |
| `child_generation_id` | child `attempt_id` | Child work is an attempt. |
| `pair_shot_generation_id` | originating `slot_id` or explicit transition record tied to slots | Do not recreate pair-shot-generation. Segment settings attach to the slot/transition that owns them. |
| `variant_fetch_generation_id` | fetch `attempt_id` or `clip_id` | Replace with the real fetch target noun. |
| `new_generation_id` | new `attempt_id` | Duplicate/create flows return attempt identity, and placement returns slot identity separately. |
| `existing_generation_id` | existing `attempt_id` or existing `slot_id` | Pick based on whether the caller is reusing output or placing an existing slot. |
| `input_image_generation_ids` | input `slot_id` list or input `attempt_id` list | Worker contracts must type whether they require shot-local inputs or reusable attempt outputs. |
| `start_image_generation_id` / `end_image_generation_id` | start/end `slot_id` for travel placement; attempt ids for source outputs | Segment/travel tasks need typed fields, not generic generation ids. |
| `based_on` generation link | source `attempt_id` | Lineage points at attempts. |
| `duplicate_as_new_generation` | duplicate/create attempt + optional place slot | Split output creation from placement. |
| `create_generation_on_task_complete` | complete task into attempt lifecycle | Task completion creates/updates attempts and may update a slot pointer. |

## Service Boundary Rule

Every cross-service payload must spell out whether it carries `slot_id`, `attempt_id`, `task_id`, or `clip_id`. Payloads must not use generic `id` where more than one kernel noun is possible, and must not use `generationId` camelCase as a compatibility escape hatch.
