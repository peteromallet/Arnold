# Superfixer Alive-But-Failed Recovery North Star

The repair system must never treat process activity as proof that a repairable
failure cleared.

The immediate target is operational, not architectural: deploy and prove the
alive-but-failed repair-custody correction against the original
`megaplan-native-parity-corrective` cloud session, then leave a concise handoff
that `workflow-boundary-contracts` can generalize later.

End state:

- `live_with_fresh_activity` is legacy compatibility input only, not success.
- New liveness-without-clearance producers write `partial_liveness`.
- `partial_liveness` is non-success and never clears repair markers or writes
  `last_success_*`.
- A live process plus unchanged repairable failure receipt is
  `alive_but_failed` / attention-needed custody, not `running`.
- Repair success requires evidence that the original failure receipt, finding,
  or blocker fingerprint cleared, or a structured true-human/no-fix verdict.
- The cloud runtime source and installed wrappers are actually updated, with
  source/runtime/wrapper identity recorded.
- Any remaining native-parity product failure is separated from repair-system
  custody failure.

Do not build the full `BoundaryContract` system here. This sprint produces the
operational precedent that the boundary epic consumes.
