# Auto-Improve Findings

## Iteration 001 — Baseline
- Date: 2026-03-30
- Pass rate: 67% (10/15 scorable). 3 infra errors had correct patches.
- Top failure pattern: `under_scoped` (3/5 real failures) — pipeline finds the right bug but misses other code paths that need the same fix.
- Change applied: Prep prompt now requires grepping for ALL usages of the buggy function/parameter, not just the first one found.
- Also notable: 3 patches were gold-identical or equivalent but failed due to Docker/Modal scoring infra on Apple Silicon. Real pipeline performance is better than raw numbers suggest.
- Follow-up: Does the "grep all usages" instruction actually help, or does the model ignore it? Is sympy-18199 (100-line overhaul) fundamentally out of scope for a "minimal fix" pipeline?
