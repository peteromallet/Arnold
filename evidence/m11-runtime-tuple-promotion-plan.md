# M11 Runtime Tuple Promotion Plan

Status: prepared only. No commit, deployment, runtime selection, `.pth`, venv,
wrapper, marker, service, or process was changed.

## Observed binding

- Approved interpreter:
  `/workspace/.megaplan/engine-runtimes/d6a7b716-execute-projection/venv/bin/python`
- Interpreter SHA-256:
  `f90d942117b90a2cc1596eb62a0a6eee9c46e832d0b0f1335a48c4bf5da10ba4`
- Editable `.pth`:
  `/workspace/.megaplan/engine-runtimes/d6a7b716-execute-projection/venv/lib/python3.11/site-packages/_editable_impl_arnold.pth`
- `.pth` SHA-256:
  `0294b47214797e2bd28f6b2b1d8eb77f03a5886d5139fe46d76ee4f320786d28`
- Exact editable/import root:
  `/workspace/runtime-candidates/arnold-5bf11d5a5600`
- Exact clean runtime revision:
  `45650f8da0fbdc751e06421ea0ae38d5a597da91`
- M11 working checkout revision:
  `88f1f39c8f06832e155501ff13dd4e00a1522f94`
- The M11 checkout has 317 dirty or untracked paths. It is not a promotable
  runtime identity.

The hot environment currently selects distinct content-addressed source roots
for watchdog, auditor, launch/worker, meta-repair, and supervisor roles. Those
role bindings must be attested independently; one import-root check must not be
treated as proof of the whole control plane.

## Why a commit is required

The existing editable runtime is clean and content-addressed. Copying the dirty
M11 working tree into it would destroy both properties, make rollback
ambiguous, and change live behavior before acceptance. The M11 source must
first become a reviewed commit whose complete tree can be reproduced.

## Promotion procedure

1. Inventory the 317 M11 paths and partition them into:
   intended M11 source/tests/evidence, unrelated operator artifacts, and
   generated or disposable files. Preserve unrelated work; do not include it
   in the candidate.
2. Create one reviewed M11 commit from only the intended partition. Record its
   commit and tree hashes. This is the authorization boundary; stop if the
   resulting checkout is not clean.
3. In a separate scratch worktree based on runtime revision `45650f8d`, merge
   or cherry-pick the reviewed M11 commit. Resolve there, never in the bound
   editable checkout. Record the resulting candidate commit and tree hashes.
4. Run the focused runtime-provenance suite and the M11 acceptance suite from
   the approved interpreter with `python -P`. Run the strict tuple validator
   against the scratch candidate's expected commit, imports, wrappers,
   supervisor argv, and marker fixture. Reject any dirty tree or unpinned
   component.
5. Prove the candidate commit is the exact tested tree. Preserve the current
   runtime commit as the rollback identity. Obtain explicit promotion
   authorization.
6. With the M11 runner stopped at a durable boundary, move the existing
   editable checkout
   `/workspace/runtime-candidates/arnold-5bf11d5a5600` to the exact tested
   candidate commit. Do not reinstall and do not alter the venv or `.pth`.
7. Before any restart, run the approved interpreter with `-P` and require a
   strict receipt proving:
   exact interpreter path/hash and safe-path mode; exact editable metadata
   root; exact `.pth` path/hash/entries; exact module paths; clean exact Git
   revision; exact wrapper set/hashes/modes; exact supervisor argv; and exact
   target-marker hash plus stable identity fields.
8. Atomically update the marker's runtime binding to the strict receipt, then
   perform one authorized relaunch. Verify the running PID command line and
   post-launch import probe reproduce the same tuple. A mismatch is a failed
   deployment, not a warning.
9. Roll back by stopping at a durable boundary and selecting the preserved
   `45650f8d` commit in the same editable checkout, then regenerate and verify
   the previous strict receipt. The `.pth` and venv remain unchanged.

## Promotion gates

- No dirty source tree at build, promotion, restart, or rollback.
- No source copy into the bound editable checkout.
- No `.pth` or venv mutation.
- No marker update without a valid strict receipt.
- No inference that role-specific hot-environment roots equal the M11 runtime;
  each role must have an explicit expected root and receipt.
- No restart or deployment in this implementation step.
