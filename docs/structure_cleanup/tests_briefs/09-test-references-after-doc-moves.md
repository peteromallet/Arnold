# Tests Layer Audit 09: References After Doc Moves

Audit test references to docs paths already moved during this cleanup.

Questions:
- Do tests still refer to old docs paths such as `docs/testing.md`,
  `docs/template_porting_workbench.md`, `docs/strict_ready_exceptions.*`,
  `docs/gold_template_wan_i2v.py`, or `docs/m4_resolution_context.md`?
- Are compatibility references intentional?
- What exact test updates are safe?

Use grep/static inspection only; do not run broad tests.
