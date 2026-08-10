---
id: 01KTPVVVVV001TYPEDSTEPIO
title: Typed Step-IO Envelope — make the data crossing generic seams typed
status: open
source: agent
tags:
- megaplan
- architecture
- tech-debt
- successor-epic
- typed-io
codebase_id: null
created_at: '2026-06-10T06:30:00.000000+00:00'
last_edited_at: '2026-06-10T06:30:00.000000+00:00'
epics: []
---

# Typed Step-IO Envelope — Successor Epic

Peer epic to Evidence-First (which gives truth of STATE). This epic gives truth of
**DATA crossing seams**: the control-plane payloads that cross generic Arnold
boundaries are currently untyped megaplan dicts. A second pipeline must construct
megaplan-shaped dicts to drive the control plane.

M7 made the runtime *mechanisms* generic. This epic makes the *data* generic.

## Explicit deferred identifiers from M7

### Supervisor model (`arnold/supervisor/model.py`)

| Identifier | Current type/usage | Problem |
|---|---|---|
| `RunRecord.plan_id` | `str \| None` | Planning identity on generic record |
| `RunRecord.last_phase` | `str \| None` | Megaplan phase name on generic record |
| `RunRecord.tier_escalations_used` | `int` | Robustness-tier counter on generic record |
| `RunRecord.escalation_tier_pin` | `int \| None` | Tier pin on generic record |
| `RunRecord.pr_number` | `int \| None` | Chain PR number on generic record |
| `RunRecord.pr_state` | `str \| None` | Chain PR state on generic record |
| `SupervisorVariantKind.CHAIN` | `= "chain"` | Planning-flavored variant name |

### Supervisor outcomes (`arnold/supervisor/outcomes.py`)

| Identifier | Current type/usage | Problem |
|---|---|---|
| `NormalizedOutcome.plan` | `str \| None` | Planning name on generic outcome |
| `NormalizedOutcome.last_phase` | `str \| None` | Phase name on generic outcome |
| `NormalizedOutcome.tier_escalations_used` | `int` | Tier counter on generic outcome |

### Runtime operations (`arnold/runtime/operations.py`)

| Identifier | Enum member | Problem |
|---|---|---|
| `OperationKind.OVERRIDE_LIST` | `"override_list"` | Override-list — deferred pending Typed Step-IO carriers |
| `OperationKind.OVERRIDE_APPLY` | `"override_apply"` | Override-apply — deferred pending Typed Step-IO carriers |
| `OperationKind.PROFILE_VALIDATE` | `"profile_validate"` | Profile-validate — deferred pending Typed Step-IO carriers |
| `OperationKind.RESUME` | `"resume"` | Resume — deferred pending Typed Step-IO carriers |

### By-convention planning keys (15+)

These keys are carried as untyped dict entries through:
- `OperationRequest.payload`
- `StepContext.state`
- `hook_extensions`

Known keys include (non-exhaustive): `phase`, `plan_dir`, `tier_spec`,
`success_criteria`, `robustness`, `profile_name`, `model_routing`, `depth`,
`reviewer_count`, `prep_model`, `critic_model`, `escalation_ladder`, `loop_cap`,
`feedback_enabled`, `tiebreaker_enabled`, `auto_start`, `resume_cursor`,
`blocked_tasks`, `user_approved`.

### Oracle trace note

Step 9 oracle traces (`tests/oracle/fixtures/manifest.json`) were recorded with
un-renamed planning-flavored names. They may need re-recording when the Typed
Step-IO Envelope epic lands and field names change.

## Scope

- Design typed carrier types (`StepIOEnvelope`, `OperationEnvelope`,
  `StatePayload`, …) that replace `Mapping[str, Any]` dicts at the generic seam.
- Migrate Megaplan's 15+ by-convention keys to typed fields on Megaplan-owned
  payload types that implement the generic carrier protocol.
- Restructure `RunRecord` and `NormalizedOutcome` to carry plugin-owned metadata
  through typed slots rather than planning-flavored concrete fields.
- Rename `SupervisorVariantKind.CHAIN` to a neutral name or move to plugin vocab.
- Resolve the four deferred `OperationKind` members — either keep as neutral
  operation kinds with typed request/result carriers, or move to plugin vocabulary.
- Ensure a second (non-Megaplan) pipeline can drive the control plane without
  constructing megaplan-shaped dicts.
- Re-record oracle traces if field renames change trace output.

## Out of scope

- Not a plugin VM, package manager, remote registry, or signing chain.
- Not a full schema-coercion framework.
- Not a rewrite of Megaplan's internal state machine or auto driver.

## Suggested touchpoints

- `arnold/supervisor/model.py` — `RunRecord` restructuring
- `arnold/supervisor/outcomes.py` — `NormalizedOutcome` restructuring
- `arnold/runtime/operations.py` — `OperationKind` member resolution
- `arnold/runtime/envelope.py` — typed carrier introduction
- `arnold/pipeline/types.py` — `StepContext` typed state
- `arnold/pipelines/megaplan/state.py` — Megaplan-owned payload types
- `arnold/pipelines/megaplan/control.py` — typed control payloads
- `tests/oracle/fixtures/manifest.json` — oracle trace re-recording
- `tests/arnold/runtime/` — typed carrier tests
