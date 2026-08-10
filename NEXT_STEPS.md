# Next Steps: Complete Cleanup + Workflow-Manifest-Runtime Epics

This doc is the working resume point for finishing the two ordered epics.
It replaces any stale chain status or compacted conversation context.

## Ordered Epic List

1. **`/Users/peteromalley/Documents/Arnold/.megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml`**
2. **`/Users/peteromalley/Documents/Arnold/.megaplan/briefs/workflow-manifest-runtime/chain.yaml`**

Use the cleanup worktree for all cleanup work:
`/Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root`.
Keep the Arnold editable install pointed at that worktree; fix root editable-install drift when it appears.

---

## Current Resume Point

- Cleanup M0 and M1 are complete.
- Active M2 plan: **`m2-parity-and-delete-outcome-20260626-1253`**.
- Active branch: `cleanup-single-root-m2-parity-delete`.
- Chain status shows M2 `in_progress`, last recorded state `done`, worktree is dirty.
- The execute phase for M2 has already run; the remaining work is verification, fixing active-test failures, and closing M2 so M3 can start.

Do not trust stale chain status blindly. Use the commands below to re-derive state each session.

---

## North Star (preserved)

Plain Python workflow composition, shared invocable step/workflow interfaces, nested workflows, normal Python control flow including loops, AST-derived structure instead of authored graphs, deterministic validator-enforced routing, arbitrary side effects inside recorded steps, stable pack identity/versioning, queryable execution structure, tree-shaped audit traces, and path-addressed resume. Completed step results replay; new agent steps may still make fresh decisions.

---

## Rules

- Finish both epics; do not treat either as exploration or partial cleanup.
- Use Codex subagents for hard investigation, fixes, validation, and blockers; sense-check their conclusions.
- Preserve profile model selections exactly as declared in each plan/chain.
- No permanent shims. Cleanup must make the canonical package authoritative.
- No uncontrolled full-suite fallback; tests must be selected by the plan/finalize contract or fail closed.
- Fix root causes in Arnold, the harness, tests, docs, scripts, chain state, or environment instead of working around them.

---

## M2: Parity and Delete — Remaining Work

### Immediate fixes already identified

1. **Pipeline manifests** — fixed:
   - `arnold_pipelines/evidence_pack/__init__.py`: `supported_modes = ("graph",)`, `driver = ("graph", "verify")`.
   - `arnold_pipelines/megaplan/pipelines/epic_blitz.py`: `supported_modes = ("graph",)`.
2. **Legacy-reference allowlist** — removed stale entries for tests that no longer contain the legacy pattern.
3. **Conformance package-name-staleness allowlist** — add to `arnold/conformance/_allowlist.txt`:
   - `package-name-staleness arnold.agent.tools.terminal_tool`
   - `package-name-staleness arnold.pipeline.registry`
4. **Discovery behavior** — `discover_python_pipelines()` currently raises an aggregate `RuntimeError` for any rejected in-tree module. The integrity tests expect broken in-tree modules to warn and be skipped. Decide whether to relax the aggregate raise or update the tests; do not leave the mismatch.
5. **Test-isolation failures** — several conformance/native tests fail only when run after earlier tests that leave `sys.modules` state. Fix at root (subprocess isolation or explicit module cleanup) rather than re-ordering tests.

### Verification commands

```bash
cd /Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root

# Plan / chain state
uv run python -m arnold_pipelines.megaplan introspect --plan m2-parity-and-delete-outcome-20260626-1253
uv run python -m arnold_pipelines.megaplan chain status --spec .megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml

# Active test run (pyenv Python has pytest; .venv does not)
PYTHONPATH=/Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root \
  /Users/peteromalley/.pyenv/versions/3.11.11/bin/python -m pytest \
  tests/arnold/conformance \
  tests/arnold_pipelines/megaplan \
  tests/arnold/pipeline/native \
  tests/test_pipeline_composability.py \
  tests/test_pipeline_compose.py \
  tests/test_generate_arnold_docs.py \
  tests/test_no_bare_subprocess.py \
  tests/test_pipeline_discovery_integrity.py \
  --tb=short -q --no-header
```

Because M2 changes canonical package, discovery, conformance, and packaging surfaces, the finalize contract requires the full selection (`test_selection: full`) for final acceptance.

### Closing M2

After the active tests are green and the plan’s contracted selectors pass:

1. Run the megaplan review step for the M2 plan if it has not been automatically marked complete.
2. Advance the cleanup chain to M3.

---

## M3: Merge-Result Closeout

- Chain spec: `.megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml`
- Branch: `cleanup-single-root-m3-closeout`
- Vendor/profile: `partnered-5` / Codex
- Goal: run only post-merge conformance on the integrated result and close remaining external cleanup exceptions.

### M3 done criteria

- Post-merge conformance gates pass on the integrated checkout.
- Old TypeScript Arnold snapshot archival/deletion is verified.
- Active operational worktree cleanup triggers are verified.
- No unapproved legacy path usage remains in source/test/doc/skill scans.
- `git status --porcelain` shows no symlink/type churn.

### M3 commands

```bash
cd /Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root

# Start/advance the chain into M3
uv run python -m arnold_pipelines.megaplan chain run --spec .megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml

# Or, if the chain is already on M3 and needs a fresh plan:
uv run python -m arnold_pipelines.megaplan init --spec .megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml --milestone m3-merge-result-closeout
```

Use the same test runner and editable-install discipline as M2.

---

## Workflow-Manifest-Runtime Epic

After M3 is complete and the cleanup result is merged back into `native-python-working-tree`, start the second epic from that integrated base.

- Chain spec: `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- Base branch: `native-python-working-tree` (must contain the completed cleanup result)
- Milestones (in order):
  1. `m1-baseline-manifest-contract`
  2. `m2-explicit-node-dsl-compiler`
  3. `m3-manifest-runner-runtime`
  4. `m4-megaplan-product-migration`
  5. `m5-shipped-pipelines-cli-docs`
  6. `m6-clean-break-purge-conformance`
  7. `m7-merge-result-conformance`

### Workflow-Manifest-Runtime commands

```bash
cd /Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root

# Start the new chain from the cleanup result
uv run python -m arnold_pipelines.megaplan chain run --spec .megaplan/briefs/workflow-manifest-runtime/chain.yaml

# Or initialize the first milestone explicitly
uv run python -m arnold_pipelines.megaplan init --spec .megaplan/briefs/workflow-manifest-runtime/chain.yaml --milestone m1-baseline-manifest-contract
```

Do not reuse the cleanup worktree if its branch state becomes unrelated; create or switch worktrees as needed, but always keep the editable install pointed at the active worktree.

---

## Environment & Tooling Notes

- **Megaplan launcher:** `uv run python -m arnold_pipelines.megaplan` (the old `arnold.pipelines.megaplan` path is gone).
- **Editable install:** `uv pip show arnold` should report `Editable project location: /Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root`. Reinstall with `uv pip install -e /Users/peteromalley/Documents/.megaplan-worktrees/arnold-cleanup-single-root` if it drifts back to the root repo.
- **Codex isolation:** set `MEGAPLAN_ENGINE_ISOLATION_PROVIDER=self_hosted_editable` for Codex steps; `logical_local_dev` is rejected by the writable-root check.
- **Test runner:** use `PYTHONPATH=<worktree> /Users/peteromalley/.pyenv/versions/3.11.11/bin/python -m pytest ...`. The `.venv` only has runtime packages; system pyenv Python has pytest and test deps.
- **Destructive execute steps:** pass `--confirm-destructive` when the executor requires it.

---

## Known Blockers / Watch Items

- The M2 execute audit reported many “unclaimed” files under `arnold/pipelines/megaplan`. Those files are already deleted in the worktree; the audit appears to have run against the root repo state, not the worktree. Trust the worktree `git status` over the execute advisory for deleted legacy paths.
- The M2 plan’s structured selectors still reference archived test paths (e.g. `tests/test_pipeline_runtime_e2e.py`). Use `test_selection: full` and the contracted active selectors for verification; update the plan metadata if needed, but do not run an uncontrolled full suite as a substitute for fixing selectors.
- Chain state was manually reconciled from the root repo into the worktree; always double-check `chain status` before advancing.

---

## Done Definition for This Doc

This doc can be removed or archived when:

1. Cleanup M3 is complete and merged.
2. Workflow-manifest-runtime M1 has been initialized and its first gate passes.
