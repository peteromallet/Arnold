Working directory: /Users/peteromalley/Documents/Arnold

You are SA1: Checker & closure authority for the Megaplan native semantic parity corrective master plan.

Read source files directly. Do not modify files.

Scope:
- Map every validation entry point in `arnold/workflow/source_compiler.py`.
- Identify which paths enforce row evidence and which do not, especially `check_workflow_file(..., evidence=None)` vs `check_workflow_source(...)`.
- Identify where S5 review/finalize rows currently pass on policy-surface existence alone.
- Identify repository paths where final closure could route around the strict path.

Return:
- Ranked findings, each with exact `file:line` evidence.
- Commands you ran, if any.
- Keep it under 900 words.
- No implementation suggestions except machine-checkable gate implications.
