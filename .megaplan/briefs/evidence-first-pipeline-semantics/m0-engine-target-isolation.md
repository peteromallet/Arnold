# M0: Engine Target Isolation

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Make engine/target separation a prevention-first invariant before any evidence or enforcement work depends on it: the driver runs from an isolated worktree or container, the engine is never target-writable, and engine==target overlap is refused before mutating phases.

This retires most contamination detection work by removing the contamination path, and removes the dogfood-shadow trap where a target execute can mutate the driver engine and corrupt later milestones.

**The load-bearing requirement is engine WRITE-isolation, not path-overlap detection.** Observed contamination occurred with engine and target at *distinct, non-overlapping paths*: a relocation worker rewrote the driver engine's own `megaplan/workers/_impl.py` (creating a circular import that crashed `megaplan status` and stalled the chain), because the worker's working directory / package-resolution pointed at the engine even though its assigned project was the target. An overlap-refusal preflight alone does NOT catch this. The engine must be made physically un-writable by workers during the run (read-only mount / immutable checkout / worker filesystem sandboxed to the target), and the worker cwd / package-resolution must not default to the engine. Overlap refusal is a complementary cheap guard, not the primary control.

## Scope

IN:

- Establish a driver workspace model where the running engine is isolated from the target workspace.
- Refuse engine==target path overlap before execute, review-rework, reset, reconcile, or any other target-mutating phase.
- Record enough isolation evidence for later transition policy and provenance milestones to cite: engine path, target path, and target head/base.
- Ensure all target mutation goes through the target workspace, never through the driver engine.
- Neutralize the worker cwd / package-resolution leak: a worker doing target work must not be able to resolve or write engine paths even when engine and target are distinct directories (set worker cwd to the target, and/or make the engine read-only to worker processes).
- Establish an execution-environment context (ticket `01KTA78BYT`): at chain start, RESOLVE and PERSIST `{project_root, engine_root}` as live path context. By definition, ALL relative paths in specs resolve against `project_root`; subprocess invocations pass ABSOLUTE paths only.
- Land the L1 subprocess-cwd stopgap that this contract generalizes/supersedes (ticket `01KTA78BYT`, from a Codex fix-level review): the Codex execute worker spawns `run_command(... cwd=Path.cwd())` at `megaplan/workers/_impl.py:2354`, and in chain/auto `Path.cwd()` is the ENGINE, so relative edits hit the driver engine. Fix = `cwd = resolve_work_dir(state)` (the target), matching Shannon which already uses `cwd=ctx.work_dir` (`megaplan/workers/shannon.py:1038`). The in-process sandbox (`megaplan/runtime/sandbox.py`) guards only in-process tool handlers, NOT the Codex/Shannon SUBPROCESS — the subprocess cwd is the real hole.
- Make path/brief resolution failures report with fidelity (ticket `01KTA79SHN`): a path or brief resolution failure must report the RESOLVED ABSOLUTE path and the owning root (e.g. "idea file not found: <abs path>"), never a misleading `BRIEF_MISSING`. `markdown_body` (`megaplan/artifacts.py:61`) must propagate `OSError` instead of swallowing it; the `except OSError` in `megaplan/handlers/init.py:299-320` is dead code because the inner parse catches `OSError` and returns `None`.

OUT:

- Do not build broad contamination-detection gates as the primary control.
- Do not solve unrelated sandbox hardening or process isolation beyond engine/target write separation.
- Do not change evidence schemas beyond minimal isolation records needed by later milestones.
- Do not make local development impossible; require a separated target workspace or a verified isolation provider for mutating phases.

## Locked Decisions

- Prevention comes before detection: the engine must not be target-writable during mutating phases.
- Engine==target overlap is refused before mutation, not diagnosed after failure.
- Write-isolation is the primary control; overlap refusal is a secondary guard. Contamination has been observed with non-overlapping paths via a worker cwd/resolution leak, so the engine must be physically un-writable by workers — refusing overlap alone is insufficient.
- The driver engine is the authority running the pipeline; target changes are work product, not engine updates.
- An execution-environment context `{project_root, engine_root}` is resolved and persisted at chain start; relative spec paths resolve against `project_root` by definition; subprocesses receive absolute paths only (ticket `01KTA78BYT`).
- Resolution-failure errors are high-fidelity: they name the resolved absolute path and owning root, never `BRIEF_MISSING` for a file that does not exist (ticket `01KTA79SHN`).

## Open Questions

- Whether the default isolation mechanism is an in-repo worktree separation or a container.
- Whether the default isolation mechanism is sufficient for same-checkout local development, or whether same-checkout mutating runs should remain refused.

## Constraints

- Preserve existing local iteration ergonomics where separated workspaces or verified isolation can make them safe.
- Keep setup cheap enough to run before every mutating phase.
- Avoid touching target files during preflight checks.
- Produce operator-visible refusal details with paths, phase, and concrete isolation instructions.

## Done Criteria

1. Driver startup or phase preflight identifies the engine workspace and target workspace.
2. Mutating phases refuse to run when writable target roots overlap the engine root.
3. A worker doing target work CANNOT write into the driver engine even when engine and target are distinct paths — engine writes by worker processes physically fail or are redirected to the target (not merely diagnosed). Regression: reproduce the observed failure (a relocation worker rewriting the engine's `megaplan/workers/_impl.py` → circular import → `status` crash) and assert it can no longer occur.
4. Isolation records can be referenced by later provenance and transition decisions.
5. Tests cover separated worktree, container or equivalent isolation, overlap refusal, and the dogfood-shadow contamination scenario.
6. A relative spec path (e.g. the idea/brief path) resolves against `project_root`, not the engine root (ticket `01KTA78BYT`).
7. A subprocess execute/Shannon worker CANNOT write the engine: its cwd is the resolved target work dir, not `Path.cwd()`/the engine (ticket `01KTA78BYT`).
8. A missing brief/idea file reports its resolved absolute path and owning root, never `BRIEF_MISSING`; `markdown_body` propagates `OSError` rather than returning `""` (ticket `01KTA79SHN`).

## Touchpoints

- engine/run bootstrap and driver workspace setup
- mutating phase preflights
- `megaplan/_core/workflow.py`
- `megaplan/handlers/execute.py`
- `megaplan/handlers/review.py`
- reset/reconcile entrypoints
- isolation and dogfood-shadow regression tests
- `megaplan/chain/__init__.py` (~L1830, execution-environment context resolve/persist) — ticket `01KTA78BYT`
- `megaplan/workers/_impl.py:2354` (`run_command(... cwd=Path.cwd())` → `cwd = resolve_work_dir(state)`) — ticket `01KTA78BYT`
- `megaplan/workers/shannon.py:1038` (`cwd=ctx.work_dir`, the correct precedent) — ticket `01KTA78BYT`
- `megaplan/runtime/sandbox.py` (in-process guard only; does NOT cover the subprocess cwd hole) — ticket `01KTA78BYT`
- `megaplan/artifacts.py:61` (`markdown_body` must propagate `OSError`) — ticket `01KTA79SHN`
- `megaplan/handlers/init.py:299-320` (dead `except OSError`; report resolved absolute path) — ticket `01KTA79SHN`

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the prevention boundary for the contamination class and must be settled before later evidence gates can rely on the driver engine being trustworthy.
