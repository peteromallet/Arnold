# Sprint 0 — Spike: validate Store Protocol + transaction journal

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 0 — Spike", lines ~680-693). Read the full design doc before starting; all architectural decisions are there.

**Purpose:** validate the refined `Store` Protocol and transaction journal against real call sites before committing to Sprint 1's full implementation. This is a throwaway-branch derisking exercise. **No production code lands.**

## Scope

- Implement `Store` Protocol stubs in a throwaway branch (do NOT merge to main).
- Implement transaction journal `prepare`/`commit`/`recover` in a minimal `FileStore`.
- Wire 5 representative editorial.py call sites to call the new Store: `create_epic`, `update_body`, `set_sprint_queue`, `add_checklist_items`, `record_epic_event` — all inside one transaction.
- Inject a crash mid-transaction (kill the process between prepare and commit); verify recover-on-open restores consistent state.
- Round-trip a real `auto.py` plan through `PlanRepository` (file mode); confirm tight-loop reads in `auto.py:197, 223, 685` still work.
- Write a 1-page report at `docs/sprint-0-spike-report.md` listing Protocol issues found and changes to fold into Sprint 1.

## Reference repos

- Megaplan (this repo): you're working in it.
- Arnold source for editorial reference: clone from https://github.com/peteromallet/arnold to `./arnold-source/` (read-only — do not modify).

## Acceptance

- `docs/sprint-0-spike-report.md` exists with the report.
- No changes to production code paths (the throwaway branch is discarded; only the report lands on main).
- Crash-mid-transaction test demonstrates recovery.

## Out of scope

- Implementing the full Store/FileStore/DBStore — that's Sprint 1+.
- Touching production `auto.py`, `workers.py`, or any non-spike file outside the throwaway branch.
- Editorial logic transplant — that's Sprint 4+.

## Robustness

`light` — this is a spike with a narrow, well-defined output (one report).
