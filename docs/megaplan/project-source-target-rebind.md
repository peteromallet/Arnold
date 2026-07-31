# Guarded project-source target rebind

`megaplan chain target-rebind` changes the project checkout and milestone
baseline for an already materialized chain plan. It is separate from:

- `chain rebind`, which adopts a content-addressed chain-spec bundle;
- `chain runtime-rebind`, which changes the installed engine runtime; and
- `chain reconcile-source`, which registers a future milestone brief.

Use it only when an existing milestone was planned on one commit but must
execute on a verified fast-forward successor without attributing the successor's
already-landed changes to the milestone.

## Safety boundary

Cutover and rollback both require:

- matching durable operator-pause authority in chain and plan state;
- the exact project/session directory, spec hash, chain-state hash, plan-state
  hash, current milestone, and current plan;
- the exact current branch, HEAD, and `milestone_base_sha`;
- a clean Git worktree and no active plan/auto driver;
- exact source and destination SHAs advertised by the named origin refs; and
- no execute, finalize, or review history or artifacts.

Cutover additionally requires a strict fast-forward and requires the destination
branch to equal the branch configured for the current milestone. Rollback must
exactly invert the active cutover and is refused after execution begins.

The transaction switches or creates the destination branch, updates
`meta.chain_policy.milestone_base_sha`, writes the same append-only
`project_source_binding` receipt into chain and plan metadata, refreshes only
the observational `target_head`, and invalidates active stale gate artifacts.
It does not change the chain's launch-time `target_base_ref`.

The plan remains paused. Its pause receipt is changed to restore `critiqued`,
with a fresh `gate` resume cursor. Explicit `chain resume` is still required.

When the load-bearing milestone inputs changed, this gate-only path is not
enough. Follow it with `chain seed-rematerialize`; do not resume the old plan.

If any Git, artifact, plan-state, or chain-state step fails, the command restores
the original branch and exact HEAD, restores both JSON blobs byte-for-byte, and
restores invalidated gate artifacts.

## Collect the guards

Collect all hashes while the chain is paused and no process is mutating it:

```bash
sha256sum path/to/chain.yaml
sha256sum .megaplan/plans/.chains/chain-*.json
sha256sum .megaplan/plans/<plan>/state.json
git branch --show-current
git rev-parse HEAD
git ls-remote --heads origin \
  refs/heads/<current-source-ref> \
  refs/heads/<advertised-successor-ref>
```

On macOS, use `shasum -a 256` in place of `sha256sum`.

## Cut over

```bash
python -m arnold_pipelines.megaplan chain target-rebind \
  --spec path/to/chain.yaml \
  --project-dir /workspace/<session> \
  --direction cutover \
  --expected-session-id <session> \
  --expected-current-milestone <milestone-label> \
  --expected-current-plan <plan-name> \
  --from-branch <current-local-branch> \
  --from-head <40-char-current-sha> \
  --from-milestone-base <same-current-sha> \
  --from-ref refs/heads/<advertised-current-ref> \
  --to-branch <configured-milestone-branch> \
  --to-head <40-char-successor-sha> \
  --to-ref refs/heads/<advertised-successor-ref> \
  --expected-spec-sha256 <64-char-sha256> \
  --expected-target-spec-sha256 <64-char-target-sha256-if-chain-changed> \
  --expected-chain-state-sha256 <64-char-sha256> \
  --expected-plan-state-sha256 <64-char-sha256> \
  --reason "activate verified project source" \
  --actor operator
```

Record the returned post-transaction state hashes. Before resuming, verify that
the returned branch and HEAD are still checked out.

`--expected-target-spec-sha256` defaults to the source spec hash. Supplying it
allows a content-addressed target checkout to carry an amended chain spec, but
the current milestone index, label, and configured branch must remain
identical.

## Rematerialize changed M10 inputs

If the brief, North Star, chain spec, or load-bearing decisions changed, create
a JSON seed manifest and hash the manifest itself:

```json
{
  "schema": "arnold.megaplan.seed_manifest.v1",
  "session_id": "<session>",
  "milestone": "<milestone-label>",
  "plan": "<plan-name>",
  "target": {
    "branch": "<configured-milestone-branch>",
    "head": "<40-char-target-sha>"
  },
  "previous_bundle_sha256": "<bound-chain-bundle-sha256-or-empty>",
  "active_bundle_sha256": "<current-chain-bundle-sha256>",
  "assets": [
    {"kind": "chain_spec", "path": ".megaplan/initiatives/x/chain.yaml", "sha256": "<sha256>"},
    {"kind": "milestone_brief", "path": ".megaplan/initiatives/x/m10.md", "sha256": "<sha256>"},
    {"kind": "north_star", "path": ".megaplan/initiatives/x/NORTHSTAR.md", "sha256": "<sha256>"},
    {"kind": "decision", "path": ".megaplan/initiatives/x/decisions.md", "sha256": "<sha256>"}
  ]
}
```

Then, while the target-rebound plan is still paused:

```bash
python -m arnold_pipelines.megaplan chain seed-rematerialize \
  --spec path/to/chain.yaml \
  --project-dir /workspace/<session> \
  --expected-session-id <session> \
  --expected-current-milestone <milestone-label> \
  --expected-current-plan <plan-name> \
  --expected-branch <configured-milestone-branch> \
  --expected-head <40-char-target-sha> \
  --expected-spec-sha256 <current-spec-sha256> \
  --expected-chain-state-sha256 <current-chain-state-sha256> \
  --expected-plan-state-sha256 <current-plan-state-sha256> \
  --seed-manifest path/to/m10-seed-manifest.json \
  --expected-seed-manifest-sha256 <manifest-sha256> \
  --reason "rematerialize M10 from amended load-bearing inputs"
```

This second transaction is allowed only before execute and under the same
durable pause. It verifies every manifest asset byte-for-byte, binds the active
chain/assets bundle, archives the complete superseded plan under
`.seed-rematerialize-archive`, and removes its gate/finalize/review evidence
from the active plan. It then recreates the brief snapshot, North Star
artifacts, imported decisions, and canonical-source binding in a fresh plan
epoch at the same chain milestone. The pause restores to `initialized`, so the
next explicit resume performs a fresh plan/critique/gate sequence.

Failures after archive creation or either state write restore both state files
and every moved plan artifact. The content-addressed archive remains available
after success for audit and manual recovery; no accepted execute history or
execution artifact may be present.

### Roll back a successful seed rematerialization

Rollback is available only while the fresh epoch is still paused with its
single synthetic init receipt: no plan output, iteration, execute evidence, or
other new planning history may exist. Roll back the project target first using
`chain target-rebind --direction rollback`, then restore the predecessor seed:

```bash
python -m arnold_pipelines.megaplan chain seed-rematerialize \
  --direction rollback \
  --spec path/to/chain.yaml \
  --project-dir /workspace/<session> \
  --expected-session-id <session> \
  --expected-current-milestone <milestone-label> \
  --expected-current-plan <plan-name> \
  --expected-branch <restored-source-branch> \
  --expected-head <40-char-restored-source-sha> \
  --expected-spec-sha256 <restored-spec-sha256> \
  --expected-chain-state-sha256 <current-chain-state-sha256> \
  --expected-plan-state-sha256 <current-plan-state-sha256> \
  --seed-manifest path/to/m10-seed-manifest.json \
  --expected-seed-manifest-sha256 <manifest-sha256> \
  --expected-cutover-event-sha256 <cutover-event-content-sha256> \
  --expected-archive-manifest-sha256 <archive-manifest-sha256> \
  --reason "restore predecessor M10 seed"
```

The rollback verifies the cutover receipt, snapshot-manifest digest, and every
archived file. It restores the predecessor planning state and artifacts,
preserves the target rollback's append-only project-source receipt, restores
the predecessor execution bundle binding, and appends a seed rollback receipt.
Cutover may then be repeated with fresh CAS hashes. Failure at any rollback
write restores the rematerialized epoch exactly.

## Roll back before execute

Rollback uses fresh state hashes and reverses the branch, HEAD, baseline, and
advertised refs:

```bash
python -m arnold_pipelines.megaplan chain target-rebind \
  --spec path/to/chain.yaml \
  --project-dir /workspace/<session> \
  --direction rollback \
  --expected-session-id <session> \
  --expected-current-milestone <milestone-label> \
  --expected-current-plan <plan-name> \
  --from-branch <configured-milestone-branch> \
  --from-head <40-char-successor-sha> \
  --from-milestone-base <same-successor-sha> \
  --from-ref refs/heads/<advertised-successor-ref> \
  --to-branch <original-local-branch> \
  --to-head <40-char-original-sha> \
  --to-ref refs/heads/<advertised-original-ref> \
  --expected-spec-sha256 <current-64-char-sha256> \
  --expected-chain-state-sha256 <current-64-char-sha256> \
  --expected-plan-state-sha256 <current-64-char-sha256> \
  --reason "roll back project source before execute" \
  --actor operator
```

Once execute history or artifacts exist, source rollback is deliberately
unavailable. Use the ordinary milestone repair/revert lifecycle instead.

## Resume and publication invariant

Both chain resume and mutating plan preflight enforce the binding:

- the checked-out branch must remain the bound milestone branch; and
- the bound source SHA must be an ancestor of the current HEAD.

The same assertion runs before milestone completion. This prevents a
`--no-push --no-git-refresh` resident from silently returning to the old branch
and prevents the final milestone head from dropping the rebound source.

If a later resume enables the PR/push lifecycle, the chain does not run the
ordinary "create branch from chain base" or automatic-rebase path for a bound
milestone. It publishes the current bound branch only when the remote is absent
or is an ordinary fast-forward ancestor of local HEAD, then verifies that the
advertised remote head exactly equals local HEAD and still contains the bound
source. A remote branch that omits the bound source or has diverged fails closed
before it can replace local custody.
