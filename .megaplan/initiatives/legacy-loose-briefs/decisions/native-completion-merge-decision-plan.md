# Native Completion Merge Decision Plan

## Decision

Merge `native-python-pipelines-completion-thread2` into
`native-python-working-tree` as the completed native-python-pipelines-completion
epic. Do not merge `megaplan-single-20260624-2002` or any dirty
`megaplan-single` worktree wholesale. Treat single-root Megaplan consolidation
as a separate cleanup PR/epic step after the completed native epic is integrated.

This is the call: `thread2` is the integration branch; `megaplan-single` is not.

## Evidence

- `native-python-working-tree` is an ancestor of
  `native-python-pipelines-completion-thread2`; the completion branch is suitable
  for a fast-forward once the working tree is clean.
- `native-python-pipelines-completion-thread2` contains the completed M1-M7
  sequence, ending at:
  `b3156f20 M7: megaplan relocation, final import inventory, and compatibility purge`.
- The older `native-python-pipelines-completion` branch is behind and should not
  be used as the merge source.
- `megaplan-single-impl-fix` / `megaplan-single-20260624-2002` had the right
  root concern but was a large destructive dirty effort, not a clean merge
  candidate.
- Follow-up planning docs and validation notes are useful, but should be a
  separate planning commit from the completion epic merge.

## Keep / Delete / Defer

### Keep

- Keep `native-python-pipelines-completion-thread2` as the completed epic source.
- Keep the current follow-up epic docs:
  - `briefs/native-composition-followup/`
  - `briefs/native-platform-followup/`
  - `briefs/native-endstate-validation-review.md`
  - `briefs/megaplan-functionality-regression-review.md`
- Keep the principle from `megaplan-single`: one Megaplan implementation
  authority should eventually win, and duplicate-root drift must be eliminated.
- Keep existing compatibility gates:
  - `tests/test_pipeline_run_cli.py`
  - `tests/characterization/test_import_surface.py`
  - Megaplan resume/import/CLI characterization tests.

### Delete / Discard

- Do not merge dirty `megaplan-single` code changes.
- Discard local uncommitted `megaplan-single` implementation contamination before
  merging completion.
- Do not cherry-pick from `megaplan-single` unless a specific patch is reviewed
  and passes the compatibility gates.
- Do not merge the older `native-python-pipelines-completion` branch.

### Defer

- Defer complete deletion of `arnold/pipelines/megaplan` or complete
  consolidation into `arnold_pipelines/megaplan` to a later dedicated cleanup.
- Defer any hard "no legacy import path" policy until the CLI, import surface,
  resume, chain/PR, and package-discovery compatibility contracts are all
  explicitly green.

## Required Pre-Merge Cleanup

The current working tree must be made clean before merging. Split local work into
three buckets:

1. **Planning docs to keep**
   Commit these separately after the completion merge, or stash them before the
   merge and re-apply after:
   - follow-up epic directories;
   - validation review notes;
   - M6/M7 acceptance-criteria tightening.

2. **Dirty implementation changes to discard**
   Local edits under active Megaplan implementation paths that came from
   `megaplan-single` should not be carried into the completion merge.

3. **Unknown local changes**
   Anything not clearly planning docs or completed-epic work must be reviewed
   before it is kept. Default to discard or separate PR, not silent inclusion.

## Merge Sequence

```bash
# 1. Save planning docs if they are not committed.
git switch native-python-working-tree
git status --short

# Option A: commit planning docs now on a temporary branch.
git switch -c planning/native-composition-followups
git add briefs/native-composition-followup \
        briefs/native-platform-followup \
        briefs/native-endstate-validation-review.md \
        briefs/megaplan-functionality-regression-review.md \
        briefs/native-completion-merge-decision-plan.md \
        briefs/native-python-pipelines-completion/m6-docs-and-scaffolds-native-first.md \
        briefs/native-python-pipelines-completion/m7-megaplan-relocation-and-final-purge.md
git commit -m "docs: plan native composition and platform follow-ups"

# 2. Return to working branch and clean implementation contamination.
git switch native-python-working-tree
# Use targeted restore only after confirming the files are dirty megaplan-single
# contamination, not user work.

# 3. Fast-forward completion.
git merge --ff-only native-python-pipelines-completion-thread2

# 4. Re-apply/merge planning docs as a separate commit or PR.
```

Do not use a normal merge commit unless fast-forward fails. If fast-forward
fails, stop and inspect; do not force a merge through conflicts.

## Validation Ladder

Run this ladder before opening the PR to `main`:

```bash
python -m arnold_pipelines.megaplan chain status \
  --spec briefs/native-python-pipelines-completion/chain.yaml

pytest tests/test_pipeline_run_cli.py
pytest tests/characterization/test_import_surface.py
pytest tests/arnold_pipelines/megaplan
pytest tests/arnold/pipeline/native
```

If those pass, run the broader suite or the repo's documented CI command. If a
compatibility test fails, fix or explicitly document the compatibility decision;
do not delete the test to make the merge green.

## Main PR Strategy

Open one PR from `native-python-working-tree` to `main` for the completed epic
after the fast-forward and gates pass.

Do not include:

- dirty `megaplan-single` implementation changes;
- single-root deletion beyond what `thread2` already contains;
- follow-up epic execution work.

Planning docs may be included as a separate docs commit or separate PR. They
should not obscure the diff for the completed native implementation epic.

## Post-Merge Work

After the completion epic lands on `main`, start a fresh single-root cleanup from
that base only if it is still needed. Its acceptance criteria should be:

- decide the final authority between `arnold/pipelines/megaplan` and
  `arnold_pipelines/megaplan`;
- inventory all imports in both directions;
- keep explicit temporary shims only where tests prove they are required;
- delete or migrate one surface at a time;
- keep `tests/test_pipeline_run_cli.py` and
  `tests/characterization/test_import_surface.py` as hard gates.

No big-bang deletion.
