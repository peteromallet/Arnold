# M4: Move Megaplan Stages And Handler Placement Into The Plugin

## Outcome

Move Megaplan-specific stage implementations and handler placement into `arnold/pipelines/megaplan/` so generic Arnold runtime no longer owns planning stages.

## Scope

In:
- Move planning-specific stage implementations into plugin-local `stages/`.
- Move the explicit stage source set from the plan:
  - `megaplan/_pipeline/stages/prep.py` -> `arnold/pipelines/megaplan/stages/prep.py`
  - `megaplan/_pipeline/stages/plan.py` -> `arnold/pipelines/megaplan/stages/plan.py`
  - `megaplan/_pipeline/stages/critique.py` -> `arnold/pipelines/megaplan/stages/critique.py`
  - `megaplan/_pipeline/stages/gate.py` -> `arnold/pipelines/megaplan/stages/gate.py`
  - `megaplan/_pipeline/stages/revise.py` -> `arnold/pipelines/megaplan/stages/revise.py`
  - `megaplan/_pipeline/stages/finalize.py` -> `arnold/pipelines/megaplan/stages/finalize.py`
  - `megaplan/_pipeline/stages/execute.py` -> `arnold/pipelines/megaplan/stages/execute.py`
  - `megaplan/_pipeline/stages/review.py` -> `arnold/pipelines/megaplan/stages/review.py`
  - `megaplan/_pipeline/stages/tiebreaker.py` -> `arnold/pipelines/megaplan/stages/tiebreaker.py`
- Move or keep handlers under plugin-local `handlers/` only where adapter separation remains useful.
- Update Megaplan `pipeline.py` to compose local stages.
- Preserve stage behavior for prep, plan, critique, gate, revise, finalize, execute, review, and tiebreaker.
- `feedback` phase behavior is preserved through Megaplan plugin operations, not as a graph stage in this move.

Out:
- Do not move prompts/state/profiles/control here; that is M5a.
- Do not move execute/review/orchestration policy internals here except where a stage wrapper requires it.
- Do not rename the package.

## Locked Decisions

- Megaplan owns stage vocabulary and stage implementations.
- Generic Arnold code must not import Megaplan stage classes.
- No old-path import shims unless explicitly required by M-1 migration paths.

## Required Outputs

- Handler placement decision: collapse handlers into stage modules or keep them in plugin-local `handlers/`, with each temporary bridge named.
- Which stage adapters need temporary bridge imports until M5a/M5b.

## Constraints

- Preserve planning parity, feedback behavior, and tiebreaker behavior.
- Keep generic boundary tests green.
- Before moving stage files, confirm dispatch, discovery, resource resolution, profile loading, and legacy alias routing support `arnold.pipelines.megaplan`.

## Done Criteria

- Megaplan stages live under `arnold/pipelines/megaplan/stages/`.
- Handler placement is plugin-local or documented as a temporary bridge.
- Megaplan plugin imports its own stages locally.
- Generic runtime has no imports from Megaplan stages/handlers.
- Stage parity tests pass.

## Touchpoints

- `megaplan/_pipeline/stages/`
- `megaplan/handlers/`
- `megaplan/pipelines/planning/`
- `arnold/pipelines/megaplan/`

## Anti-Scope

- Do not weaken boundary tests.
- Do not flatten dynamic prompts.
- Do not rename the top-level package or CLI entrypoints; that is M6. This milestone moves stage/handler files into the target plugin home only.
