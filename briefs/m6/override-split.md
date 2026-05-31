# M6 Override Namespace Split

## Audit Source

Audited `megaplan/handlers/override.py` on 2026-05-31. The canonical source is the
actual `_OVERRIDE_ACTIONS` dispatch table plus the routed mirror
`_ROUTED_OVERRIDE_ACTIONS`. The provisional names `set-feedback`, `set-prep`, and
`mark-resolved` do not exist in the current source and are therefore not part of
the M6 CLI contract.

## Canonical Action Set

| Action | Handler | Scope | Arnold path | Semantics |
| --- | --- | --- | --- | --- |
| `abort` | `_override_abort` | umbrella | `arnold override abort ...` | Set `current_state` to `aborted`, append override metadata with `reason`, save state, best-effort emit `override_applied`, return terminal abort response. |
| `add-note` | `_override_add_note` | umbrella | `arnold override add-note ...` | Append a note and matching override metadata with `source`, merge-save metadata, best-effort emit `override_applied` and `note_added`, return the current state and next inferred step. |
| `set-robustness` | `_override_set_robustness` | umbrella | `arnold override set-robustness ...` | Validate robustness, reject terminal plans, update `state["config"]["robustness"]`, append from/to override metadata, save, emit, return current state and inferred next step. |
| `set-profile` | `_override_set_profile` | umbrella | `arnold override set-profile ...` | Validate profile, reject terminal plans, resolve profile models, update `profile` and `phase_model`, append from/to override metadata, save, emit, return current state and inferred next step. |
| `set-model` | `_override_set_model` | umbrella | `arnold override set-model ...` | Validate phase/model/effort against premium routing, update or append the phase model pin, append previous/new spec override metadata, save, return current state and inferred next step. |
| `set-vendor` | `_override_set_vendor` | umbrella | `arnold override set-vendor ...` | Validate phase/vendor, swap the current premium spec through the profile swapper and parser, update or append the phase model pin, append previous/new spec override metadata, save, return current state and inferred next step. |
| `force-proceed` | `_override_force_proceed` | planning | `arnold planning override force-proceed ...` | Preserve the exact planning handler path: strict-notes blocks unabsorbed user notes and requires `--user-approved` on ESCALATE; executed plans move to done; critiqued or recoverable blocked plans rebuild a forced `PROCEED` gate, record unresolved flags as debt, save state, emit, and return finalize guidance. |
| `replan` | `_override_replan` | planning | `arnold planning override replan ...` | Require gated/finalized/critiqued/failed state, reset to planned, clear last gate, append replan override metadata and optional note, save, emit, return the latest plan file and next workflow step. |
| `recover-blocked` | `_override_recover_blocked` | planning | `arnold planning override recover-blocked ...` | Require blocked state, `--reason`, valid `resume_cursor.phase`, topology recovery predecessor, non-external-error blocker context, `phase_result.json`, and all blockers resolved as non-terminal; restore predecessor state, clear failure/active step, append recovery metadata, save, return blocker details. |
| `resume-clarify` | `_override_resume_clarify` | planning | `arnold planning override resume-clarify ...` | Require `awaiting_human` with prep-sourced clarification, warn if no user note answers exist, move to prepped, append override metadata, save, emit, return plan-ready next step. |

## Split Rule

`arnold override ...` is the umbrella control-plane path. It accepts only
`abort`, `add-note`, and the audited `set-*` actions.

`arnold planning override ...` is the planning-module path. It accepts only the
planning state-machine overrides: `force-proceed`, `replan`, `recover-blocked`,
and `resume-clarify`.

Both paths forward to the existing `megaplan override <action> ...` command.
`megaplan/handlers/override.py` is intentionally unchanged for this split, so
planning semantics, including the strict-notes force-proceed checks, stay
verbatim on the planning path.

## Drift Guard

`tests/cli/test_arnold_parser_snapshot.py` snapshots:

- the discovered top-level Arnold modules,
- the generic and planning-only module verbs,
- the umbrella/planning override action split,
- the inherited `megaplan override` positional choices and option flags, and
- the forwarding/error behavior for both namespaces.

Any added, removed, or moved action must update this document, the Arnold split
constants, and the parser-snapshot expectation in the same change.
