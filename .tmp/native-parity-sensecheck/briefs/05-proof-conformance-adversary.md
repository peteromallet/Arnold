# Lens 5 — proof/conformance adversary

Working directory: `/Users/peteromalley/Documents/Arnold`. Strictly read-only. Do not modify files.

Adversarially inspect native-parity scenarios, evidence generation, semantic validators/checkers, fixtures/goldens, mutation/deletion tests, installed-wheel/sdist/package tests, sprint proof gates, and final conformance reports. Begin with the required report/plan/NORTHSTAR/chain/s1-s7/m1-m10 set, then locate all relevant code and tests using `rg`.

For every material end-state claim, determine whether proof is behavioral and causally tied to the authored native semantic carrier, or can false-pass via self-authored evidence, allowlists, substring/AST presence checks, fixtures not produced by runtime, mocks/fallbacks, stale generated reports, tests exercising legacy paths, source-only assertions, package tests importing but not executing, or deletion/mutation tests that delete the wrong carrier. Explicitly identify old false-pass patterns genuinely blocked and those still reproducible. Run targeted read-only tests/checkers if useful. Return: (1) proof-quality matrix, (2) concrete false-pass mechanisms with exact `path:line` evidence and reproduction logic, (3) missing minimum regression gates, and (4) ranked proof gaps with severity/confidence/consequence/smallest action. Green tests and generated reports are not proof by themselves.
