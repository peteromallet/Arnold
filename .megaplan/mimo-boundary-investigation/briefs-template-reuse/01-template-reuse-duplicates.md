Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating whether any megaplan structured-output phase needs to use the same JSON template twice, or whether each attempt/phase should get one scratch template path.

Question to answer:
- Are there cases where the same template file should be reused twice in the same logical phase, same iteration, or same retry?
- Are there cases where templates must be distinct to avoid clobbering outputs?

Focus on:
- critique parallel per-check outputs
- gate reprompt / tiebreaker paths
- execute per-batch outputs and checkpoints
- review parallel per-check outputs
- finalize retries
- auto/resume retries

Suggested files:
- arnold/pipelines/megaplan/handlers/critique.py
- arnold/pipelines/megaplan/orchestration/parallel_critique.py
- arnold/pipelines/megaplan/handlers/gate.py
- arnold/pipelines/megaplan/handlers/finalize.py
- arnold/pipelines/megaplan/handlers/execute.py
- arnold/pipelines/megaplan/execute/batch.py
- arnold/pipelines/megaplan/handlers/review.py
- arnold/pipelines/megaplan/orchestration/parallel_review.py
- arnold/pipelines/megaplan/auto.py

Return:
1. Short verdict.
2. Matrix: phase/subphase, template path naming rule, reuse or unique, why.
3. Any high-risk clobber cases.
4. Test recommendations.
