Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating whether `critique_evaluator` should also get a template-fill JSON contract.

Question to answer:
- Is `critique_evaluator` a structured-output boundary in the same sense as critique/gate/finalize/execute/review?
- If yes, what should the template look like, and how should it differ from critique templates?
- If no, why not?

Suggested files:
- arnold/pipelines/megaplan/handlers/critique.py
- arnold/pipelines/megaplan/prompts/critique_evaluator.py
- arnold/pipelines/megaplan/audits/critique_evaluator.py
- arnold/pipelines/megaplan/model_seam.py
- arnold/pipelines/megaplan/schemas/runtime.py
- tests/test_critique.py
- tests/arnold/pipelines/megaplan/test_model_seam.py

Return:
1. Verdict: include / exclude / partial.
2. Proposed template JSON if included.
3. How it should be named and promoted.
4. Recovery/coercion needs.
5. Tests to add.
