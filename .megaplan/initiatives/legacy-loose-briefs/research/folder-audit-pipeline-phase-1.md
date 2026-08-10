# Folder Audit Pipeline — Phase 1: Prove the Core Loop

## Outcome

Create a new Arnold graph-driven pipeline called `folder-audit` that walks a target directory tree level-by-level and uses a subagent at each folder to judge whether its immediate children belong there and at the right level of abstraction. The pipeline emits a structured JSON audit plus an annotated Markdown tree, but does not mutate the input directory. This phase deliberately keeps the execution engine monolithic inside the pipeline; extraction into a reusable batch executor is out of scope.

The primary goal of Phase 1 is to prove the subagent prompt and taxonomy on real directory trees. The deliverable is a working pipeline that can be run with `arnold run folder-audit <target_dir>` and produces useful, reviewable output.

## Scope

In scope:

1. Scaffold a new graph-driven sibling-file pipeline via `python -m arnold pipelines new folder-audit --driver graph`.
2. Build a tree ingester step that:
   - reads `target_dir` from `ctx.inputs`,
   - walks the directory respecting `.gitignore`, hidden files, and a configurable max depth,
   - emits a level-ordered list of folders.
3. Write a subagent prompt at `folder-audit/prompts/audit_folder.md` that accepts:
   - folder path,
   - level in the tree,
   - parent folder's inferred purpose,
   - list of immediate children with names and file/dir types,
   - closed taxonomy of classifications,
   - required JSON output schema.
4. Implement a one-level dispatch step that fans the prompt out to every folder at the target level in parallel, collects JSON outputs, and writes them to `ctx.plan_dir` (e.g., `level_1.json`).
5. Iterate the prompt and taxonomy until classifications are reliable on representative folders from this repo.
6. Add multi-level traversal that processes level 0, then level 1, etc., passing each folder's inferred purpose down to its children. Guard the loop with a `loop_condition` so `arnold pipelines check` passes.
7. Add a reconciliation pass that resolves simple parent/child disagreements (e.g., an item marked `too_granular` at the parent should be downgraded to `fit` if the child folder accepts it).
8. Emit final artifacts to `ctx.plan_dir`:
   - `audit.json` — structured per-folder results,
   - `audit.md` — annotated tree view with a classification legend and rationale blocks.
9. Validate with `arnold pipelines check folder-audit` and run it against a real directory.

Out of scope:

- Extracting a reusable `batch_executor` module or pipeline.
- Cost estimation, task sizing, or adaptive batching.
- Automatic rename/move suggestions or filesystem mutations.
- Resume/continuation logic beyond what the graph executor provides.
- Typed ports, lifecycle hooks, or package-module form.
- Handling symlinks, circular references, or non-standard filesystem layouts beyond safe defaults.

## Locked Decisions

- The pipeline is a graph-driven sibling-file module under `arnold/pipelines/megaplan/pipelines/folder_audit.py`.
- Traversal is level-order BFS so parent purposes are known before child judgments are made.
- Each folder is analyzed by exactly one subagent call in this phase; no batching of multiple folders into one call.
- The subagent prompt uses a closed taxonomy so outputs are machine-aggregable.
- Classifications must be one of: `fit`, `too_granular`, `wrong_level_of_abstraction`, `mixed_concerns`, `misplaced`, `orphaned`, `naming_mismatch`, `overpacked`, `underpacked`, `duplicate`, `unclear`.
- The pipeline is read-only: all outputs go to `ctx.plan_dir`, never back into the target directory.
- Hidden files and directories are skipped by default; `.gitignore` is respected by default.
- Reconciliation is rule-based, not a second subagent pass.

## Open Questions

- What should the default `max_depth` be? (Start with 8.)
- Should the user be able to supply an expected top-level taxonomy, or should everything be inferred bottom-up? (Start with bottom-up inference only.)
- Should the annotated Markdown tree preserve the full original tree or only folders? (Start with folders plus annotated children.)

## Constraints

- Must pass `arnold pipelines check folder-audit` before the run is considered complete.
- Must not import or depend on any future `batch_executor` abstraction.
- Must keep module-level contract fields as simple literals per the Arnold authoring contract.
- Must use only existing Arnold graph executor primitives (`Stage`, `Edge`, `StepResult`, `loop_condition`) for loops.

## Done Criteria

- `python -m arnold pipelines check folder-audit` succeeds with no warnings.
- `python -m arnold run folder-audit /path/to/dir` completes and writes `audit.json` and `audit.md` to the plan directory.
- `audit.json` contains per-folder `inferred_purpose`, `confidence`, and classified items for every visited folder.
- `audit.md` renders a readable annotated tree with a legend.
- Running the pipeline against a sample of this repo's directories produces classifications that a human reviewer finds reasonable.
- The subagent prompt includes the closed taxonomy and required JSON schema.

## Touchpoints

- `arnold/pipelines/megaplan/pipelines/folder_audit.py`
- `arnold/pipelines/megaplan/pipelines/folder-audit/skills/folder-audit/SKILL.md`
- `arnold/pipelines/megaplan/pipelines/folder-audit/prompts/audit_folder.md`

## Anti-Scope

- Do not create a separate `batch_executor` pipeline or module in this phase.
- Do not mutate, rename, or move files in the target directory.
- Do not add resume/continuation complexity before the core loop is proven.
- Do not over-generalize the prompt; keep it focused on folder purpose and child fit.
