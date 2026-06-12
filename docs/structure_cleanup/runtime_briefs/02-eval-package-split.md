Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit the runtime eval split.

Context:
- `vibecomfy/runtime/` contains both flat files (`eval.py`, `eval_plan.py`, `eval_prompt.py`, `preview_types.py`) and a package `runtime/eval/`.
- Determine whether this is a clean package split, a temporary compatibility bridge, or unresolved duplication.
- Do not edit files.

Focus:
- Compare flat files to `runtime/eval/core.py`, `plan.py`, `prompt.py`, `preview_types.py`, and `__init__.py`.
- Identify exact importers of flat modules and package modules.
- Recommend deletion/migration plan with tests.

Output:
- Decision list for each eval-related file.
- Include exact import rewrites if deletion is safe.
- Keep under 900 words.
