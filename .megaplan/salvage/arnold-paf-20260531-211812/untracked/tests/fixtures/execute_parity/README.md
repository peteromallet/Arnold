# Execute Outcome Parity Fixtures

These directories are structural placeholders. The T11 characterization test
(`tests/characterization/test_execute_outcome_parity.py`) generates plan
fixtures dynamically via ``_setup_plan_for_execute`` /
``_setup_multi_task_plan`` — the same pattern used by T13's replay oracle.

Each subdirectory corresponds to one of the four outcomes exercised by the test:

- ``success/`` — task completes cleanly, ``_phase_outcome='success'``,
  ``next_step='review'```, ``state=STATE_EXECUTED``.
- ``blocked_by_quality/`` — task reports a quality-gate deviation,
  ``_phase_outcome='blocked_by_quality'``, ``next_step='execute'``,
  ``state=STATE_FINALIZED``.
- ``blocked_by_prereq/`` — within-session blocked task triggers auto-loop
  early-return, ``_phase_outcome='blocked_by_prereq'``,
  ``next_step='execute'``, ``state=STATE_FINALIZED``.
- ``timeout/`` — worker timeout caught by auto-loop,
  ``_phase_outcome='timeout'``, ``next_step='execute'``,
  ``state=STATE_FINALIZED``.

If a future task requires persisting static payloads (e.g. for a VCR-style
replay), place them here.  For now the test is self-contained.
