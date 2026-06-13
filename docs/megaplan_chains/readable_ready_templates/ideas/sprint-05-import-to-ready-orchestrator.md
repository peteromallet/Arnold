# Sprint 5: Import-To-Ready Orchestrator

Implement Sprint 5 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Provide a default staged process for taking a raw workflow to a ready candidate.

## Scope

- Add a VibeComfy-owned staged command such as:
  `python -m vibecomfy.cli port ready <workflow> --ready-id <kind>/<name>`.
- The command should run preflight, schema enrichment, mechanical conversion,
  compile parity, contract draft, readability doctor, manual review packet,
  final gates, and atomic promotion.
- Produce manual review packets for ambiguous widgets, output names, public
  knobs, subgraphs, models, and runtime requirements.
- Implement mode-specific opaque subgraph policy: scratchpad warning,
  strict-ready/app-active error.
- Do not allow strict-ready by wrapping an opaque UUID runtime node in a nicer
  Python name. Promotion means real workflow-builder code, a known first-class
  replacement node, and declared inputs/outputs/requirements.
- Add clear status output and JSON artifacts for agents.
- Do not require RunPod or live runtime by default.
- Add diagnostic stability tests for code names, severity levels, JSON fields,
  text/JSON consistency, and severity transitions before promoting warnings.

## Success Criteria

- Clean workflows can become ready-template candidates through one command.
- Ambiguous workflows produce actionable review packets instead of bad templates.
- The command does not overwrite manual files or skip gates.
- Diagnostic codes are stable enough for agents and CI to consume.
