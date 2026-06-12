# Docs Reference Audit 01: Deleted Module Active Docs

Audit active docs for references to deleted files:

- `vibecomfy/commands/port.py`
- `vibecomfy/commands/_analyze_names.py`
- `vibecomfy/router.py`
- `vibecomfy/patches/resize_schema.py`

| File | Active Docs (patched) | Historical/Audit Docs (left) | Cleanup Logs (left) |
|---|---|---|---|
| `vibecomfy/commands/port.py` | — | handoff-m2b.md:153, audit/01-cli-commands.md:6, RESULTS.md:74, architecture-review-codex.md:1 | artifacts/, status.md, package_results/, dead_module_results/, dead_module_briefs/ |
| `vibecomfy/commands/_analyze_names.py` | — | — | status.md, package_results/, dead_module_results/, dead_module_briefs/ |
| `vibecomfy/router.py` | revised_plan.md:15,104-115 ✅ | — | status.md, package_results/, dead_module_results/, dead_module_briefs/ |
| `vibecomfy/patches/resize_schema.py` | revised_plan.md:13,79-86 ✅ | audit/04-layer2-architecture.md:19, RESULTS.md:157 | status.md, package_results/, dead_module_briefs/ |

## Patches Applied

All patches to `docs/plans/revised_plan.md`:

1. **Status table Unit 3**: `**NOT done**` → `**DONE**`; description updated to "deleted — confirmed orphan, zero references"
2. **Status table Unit 5**: `**NOT done**` → `**DONE**`; description updated to reflect `router.py` deleted, package exists, shim in place
3. **Step 4 body**: Marked each sub-step with ✅ and past-tense confirmation
4. **Step 6 body**: Marked each sub-step with ✅ and past-tense confirmation

## Rationale for Leaves

| Doc | Reason |
|---|---|
| `handoff-m2b.md:153` "Current wiring in port.py" | Dated sprint handoff (2026-05-28); describes architecture-at-time. The functions (`_build_conversion_provider`, `_build_authoring_provider`) still live at `vibecomfy/commands/port/_shared.py`, but the section is an architectural evidence snapshot, not a live reference. |
| `audit/01-cli-commands.md:6` "port.py:611 corrupted" | Audit finding about a bug in a now-deleted file. RESULTS.md already tracks the fix as `fixed`. Preserve for audit trail. |
| `RESULTS.md:74` "current port.py is a small registered module" | Reconciliation record of what the codebase looked like at cleanup time. Stale-by-definition as cleanup completes. |
| `architecture-review-codex.md:1` port.py:1500 footnote | Architecture evidence with absolute-path footnotes; the substance is about schema design, not the file reference. |
| `audit/04-layer2-architecture.md:19` resize_schema orphan | Audit finding whose recommendation was executed. Preserve for audit trail. |
| All `docs/structure_cleanup/` and `artifacts/` files | Explicit cleanup/audit logs — not active docs by design. |
