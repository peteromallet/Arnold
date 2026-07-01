# M6 Dual-Run Oracle Bake Time

`tests/oracle/test_dual_run_oracle.py` is the SOLE retirement authority for PR4.
PR4 is not retired by parser snapshots, unit parity, manual inspection, or a
one-off smoke command. It is retired only when this oracle stays green against
the checked-in recovery, escalate, and blocked traces and the discovered
planning path completes the planning-shaped throwaway plan end-to-end.

The trace fixtures live in `tests/oracle/fixtures/` and are refreshed once per
release with:

```bash
python scripts/record_oracle_traces.py
python scripts/record_oracle_traces.py --check
```

Evidence strength is time-dependent. A same-day green carries weaker evidence than a soak-period green because it proves only that the current checkout and
fixture set agree right now. A soak-period green is stronger because unrelated
changes have had time to exercise the same retirement authority without
breaking recovery, escalation, blocked/resume, or discovered-planning behavior.
