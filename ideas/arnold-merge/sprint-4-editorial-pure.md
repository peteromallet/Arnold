# Sprint 4 — Editorial transplant: pure logic

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 4 — Editorial transplant: pure logic", lines ~760-773, plus the broader "Editorial Logic Transplant" section earlier in the doc).

**Predecessor:** Sprint 3 has shipped MultiStore + migrate_epic. Sprints 1-3 built the infrastructure — Sprint 4 starts using it for real work.

## Scope

Port Arnold's editorial code per the design doc's Editorial Logic Transplant section. **All operations go through `Store`** — no direct Supabase or filesystem calls.

Includes:
- Gating logic (transition validation, prerequisite checks).
- Body editor (epic body markdown CRUD with validation).
- Lockdown (epic state freeze for review phases).
- Checklist: full CRUD, ordering, completion tracking.
- Sprints: full CRUD + queue normalization (auto-assign positions, enforce uniqueness).
- Hot-context loader (`load_hot_context` joins from Sprint 1's Store) — call sites in `auto.py` use this instead of multi-table reads.
- Run lifecycle contract: plan state machine extension to handle `failed`/`blocked`/`cancelled`, failure record persisted on `Plan`, resume cursor on `Plan`.

## Reference repos

- Arnold source (read-only, for porting reference): https://github.com/peteromallet/arnold — clone to `./arnold-source/`. Look at `agent_kit/tools/editorial.py`, `agent_kit/tools/editorial_reads.py`, `agent_kit/gating.py`, `agent_kit/sprints.py`.

## Acceptance

- An epic can be created, body-edited, transitioned through full lifecycle, with **all gates Arnold currently enforces** still active.
- Plan failure records are queryable; `resume_plan` re-enters at the cursor.
- `pytest tests/editorial_*.py --backend file` green.
- `pytest tests/editorial_*.py --backend db` green.
- Behavior parity with Arnold: a known editorial flow run side-by-side produces equivalent state.

## Out of scope

- Revert (Sprint 5).
- Second opinions runner (Sprint 5).
- Image management (Sprint 5).
- Full-text search (Sprint 5).
- Discord control plane (Sprint 6).

## Robustness

`light` — pure-logic port; mostly mechanical with clear acceptance criteria and Arnold as a behavioral reference.
