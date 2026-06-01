# M5b: Move Execute, Review, And Orchestration Policy Into The Plugin

## Outcome

Move Megaplan execute, review, and orchestration policy into the Megaplan plugin according to the M-1 disposition manifest, leaving only policy-free service interfaces or runtime mechanics in Arnold.

## Scope

In:
- Move execute policy that depends on task complexity, destructive confirmation, blocked-task recovery, review coupling, evidence checks, and final-plan artifacts into the plugin.
- Move review policy that handles incomplete verdicts, empty evidence, rework, batch-by-batch review, and blocked-status acceptance into the plugin.
- Move orchestration helpers for gate checks, plan audit, tiebreaker support, iteration pressure, completion contracts, critique status, execution evidence, and verifiability into the plugin unless M-1 classified a narrow service interface.
- Keep generic batch runtime and recovery classifier seams from M3d policy-free.

Out:
- Do not rework stage wrappers unless required by the move.
- Do not rename package or CLI.
- Do not generalize Megaplan execution/review semantics into Arnold.

## Locked Decisions

- Megaplan owns execute/review/orchestration meanings.
- Arnold owns only neutral mechanics: envelopes, drivers, timeout supervision, batch runners, aggregation hooks, and service interfaces proven by M-1. It must not encode execute/review/orchestration meanings, defaults, or fallback behavior.
- Every move cites its M-1 disposition row.
- M3d batch/recovery contracts and neutral runtime-settings carriers are upstream contracts and must not regress here.

## Runtime Settings Boundary

Arnold operational settings remain neutral carriers. Megaplan policy settings include destructive confirmation mode, review approval policy, blocked lifecycle, batch transitions, evidence requirements, tier selection, and iteration pressure. Each setting must have an explicit owner, precedence path, effective value or unset/unsupported state, and dry-run source reporting.

## Required Outputs

- Which orchestration modules, if any, become `arnold-service-interface` rather than plugin policy.
- Test relocation map for any existing tests that must move under plugin-local test directories.

## Constraints

- Preserve execute policy details: destructive confirmation, review-mode approval, blocked lifecycle, retry-blocked-tasks, batch transitions, timeout checkpoint recovery, evidence attribution, and tier selection.
- Preserve review policy details: incomplete verdicts, empty evidence, rework staying in review, batch-by-batch review, and blocked-status acceptance.
- Preserve completion-contract and capsule-warrant behavior.

## Done Criteria

- Execute/review/orchestration policy lives under `arnold/pipelines/megaplan/` or is explicitly classified as neutral service interface.
- Generic Arnold runtime imports no Megaplan orchestration policy.
- Execute/review/orchestration tests pass after relocation.
- Boundary gates distinguish policy imports from service-interface imports.

## Touchpoints

- `megaplan/execute/`
- `megaplan/review/`
- `megaplan/orchestration/`
- `megaplan/audits/`
- `arnold/pipelines/megaplan/`
- execute/review/orchestration tests

## Anti-Scope

- Do not rename package.
- Do not delete old paths until M7.
