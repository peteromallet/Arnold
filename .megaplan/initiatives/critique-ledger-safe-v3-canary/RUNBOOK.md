# Finite zero-recovery runbook

Every attempt uses a completely new container name, repository checkout, plan
name, and receipt directory. Never delete or rename the preserved v2 container.

1. Independently review implementation commit A and manifest commit B.
2. Run `cloud capacity-inventory`, then the ordinary preflight. If ENOSPC is the
   exact byte-floor-only blocker, run `cloud reclaim-dangling-build-cache`
   (dry-run), inspect the proposal, then rerun with `--apply` once.
3. Rerun inventory and preflight. Require GO.
4. Build and deploy the zero profile. Require the typed predeploy, host-fence,
   and preserved-predecessor evidence.
5. Invoke only `cloud run-zero-recovery-canary`; never `exec`, `chain`, `auto`,
   `resume`, `attach`, `bootstrap`, or a resident/recovery command.
6. Collect the content-addressed run receipt. A non-PROCEED gate or any failed
   phase ends the attempt; do not retry it.

For a complete relaunch, make a new manifest commit with a new canary container,
repo workspace, plan name, and receipt path. Preserve every prior container and
receipt; repeat all gates from step 1.
