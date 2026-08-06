# Flash report contract

Use this exact field order.

```text
FLASH REPORT
1. question_id:
2. verdict: supported | refuted | undetermined
3. investigated_claim:
4. vantage:
   - hostname/container:
   - workspace:
   - runtime_or_commit:
   - investigator:
5. utc_window:
   - started:
   - ended:
6. artifacts:
   - absolute_path:
     exists: yes | no
     type:
     size_bytes:
     mtime_utc:
     sha256:
     role: producer | consumer | persistence | policy | log | authority
7. commands:
   - cwd:
     exact_command:
     started_utc:
     ended_utc:
     exit_code:
     stdout_summary:
     stderr_summary:
8. trace:
   - producer:
     produced_value_or_key:
     consumer:
     consumed_value_or_key:
     persistence:
     persisted_value_or_key:
     policy:
     predicate_and_result:
9. adherence_classification: ADHERENCE | MISSING_STRUCTURE
10. missing_or_contradictory_structure:
11. evidence_supporting_verdict:
12. evidence_against_verdict:
13. confidence: high | medium | low
14. confidence_basis:
15. immediate_decision_informed:
16. durable_decision_informed:
17. safety_observations:
18. unresolved_questions:
```

Classification rules:

- `supported` requires affirmative supporting evidence; `refuted` requires affirmative contradictory evidence; absence, ambiguity, or inaccessible evidence is `undetermined`.
- `ADHERENCE` requires a complete, identity-matched producer -> consumer -> persistence -> policy trace for the inspected contract. Any absent, ambiguous, contradictory, or untraceable required edge is `MISSING_STRUCTURE`, even when the terminal value looks plausible.
- Hash every inspected persistent artifact. For a missing artifact use `not-applicable` for size, mtime, and hash.
- Record commands verbatim, including cwd, UTC bounds, nonzero exits, and concise stdout/stderr summaries.
- Separate immediate incident facts from durable design implications. Do not treat ancestry, code equivalence, a clean worktree, or a passing reproduction as execution authority.
