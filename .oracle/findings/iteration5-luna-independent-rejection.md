# Independent Luna Batch 2 iteration-4 rejection

Verdict: `REJECT_BATCH_2`

Exact candidate reviewed:

- code: `5c74f0c6155deedf22b911bc588d5c8a79e12390`
- evidence: `34adf5c59b52a272bf8eb7016c623678be6ba1c3`

Additional blocking findings beyond the Sol fallback review:

1. Production babysitter waits for the worker to exit before reading its PID
   (`managed_agent.py:1068`, `babysitter/launch.py:596-638`), while
   `_worker_identity` rejects dead PIDs (`worker_dispatch.py:620-648`). The
   review probe produced `accepted` plus `permanent_hold_ambiguous`, never a
   terminal outcome.
2. Babysitter `LaunchResult.value` omits required nullable
   `DispatchOutcome` fields; strict normalization at
   `worker_dispatch.py:675-678` rejects even a legitimate result.
3. `IncidentLedger.append_controlled_adapter_state` validates only receipt
   binding (`ledger.py:672-675`). Review probes admitted forged physical doors
   and illegal fresh-reservation `accepted` and `closed` transitions.
4. The authority checker returned `ok` for raw `subprocess.Popen` in a
   canonical door, computed `getattr` launch, and an aliased nested launch.

Required disposition: fix all items at the production root, add positive and
adversarial regressions, and include their literal raw outputs in the next
evidence seal. This finding grants no merge, push, or Batch 3 authority.
