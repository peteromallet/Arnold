# Resolution contract — source-discriminated scoping

## Purpose

There are **two resolution pipelines** (disk and memory) that use **different field
names, different persistence, and different empty-list rules**. This document is the
canonical source of truth for the shared `resolution_applies_to_task` function,
including source selection, alias fields, and per-caller migration impact. All
downstream unification work (M1 tasks T3–T10) references this contract.

## Source discriminator

The shared `resolution_applies_to_task` uses an explicit `source` keyword argument:

| Source value | Pipeline | Persistence | Primary field name |
|---|---|---|---|
| `"disk"` | `resolutions.py` / `cli.py` | `user_action_resolutions.json` (JSON file on disk) | `applies_to_task_ids` |
| `"memory"` | `user_actions.py` / `blocker_recovery.py` | `state.meta.user_action_resolutions` (in-memory event list) | `applies_to_tasks` |

The discriminator is **required** — there is no default. Every caller must declare
which pipeline it represents. This prevents cross-pipeline ambiguity and makes the
contract grep-able.

**Design rationale (SD1):** Shape heuristics (e.g., detecting the presence of
`applies_to_task_ids` vs `applies_to_tasks`) are fragile across two data sources with
different persistence and field names. An explicit discriminator is simpler to audit
and avoids silent misrouting.

## Field-name aliasing

The shared function reads **both** field names regardless of source:

- `applies_to_task_ids` (primary for `"disk"`)
- `applies_to_tasks` (primary for `"memory"`)

If a single resolution dict contains both fields (should not happen in practice),
`applies_to_task_ids` wins for `source="disk"` and `applies_to_tasks` wins for
`source="memory"`. The function does not merge or cross-reference the two fields.

**Alias table:**

| source | Primary field | Alias (fallback) | State field |
|---|---|---|---|
| `"disk"` | `applies_to_task_ids` | `applies_to_tasks` | `state` |
| `"memory"` | `applies_to_tasks` | `applies_to_task_ids` | `resolution` |

## Semantic contract

### `source="disk"` (disk pipeline — `resolutions.py`)

| Condition | Result | Rationale |
|---|---|---|
| Resolution is not a dict | `False` | Defensive — non-dicts don't carry scope |
| `applies_to_task_ids` key **missing** | `True` (applies to all tasks) | Backward-compat with resolutions created before the field existed |
| `applies_to_task_ids` is not a list | `False` | Malformed scope → no task match |
| `applies_to_task_ids` is an empty list `[]` | `True` (applies to all tasks) | Disk pipeline: the CLI `upsert` function defaults to `[]` meaning "all tasks"; this is the **documented behavior** in `upsert_user_action_resolution` (line 131) |
| `applies_to_task_ids` is a non-empty list | `True` if `task_id` is in the list | Standard scoping |
| `task_id` is `None` | `False` | Safety — no disk caller passes `None` |

### `source="memory"` (memory pipeline — `user_actions.py`)

| Condition | Result | Rationale |
|---|---|---|
| Resolution event is not a dict or is `None` | `False` | Defensive guard |
| `applies_to_tasks` key **missing** (i.e., `None`) | `True` (applies to all tasks) | An operator who resolved without listing tasks resolved for everyone |
| `applies_to_tasks` is not a list | `False` | Malformed scope → no match |
| `applies_to_tasks` is an **explicit** empty list `[]` | `False` for any concrete `task_id` | The operator explicitly resolved for no tasks — this is a meaningful signal distinct from "didn't specify" |
| `applies_to_tasks` is a non-empty list | `True` if `task_id` is in the list (after safe filtering) | Standard scoping |
| `task_id` is `None` | `True` | Aggregate/overview check — caller (`action_resolution_status`) uses this to see if any resolution exists |
| Empty strings in task list | Filtered out by set comprehension | Defensive; validated events shouldn't have them, but `state.meta` can accumulate raw events |

### Why preserve different empty-list rules?

The two pipelines serve different UX flows:

1. **Disk (`user_action_resolutions.json`):** The CLI's `upsert_user_action_resolution`
   function (line 131) explicitly documents that an empty or `None`
   `applies_to_task_ids` means "applies to *all* tasks." The default value when the
   field is not explicitly provided is `[]`. This is a **persistence-layer default**
   that the operator may never have seen. Treating `[]` as "all" preserves
   compatibility with all existing resolution files.

2. **Memory (`state.meta` events):** `build_resolution_event` (line 179) only sets
   `applies_to_tasks` when the `tasks` parameter is explicitly provided. If the
   operator doesn't pass `tasks`, the key is entirely absent. An **explicit empty
   list** `[]` is semantically meaningful: the operator consciously resolved for no
   concrete tasks. This supports workflows where a resolution is recorded as a
   formality even though no tasks are currently blocked.

Collapsing these into a single rule would silently change behavior for at least one
pipeline, potentially misrouting blocked work. The explicit source discriminator
preserves both contracts.

## Safe set-comprehension filtering (SD3)

The shared function applies uniform safe filtering for task ID membership checks:

```python
task_id in {item for item in task_list if isinstance(item, str) and item}
```

This is applied for **both** source modes. Rationale:

- **Disk callers** do not produce empty-string task IDs in practice due to upstream
  validation, so this is a pure safety improvement with zero behavioral impact.
- **Memory callers** already used this filtering; preserving it ensures no
  regression.
- Uniform filtering simplifies the implementation and eliminates a vector for
  future divergence.

## Per-caller migration-impact table

### Disk pipeline callers

| Caller | File | Line(s) | Current import | Migration impact |
|---|---|---|---|---|
| `_compute_user_action_blockers` | `cli.py` | 245, 310 | `from megaplan.resolutions import resolution_applies_to_task` | Thin wrapper in `resolutions.py` preserves import; add `source="disk"` |
| `_format_user_action_blocks` | `prompts/execute.py` | 24, 296 | `from megaplan.resolutions import resolution_applies_to_task` | Thin wrapper preserves import; add `source="disk"` |
| `TestResolutionHelpers` | `tests/test_resolutions.py` | 31, 237–281 | `from megaplan.resolutions import resolution_applies_to_task` | Thin wrapper preserves import; tests characterize disk semantics |

### Memory pipeline callers

| Caller | File | Line(s) | Current import | Migration impact |
|---|---|---|---|---|
| `evaluate_prerequisite_blockers` | `blocker_recovery.py` | 24, 431 | `from megaplan.user_actions import resolution_applies_to_task` | Thin wrapper preserves import; add `source="memory"` |
| `action_resolution_status` | `user_actions.py` | 103 | Internal call (same module) | Internal delegation; add `source="memory"` |
| Characterization tests | `tests/test_blocker_recovery.py` | 73–129 | `from megaplan.user_actions import resolution_applies_to_task` | Thin wrapper preserves import; tests characterize memory semantics |

### Quality pipeline

| Caller | File | Current import | Migration impact |
|---|---|---|---|
| Quality classifier helpers | `quality_resolutions.py` | N/A (own module) | **Not affected** — quality resolutions use `classify_quality_resolution_behavior`, not `resolution_applies_to_task`. Quality is a separate domain with different state constants (4 states vs 5) and validates `blocker_id` not `action_id`. |
| `evaluate_quality_blockers` | `blocker_recovery.py` | `from megaplan.quality_resolutions import classify_quality_resolution_behavior` | Quality pipeline is **unchanged** — it does not call `resolution_applies_to_task` |

## State-membership sets vs. behavior output constants — distinct classification layers

> ⚠️ **Do not merge these.** They serve different purposes and collapsing them would
> conflate state classification with execution behavior.

### State-membership sets (`resolutions.py` lines 29–33)

These classify **which resolution states** belong to a broader category. They are
used for **validation and gating** (e.g., "is this state in the set of fallback
states?").

| Constant | Module | Value | Purpose |
|---|---|---|---|
| `FALLBACK_STATES` | `resolutions.py` | `frozenset({"accepted_blocked", "waived"})` | States that allow the executor to proceed with fallback |
| `HARD_BLOCK_STATES` | `resolutions.py` | `frozenset({"manual_required", "rejected"})` | States that require a hard stop (plus implicit "missing") |
| `SUPPORTED_USER_ACTION_RESOLUTION_STATES` | `resolutions.py` | `frozenset({"satisfied", "accepted_blocked", "waived", "manual_required", "rejected"})` | Complete set of valid user-action resolution states |

### Behavior output constants (`user_actions.py` lines 18–21, `quality_resolutions.py` lines 23–26)

These are **output values** returned by classifier functions. They tell the executor
what to *do*, not what something *is*.

**User-action domain:**

| Constant | Module | Value | Produced by |
|---|---|---|---|
| `OMIT` | `user_actions.py` | `"omit"` | `classify_resolution_behavior("satisfied")` |
| `FALLBACK` | `user_actions.py` | `"fallback"` | `classify_resolution_behavior("accepted_blocked" \| "waived")` |
| `HARD_BLOCK` | `user_actions.py` | `"hard_block"` | `classify_resolution_behavior("manual_required" \| "rejected" \| None \| unknown)` |
| `UNRESOLVED` | `user_actions.py` | `"unresolved"` | `action_resolution_status` when no event exists |

**Quality domain:**

| Constant | Module | Value | Produced by |
|---|---|---|---|
| `ADVANCE_WITH_DEBT` | `quality_resolutions.py` | `"advance_with_debt"` | `classify_quality_resolution_behavior("accepted_with_debt")` |
| `RERUN_REQUIRED` | `quality_resolutions.py` | `"rerun_required"` | `classify_quality_resolution_behavior("fixed")` with active deviation |
| `RESOLVED` | `quality_resolutions.py` | `"resolved"` | `classify_quality_resolution_behavior("fixed")` with inactive deviation |
| `HARD_BLOCK` | `quality_resolutions.py` | `"hard_block"` | `classify_quality_resolution_behavior(MANUAL_REQUIRED \| REJECTED \| None \| unknown)` |

### Why they must stay separate

- `FALLBACK_STATES` is a **membership test** ("is the state `accepted_blocked` or
  `waived`?"). `FALLBACK` is a **behavior instruction** ("proceed with fallback").
- `HARD_BLOCK_STATES` is a **membership test** ("is the state `manual_required` or
  `rejected`?"). `HARD_BLOCK` is a **behavior instruction** ("stop — do not
  proceed").
- Quality resolution states (`accepted_with_debt`, `fixed`, `manual_required`,
  `rejected`) are a **different domain** from user-action resolution states
  (`satisfied`, `accepted_blocked`, `waived`, `manual_required`, `rejected`). They
  share only `manual_required` and `rejected` by name, but their semantics and
  required metadata differ.
- The `HARD_BLOCK` string literal appears in **three** places with **three**
  different scopes: `user_actions.HARD_BLOCK` (user-action behavior output),
  `quality_resolutions.HARD_BLOCK` (quality behavior output), and
  `resolutions.HARD_BLOCK_STATES` (state-membership set). They are deliberately
  distinct and must not be aliased across domains.

## Classifier output mapping (behavior-preserved)

The M1 unification must preserve all classifier outputs exactly. These are
load-bearing for `blocker_recovery.py` orchestration.

### `classify_resolution_behavior` (user-action domain)

| Input state | Output | Notes |
|---|---|---|
| `"satisfied"` | `"omit"` | Resolved — no blocker |
| `"accepted_blocked"` | `"fallback"` | Proceed with fallback |
| `"waived"` | `"fallback"` | Proceed with fallback |
| `"manual_required"` | `"hard_block"` | Needs human |
| `"rejected"` | `"hard_block"` | Cannot proceed |
| `None` / unknown / empty | `"hard_block"` | Unresolved = block |

### `resolution_recommended_action` (disk domain)

| Input state | Output | Notes |
|---|---|---|
| `"accepted_blocked"` or `"waived"` | `"continue_with_fallback"` | Proceed with fallback instructions |
| `"satisfied"` | `"retry_execute"` | Prerequisite met — rerun |
| `"rejected"` | `"cannot_continue"` | Terminal block |
| `"manual_required"` | `"awaiting_human"` | Needs operator |
| None / unknown / missing state | `"awaiting_human"` | Unresolved = awaiting |

### `classify_quality_resolution_behavior` (quality domain)

| Input state | Deviation active? | Output | Notes |
|---|---|---|---|
| `"accepted_with_debt"` | — | `"advance_with_debt"` | Proceed (debt recorded) |
| `"fixed"` | Yes | `"rerun_required"` | Rerun to verify fix |
| `"fixed"` | No | `"resolved"` | Fix confirmed |
| `"manual_required"` | — | `"hard_block"` | Needs human |
| `"rejected"` | — | `"hard_block"` | Cannot proceed |
| None / unknown / empty | — | `"hard_block"` | Unresolved = block |

## Backward compatibility

Old modules (`resolutions.py`, `user_actions.py`) retain thin wrapper functions that
delegate to the shared `resolution_contract.py` implementation with hardcoded
`source` values. This preserves backward compatibility for all existing imports
without requiring call-site churn. The grep verification (T10) should confirm
implementation centralization rather than reject wrappers.

```python
# In resolutions.py (thin wrapper):
def resolution_applies_to_task(resolution, task_id):
    return _shared_resolution_applies_to_task(resolution, task_id, source="disk")

# In user_actions.py (thin wrapper):
def resolution_applies_to_task(resolution_event, task_id):
    return _shared_resolution_applies_to_task(resolution_event, task_id, source="memory")
```

## Quality domain boundaries

Quality resolutions are a **separate domain** and must not be forcibly unified with
user-action resolutions:

| Aspect | User-action | Quality |
|---|---|---|
| State constants (count) | 5 (`satisfied`, `accepted_blocked`, `waived`, `manual_required`, `rejected`) | 4 (`accepted_with_debt`, `fixed`, `manual_required`, `rejected`) |
| ID field | `action_id` | `blocker_id` |
| Required metadata | `reason`, `fallback_mode`, `instructions`, `applies_to_task_ids` | `phase`, `evidence`, `debt_note` (required for `accepted_with_debt`) |
| Scoping function | `resolution_applies_to_task` | **None** — quality blockers are per-blocker, not per-task |
| Persistence | `state.meta.user_action_resolutions` | `state.meta.quality_gate_resolutions` |
| Validation strictness | Moderate (empty-string action_id rejected) | Strict (`accepted_with_debt` requires phase + evidence + debt_note) |

The shared `_event_sort_key` helper (byte-identical in both modules) can be unified
without crossing domain boundaries. The `validate_*` and `build_*` event functions
remain domain-specific because they validate different required fields.

## Shared helper unification scope

Functions eligible for unification (structurally identical across domains):

| Function | In `user_actions.py` | In `quality_resolutions.py` | Unification plan |
|---|---|---|---|
| `_event_sort_key` | Line 24 | Line 29 | Move to shared module; single definition |
| Latest-event aggregator pattern | `effective_resolutions` (line 40) | `latest_quality_resolutions` (line 138) | Shared base with domain-specific key field (`action_id` vs `blocker_id`) and validation rules |

Functions that stay domain-specific:

| Function | Reason |
|---|---|
| `validate_*_resolution_event` | Different required fields (`action_id` vs `blocker_id`; `accepted_with_debt` context requirements) |
| `build_*_resolution_event` | Different required parameters |
| `classify_*_behavior` | Different state sets and output vocabularies |

## References

- Brief: `.megaplan/briefs/hardening-epic/m1-resolution-unification.md`
- Disk module: `megaplan/resolutions.py`
- Memory module: `megaplan/user_actions.py`
- Quality module: `megaplan/quality_resolutions.py`
- Main consumer: `megaplan/blocker_recovery.py`
- Characterization tests: `tests/test_resolutions.py`, `tests/test_blocker_recovery.py`, `tests/test_quality_resolutions.py`
